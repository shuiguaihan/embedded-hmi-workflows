# Deploy Action Config Schema

The recommended config path is `project_ai/build-deploy.skill.yaml`.

Use JSON-compatible YAML. In practice, write the file as JSON text with a `.yaml` suffix so the bundled scripts can parse it with the Python standard library.

## Minimal Shape

```json
{
  "version": 1,
  "logs_dir": "project_ai/build-deploy-runs",
  "deploy": {
    "local_artifact": "relative/or/absolute/path/to/local/file",
    "target": {
      "kind": "ssh",
      "host": "192.0.2.10",
      "port": 22,
      "user": "root",
      "auth_mode": "key",
      "key_path": "/path/to/private_key"
    },
    "copy": {
      "remote_tmp_path": "/remote/file.new",
      "remote_final_path": "/remote/file"
    },
    "backup": {
      "enabled": true
    },
    "restart": {
      "command": "service app restart"
    },
    "health_checks": [
      "pgrep app"
    ]
  }
}
```

## Supported Fields

### Top Level

- `version`: required integer, currently `1`
- `logs_dir`: optional string, default `project_ai/build-deploy-runs`
- `secrets_file`: optional string, default `project_ai/build-deploy.secrets.local.json`

### `deploy`

- `local_artifact`: required string
- `target`: required object
- `copy`: required object
- `backup`: optional object
- `restart`: optional object
- `health_checks`: optional array of shell commands
- `timeouts`: optional object

### `deploy.target`

- `kind`: required string, currently only `ssh`
- `host`: required string
- `port`: optional integer, default `22`
- `user`: required string
- `auth_mode`: optional string, supported values: `key`, `password`
- `key_path`: optional string, used when `auth_mode=key`
- `password_env`: optional string, used when `auth_mode=password`
- `secret_ref`: optional string; looks up auth details in the local secrets file

### `deploy.copy`

- `remote_tmp_path`: optional string; defaults to `remote_final_path + ".new"`
- `remote_final_path`: required string
- `mode`: optional string; for example `755`

### `deploy.backup`

- `enabled`: optional boolean, default `false`
- `remote_backup_path`: optional string; defaults to `remote_final_path + ".backup_<timestamp>"`

### `deploy.restart`

- `command`: optional string

### `deploy.timeouts`

- `startup_timeout_seconds`: optional integer, default `30`
- `health_poll_interval_seconds`: optional integer, default `2`

## Notes

- Relative local paths resolve from the project root.
- Password auth requires `sshpass` to be installed locally.
- Health checks run after the replace-and-restart step completes.
- When both `secret_ref` and `password_env` are present, the secret file is checked first and environment fallback remains available.

## Local Secrets File

Recommended local-only path:

```json
{
  "version": 1,
  "deploy_board": {
    "auth_mode": "password",
    "password": "example"
  }
}
```

Use `deploy.target.secret_ref` to reference one entry from this file. The secrets file should stay uncommitted.
