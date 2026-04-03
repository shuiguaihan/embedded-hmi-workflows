# Build Action Config Schema

The recommended config path is `project_ai/build-deploy.skill.yaml`.

Use JSON-compatible YAML. In practice, write the file as JSON text with a `.yaml` suffix so the bundled scripts can parse it with the Python standard library.

## Minimal Shape

```json
{
  "version": 1,
  "logs_dir": "project_ai/build-deploy-runs",
  "build": {
    "working_dir": "relative/or/absolute/path",
    "command": "make -j4",
    "artifact_path": "relative/or/absolute/path/to/output",
    "env": {
      "KEY": "VALUE"
    },
    "host": {
      "kind": "local"
    }
  }
}
```

## Supported Fields

### Top Level

- `version`: required integer, currently `1`
- `logs_dir`: optional string, default `project_ai/build-deploy-runs`
- `secrets_file`: optional string, default `project_ai/build-deploy.secrets.local.json`

### `build`

- `working_dir`: required string
- `command`: required string
- `artifact_path`: required string
- `env`: optional object of string pairs
- `fetch_artifact_to`: optional string; when `host.kind=ssh`, copy the built artifact back to this local path
- `host`: optional object

### `build.host`

- `kind`: required when `host` is present, supported values: `local`, `ssh`
- `host`: required for `ssh`
- `port`: optional integer, default `22`
- `user`: required for `ssh`
- `auth_mode`: optional string, supported values: `key`, `password`
- `key_path`: optional string, used when `auth_mode=key`
- `password_env`: optional string, used when `auth_mode=password`
- `secret_ref`: optional string; looks up auth details in the local secrets file
- `ssh_workdir`: optional string; overrides `working_dir` on the remote host

## Local Secrets File

Recommended local-only path:

```json
{
  "version": 1,
  "build_vm": {
    "auth_mode": "password",
    "password": "example"
  }
}
```

Use `build.host.secret_ref` to reference one entry from this file. The secrets file should stay uncommitted.

## Notes

- Relative local paths resolve from the project root.
- For the recommended layout, project root is the parent directory of `project_ai/`.
- Relative remote artifact paths resolve from `ssh_workdir` when present, otherwise from `working_dir`.
- Password auth requires `sshpass` to be installed locally.
- When both `secret_ref` and `password_env` are present, the secret file is checked first and environment fallback remains available.
