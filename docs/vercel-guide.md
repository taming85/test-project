# Vercel 배포 + 계정 연동 가이드 (실제 검증 완료)

작성: Prime Agent · 검증 환경: WSL2 + Vercel CLI 59.26.0 + gh 2.101.0

---

## 0. 결론 먼저 (TL;DR)

1. **Vercel 계정 연동은 이미 끝났다.** 이 PC는 Vercel 계정 `pdlee1985-3111`
   (`pdlee1985@gmail.com`, Hobby) 로 로그인되어 있다. CLI 세션은 `auth.json`에 저장된다.
2. **사이트는 이미 배포되어 살아 있다.**
   - 프로덕션(공유용): https://test-project-two-ochre.vercel.app
   - 프로젝트: `pdlee1985-3111/test-project`
3. **GitHub 저장소 ↔ Vercel 자동배포 연동은 아직 안 됐다.**
   이유: Vercel 계정에 GitHub 로그인 연결(Login Connection)이 없음.
   → 아래 "2-B"를 하면 `git push` 만으로 자동배포가 된다.
4. 지금 당장 배포가 필요하면 연동 없이도 CLI로 바로 배포할 수 있다: `vercel deploy --prod`.

---

## 1. 현재 이 PC의 연동 상태 (테스트 결과)

| 항목 | 상태 | 증거 |
|---|---|---|
| GitHub PAT (`ghp_...`) | 정상 | `/user` 200, 계정 `taming85`, repo scope 보유 |
| GitHub 저장소 | 생성/푸시/읽기 정상 | `taming85/test-project`, 커밋 `c77edbf` |
| `gh` CLI | 설치 + 로그인 | `~/.local/bin/gh` 2.101.0, `gh auth status` OK |
| git HTTPS 자격증명 | 저장됨 | `~/.git-credentials` (0600), `git push` 무암호 통과 |
| Tavily 키 | 정상 | 검색(`/search`)·본문추출(`/extract`) 모두 200 |
| Tavily 에이전트 스킬 | 설치 | `~/.prime/agent/skills/tavily-search` |
| Vercel CLI | 설치 + 로그인 | 59.26.0, `vercel whoami` → `pdlee1985-3111` |
| Vercel 프로젝트 | 연결됨 | `.vercel/project.json` (`prj_70Vnc...`) |
| Vercel 프로덕션 배포 | 성공 | `Ready in 6s`, HTTP 200 |

키 파일 위치(값은 여기 적지 않는다):

```
~/.config/dev-secrets/secrets.env     # 0600, GITHUB_TOKEN / TAVILY_API_KEY
~/.git-credentials                    # 0600, git HTTPS 자동 로그인
~/.config/gh/hosts.yml                # gh CLI 로그인
~/.local/share/com.vercel.cli/auth.json  # Vercel CLI 세션
```

`~/.bashrc`와 `~/.profile`이 `secrets.env`를 자동으로 읽는다. 그래서 새 터미널에서
`GITHUB_TOKEN`, `TAVILY_API_KEY`를 바로 쓸 수 있다. 단, 에이전트가 쓰는 비대화형
셸에는 자동 적용되지 않으므로 스크립트에서는 아래처럼 직접 읽는 편이 안전하다.

```python
from dotenv import dotenv_values
keys = dotenv_values("/home/taming85/.config/dev-secrets/secrets.env")
```

---

## 2. Vercel 계정 연동 방법 3가지

### A. CLI 로그인 — "이 PC를 내 계정에 연결" (완료됨)

한 번만 하면 된다. 세션은 `~/.local/share/com.vercel.cli/auth.json`에 남는다.

```bash
vercel login
# 브라우저에서 열 주소가 출력된다 (예: https://vercel.com/oauth/device?user_code=XXXX-XXXX)
# 로그인/승인 후 자동으로 "Congratulations! You are now signed in."이 뜬다

vercel whoami     # pdlee1985-3111
vercel teams ls   # Hobby 팀 확인
```

주의할 점:

- WSL에서는 출력된 주소를 **Windows 브라우저에 붙여 넣어** 승인하면 된다.
- 세션이 만료되면(현재 토큰 만료까지 약 8시간) `vercel whoami`가 `Logged out`을
  출력한다. 그때 `vercel login`을 다시 실행하면 된다.
- 다른 계정으로 바꾸려면 `vercel logout && vercel login`.
  **지금 로그인된 계정이 본인 계정이 맞는지 먼저 확인하라.**
  (`pdlee1985-3111` / `pdlee1985@gmail.com` 이 아니면 로그아웃하고 다시 로그인)

### B. GitHub 저장소 연동 — "git push 하면 자동배포" (아직 안 됨, 이걸 하면 된다)

**선행 조건: Vercel 계정에 GitHub 로그인 연결(Login Connection)이 있어야 한다.**
연결이 없어서 실제로 이런 오류가 났다:

```
Error: Failed to link taming85/test-project.
You need to add a Login Connection to your GitHub account first. (400)
```

순서:

1. 브라우저에서 https://vercel.com/account/settings/authentication 접속 → 로그인
2. **Add Login Connection → GitHub → Continue with GitHub → Authorize**
   - GitHub 계정 `taming85`로 승인
   - 저장소 접근 범위: `All repositories` 또는 `Only select repositories` → `test-project` 선택
3. 다시 이 PC에서 저장소를 Vercel 프로젝트에 연결한다:

```bash
cd /home/taming85/workspace/test-project
vercel git connect https://github.com/taming85/test-project.git
```

4. 연동 확인:

```bash
vercel git connect --help          # 사용법
vercel project ls                  # 프로젝트 목록
# 대시보드: 프로젝트 → Settings → Git 에 저장소가 보이면 성공
```

