# -*- coding: utf-8 -*-
"""기사 -> 계약 이벤트 정규화.

역할: 기사 제목/요약에서 (공급사, 발주처, 계약금액, 계약일, 구분) 을 뽑아
      중복(동일 계약 복수 보도)을 제거한다.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from email.utils import parsedate_to_datetime

from radar.config import (
    CUSTOMERS, CONTRACT_KEYWORDS, DOMAIN_KEYWORDS, EQUIPMENT_KEYWORDS,
    WATCHLIST, OWN_BRAND_BLOCKLIST,
)

AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(조\s*원|억\s*원|억|만\s*원|조)")
UNIT = {"조": 1e12, "억": 1e8, "만": 1e4}
NAME_RE = re.compile("(" + "|".join(sorted(WATCHLIST, key=len, reverse=True)) + ")")
STOP_SOURCES = ("네이버 블로그", "Naver Blog", "유튜브", "YouTube", "티스토리")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def to_won(value: str, unit: str) -> float | None:
    u = "".join(unit.split())
    for k, mult in UNIT.items():
        if u.startswith(k):
            return float(value.replace(",", "")) * mult
    return None


def parse_amount(text: str) -> float | None:
    best = None
    for value, unit in AMOUNT_RE.findall(text or ""):
        won = to_won(value, unit)
        if won and (best is None or won > best):
            best = won
    return best


def to_event(item: dict) -> dict | None:
    title = _norm(item.get("title"))
    desc = _norm(item.get("desc"))
    if not item.get("pub"):
        return None
    try:
        date = parsedate_to_datetime(item["pub"]).date()
    except Exception:
        return None
    if any(s in (item.get("source") or "") for s in STOP_SOURCES):
        return None

    blob = title + " " + desc
    customers = [c for c in CUSTOMERS if c in blob]
    if not customers:
        return None
    hit = NAME_RE.search(title) or NAME_RE.search(desc)
    if not hit:
        return None
    supplier = hit.group(1)
    if any(b == supplier for b in OWN_BRAND_BLOCKLIST):
        return None
    if not any(w in blob for w in CONTRACT_KEYWORDS):
        return None
    if not any(w in blob for w in DOMAIN_KEYWORDS):
        return None

    return {
        "date": date.isoformat(),
        "supplier": supplier,
        "customers": customers,
        "amount": parse_amount(title) or parse_amount(desc),
        "equipment": any(w in blob for w in EQUIPMENT_KEYWORDS),
        "title": title,
        "link": item.get("link"),
        "source": item.get("source"),
        "query": item.get("query"),
    }


def dedupe(events: list[dict],AmountWindowDays=14, NearWindowDays=3) -> list[dict]:
    """동일 계약 복수 보도 제거: 동일(공급사, 발주처) + 금액유사(14일) 또는 근접일자(3일)."""
    def rank(r):
        # 공시(DART)를 항상 우선, 그다음 금액 큰 순
        return (r.get("source_kind") != "dart", -(r["amount"] or 0), r["date"])
    ordered = sorted(events, key=rank)
    kept: list[dict] = []
    for e in ordered:
        d = dt.date.fromisoformat(e["date"])
        dup = False
        for k in kept:
            if e["supplier"] != k["supplier"] or e["customers"] != k["customers"]:
                continue
            kd = dt.date.fromisoformat(k["date"])
            same_amount = (
                e["amount"] and k["amount"] and abs(e["amount"] - k["amount"]) < 1
                and abs((d - kd).days) <= AmountWindowDays
            )
            if same_amount or abs((d - kd).days) <= NearWindowDays:
                dup = True
                break
        if not dup:
            kept.append(e)
    return sorted(kept, key=lambda r: r["date"], reverse=True)


def merge_sources(dart_events, news_events, window_days=14):
    """동일 계약이면 공시(DART)를 우선하고 뉴스판을 제거한다."""
    kept = []
    for n in news_events:
        nd = dt.date.fromisoformat(n["date"])
        superseded = any(
            n["supplier"] == d["supplier"]
            and set(n["customers"]) & set(d["customers"])
            and abs((nd - dt.date.fromisoformat(d["date"])).days) <= window_days
            for d in dart_events
        )
        if not superseded:
            kept.append(n)
    return dart_events + kept


def build(articles: list[dict]) -> list[dict]:
    events = [e for e in (to_event(a) for a in articles) if e]
    return dedupe(events)
