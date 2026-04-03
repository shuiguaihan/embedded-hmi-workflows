#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path


CONFIG_CANDIDATES = [
    "project_ai/build-deploy.skill.yaml",
    "project_ai/build-deploy.skill.json",
]
DEFAULT_SECRETS_FILE = "project_ai/build-deploy.secrets.local.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a configured build action.")
    parser.add_argument("--config", help="Path to the build/deploy config file.")
    parser.add_argument("--plan", action="store_true", help="Print and save the build plan without executing it.")
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def discover_config(start_dir: Path) -> Path | None:
    current = start_dir.resolve()
    for base in [current, *current.parents]:
        for candidate in CONFIG_CANDIDATES:
            path = base / candidate
            if path.exists():
                return path
    return None


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Config {path} is not valid JSON-compatible YAML: {exc}")


def require_string(mapping: dict, key: str, scope: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"Missing required string field {scope}.{key}")
    return value


def get_project_root(config_path: Path) -> Path:
    if config_path.parent.name == "project_ai":
        return config_path.parent.parent
    return config_path.parent


def resolve_local_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def resolve_remote_path(base_dir: str, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return value
    return str(Path(base_dir) / path)


def shell_command(command: str) -> list[str]:
    return ["/bin/bash", "-lc", command]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def format_command_for_log(command: list[str]) -> str:
    redacted: list[str] = []
    expects_password = False
    uses_sshpass = bool(command) and Path(command[0]).name == "sshpass"
    for part in command:
        if expects_password:
            redacted.append("***")
            expects_password = False
            continue
        redacted.append(part)
        if uses_sshpass and part == "-p":
            expects_password = True
    return " ".join(shlex.quote(part) for part in redacted)


def load_optional_secrets(config: dict, project_root: Path) -> dict:
    secrets_value = config.get("secrets_file", DEFAULT_SECRETS_FILE)
    if secrets_value is None:
        return {}
    if not isinstance(secrets_value, str) or not secrets_value.strip():
        fail("secrets_file must be a string when provided.")
    secrets_path = resolve_local_path(project_root, secrets_value)
    if not secrets_path.exists():
        return {}
    secrets = load_config(secrets_path)
    if not isinstance(secrets, dict):
        fail(f"Secrets file {secrets_path} must decode to an object.")
    return secrets


def resolve_auth_settings(mapping: dict, scope: str, project_root: Path, secrets: dict) -> dict:
    secret_entry: dict = {}
    secret_ref = mapping.get("secret_ref")
    if secret_ref is not None:
        if not isinstance(secret_ref, str) or not secret_ref.strip():
            fail(f"{scope}.secret_ref must be a non-empty string.")
        secret_value = secrets.get(secret_ref)
        if not isinstance(secret_value, dict):
            fail(f"Secret reference {secret_ref} for {scope} was not found in the secrets file.")
        secret_entry = secret_value

    auth_mode = secret_entry.get("auth_mode", mapping.get("auth_mode", "key"))
    if auth_mode not in {"key", "password"}:
        fail(f"{scope}.auth_mode must be key or password.")

    key_path_value = secret_entry.get("key_path") or mapping.get("key_path")
    key_path = ""
    if key_path_value is not None:
        if not isinstance(key_path_value, str) or not key_path_value.strip():
            fail(f"{scope}.key_path must be a non-empty string when provided.")
        key_path = str(resolve_local_path(project_root, key_path_value))

    password = secret_entry.get("password")
    if password is not None and (not isinstance(password, str) or not password):
        fail(f"{scope} password in secrets must be a non-empty string.")

    password_env = secret_entry.get("password_env") or mapping.get("password_env")
    if password_env is not None and (not isinstance(password_env, str) or not password_env.strip()):
        fail(f"{scope}.password_env must be a non-empty string when provided.")

    if auth_mode == "password" and not password:
        if password_env:
            password = os.environ.get(password_env)
            if not password:
                fail(f"Environment variable {password_env} is required for password auth.")
        elif secret_ref:
            fail(f"Secret reference {secret_ref} for {scope} is missing a password.")
        else:
            fail(f"{scope} password auth requires password_env or secret_ref.")

    return {
        "auth_mode": auth_mode,
        "key_path": key_path,
        "password": password or "",
    }


def ssh_prefix(host: dict, project_root: Path, secrets: dict) -> list[str]:
    target_host = require_string(host, "host", "build.host")
    user = require_string(host, "user", "build.host")
    port = str(host.get("port", 22))
    auth = resolve_auth_settings(host, "build.host", project_root, secrets)
    auth_mode = auth["auth_mode"]
    prefix: list[str] = []
    if auth_mode == "password":
        sshpass = shutil_which("sshpass")
        if not sshpass:
            fail("Password auth requires sshpass in PATH.")
        prefix.extend([sshpass, "-p", auth["password"]])
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-p", port]
    key_path = auth["key_path"]
    if auth_mode == "key" and key_path:
        cmd.extend(["-i", key_path])
    cmd.append(f"{user}@{target_host}")
    return prefix + cmd


def scp_from_remote(host: dict, project_root: Path, secrets: dict, remote_path: str, local_path: Path) -> subprocess.CompletedProcess[str]:
    target_host = require_string(host, "host", "build.host")
    user = require_string(host, "user", "build.host")
    port = str(host.get("port", 22))
    auth = resolve_auth_settings(host, "build.host", project_root, secrets)
    auth_mode = auth["auth_mode"]
    prefix: list[str] = []
    if auth_mode == "password":
        sshpass = shutil_which("sshpass")
        if not sshpass:
            fail("Password auth requires sshpass in PATH.")
        prefix.extend([sshpass, "-p", auth["password"]])
    cmd = ["scp", "-P", port, "-o", "StrictHostKeyChecking=no"]
    key_path = auth["key_path"]
    if auth_mode == "key" and key_path:
        cmd.extend(["-i", key_path])
    cmd.extend([f"{user}@{target_host}:{remote_path}", str(local_path)])
    return subprocess.run(prefix + cmd, capture_output=True, text=True)


def shutil_which(binary: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def run_and_log(command: list[str], log_path: Path, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    log = [
        f"Command: {format_command_for_log(command)}",
        f"Return code: {result.returncode}",
        "",
        "STDOUT:",
        result.stdout,
        "",
        "STDERR:",
        result.stderr,
    ]
    write_text(log_path, "\n".join(log))
    return result


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve() if args.config else discover_config(Path.cwd())
    if config_path is None:
        fail("No build config found. Expected project_ai/build-deploy.skill.yaml or pass --config.")

    config = load_config(config_path)
    project_root = get_project_root(config_path)
    logs_dir_value = config.get("logs_dir", "project_ai/build-deploy-runs")
    logs_dir = resolve_local_path(project_root, logs_dir_value)
    secrets = load_optional_secrets(config, project_root)
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S-build")
    run_dir = logs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    build = config.get("build")
    if not isinstance(build, dict):
        fail("Config is missing the build section.")

    working_dir_value = require_string(build, "working_dir", "build")
    command = require_string(build, "command", "build")
    artifact_value = require_string(build, "artifact_path", "build")
    env_overrides = build.get("env", {})
    if env_overrides is None:
        env_overrides = {}
    if not isinstance(env_overrides, dict):
        fail("build.env must be an object.")

    host = build.get("host", {"kind": "local"})
    if not isinstance(host, dict):
        fail("build.host must be an object.")
    host_kind = host.get("kind", "local")
    if host_kind not in {"local", "ssh"}:
        fail("build.host.kind must be local or ssh.")

    plan_lines = [
        f"Config: {config_path}",
        f"Host kind: {host_kind}",
        f"Working directory: {working_dir_value}",
        f"Command: {command}",
        f"Artifact path: {artifact_value}",
    ]
    plan_path = run_dir / "build-plan.txt"
    write_text(plan_path, "\n".join(plan_lines) + "\n")

    summary: dict[str, object] = {
        "config_path": str(config_path),
        "project_root": str(project_root),
        "host_kind": host_kind,
        "working_dir": working_dir_value,
        "command": command,
        "artifact_path": artifact_value,
        "plan_path": str(plan_path),
        "status": "planned" if args.plan else "pending",
    }

    if args.plan:
        summary_path = run_dir / "build-summary.json"
        write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        return

    command_log = run_dir / "build-command.log"
    verify_log = run_dir / "build-artifact-check.log"
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in env_overrides.items()})

    fetched_artifact = ""
    if host_kind == "local":
        working_dir = resolve_local_path(project_root, working_dir_value)
        result = run_and_log(shell_command(command), command_log, cwd=working_dir, env=env)
        artifact_path = resolve_local_path(project_root, artifact_value)
        exists = artifact_path.exists()
        write_text(verify_log, f"Checked local artifact: {artifact_path}\nExists: {exists}\n")
        summary["artifact_path"] = str(artifact_path)
    else:
        remote_workdir = host.get("ssh_workdir") or working_dir_value
        exports = " ".join(f"export {key}={shlex.quote(str(value))};" for key, value in env_overrides.items())
        remote_command = f"mkdir -p {shlex.quote(remote_workdir)}; cd {shlex.quote(remote_workdir)}; {exports} {command}".strip()
        result = run_and_log(ssh_prefix(host, project_root, secrets) + [remote_command], command_log)
        remote_artifact = resolve_remote_path(str(remote_workdir), artifact_value)
        verify_result = run_and_log(ssh_prefix(host, project_root, secrets) + [f"test -e {shlex.quote(remote_artifact)}"], verify_log)
        exists = verify_result.returncode == 0
        summary["artifact_path"] = remote_artifact
        fetch_to = build.get("fetch_artifact_to")
        if exists and isinstance(fetch_to, str) and fetch_to.strip():
            local_copy = resolve_local_path(project_root, fetch_to)
            local_copy.parent.mkdir(parents=True, exist_ok=True)
            copy_result = scp_from_remote(host, project_root, secrets, remote_artifact, local_copy)
            copy_log = run_dir / "build-fetch.log"
            copy_log_content = [
                f"Remote artifact: {remote_artifact}",
                f"Local copy: {local_copy}",
                f"Return code: {copy_result.returncode}",
                "",
                "STDOUT:",
                copy_result.stdout,
                "",
                "STDERR:",
                copy_result.stderr,
            ]
            write_text(copy_log, "\n".join(copy_log_content))
            if copy_result.returncode == 0:
                fetched_artifact = str(local_copy)

    summary["status"] = "completed" if result.returncode == 0 and exists else "failed"
    summary["command_log"] = str(command_log)
    summary["artifact_check_log"] = str(verify_log)
    summary["artifact_verified"] = exists
    summary["fetched_artifact"] = fetched_artifact
    summary["returncode"] = result.returncode

    summary_path = run_dir / "build-summary.json"
    write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    raise SystemExit(0 if summary["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
