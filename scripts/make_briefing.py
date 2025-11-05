#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Morning Briefing (네이버 검색 뉴스 API + 네이버 금융 상한가 + 섹터)
- 뉴스: 네이버 검색 뉴스 Open API (키 없으면 네이버 RSS로 폴백)
- 상한가: 네이버 금융 상한가 페이지 파싱(실제 상한가 10개, reason은 공란)
- 섹터: data/sectors.json

출력: briefing.json
"""

from __future__ import annotations
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_JSON = ROOT / "briefing.json"

KST = timezone(timedelta(hours=9))
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "ko-KR,ko;q=0.9",
})

# 네이버 검색 뉴스 API 설정 (Secrets에 저장 권장)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
NAVER_NEWS_API = "https://openapi.naver.com/v1/search/news.json"

# 네이버 뉴스 RSS(폴백)
NAVER_RSS = {
    "politics": "https://rss.naver.com/politics/politics_general.xml",
    "economy": "https://rss.naver.com/economy/economy_general.xml",
    "society": "https://rss.naver.com/society/society_general.xml",
    "culture": "https://rss.naver.com/culture/culture_general.xml",
    "world": "https://rss.naver.com/world/world_general.xml",
    "technology": "https://rss.naver.com/it/it_general.xml",
    "entertainment": "https://rss.naver.com/entertainment/entertainment_general.xml",
    "sports": "https://sports.news.naver.com/rss/index.nhn?category=all",
}

# 카테고리 쿼리(네이버 API용)
NEWS_QUERIES = {
    "politics": "정치",
    "economy": "경제",
    "society": "사회",
    "culture": "문화",
    "world": "세계",
    "technology": "기술 OR 과학 OR IT",
    "entertainment": "연예",
    "sports": "스포츠",
}

MAX_HEADLINES_PER_CAT = 9


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def last_trading_day(base_dt: datetime) -> datetime:
    wd = base_dt.weekday()  # Mon=0 ... Sun=6
    if wd == 5:
        return (base_dt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 6:
        return (base_dt - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 0 and base_dt.hour < 9:
        return (base_dt - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    return base_dt.replace(hour=0, minute=0, second=0, microsecond=0)


def clean_html_tags(s: str) -> str:
    if not s:
        return ""
    # 네이버 API 응답의 <b>...</b> 제거 및 HTML 엔티티 언이스케이프
    s = re.sub(r"<\/?b>", "", s)
    s = re.sub(r"&quot;|&#34;", '"', s)
    s = re.sub(r"&amp;|&#38;", "&", s)
    s = re.sub(r"&lt;|&#60;", "<", s)
    s = re.sub(r"&gt;|&#62;", ">", s)
    s = re.sub(r"&apos;|&#39;", "'", s)
    return s.strip()


def host_to_src(url: str) -> str:
    try:
        host = urlparse(url).netloc
        host = re.sub(r"^www\.", "", host)
        return host or "뉴스"
    except Exception:
        return "뉴스"


def fetch_news_by_api() -> Dict[str, List[Dict[str, str]]]:
    """네이버 검색 뉴스 Open API로 카테고리별 뉴스 수집"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {}  # 없으면 폴백 사용
    res: Dict[str, List[Dict[str, str]]] = {}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    for key, query in NEWS_QUERIES.items():
        params = {"query": query, "display": MAX_HEADLINES_PER_CAT, "sort": "sim"}
        try:
            r = SESSION.get(NAVER_NEWS_API, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            items: List[Dict[str, str]] = []
            for it in data.get("items", [])[:MAX_HEADLINES_PER_CAT]:
                title = clean_html_tags(it.get("title", ""))
                origin = it.get("originallink") or it.get("link") or ""
                url = origin.strip()
                src = host_to_src(url)
                if title and url:
                    items.append({"title": title, "url": url, "src": src})
            res[key] = items
            time.sleep(0.2)
        except Exception:
            res[key] = []
    return res


def fetch_news_by_rss() -> Dict[str, List[Dict[str, str]]]:
    """네이버 RSS 폴백"""
    res: Dict[str, List[Dict[str, str]]] = {}
    for key, url in NAVER_RSS.items():
        feed = feedparser.parse(url)
        items: List[Dict[str, str]] = []
        for e in feed.entries[:MAX_HEADLINES_PER_CAT]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            src = host_to_src(link) if link else "네이버뉴스"
            items.append({"title": title, "url": link, "src": src})
        res[key] = items
        time.sleep(0.2)
    return res


def build_news_section() -> Dict[str, List[Dict[str, str]]]:
    # API 우선, 실패/미설정 시 RSS 폴백
    api_news = fetch_news_by_api()
    if api_news and any(api_news.values()):
        return api_news
    return fetch_news_by_rss()


def fetch_limit_up_real(max_items: int = 10) -> List[Dict[str, str]]:
    """네이버 금융 상한가 페이지에서 실제 상한가 종목 추출"""
    url = "https://finance.naver.com/sise/sise_upper.naver"
    try:
        resp = SESSION.get(url, timeout=10)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.select_one("table.type_2")
        items: List[Dict[str, str]] = []
        if not table:
            return items
        for tr in table.select("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            name = tds[1].get_text(strip=True)
            if not name or name == "종목명":
                continue
            items.append({"name": name, "reason": ""})
            if len(items) >= max_items:
                break
        return items
    except Exception:
        return []


def load_sectors() -> Dict[str, List[str]]:
    p = DATA_DIR / "sectors.json"
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> int:
    ts = now_kst()
    ltd = last_trading_day(ts)
    is_weekend = ts.weekday() >= 5

    news = build_news_section()
    limit_up = fetch_limit_up_real(max_items=10)
    sectors = load_sectors()

    out = {
        "generated_at": ts.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "date": ts.strftime("%Y-%m-%d"),
        "last_trading_day": ltd.strftime("%Y-%m-%d"),
        "weekend_note": "금요일 장 기준 브리핑입니다." if is_weekend else "",
        "news": news,  # keys: politics,economy,society,culture,world,technology,entertainment,sports
        "limit_up": limit_up,  # [{"name": "...", "reason": ""}, ...]
        "sectors": sectors,
        "sector_order": list(sectors.keys()),
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
