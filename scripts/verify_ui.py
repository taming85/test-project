# -*- coding: utf-8 -*-
"""UI 자동 검증: 렌더링/레이아웃/접근성 지표를 수치로 확인.

사용법: python3 scripts/verify_ui.py <url>
종료코드 0 = 문제 없음
"""
import json
import sys

from playwright.sync_api import sync_playwright

JS_AUDIT = """
() => {
  const parseRGB = (s) => {
    const m = s.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p[3] === undefined ? 1 : p[3] };
  };
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const lum = ({ r, g, b }) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const ratio = (fg, bg) => { const a = lum(fg), b = lum(bg); const hi = Math.max(a, b), lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05); };
  const bgOf = (node) => {
    let el = node;
    while (el) {
      const c = parseRGB(getComputedStyle(el).backgroundColor);
      if (c && c.a > 0.85) return c;
      el = el.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  };

  const res = {};
  res.rows = document.querySelectorAll('#rows tr').length;
  res.bars = document.querySelectorAll('#monthly-chart .bar').length;
  res.leaders = document.querySelectorAll('#leaderboard li').length;
  res.kpi = ['kpi-count', 'kpi-amount', 'kpi-equip', 'kpi-recent']
    .map((id) => (document.getElementById(id) || {}).textContent || '').join(' | ');
  res.lastRun = (document.getElementById('last-run') || {}).textContent || '';
  res.title = document.title;
  res.docWidth = document.documentElement.scrollWidth;
  res.winWidth = window.innerWidth;
  res.hasConfig = !!window.__RADAR_CONFIG__ && !!window.__RADAR_CONFIG__.supabaseAnonKey;

  // 명암비 검사 대상
  const targets = {
    body: document.body,
    kpiLabel: document.querySelector('.kpi-label'),
    kpiValue: document.querySelector('.kpi-value'),
    cell: document.querySelector('#rows td'),
    muted: document.querySelector('.muted'),
    th: document.querySelector('.data-table th'),
  };
  res.contrast = {};
  for (const [k, v] of Object.entries(targets)) {
    if (!v) continue;
    const fg = parseRGB(getComputedStyle(v).color);
    const bg = bgOf(v);
    res.contrast[k] = fg && bg ? Number(ratio(fg, bg).toFixed(2)) : null;
  }
  return res;
}
"""


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8137/"
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            for name, size in (("desktop", (1440, 980)), ("mobile", (390, 900))):
                page = browser.new_page(viewport={"width": size[0], "height": size[1]})
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(1500)
                if theme == "dark":
                    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
                    page.wait_for_timeout(400)
                res = page.evaluate(JS_AUDIT)
                tag = f"{theme}/{name}"
                print(f"--- {tag}")
                print(f"    rows={res['rows']} bars={res['bars']} leaders={res['leaders']}")
                print(f"    kpi={res['kpi']}")
                print(f"    lastRun={res['lastRun'][:80]}")
                print(f"    width doc={res['docWidth']} win={res['winWidth']}")
                print(f"    contrast={json.dumps(res['contrast'], ensure_ascii=False)}")
                if res["rows"] <= 1:
                    problems.append(f"{tag}: 데이터 행 없음")
                if res["bars"] == 0:
                    problems.append(f"{tag}: 차트 없음")
                if res["docWidth"] > res["winWidth"] + 1:
                    problems.append(f"{tag}: 가로 오버플로 {res['docWidth']}>{res['winWidth']}")
                if errs:
                    problems.append(f"{tag}: JS 오류 {errs[:2]}")
                if not res["hasConfig"]:
                    problems.append(f"{tag}: config.js 미로드")
                for k, v in res["contrast"].items():
                    if v is not None and v < 4.5:
                        problems.append(f"{tag}: 명암비 부족 {k}={v}")
                page.close()
        browser.close()
    print()
    if problems:
        print("[FAIL]")
        for p in problems:
            print("  -", p)
        return 1
    print("[PASS] 렌더링·레이아웃·명암비 모두 기준 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
