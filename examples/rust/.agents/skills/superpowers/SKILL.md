---
name: superpowers
description: Superpowers workflow instructions adapted to write specs, plans, and workspace files under airoom/artifacts/.
---

# Superpowers Integration for AIroom

Superpowers workflows generate design specifications, implementation plans, brainstorming logs, and SDD workspaces. In this project, all such outputs are configured to resolve beneath `airoom/artifacts/`:

- **Specs**: `airoom/artifacts/docs/superpowers/specs/`
- **Plans**: `airoom/artifacts/docs/superpowers/plans/`
- **Brainstorming State**: `airoom/artifacts/.superpowers/brainstorm/`
- **SDD Workspaces**: `airoom/artifacts/.superpowers/sdd/`

## Scripts

Use `.agents/skills/superpowers/scripts/sdd-workspace <plan-path>` to initialize a plan-scoped workspace under `airoom/artifacts/.superpowers/sdd/`.
