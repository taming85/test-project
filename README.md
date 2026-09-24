# test-project

Static demo site used to verify the GitHub + Vercel workflow.

- Production: https://test-project-two-ochre.vercel.app
- Vercel project: `pdlee1985-3111/test-project`
- Guide (Korean): [docs/vercel-guide.md](docs/vercel-guide.md) — account linking, auto-deploy, troubleshooting

## Local preview

```bash
npx serve public
```

## Deploy

```bash
vercel deploy            # preview
vercel deploy --prod     # production
```

## Secrets

Local keys live outside the repo, in `~/.config/dev-secrets/secrets.env` (0600):
`GITHUB_TOKEN`, `TAVILY_API_KEY`. Tests use them; nothing is committed.
