#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
매일 아침 브리핑 JSON 생성기
- 뉴스: Google News RSS (경제/정치/연예/증시)
- 상한가: '상한가' 키워드 뉴스에서 종목/이유 추출(휴리스틱)
- 섹터: data/sectors.json 고정 리스트

출력: 리포 루트 briefing.json
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = ROOT / "briefing.json"

# -------- CONFIG --------
KST = timezone(timedelta(hours=9))

# 카테고리당 기사 개수(헤더 제거를 고려하면 6~7 권장)
MAX_HEADLINES_PER_CAT = 7

NEWS_QUERIES = {
    "economy": "경제",
    "politics": "정치",
    "entertainment": "연예",
    "market": "증시 OR 코스피 OR 코스닥"
}

GN_RSS = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
# ------------------------


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def last_trading_day(base_dt: datetime) -> datetime:
    wd = base_dt.weekday()  # Mon=0 ... Sun=6
    if wd == 5:   # Sat -> Fri
        return (base_dt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 6:   # Sun -> Fri
        return (base_dt - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 0 and base_dt.hour < 9:
        # 월요일 아침 이른 시간엔 전 영업일(금)로
        return (base_dt - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    return base_dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_google_news(query: str, max_items: int = 5) -> List[Dict[str, Any]]:
    url = GN_RSS.format(q=quote_plus(query))
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:max_items]:
        title = e.get("title", "").strip()
        link = e.get("link", "").strip()
        src = ""
        if "source" in e and e.source and hasattr(e.source, "title"):
            src = getattr(e.source, "title", "") or ""
        if not src and link:
            try:
                host = requests.utils.urlparse(link).netloc
                src = host.replace("www.", "")
            except Exception:
                src = ""
        items.append({"title": title, "url": link, "src": src})
    return items


def clean_title(txt: str) -> str:
    t = re.sub(r"\[[^\]]+\]", "", txt)     # [태그] 제거
    t = re.sub(r"\([^)]*\)", "", t)        # (괄호) 제거
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def extract_names_from_title(title: str) -> List[str]:
    t = clean_title(title)
    if "상한가" not in t:
        return []
    left = t.split("상한가")[0]
    parts = re.split(r"[·,／/∙ㆍ•&]|와|및|과|\+", left)
    names = []
    for p in parts:
        p = p.strip(" -—:·,")
        if re.fullmatch(r"[가-힣A-Za-z0-9\.\-&]{2,20}", p):
            names.append(p)
        else:
            p2 = re.sub(r"[^가-힣A-Za-z0-9\.\-&\s]", "", p).strip()
            if 2 <= len(p2) <= 20 and re.search(r"[가-힣A-Za-z]", p2):
                names.append(p2)
    out = []
    for n in names:
        if n and n not in out:
            out.append(n)
    return out


def extract_reason_from_title(title: str) -> str:
    t = clean_title(title)
    for sep in ["—", "-", ":", "…", "..", "·"]:
        if sep in t:
            seg = t.split(sep, 1)[-1].strip()
            if 4 <= len(seg) <= 60:
                return seg
    if "상한가" in t:
        seg = t.split("상한가", 1)[-1].strip(" .!?,/·-—")
        if 4 <= len(seg) <= 60:
            return seg
    return t[:60]


def fetch_article_text(url: str, timeout: int = 8) -> str:
    try:
        resp = SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        txt = " ".join(ps)
        return re.sub(r"\s{2,}", " ", txt).strip()
    except Exception:
        return ""


def extract_limit_up(max_items: int = 10) -> List[Dict[str, str]]:
    queries = ['상한가 종목', '특징주 상한가', '코스닥 상한가', '코스피 상한가']
    entries: List[Dict[str, Any]] = []
    seen_titles = set()
    for q in queries:
        items = get_google_news(q, max_items=8)
        for it in items:
            t = it["title"]
            if t in seen_titles:
                continue
            seen_titles.add(t)
            if "상한가" in t:
                entries.append(it)

    picks: List[Dict[str, str]] = []
    seen_names = set()
    for e in entries:
        title = e["title"]
        names = extract_names_from_title(title)
        if not names:
            body = fetch_article_text(e["url"])
            if "상한가" in body:
                m = re.search(r"([가-힣A-Za-z0-9\.\-&\s]{2,20})\s*상한가", body)
                if m:
                    names = [m.group(1).strip()]
        reason = extract_reason_from_title(title)
        for n in names:
            if n in seen_names:
                continue
            seen_names.add(n)
            picks.append({"name": n, "reason": reason})
            if len(picks) >= max_items:
                break
        if len(picks) >= max_items:
            break
    return picks


def load_sectors() -> Dict[str, List[str]]:
    p = DATA_DIR / "sectors.json"
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_news_section() -> Dict[str, List[Dict[str, str]]]:
    res: Dict[str, List[Dict[str, str]]] = {}
    for key, q in NEWS_QUERIES.items():
        items = get_google_news(q, max_items=MAX_HEADLINES_PER_CAT)
        res[key] = items
        time.sleep(0.4)  # 과도 요청 방지
    return res


def main() -> int:
    ts = now_kst()
    ltd = last_trading_day(ts)
    is_weekend = ts.weekday() >= 5

    news = build_news_section()
    limit_up = extract_limit_up(max_items=10)
    sectors = load_sectors()

    out = {
        "generated_at": ts.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "date": ts.strftime("%Y-%m-%d"),
        "last_trading_day": ltd.strftime("%Y-%m-%d"),
        "weekend_note": "금요일 장 기준 브리핑입니다." if is_weekend else "",
        "news": news,
        "limit_up": limit_up,
        "sectors": sectors,
        "sector_order": list(sectors.keys())
    }

    with OUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
