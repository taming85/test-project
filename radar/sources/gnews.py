# -*- coding: utf-8 -*-
"""Google News RSS 수집기.

- 별도 인증/키 불필요
- 키워드 조합으로 최근/과거 기사 수집 (때때로 수 시간~수일 선행)
- 한계: 링크가 Google 리다이렉트로 제공됨(원문 URL은 후속 단계에서 복원)
"""
from __future__ import annotations

import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE = "https://news.google.com/rss/search"
from radar.config import USER_AGENT

UA = {"User-Agent": USER_AGENT}


def build_queries(customers, watchlist, base_queries):
    qs = list(base_queries)
    for company in watchlist:
        for c in customers:
            qs.append(f"{company} {c}")
    return qs


def fetch(query: str, when: str | None = None, timeout: int = 40) -> list[dict]:
    q = f"{query} when:{when}" if when else query
    url = BASE + "?" + urllib.parse.urlencode(
        {"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    )
    r = httpx.get(url, headers=UA, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    out = []
    for block in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        def g(tag):
            m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
            return html.unescape(m.group(1)) if m else None
        out.append({
            "query": query,
            "title": g("title"),
            "link": g("link"),
            "pub": g("pubDate"),
            "source": g("source"),
            "desc": re.sub(r"<[^>]+>", "", g("description") or ""),
        })
    return out


def collect(queries, when=None, workers=10):
    with ThreadPoolExecutor(workers) as ex:
        chunks = ex.map(lambda q: fetch(q, when), queries)
        items = [it for chunk in chunks for it in chunk]
    merged = {}
    for it in items:
        if it.get("title"):
            merged.setdefault(it["title"], it)
    return list(merged.values())
