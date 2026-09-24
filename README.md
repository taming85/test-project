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

Local keys live outside the repo, in `~/API_KEYS.yaml` (0600, source of truth).
`~/.config/dev-secrets/secrets.env` is generated from it by
`python3 ~/.config/dev-secrets/sync_from_yaml.py`. Nothing is committed.
