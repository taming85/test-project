# -*- coding: utf-8 -*-
"""사이트 스크린샷 캡처 (배포 검증용).

사용법: python3 scripts/shot.py <url> [outdir]
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 980), "mobile": (390, 900)}


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8137/"
    out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "shots")
    out.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            for name, (w, h) in VIEWPORTS.items():
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
                msgs = []
                page.on("console", lambda m: msgs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
                page.on("pageerror", lambda e: msgs.append(f"pageerror: {e}"))
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(1800)
                if theme == "dark":
                    page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
                    page.wait_for_timeout(600)
                page.screenshot(path=str(out / f"{theme}-{name}.png"), full_page=True)
                rows = page.locator("#rows tr").count()
                kpi = page.locator("#kpi-count").inner_text()
                print(f"{theme:5s} {name:7s} rows={rows} kpi={kpi} errors={msgs}")
                if msgs:
                    errors.append((theme, name, msgs))
                page.close()
        browser.close()
    if errors:
        print("\n[콘솔 오류]")
        for e in errors:
            print(e)
        return 2
    print("\n[OK] 콘솔 오류 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
