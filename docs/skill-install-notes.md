# Claude Code skill install notes

Date: 2026-09-24  |  Host: Linux (WSL2)  |  Claude Code 2.1.281

## Result: both installed and registered (user scope)

| Plugin | Version | Install path | Enabled |
|---|---|---|---|
| superpowers@superpowers-marketplace | 6.4.1 | `/home/taming85/.claude/plugins/cache/superpowers-marketplace/superpowers/6.4.1` | true |
| ui-ux-pro-max@ui-ux-pro-max-skill | 2.13.0 | `/home/taming85/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.13.0` | true |

Both were installed through the **plugin marketplace** mechanism (the maintainer-documented path for each repo),
not by copying into `~/.claude/skills/`.

## Exact commands run

```bash
# 1) superpowers (obra / Jesse Vincent)
claude plugin marketplace add obra/superpowers-marketplace
claude plugin install superpowers@superpowers-marketplace -y --scope user

# 2) ui-ux-pro-max (nextlevelbuilder)
claude plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
claude plugin install ui-ux-pro-max@ui-ux-pro-max-skill -y --scope user

# verification (non-interactive)
claude plugin marketplace list
claude plugin list --json
claude plugin details superpowers
claude plugin details ui-ux-pro-max
claude plugin list --available --json
```

`-y` is required because stdin is not a TTY. Marketplace sources were confirmed from the repos'
READMEs (fetched with `curl -sL https://raw.githubusercontent.com/<owner>/<repo>/main/README.md`).

## Where files landed

- Settings: `~/.claude/settings.json` gets `enabledPlugins` + `extraKnownMarketplaces`.
- Registry: `~/.claude/plugins/installed_plugins.json` (with git commit SHAs).
- Marketplace clones: `~/.claude/plugins/marketplaces/`.
- Plugin payloads (skills): `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/...`
- No `~/.claude/skills/` directory was created; skills are served from the plugin cache.

## How to invoke

Both are **skill-based plugins** (no slash commands, no agents).

- superpowers, 15 skills, namespace `superpowers:<name>`. Invoke with the Skill tool or
  `/superpowers:<name>` (e.g. `/superpowers:brainstorming`, `/superpowers:systematic-debugging`,
  `/superpowers:test-driven-development`). A `SessionStart` hook auto-injects the
  `using-superpowers` skill into every session, which makes Claude check for a relevant skill
  before responding. Verified by running the hook locally:
  `CLAUDE_PLUGIN_ROOT=$PWD bash hooks/run-hook.cmd session-start` -> emits SessionStart
  `additionalContext` with the skill body.
- ui-ux-pro-max, 7 skills: `ui-ux-pro-max`, `design`, `design-system`, `brand`, `ui-styling`,
  `banner-design`, `slides`. Auto-activates on UI/UX requests; also callable directly
  (e.g. `/design`, `/ui-ux-pro-max`, `/design-system`).

Example prompts: "Build a landing page for my SaaS product", "Create a dashboard for healthcare analytics".
Skill-local search engine verified (Python 3.x, stdlib only):

```bash
python3 ~/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.13.0/.claude/skills/ui-ux-pro-max/scripts/search.py "SaaS landing page" --domain style --json
```
Returned 3 ranked style rows from `styles.csv` (exit 0).

## Blocker (not an install failure)

`claude -p "..."` prints `Not logged in · Please run /login`. So end-to-end execution inside a
Claude Code session could not be exercised. Registration/loading was proven with the non-interactive
`claude plugin ...` commands (they read the same settings and plugin cache the session uses) and by
running the superpowers SessionStart hook and the ui-ux-pro-max search script directly.

Manual next step to finish verification: run `claude` and `/login` (Anthropic auth or API key), then
inside the session run `/plugin` (installed list) and `/superpowers:brainstorming`.

## superpowers skill inventory (15)

### `brainstorming`
```yaml
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
```

### `diagnosing-superpowers`
```yaml
name: diagnosing-superpowers
description: Use when a superpowers session went wrong and your human partner wants to know why — repeated work, ignored plans, stumbles, poor results, a skill that didn't fire, "it took too long", "why is it so expensive", "what is it doing" — or wants to build a bug report for the superpowers maintainers, for the current session or a past one identified by id or path, on any harness.
```

### `dispatching-parallel-agents`
```yaml
name: dispatching-parallel-agents
description: Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies
```

### `executing-plans`
```yaml
name: executing-plans
description: Use when executing an implementation plan in the current session as the implementer yourself — your human partner chose inline execution, or no subagent tool is available
```

### `finishing-a-development-branch`
```yaml
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work
```

### `receiving-code-review`
```yaml
name: receiving-code-review
description: Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
```

### `requesting-code-review`
```yaml
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements
```

### `subagent-driven-development`
```yaml
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
```

### `systematic-debugging`
```yaml
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
```

### `test-driven-development`
```yaml
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
```

