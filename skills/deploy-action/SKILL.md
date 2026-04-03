---
name: deploy-action
description: Execute a project-configured deploy action from a local config file, capture transfer and restart logs, and report the final health-check result. Use when Codex needs to upload artifacts, replace files, restart services, or run health checks through a reusable config such as `project_ai/build-deploy.skill.yaml`.
---

# Deploy Action

Use this skill to execute one deploy action described by project configuration. Keep the skill focused on deployment mechanics; do not block on requirement review, test design, or any other workflow gate.

## Quick Start

1. Find a project config file, preferably `project_ai/build-deploy.skill.yaml`.
2. If the repo only contains `project_ai/build-deploy.skill.example.yaml`, tell the user to create the real config first.
3. Run `tools/run_deploy.py --config <path>` to execute, or add `--plan` to preview without side effects.
4. Report the source artifact, target host, remote path, restart action, health-check result, and log locations.

## Config Contract

- Read only the `deploy` section from the config.
- Expect the config file to be JSON-compatible YAML.
- Resolve local file paths from the project root. The recommended layout is project root + `project_ai/build-deploy.skill.yaml`.
- Treat missing required fields as configuration errors. Do not infer remote paths or restart commands.

Read `references/config-schema.md` when the config is missing, needs edits, or the project wants to onboard this skill.

## Execution Rules

- Prefer the checked-in config over ad hoc `scp` and `ssh` command construction.
- Support SSH-based deploy targets.
- Write logs under the configured `logs_dir`, or default to `project_ai/build-deploy-runs/`.
- Upload to a temporary path first, then move into place.
- If backup is enabled, preserve the previous target before overwrite.
- Run health checks only after the file replacement and optional restart command finish.
- Do not interpret a successful deploy as acceptance or verification completion. Stop after reporting the deploy result.

## Output Requirements

Always report:

- Config path used
- Local artifact path
- Target host and port
- Temporary path and final remote path
- Backup path when enabled
- Restart command and whether it ran
- Health checks and whether they passed
- What was verified and what was not verified

## Script

Primary entrypoint:

```bash
python3 tools/run_deploy.py --config /abs/path/to/project_ai/build-deploy.skill.yaml
```

Preview mode:

```bash
python3 tools/run_deploy.py --config /abs/path/to/project_ai/build-deploy.skill.yaml --plan
```
