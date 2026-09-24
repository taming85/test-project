# -*- coding: utf-8 -*-
"""~/API_KEYS.yaml -> public/config.js 생성 (프런트 노출용 publishable/anon 키만)."""
import argparse, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "public" / "config.js"


def read_keys():
    import yaml
    p = pathlib.Path.home() / "API_KEYS.yaml"
    if p.exists():
        y = yaml.safe_load(p.read_text()) or {}
        return y.get("supabase", {}) or {}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-env", action="store_true", help="키를 stdout 환경변수 형태로도 출력")
    a = ap.parse_args()
    s = read_keys()
    url = os.getenv("SUPABASE_URL") or s.get("url") or ""
    key = os.getenv("SUPABASE_ANON_KEY") or s.get("anon_key") or ""
    if url.endswith("/v1"):
        url = url  # 이미 /rest/v1 형태
    if not key:
        print("anon key 를 찾지 못했습니다.", file=sys.stderr)
        return 1
    out = ('/* 생성 파일: python3 scripts/gen_config.py\n'
           '   이 파일은 커밋된다. 정적 사이트라 빌드 단계가 없기 때문.\n'
           '   들어있는 값은 Supabase publishable(anon) 키이며 RLS 로 SELECT 만 허용된다. */\n'
           'window.__RADAR_CONFIG__ = {\n'
           '  supabaseUrl: "' + url + '",\n'
           '  supabaseAnonKey: "' + key + '"\n};\n')
    TEMPLATE.write_text(out, encoding="utf-8")
    print(f"wrote {TEMPLATE}")
    if a.write_env:
        print(f"SUPABASE_URL={url}")
        print(f"SUPABASE_ANON_KEY={key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