### `using-git-worktrees`
```yaml
name: using-git-worktrees
description: Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback
```

### `using-superpowers`
```yaml
name: using-superpowers
description: Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions
```

### `verification-before-completion`
```yaml
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
```

### `writing-plans`
```yaml
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
```

### `writing-skills`
```yaml
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
```

## ui-ux-pro-max skill inventory (7)

### `banner-design`
```yaml
name: banner-design
description: "Design banners for social media, ads, website heroes, creative assets, and print. Multiple art direction options with optional generated or supplied visuals. Actions: design, create, generate banner. Platforms: Facebook, Twitter/X, LinkedIn, YouTube, Instagram, Google Display, website hero, print. Styles: minimalist, gradient, bold typography, photo-based, illustrated, geometric, retro, glassmorphism, 3D, neon, duotone, editorial, collage."
argument-hint: "[platform] [style] [dimensions]"
license: MIT
metadata:
  author: claudekit
  version: "1.0.0"
```

### `brand`
```yaml
name: brand
description: Brand voice, visual identity, messaging frameworks, asset management, brand consistency. Activate for branded content, tone of voice, marketing assets, brand compliance, style guides.
argument-hint: "[update|review|create] [args]"
metadata:
  author: claudekit
  version: "1.0.0"
```

### `design-system`
```yaml
name: design-system
description: Token architecture, component specifications, and slide generation. Three-layer tokens (primitive→semantic→component), CSS variables, spacing/typography scales, component specs, strategic slide creation. Use for design tokens, systematic design, brand-compliant presentations.
argument-hint: "[component or token]"
license: MIT
metadata:
  author: claudekit
  version: "1.0.0"
```

### `design`
```yaml
name: design
description: "Comprehensive design skill: brand identity, design tokens, UI styling, logo generation (55 styles, Gemini, Atlas Cloud, or MuAPI AI), corporate identity program (50 deliverables, CIP mockups), HTML presentations (Chart.js), banner design (22 styles, social/ads/web/print), icon design (15 styles, SVG, Gemini 3.1 Pro), social photos (HTML→screenshot, multi-platform). Actions: design logo, create CIP, generate mockups, build slides, design banner, generate icon, create social photos, social media images, brand identity, design system. Platforms: Facebook, Twitter, LinkedIn, YouTube, Instagram, Pinterest, TikTok, Threads, Google Ads."
argument-hint: "[design-type] [context]"
license: MIT
metadata:
  author: claudekit
  version: "2.1.0"
```

### `slides`
```yaml
name: slides
description: Create strategic HTML presentations with Chart.js, design tokens, responsive layouts, copywriting formulas, and contextual slide strategies.
argument-hint: "[topic] [slide-count]"
metadata:
  author: claudekit
  version: "1.0.0"
```

### `ui-styling`
```yaml
name: ui-styling
description: Create beautiful, accessible user interfaces with shadcn/ui components (built on Radix UI + Tailwind), Tailwind CSS utility-first styling, and canvas-based visual designs. Use when building user interfaces, implementing design systems, creating responsive layouts, adding accessible components (dialogs, dropdowns, forms, tables), customizing themes and colors, implementing dark mode, generating visual designs and posters, or establishing consistent styling patterns across applications.
argument-hint: "[component or layout]"
license: MIT
metadata:
  author: claudekit
  version: "1.0.0"
```

### `ui-ux-pro-max`
```yaml
name: ui-ux-pro-max
description: "UI/UX design intelligence for web, mobile, and desktop. This skill should be used when designing, building, reviewing, or fixing interfaces, including pages, components, design systems, accessibility, interaction, responsive layout, typography, color, charts, and stack-specific UI implementation. Searchable local data: 79 searchable styles (50 active), 192 product palettes and reasoning profiles, 74 font pairings, 119 UX guidelines, 105 icons, 17 GSAP presets, 25 chart types, and 22 stacks."
```

## Optional extras (NOT installed)

`claude plugin list --available --json` shows other plugins in the superpowers marketplace:
`superpowers-chrome` (3.0.5), `elements-of-style` (1.0.0), `episodic-memory` (1.6.0),
`superpowers-lab` (0.5.0), `superpowers-developing-for-claude-code` (0.3.1), `superpowers-dev`
(dev branch - "you must uninstall other versions first"), `claude-session-driver` (4.0.0).
Install any with `claude plugin install <name>@superpowers-marketplace -y --scope user`.

## Notes / alternatives (from repo READMEs)

- ui-ux-pro-max also ships a CLI installer: `npx ui-ux-pro-max-cli init --ai claude [--global]`
  (npm package `ui-ux-pro-max-cli`, binary `uipro`). Not needed here; the marketplace install
  succeeded, so the README's symlink issue for versions < v2.5.1 did not apply (v2.13.0 installed).
- `claude plugin marketplace update` refreshes catalogs; `claude plugin update <id>` upgrades a plugin.
