---
name: build-action
description: Execute a project-configured build action from a local config file, capture logs, and report artifact results. Use when Codex needs to compile, package, or run a reusable build command through a checked-in config such as `project_ai/build-deploy.skill.yaml` instead of reconstructing ad hoc shell commands.
---

# Build Action

Use this skill to execute one build action described by project configuration. Keep the skill focused on the build itself; do not block on workflow gates, reviews, or deployment readiness.

## Quick Start

1. Find a project config file, preferably `project_ai/build-deploy.skill.yaml`.
2. If no real config exists, inspect `project_ai/build-deploy.skill.example.yaml` and tell the user which fields must be filled before execution.
3. Run `tools/run_build.py --config <path>` to execute, or add `--plan` to preview without side effects.
4. Report the working directory, command, log path, artifact path, and final status.

## Config Contract

- Read only the `build` section from the config.
- Expect the config file to be JSON-compatible YAML so it can be parsed without external dependencies.
- Resolve relative local paths from the project root. The recommended layout is project root + `project_ai/build-deploy.skill.yaml`.
- Treat missing required fields as configuration errors. Do not guess values.

Read `references/config-schema.md` when the config is missing, needs edits, or the project wants to onboard this skill.

## Execution Rules

- Prefer the checked-in config over hand-built shell snippets.
- Support `local` and `ssh` build hosts.
- Write logs under the configured `logs_dir`, or default to `project_ai/build-deploy-runs/`.
- If the build runs over SSH, verify the remote artifact path and optionally pull the artifact back when `fetch_artifact_to` is configured.
- Do not interpret build success as deploy approval. Stop after reporting the build result.

## Output Requirements

Always report:

- Config path used
- Working directory
- Exact build command
- Host kind: `local` or `ssh`
- Log file and summary file
- Artifact path, and fetched artifact path when applicable
- What was verified and what was not verified

## Script

Primary entrypoint:

```bash
python3 tools/run_build.py --config /abs/path/to/project_ai/build-deploy.skill.yaml
```

Preview mode:

```bash
python3 tools/run_build.py --config /abs/path/to/project_ai/build-deploy.skill.yaml --plan
```