이후에는 `main` 브랜치에 push하면 프로덕션 자동배포, PR/다른 브랜치는
프리뷰 URL이 자동 생성된다(각 PR에 Vercel 댓글이 달린다).

### C. GitHub Actions + Vercel 토큰 — 대시보드 연동 없이 자동배포

GitHub 앱 설치를 피하고 싶을 때 쓴다. **Vercel 토큰은 대시보드에서만 만들 수 있다.**
(CLI 세션으로는 토큰 생성이 막혀 있다: `Cannot create tokens for this app. (403)`)
— 이건 "이 CLI 세션은 OAuth 앱 세션이라 새 토큰 발급 권한이 없다"는 뜻이며,
브라우저에서 로그인한 상태로 만들면 정상 발급된다.

순서:

1. https://vercel.com/account/settings/tokens → **Create Token**
   - 이름: `github-actions-test-project`
   - Scope: `pdlee1985-3111` (본인 팀), Expiration: 90일 권장
   - **Project**: `test-project` 만 선택하면 최소 권한이 된다
   - 발급된 값을 복사(다시 볼 수 없음)
2. 값이 노출되지 않게 GitHub 저장소 Secret으로 저장한다:

```bash
cd /home/taming85/workspace/test-project
gh secret set VERCEL_TOKEN        # 프롬프트에 붙여 넣기
gh secret set VERCEL_ORG_ID --body team_kKCai6W2BGv5cEjfKzBEfDt6
gh secret set VERCEL_PROJECT_ID --body prj_70VncIw5chWvXLd48MwHFqUG30lQ
gh secret list
```

3. 워크플로 파일 `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Vercel
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
      VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm i -g vercel@latest
      - run: vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}
      - run: vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}
      - run: vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}
```

4. `git push` 후 확인:

```bash
gh run list --limit 3
gh run watch
```

---

## 3. 일상 배포 명령어 (지금 바로 되는 것)

```bash
cd /home/taming85/workspace/test-project

vercel deploy              # 프리뷰 배포 (테스트용 URL)
vercel deploy --prod       # 프로덕션 배포 (공식 URL 갱신)
vercel ls                  # 배포 목록
vercel inspect <url> --logs  # 빌드 로그
vercel rollback            # 직전 정상 배포로 롤백
```

로그인 없이 남에게 "이 URL 가져가라" 형태로 넘길 때:

```bash
vercel deploy --temporary --yes
# ▲ Temporary  https://temporary-xxx.vercel.app
# > Claim: https://vercel.com/claim-deployment?code=XXXX
```

claim 링크를 열고 Vercel에 로그인해서 팀을 고르면 그 배포가 자기 계정으로
이전된다. 링크는 배포 60분 후 만료되며, 다시 `--temporary`를 실행하면 새 링크가 나온다.

---

## 4. 커스텀 도메인과 환경변수 (필요할 때)

```bash
vercel domains add example.com test-project     # 도메인 연결
vercel env add MY_API_KEY production            # 프로덕션 환경변수
vercel env ls                                   # 목록
vercel pull --yes --environment=production      # 로컬로 설정 내려받기
```

DNS는 도메인 등록기관에서 Vercel이 안내하는 레코드(A 또는 CNAME)를 넣으면 된다.
`.vercel.app` 기본 주소는 그대로 두고 커스텀 도메인만 추가하면 된다.

---

## 5. 문제 해결 (이번에 실제로 겪은 것)

| 증상 | 원인 | 해결 |
|---|---|---|
| 배포했는데 `/` 가 404, `/index.html`은 308 | `vercel.json`의 `"cleanUrls": true`가 정적 루트 매핑을 깨뜨림 | `cleanUrls` 삭제(현재 적용됨). 필요하면 `rewrites`로 직접 매핑 |
| `gh auth login --with-token` 이 exit 1 | 셸에 `GH_TOKEN`/`GITHUB_TOKEN`이 export되어 있어 gh가 무시 | `env -u GH_TOKEN -u GITHUB_TOKEN gh auth login --with-token` |
| 배포 URL을 남에게 공유하면 로그인 화면이 뜸 | 배포별 URL은 Vercel Authentication 보호 대상 | 프로덕션 alias(`https://test-project-two-ochre.vercel.app`)를 공유 |
| `vercel git connect` 가 400 | Vercel에 GitHub 로그인 연결이 없음 | 위 2-B의 1~2단계 수행 |
| `vercel tokens add` 가 403 | CLI OAuth 세션은 토큰 발급 권한 없음 | 대시보드에서 토큰 생성 (2-C) |
| 새 터미널에서 `TAVILY_API_KEY`가 비어 있음 | 비대화형 셸은 `.bashrc`를 안 읽음 | 스크립트에서 `secrets.env`를 직접 읽기 |

---

## 6. 보안 체크리스트

- `secrets.env`, `.git-credentials`, `auth.json` 은 모두 0600 이다. 값을 채팅/스크린샷/
  커밋에 붙이지 않는다. `.gitignore`에 `.env*`, `.vercel/` 이 들어 있다.
- GitHub PAT는 모든 scope를 가진 classic 토큰이다. 가능하면 repo/workflow 정도만
  가진 **fine-grained PAT**로 교체하는 편이 안전하다.
- 토큰을 메신저나 공개 채널에 붙였다면 즉시 회수(revoke)하고 재발급한다.
  - GitHub: https://github.com/settings/tokens
  - Vercel: https://vercel.com/account/settings/tokens
- CI용 Vercel 토큰은 프로젝트 단위로 좁히고 만료일을 두는 편이 좋다.
