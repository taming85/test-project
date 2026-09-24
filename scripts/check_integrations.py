#!/usr/bin/env python3
"""Check that the GitHub, Tavily, and Vercel integrations are working.

Run:  uv run --with httpx --with python-dotenv python3 scripts/check_integrations.py
Keys are read from the environment, then from ~/.config/dev-secrets/secrets.env
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx

SECRETS = Path.home() / ".config" / "dev-secrets" / "secrets.env"


def load() -> dict:
    values: dict[str, str] = {}
    if SECRETS.exists():
        try:
            from dotenv import dotenv_values

            values = {k: v for k, v in dotenv_values(SECRETS).items() if v}
        except ImportError:
            for line in SECRETS.read_text().splitlines():
                if line.startswith("export ") and "=" in line:
                    k, v = line[len("export ") :].split("=", 1)
                    values[k.strip()] = v.strip()
    import os

    for key in ("GITHUB_TOKEN", "TAVILY_API_KEY"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def check_github(token: str) -> bool:
    r = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  GitHub: FAIL HTTP {r.status_code} {r.text[:120]}")
        return False
    login = r.json()["login"]
    repos = httpx.get(
        "https://api.github.com/user/repos",
        headers={"Authorization": f"Bearer {token}"},
        params={"per_page": 100},
        timeout=30,
    ).json()
    print(f"  GitHub: OK  user={login}  repos={len(repos)}  scopes={r.headers.get('x-oauth-scopes', '')[:40]}...")
    return True


def check_tavily(key: str) -> bool:
    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": "vercel deploy", "max_results": 1, "include_answer": False},
        timeout=60,
    )
    if r.status_code != 200:
        print(f"  Tavily: FAIL HTTP {r.status_code} {r.text[:120]}")
        return False
    results = r.json().get("results", [])
    print(f"  Tavily: OK  results={len(results)}  first={results[0]['url'] if results else '-'}")
    return True


def check_vercel() -> bool:
    cli = subprocess.run(["vercel", "whoami"], capture_output=True, text=True, timeout=60)
    out = cli.stdout.strip().splitlines()
    who = out[-1] if out else ""
    if cli.returncode != 0 or "Logged out" in who:
        print("  Vercel: NOT LOGGED IN (run `vercel login`)")
        return False
    print(f"  Vercel: OK  account={who}")
    return True


def check_vercel_git_link(project_dir: Path | None = None) -> bool:
    """Report whether the linked Vercel project is connected to its GitHub repo."""
    import json

    project_dir = project_dir or Path(__file__).resolve().parent.parent
    proj_file = project_dir / ".vercel" / "project.json"
    auth_file = Path.home() / ".local" / "share" / "com.vercel.cli" / "auth.json"
    if not proj_file.exists() or not auth_file.exists():
        print("  Vercel git link: SKIP (no linked project or no CLI session)")
        return True
    ids = json.loads(proj_file.read_text())
    token = json.loads(auth_file.read_text())["token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = httpx.get(
        f"https://api.vercel.com/v9/projects/{ids['projectId']}", headers=headers, timeout=30
    )
    link = (r.json() or {}).get("link") or {}
    if link.get("type") == "github":
        print(
            f"  Vercel git link: OK  {link.get('org')}/{link.get('repo')}"
            f"  branch={link.get('productionBranch')}"
        )
        return True
    names = httpx.get(
        "https://api.vercel.com/v1/integrations/git-namespaces",
        headers=headers,
        params={"provider": "github"},
        timeout=30,
    ).json()
    if not names:
        print(
            "  Vercel git link: NOT CONNECTED - install the Vercel GitHub App first: "
            "https://github.com/apps/vercel/installations/new"
        )
    else:
        print(
            "  Vercel git link: NOT CONNECTED - run: "
            "vercel git connect https://github.com/<owner>/<repo>.git"
        )
    return False


def main() -> int:
    keys = load()
    print("Integration check")
    ok = []
    if not keys.get("GITHUB_TOKEN"):
        print("  GitHub: SKIP (no GITHUB_TOKEN)")
    else:
        ok.append(check_github(keys["GITHUB_TOKEN"]))
    if not keys.get("TAVILY_API_KEY"):
        print("  Tavily: SKIP (no TAVILY_API_KEY)")
    else:
        ok.append(check_tavily(keys["TAVILY_API_KEY"]))
    ok.append(check_vercel())
    ok.append(check_vercel_git_link())
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
