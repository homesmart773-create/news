#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Morning Briefing generator (JSON only)
- 뉴스: 네이버 뉴스 RSS 8개 카테고리(각 9건)
- 상한가: 네이버 금융 상한가 페이지에서 실제 상한가 종목 Top10
- 섹터: data/sectors.json

출력: 리포 루트 briefing.json
"""

from __future__ import annotations
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_JSON = ROOT / "briefing.json"

# -------- CONFIG --------
KST = timezone(timedelta(hours=9))

# 카테고리당 기사 개수(네이버 RSS 9건)
MAX_HEADLINES_PER_CAT = 9

# 네이버 뉴스 RSS 8카테고리
NAVER_RSS = {
    "politics": "https://rss.naver.com/politics/politics_general.xml",
    "economy": "https://rss.naver.com/economy/economy_general.xml",
    "society": "https://rss.naver.com/society/society_general.xml",
    "culture": "https://rss.naver.com/culture/culture_general.xml",
    "world": "https://rss.naver.com/world/world_general.xml",
    "technology": "https://rss.naver.com/it/it_general.xml",
    "entertainment": "https://rss.naver.com/entertainment/entertainment_general.xml",
    "sports": "https://sports.news.naver.com/rss/index.nhn?category=all"
}

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
    # 토(5)/일(6)은 금요일로 보정, 월요일 오전엔 전 영업일(금) 표기
    wd = base_dt.weekday()  # 월=0 ... 일=6
    if wd == 5:
        return (base_dt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 6:
        return (base_dt - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 0 and base_dt.hour < 9:
        return (base_dt - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    return base_dt.replace(hour=0, minute=0, second=0, microsecond=0)


def build_news_section() -> Dict[str, List[Dict[str, str]]]:
    """네이버 RSS로 8개 카테고리 뉴스 생성"""
    res: Dict[str, List[Dict[str, str]]] = {}
    for key, url in NAVER_RSS.items():
        feed = feedparser.parse(url)
        items: List[Dict[str, str]] = []
        # 상위 9건
        for e in feed.entries[:MAX_HEADLINES_PER_CAT]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            # 네이버 스포츠 RSS 등은 source가 비어있을 수 있어 고정값
            src = "네이버뉴스"
            items.append({"title": title, "url": link, "src": src})
        res[key] = items
        time.sleep(0.2)  # 과도 요청 방지
    return res


def fetch_limit_up_real(max_items: int = 10) -> List[Dict[str, str]]:
    """
    네이버 금융 상한가 페이지에서 실제 상한가 종목 추출
    - URL: https://finance.naver.com/sise/sise_upper.naver
    - 인코딩: EUC-KR
    """
    url = "https://finance.naver.com/sise/sise_upper.naver"
    try:
        resp = SESSION.get(url, timeout=10)
        # 네이버 금융은 EUC-KR 사용
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
            items.append({"name": name, "reason": ""})  # reason은 공란(단축어에서 name만 사용)
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
        "news": news,  # keys: politics, economy, society, culture, world, technology, entertainment, sports
        "limit_up": limit_up,  # [{"name": "...", "reason": ""}, ...]
        "sectors": sectors,
        "sector_order": list(sectors.keys())
    }

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
