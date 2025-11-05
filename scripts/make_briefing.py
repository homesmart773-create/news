#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Morning Briefing (네이버 뉴스 API + 네이버 금융 상한가 + 섹터)
- 뉴스: 네이버 검색 뉴스 Open API (키 없거나 실패 시 네이버 RSS 8카테고리 폴백)
- 상한가: 네이버 금융 상한가 페이지 파싱(실제 상한가 10개)
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
from urllib.parse import urlparse

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

# 네이버 검색 뉴스 API 설정(Secrets로 주입)
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

# 카테고리별 쿼리(네이버 API용)
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
    # 네이버 API 응답의 <b>...</b> 제거 및 HTML 엔티티 정리
    s = re.sub(r"</?b>", "", s)
    s = s.replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    return s.strip()


def host_to_src(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "") or "뉴스"
    except Exception:
        return "뉴스"


def fetch_news_by_api() -> Dict[str, List[Dict[str, str]]]:
    """네이버 검색 뉴스 Open API로 카테고리별 뉴스 수집(키 없으면 빈 dict 반환)"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {}
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    res: Dict[str, List[Dict[str, str]]] = {}
    for key, query in NEWS_QUERIES.items():
        try:
            params = {
                "query": query,
                "display": MAX_HEADLINES_PER_CAT,
                "start": 1,
                "sort": "date",  # 최신순; sim(유사도)로 바꾸고 싶으면 변경
            }
            r = SESSION.get(NAVER_NEWS_API, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            items: List[Dict[str, str]] = []
            for it in data.get("items", [])[:MAX_HEADLINES_PER_CAT]:
                title = clean_html_tags(it.get("title", ""))
                url = (it.get("originallink") or it.get("link") or "").strip()
                src = host_to_src(url)
                if title and url:
                    items.append({"title": title, "url": url, "src": src})
            res[key] = items
            time.sleep(0.2)
        except Exception:
            # 카테고리 단위 실패 시 비워두고 RSS 폴백에서 채움
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
            if title and link:
                items.append({"title": title, "url": link, "src": src})
        res[key] = items
        time.sleep(0.2)
    return res


def build_news_section() -> Dict[str, List[Dict[str, str]]]:
    """API 우선, 부족분은 RSS로 보충"""
    api_news = fetch_news_by_api()
    # API 키 없거나 결과가 비었으면 통째로 RSS 사용
    if not api_news or all(len(v) == 0 for v in api_news.values()):
        return fetch_news_by_rss()
    # 일부 비어 있으면 RSS로 채우기
    rss_news = None
    for k, v in api_news.items():
        if not v:
            if rss_news is None:
                rss_news = fetch_news_by_rss()
            api_news[k] = rss_news.get(k, [])
    return api_news


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
        "news": news,
        "limit_up": limit_up,
        "sectors": sectors,
        "sector_order": list(sectors.keys()),
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
