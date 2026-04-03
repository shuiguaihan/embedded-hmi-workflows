---
name: write-handoff
description: Use when the user asks to write or refresh a project's handoff, current_state, state.yaml, brief.md, or other compact resume surface for later continuation.
metadata:
  short-description: Refresh the canonical resume surface
---

# Write Handoff

Use this skill only to create or update handoff files.

## Scope

- decide the canonical handoff mode from project rules first
- report `mode`, `confidence`, and `reason` before writing any files
- refresh the primary resume surface before any compatibility surface
- write compatibility `current_*` only when rules or the user explicitly require it
- keep the active handoff surface lean enough for later resume

Do not use this skill to continue implementation from old handoff files. That belongs to `$resume-handoff`.

## Modes

Rules first, files second: `规则优先，文件现状次之`.

- `legacy-handoff`
  - primary outputs: `current_handoff.md` + `current_state.yaml`
- `single-current`
  - primary outputs: project `state.yaml` + `brief.md`
  - `current_*` stays compatibility-only
- `hybrid-compat`
  - primary outputs: project `state.yaml` + `brief.md`
  - compatibility `current_*` may also be refreshed after the primary surface

## Lean Handoff Rules

1. The primary resume surface is a compact entrypoint, not a transcript.
2. Structured state is not a dump of every detail.
3. Prefer links and paths over pasted content.
4. Keep only the latest actionable state.
5. Put stable long-lived facts in project memory files such as `docs/ai-handoff.md`, not in session handoff files.
6. Compatibility `current_*` existing on disk does not make it canonical.

Target size budget:

- primary markdown handoff: ideally under 60 lines
- primary structured state: ideally under 45 lines
- key files: at most 5
- key commands: at most 4
- completed / remaining / blockers / must-recheck: at most 4 items each

## Workflow

1. Read the nearest applicable `AGENTS.md` and handoff rules.
2. Detect mode:

```bash
python3 shared/handoff/handoff_mode.py detect --project-root <root>
```

3. Plan outputs:

```bash
python3 shared/handoff/handoff_mode.py plan-write \
  --project-root <root> \
  --primary-dir <primary-dir> \
  --compat-dir <compat-dir> \
  --include-compat
```

4. Render only the planned files for the active mode.
5. Fill in only the current goal, latest verified facts, must-recheck items, blockers, and next actions.
6. Run lint for the active mode:

```bash
python3 shared/handoff/lint_handoff_size.py --mode <mode> [--compat-dir <compat-dir>] <dir>
```

7. If the files exceed the budget, compress them before finishing.
8. Report `mode`, `confidence`, `reason`, verified facts, unverified facts, and whether compat was generated.

## Output Rules

- `legacy-handoff`
  - refresh `current_handoff.md`
  - refresh `current_state.yaml`
- `single-current`
  - refresh project `state.yaml`
  - refresh `brief.md`
  - write compatibility `current_*` only when rules or the user explicitly require it
- `hybrid-compat`
  - refresh project `state.yaml`
  - refresh `brief.md`
  - refresh compatibility `current_*` only after the primary surface is updated

## Writing Rules

- separate verified facts from assumptions
- report low confidence instead of silently guessing in mixed layouts
- state what was not validated and why
- keep commands executable and current
- do not duplicate large result summaries into handoff
- do not repeat the same fact across the primary resume surface
- do not paste workflow overview docs into handoff files; link them instead
- do not silently overwrite user-maintained notes
