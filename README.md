# embedded-hmi-workflows

[中文说明](README.zh-CN.md)

面向嵌入式显示器开发的工作流。

Lightweight workflow skills for embedded display and HMI development.

This repository groups a small set of reusable skills for common engineering flows:

- resume and handoff management
- build execution from checked-in config
- deploy execution from checked-in config
- lightweight shared helpers for workflow-oriented automation

The repository is intentionally small in its first public shape. It favors clear skill boundaries, local-only secrets, and publish-safe defaults over a large framework.

## Included skills

### Handoff

- `write-handoff`: refresh the canonical handoff surface for a project
- `resume-handoff`: continue from the canonical handoff surface with mutable-state rechecks

### Build and deploy

- `build-action`: execute a configured build action from a checked-in config file
- `deploy-action`: execute a configured deploy action from a checked-in config file

## Repository layout

```text
embedded-hmi-workflows/
├─ skills/
│  ├─ write-handoff/
│  ├─ resume-handoff/
│  ├─ build-action/
│  └─ deploy-action/
├─ shared/
│  └─ handoff/
├─ tools/
└─ tests/
```

- `skills/`: skill definitions and agent metadata
- `shared/`: small helpers reused by more than one skill
- `tools/`: executable scripts used by build and deploy skills
- `tests/`: focused publish-safety regression tests

## Current conventions

### Build and deploy config

The build and deploy skills currently assume a recommended project layout like this:

```text
project-root/
└─ project_ai/
   ├─ build-deploy.skill.yaml
   └─ build-deploy.secrets.local.json
```

Notes:

- `build-deploy.skill.yaml` is intended to be checked in when the team wants a reusable workflow entrypoint.
- `build-deploy.secrets.local.json` is local-only and must stay out of git.
- The scripts also support passing an explicit `--config` path.
- This repository ships a minimal starter template at `project_ai/build-deploy.skill.example.yaml`.

### Handoff modes

The handoff skills support multiple resume/write layouts, including:

- `legacy-handoff`
- `single-current`
- `hybrid-compat`

Shared handoff helpers live under `shared/handoff/`.

## Security and publishing notes

This repository is designed to avoid publishing obvious secrets, but it still assumes careful usage.

- Never commit local secrets files.
- Never commit generated build or deploy run logs.
- Review target hosts, remote paths, restart commands, and health-check commands before sharing examples.
- Password-based SSH is supported for compatibility, but key-based auth is preferred.
- Command logging in the bundled build/deploy tools masks `sshpass -p` passwords before writing logs.

## Verification

Current repository checks include:

- publish-safety tests for password masking in logged commands
- publish-safety tests to prevent RFC1918 private IP examples in public deploy docs
- Python syntax compilation checks for shipped helper scripts

Run the focused test suite with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_publish_safety -v
```

## Roadmap

Planned next steps may include:

- example configs
- broader regression coverage
- CI for publish-safety checks
- additional workflow skills for embedded display/HMI teams
