# -*- coding: utf-8 -*-
"""DART(금융감독원) 전자공시 수집기 - 계약 금액의 정본(正本) 소스.

인증: OPENDART_KEY (https://opendart.fss.or.kr 무료 발급)
      ~/API_KEYS.yaml -> dart.api_key 또는 환경변수 OPENDART_KEY

동작 순서
  1) corpCode.xml : 워치리스트 기업명 -> corp_code 매핑 (캐시)
  2) list.json    : 기업별 기간 내 공시 목록 -> '단일판매·공급계약' 류만 선택
  3) document.xml : 공시 원문(zip)에서 계약금액/계약상대방/기간/유보사유 추출
  4) 계약상대방이 발주처(현대모비스/현대트랜시스) 별칭과 맞으면 이벤트로 채택

주의: 공시 서식이 세대별로 달라 정규식을 여러 개 둔다(구서식/신서식).
      계약상대방이 해외 법인명(MOBIS North America Electrified Powertrain, LLC)으로
      나오는 경우가 많아 별칭 매칭을 반드시 거친다.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import httpx

from radar import config

BASE = "https://opendart.fss.or.kr/api"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
CACHE = pathlib.Path.home() / ".cache" / "radar"
CACHE.mkdir(parents=True, exist_ok=True)

# 발주처 별칭 (해외 법인명/영문명 포함)
COUNTERPART_ALIASES = {
    "현대모비스": ["현대모비스", "현대모비스주식회사", "주식회사 현대모비스", "모비스", "MOBIS", "Hyundai Mobis", "Hyundai MOBIS"],
    "현대트랜시스": ["현대트랜시스", "현대트랜시스주식회사", "트랜시스", "TRANSYS", "Hyundai Transys", "Hyundai Transsys"],
}

SIG = re.compile(r"단일판매[ㆍ·].{0,4}공급계약")

# 신서식 / 구서식 모두 지원
PATTERNS = {
    "amount": [r"계약금액\s*총액\(원\)\s*([\d,]+)", r"확정\s*계약금액\s*([\d,]+)", r"계약금액\(원\)\s*([\d,]+)"],
    "revenue": [r"최근\s*매출액\(원\)\s*([\d,]+)"],
    "ratio": [r"매출액\s*대비\(%\)\s*([\d,\.]+)"],
    "counterpart": [r"계약상대방\s+(.+?)\s*-\s*최근\s*매출액", r"계약상대\s+(.+?)\s*-\s*회사와의\s*관계"],
    "start": [r"시작일\s*(\d{4}-\d{2}-\d{2})"],
    "end": [r"종료일\s*(\d{4}-\d{2}-\d{2})"],
    "sign": [r"계약\(수주\)일자\s*(\d{4}-\d{2}-\d{2})"],
    "name": [r"판매[ㆍ·]공급계약\s*내용\s+(.+?)\s*2\.\s*계약내역", r"체결계약명\s+(.+?)\s*2\.\s*계약내역"],
    "region": [r"판매[ㆍ·]공급지역\s+([^\s]+)"],
    "hold_reason": [r"유보사유\s+([^\-]{2,40}?)\s*유보기한", r"유보사유\s+([^\-]{2,40}?)\s*$"],
    "hold_until": [r"유보기한\s*(\d{4}-\d{2}-\d{2})"],
    "usd": [r"계약금액은\s*USD\s*([\d,\.]+)"],
    "fx": [r"매매기준\s*환율\s*([\d,\.]+)"],
}


def key() -> str:
    if os.getenv("OPENDART_KEY"):
        return os.environ["OPENDART_KEY"]
    p = pathlib.Path.home() / "API_KEYS.yaml"
    if p.exists():
        try:
            import yaml
            return (yaml.safe_load(p.read_text()).get("dart") or {}).get("api_key", "")
        except Exception:
            pass
    return ""


def get(url: str, params: dict, timeout: int = 40, tries: int = 3):
    """타임아웃/일시 오류에 재시도."""
    last = None
    for i in range(tries):
        try:
            return httpx.get(url, params=params, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - 일시적 네트워크 오류만 흡수
            last = exc
            __import__("time").sleep(1.5 * (i + 1))
    print(f"      [dart] 요청 실패: {url.split('/')[-1]} ({last})")
    return None


def enabled() -> bool:
    return bool(key())


# ---------- 1) corp_code 매핑 ----------
def corp_map(refresh: bool = False) -> dict:
    """{기업명: {corp_code, stock_code}} - 상장사 우선, 30일 캐시."""
    cache = CACHE / "dart_corps.json"
    if cache.exists() and not refresh and (time.time() - cache.stat().st_mtime) < 30 * 86400:
        return json.loads(cache.read_text())
    r = get(f"{BASE}/corpCode.xml", {"crtfc_key": key()}, timeout=180, tries=2)
    if r is None or r.status_code != 200:
        raise RuntimeError("corpCode.xml 조회 실패")
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml").decode("utf-8"))
    out = {}
    for e in root.iter("list"):
        d = {c.tag: c.text for c in e}
        name, code, stock = d.get("corp_name"), d.get("corp_code"), d.get("stock_code") or ""
        if not name or not code:
            continue
        cur = out.get(name)
        # 상장사(stock_code 있음)를 우선한다
        if cur is None or (stock and not cur.get("stock_code")):
            out[name] = {"corp_code": code, "stock_code": stock}
    cache.write_text(json.dumps(out, ensure_ascii=False))
    return out


# ---------- 2) 공시 목록 ----------
def filings(corp_code: str, start: str, end: str, max_pages=4) -> list[dict]:
    rows = []
    for page in range(1, max_pages + 1):
        r = get(f"{BASE}/list.json", {
            "crtfc_key": key(), "corp_code": corp_code, "bgn_de": start,
            "end_de": end, "page_no": page, "page_count": 100,
        })
        if r is None or r.status_code != 200:
            break
        d = r.json()
        if d.get("status") != "000":
            break
        rows += d.get("list", [])
        if page >= d.get("total_page", 1):
            break
    return rows


def is_supply_contract(report_nm: str) -> bool:
    nm = (report_nm or "").replace(" ", "")
    return bool(SIG.search(nm)) and "해지" not in nm


# ---------- 3) 공시 원문 파싱 ----------
def flatten(rcept_no: str) -> str | None:
    r = get(f"{BASE}/document.xml", {"crtfc_key": key(), "rcept_no": rcept_no}, timeout=60, tries=2)
    if r is None or r.status_code != 200 or not r.content:
        return None
    try:
        raw = zipfile.ZipFile(io.BytesIO(r.content)).read(f"{rcept_no}.xml")
    except Exception:
        return None
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"<STYLE>.*?</STYLE>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def num(s):
    return int(s.replace(",", "")) if s and s.strip("-") and s.strip("-").replace(",", "").isdigit() else None


def parse_detail(flat: str) -> dict:
    out = {}
    for field, pats in PATTERNS.items():
        for pat in pats:
            m = re.search(pat, flat)
            if m:
                out[field] = m.group(1).strip()
                break
    for k in ("amount", "revenue"):
        if k in out:
            out[k] = num(out[k])
    for k in ("ratio", "usd", "fx"):
        if k in out:
            out[k] = num(out[k]) or float(re.sub(r"[^\d\.]", "", out[k]) or 0) or None
    out["amount"] = out.get("amount")
    return out


def match_customers(counterpart: str) -> list[str]:
    cp = (counterpart or "").upper()
    hits = []
    for canon, aliases in COUNTERPART_ALIASES.items():
        for a in aliases:
            if a.upper() in cp:
                hits.append(canon)
                break
    return hits


# ---------- 4) 수집 진입점 ----------
def collect(start: str, end: str, watchlist=None, workers=6) -> list[dict]:
    """발주처가 고객사인 계약만 이벤트 형태로 반환."""
    if not enabled():
        return []
    watchlist = watchlist or (config.WATCHLIST_EQUIPMENT + config.WATCHLIST_PARTS)
    cmap = corp_map()
    targets = [(w, cmap[w]) for w in watchlist if w in cmap]

    delisted = [w for w in watchlist if w not in cmap]
    if delisted:
        print(f"      corpCode 미매칭(비상장/표기차이): {', '.join(delisted[:8])}")

    found = []
    for name, info in targets:
        for f in filings(info["corp_code"], start, end):
            if is_supply_contract(f.get("report_nm", "")):
                found.append((name, f))

    events = []
    def safe(pair):
        try:
            return flatten(pair[1]["rcept_no"])
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(max(1, min(workers, 4))) as ex:
        flats = list(ex.map(safe, found))

    for (name, f), flat in zip(found, flats):
        if not flat:
            continue
        d = parse_detail(flat)
        customers = match_customers(d.get("counterpart", ""))
        if not customers:
            continue
        cname = d.get("name") or ""
        events.append({
            "date": d.get("sign") or f"{f['rcept_dt'][:4]}-{f['rcept_dt'][4:6]}-{f['rcept_dt'][6:8]}",
            "supplier": name,
            "customers": customers,
            "amount": d.get("amount"),
            "equipment": name in config.WATCHLIST_EQUIPMENT
                         or any(k in cname for k in config.EQUIPMENT_KEYWORDS),
            "title": (f"{cname} ({d.get('counterpart','')})" if cname
                      else f"단일판매·공급계약 ({d.get('counterpart','')})"),
            "link": VIEWER + f["rcept_no"],
            "source": "DART 공시",
            "source_kind": "dart",
            "dart_no": f["rcept_no"],
            "detail": {
                "counterpart_raw": d.get("counterpart"),
                "revenue": d.get("revenue"),
                "revenue_ratio": d.get("ratio"),
                "region": d.get("region"),
                "period": [d.get("start"), d.get("end")],
                "usd": d.get("usd"),
                "fx": d.get("fx"),
                "hold_reason": d.get("hold_reason"),
                "hold_until": d.get("hold_until"),
            },
        })
    return events
