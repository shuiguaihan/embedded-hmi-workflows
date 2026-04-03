---
name: resume-handoff
description: Use when the user asks to continue from a project's handoff, current_state, state.yaml, brief.md, or other canonical resume surface.
metadata:
  short-description: Resume from the canonical resume surface
---

# Resume Handoff

Use this skill only to resume work from existing handoff files.

## Scope

- find the canonical resume surface for the current project
- read only the minimum files needed to resume
- report `mode`, `confidence`, and 模式判断来源 before trusting any handoff
- list mutable state that must be re-checked
- continue only after separating verified facts from stale assumptions

Do not use this skill to create a new handoff package from scratch. That belongs to `$write-handoff`.

## Mode Rules

Rules first, files second: `规则优先，文件现状次之`.

- `legacy-handoff`
  - canonical path stays `current_state.yaml` -> `current_handoff.md`
- `single-current`
  - canonical path is project `state.yaml` -> `brief.md`
  - `current_*` is compatibility-only
- `hybrid-compat`
  - canonical path is project `state.yaml` -> `brief.md`
  - compatibility `current_*` is a secondary surface, not the primary one

## Read Order

- `legacy-handoff`
  1. `current_state.yaml`
  2. `current_handoff.md`
  3. formal artifacts when needed
- `single-current`
  1. project `state.yaml`
  2. `brief.md`
  3. run artifacts when needed
  4. `current_*` only in compatibility scenarios
- `hybrid-compat`
  1. project `state.yaml`
  2. `brief.md`
  3. compatibility `current_*`
  4. run artifacts when needed

Always report:

- `mode`
- `confidence`
- 模式判断来源
- 必须重查 mutable state

## Context Control Rules

1. Treat handoff files as an index, not a full archive.
2. Prefer opening the specific referenced file or section you need next.
3. Do not auto-read workflow overview docs or plan handoff docs unless the current task is workflow engineering or the handoff explicitly points there.
4. Do not load large summaries, logs, or artifacts unless they are required to unblock the next step.
5. Re-check mutable runtime state before trusting old conclusions.
6. Do not treat `current_*` as canonical just because it already exists.

## Resume Workflow

1. Read the nearest applicable `AGENTS.md` and handoff rules.
2. Detect mode:

```bash
python3 shared/handoff/handoff_mode.py detect --project-root <root>
```

3. Identify the active project and canonical resume surface.
4. Start from the smallest useful file set for that mode.
5. Extract:
   - current goal
   - blockers
   - 必须重查 items
   - next actions
6. Re-validate mutable state.
7. If the old handoff conflicts with current observations, record the conflict before proceeding.
8. Continue the first unfinished actionable step.

## Resume Rules

- prefer the primary surface over compatibility `current_*`
- report low confidence instead of silently guessing in mixed layouts
- separate verified facts from stale assumptions
- use long-lived memory files only when stable project facts are still missing
