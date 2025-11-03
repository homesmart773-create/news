#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
매일 아침 브리핑 산출:
- briefing.json (단축어용)
- briefing.html (클릭 가능한 웹페이지)

뉴스: Google News RSS (경제/정치/연예/증시)
상한가: 키워드 뉴스 휴리스틱
섹터: data/sectors.json
"""

import json
import re
import sys
import time
import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_JSON = ROOT / "briefing.json"
OUT_HTML = ROOT / "briefing.html"

# -------- CONFIG --------
KST = timezone(timedelta(hours=9))
# 카테고리당 기사 개수(정치/연예에 헤더성 항목 있을 수 있어 7 권장)
MAX_HEADLINES_PER_CAT = 7

NEWS_QUERIES = {
    "economy": "경제",
    "politics": "정치",
    "entertainment": "연예",
    "market": "증시 OR 코스피 OR 코스닥"
}

CAT_KO = {
    "economy": "경제",
    "politics": "정치",
    "entertainment": "연예",
    "market": "증시"
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
    wd = base_dt.weekday()
    if wd == 5:
        return (base_dt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 6:
        return (base_dt - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if wd == 0 and base_dt.hour < 9:
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
    t = re.sub(r"\[[^\]]+\]", "", txt)
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def extract_names_from_title(title: str) -> List[str]:
    t = clean_title(title)
    if "상한가" not in t:
        return []
    left = t.split("상한가")[0]
    parts = re.split(r"[·,／/∙ㆍ•&]|와|및|과|\+", left)
    names, out = [], []
    for p in parts:
        p = p.strip(" -—:·,")
        if re.fullmatch(r"[가-힣A-Za-z0-9\.\-&]{2,20}", p):
            names.append(p)
        else:
            p2 = re.sub(r"[^가-힣A-Za-z0-9\.\-&\s]", "", p).strip()
            if 2 <= len(p2) <= 20 and re.search(r"[가-힣A-Za-z]", p2):
                names.append(p2)
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
        time.sleep(0.4)
    return res


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def make_html_page(data: Dict[str, Any]) -> str:
    ts = data["generated_at"]
    date = data["date"]
    last = data["last_trading_day"]
    news = data["news"]
    limit_up = data.get("limit_up", [])
    sectors = data.get("sectors", {})
    sector_order = data.get("sector_order", list(sectors.keys()))

    def news_section(cat_key: str) -> str:
        items = news.get(cat_key, [])
        ko = {"economy": "경제", "politics": "정치", "entertainment": "연예", "market": "증시"}.get(cat_key, cat_key)
        lis = []
        for it in items:
            title = esc(it.get("title"))
            url = it.get("url", "#")
            src = esc(it.get("src", ""))
            lis.append(f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>'
                       f' <span class="src">— {src}</span></li>')
        return f'<section id="{cat_key}"><h2>— {ko} —</h2><ul>{"".join(lis)}</ul></section>'

    def limitup_section() -> str:
        if not limit_up:
            return ""
        lis = []
        for it in limit_up:
            name = esc(it.get("name"))
            reason = esc(it.get("reason"))
            q = quote_plus(f"{name} 상한가")
            url = f"https://m.search.naver.com/search.naver?query={q}"
            lis.append(f'<li><a href="{url}" target="_blank" rel="noopener">{name}</a> '
                       f'<span class="src">— {reason}</span></li>')
        return f'<section id="limitup"><h2>— 전일 상한가 Top10 —</h2><ol>{"".join(lis)}</ol></section>'

    def sectors_section() -> str:
        if not sectors:
            return ""
        secs_html = []
        order = sector_order or list(sectors.keys())
        for sec in order:
            stocks = sectors.get(sec, [])
            lis = []
            for s in stocks:
                q = quote_plus(f"{s} 주가")
                url = f"https://m.search.naver.com/search.naver?query={q}"
                lis.append(f'<li><a href="{url}" target="_blank" rel="noopener">{esc(s)}</a></li>')
            secs_html.append(f'<section id="sec-{quote_plus(sec)}"><h3>— {esc(sec)} —</h3><ul>{"".join(lis)}</ul></section>')
        return f'<section id="sectors"><h2>— 섹터 추천 —</h2>{"".join(secs_html)}</section>'

    nav = """
    <nav>
      <a href="#economy">경제</a>
      <a href="#politics">정치</a>
      <a href="#entertainment">연예</a>
      <a href="#market">증시</a>
      <a href="#limitup">상한가</a>
      <a href="#sectors">섹터</a>
    </nav>
    """

    css = """
    <style>
      body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,Apple SD Gothic Neo,Malgun Gothic,sans-serif;margin:16px;line-height:1.5;color:#111;}
      header{margin-bottom:12px;color:#555;}
      nav{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;}
      nav a{padding:6px 10px;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:#333;background:#fafafa}
      h1{font-size:20px;margin:0 0 6px 0}
      h2{font-size:18px;margin:18px 0 8px 0}
      h3{font-size:16px;margin:12px 0 6px 0}
      ul,ol{margin:6px 0 16px 20px}
      li{margin:6px 0}
      .src{color:#777;font-size:90%}
      footer{margin-top:20px;color:#777;font-size:90%}
      a{word-break:break-word}
    </style>
    """

    html_doc = f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morning Briefing — {esc(date)}</title>
{css}
<body>
<header>
  <h1>Morning Briefing</h1>
  <div>생성: {esc(ts)} / 기준일: {esc(date)} / 전일장: {esc(last)}</div>
</header>
{nav}
{news_section("economy")}
{news_section("politics")}
{news_section("entertainment")}
{news_section("market")}
{limitup_section()}
{sectors_section()}
<footer>
  <div>정보 제공용 · 링크를 탭하면 기사/주가를 확인하세요.</div>
</footer>
</body>
</html>"""
    return html_doc


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

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    html_text = make_html_page(out)
    with OUT_HTML.open("w", encoding="utf-8") as f:
        f.write(html_text)

    print(f"Wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"Wrote {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
