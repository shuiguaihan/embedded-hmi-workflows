#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


CONFIG_CANDIDATES = [
    "project_ai/build-deploy.skill.yaml",
    "project_ai/build-deploy.skill.json",
]
DEFAULT_SECRETS_FILE = "project_ai/build-deploy.secrets.local.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a configured deploy action.")
    parser.add_argument("--config", help="Path to the build/deploy config file.")
    parser.add_argument("--plan", action="store_true", help="Print and save the deploy plan without executing it.")
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


def shutil_which(binary: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = Path(directory) / binary
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


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


def ssh_base(target: dict, project_root: Path, secrets: dict) -> list[str]:
    host = require_string(target, "host", "deploy.target")
    user = require_string(target, "user", "deploy.target")
    port = str(target.get("port", 22))
    auth = resolve_auth_settings(target, "deploy.target", project_root, secrets)
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
    cmd.append(f"{user}@{host}")
    return prefix + cmd


def scp_to_remote(target: dict, project_root: Path, secrets: dict, local_path: Path, remote_path: str) -> subprocess.CompletedProcess[str]:
    host = require_string(target, "host", "deploy.target")
    user = require_string(target, "user", "deploy.target")
    port = str(target.get("port", 22))
    auth = resolve_auth_settings(target, "deploy.target", project_root, secrets)
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
    cmd.extend([str(local_path), f"{user}@{host}:{remote_path}"])
    return subprocess.run(prefix + cmd, capture_output=True, text=True)


def run_and_log(command: list[str], log_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
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
        fail("No deploy config found. Expected project_ai/build-deploy.skill.yaml or pass --config.")

    config = load_config(config_path)
    project_root = get_project_root(config_path)
    logs_dir_value = config.get("logs_dir", "project_ai/build-deploy-runs")
    logs_dir = resolve_local_path(project_root, logs_dir_value)
    secrets = load_optional_secrets(config, project_root)
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S-deploy")
    run_dir = logs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    deploy = config.get("deploy")
    if not isinstance(deploy, dict):
        fail("Config is missing the deploy section.")
    target = deploy.get("target")
    if not isinstance(target, dict):
        fail("deploy.target must be an object.")
    if target.get("kind") != "ssh":
        fail("deploy.target.kind currently only supports ssh.")

    local_artifact = resolve_local_path(project_root, require_string(deploy, "local_artifact", "deploy"))
    copy_cfg = deploy.get("copy")
    if not isinstance(copy_cfg, dict):
        fail("deploy.copy must be an object.")
    remote_final_path = require_string(copy_cfg, "remote_final_path", "deploy.copy")
    remote_tmp_path = copy_cfg.get("remote_tmp_path") or f"{remote_final_path}.new"
    remote_mode = copy_cfg.get("mode")

    backup_cfg = deploy.get("backup") or {}
    if not isinstance(backup_cfg, dict):
        fail("deploy.backup must be an object.")
    backup_enabled = bool(backup_cfg.get("enabled", False))
    backup_path = backup_cfg.get("remote_backup_path") or f"{remote_final_path}.backup_{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    restart_cfg = deploy.get("restart") or {}
    if not isinstance(restart_cfg, dict):
        fail("deploy.restart must be an object.")
    restart_command = restart_cfg.get("command", "")

    health_checks = deploy.get("health_checks") or []
    if not isinstance(health_checks, list):
        fail("deploy.health_checks must be an array.")

    timeouts = deploy.get("timeouts") or {}
    if not isinstance(timeouts, dict):
        fail("deploy.timeouts must be an object.")
    startup_timeout = int(timeouts.get("startup_timeout_seconds", 30))
    poll_interval = int(timeouts.get("health_poll_interval_seconds", 2))

    plan_lines = [
        f"Config: {config_path}",
        f"Local artifact: {local_artifact}",
        f"Target: {target.get('user')}@{target.get('host')}:{target.get('port', 22)}",
        f"Remote tmp path: {remote_tmp_path}",
        f"Remote final path: {remote_final_path}",
        f"Backup enabled: {backup_enabled}",
        f"Backup path: {backup_path if backup_enabled else '(disabled)'}",
        f"Restart command: {restart_command or '(none)'}",
        f"Health checks: {', '.join(health_checks) if health_checks else '(none)'}",
    ]
    plan_path = run_dir / "deploy-plan.txt"
    write_text(plan_path, "\n".join(plan_lines) + "\n")

    summary: dict[str, object] = {
        "config_path": str(config_path),
        "project_root": str(project_root),
        "local_artifact": str(local_artifact),
        "target": f"{target.get('user')}@{target.get('host')}:{target.get('port', 22)}",
        "remote_tmp_path": remote_tmp_path,
        "remote_final_path": remote_final_path,
        "backup_enabled": backup_enabled,
        "backup_path": backup_path if backup_enabled else "",
        "restart_command": restart_command,
        "health_checks": health_checks,
        "plan_path": str(plan_path),
        "status": "planned" if args.plan else "pending",
    }

    if args.plan:
        summary_path = run_dir / "deploy-summary.json"
        write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        return

    if not local_artifact.exists():
        fail(f"Deploy artifact does not exist: {local_artifact}")

    precheck_log = run_dir / "deploy-precheck.log"
    parent_dir = str(Path(remote_final_path).parent)
    precheck_result = run_and_log(ssh_base(target, project_root, secrets) + [f"test -d {shlex.quote(parent_dir)}"], precheck_log)
    if precheck_result.returncode != 0:
        summary["status"] = "failed"
        summary["precheck_log"] = str(precheck_log)
        summary_path = run_dir / "deploy-summary.json"
        write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        raise SystemExit(1)

    copy_result = scp_to_remote(target, project_root, secrets, local_artifact, remote_tmp_path)
    copy_log = run_dir / "deploy-copy.log"
    copy_log_content = [
        f"Local artifact: {local_artifact}",
        f"Remote tmp path: {remote_tmp_path}",
        f"Return code: {copy_result.returncode}",
        "",
        "STDOUT:",
        copy_result.stdout,
        "",
        "STDERR:",
        copy_result.stderr,
    ]
    write_text(copy_log, "\n".join(copy_log_content))
    if copy_result.returncode != 0:
        summary["status"] = "failed"
        summary["precheck_log"] = str(precheck_log)
        summary["copy_log"] = str(copy_log)
        summary_path = run_dir / "deploy-summary.json"
        write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        raise SystemExit(1)

    remote_steps: list[str] = []
    if backup_enabled:
        remote_steps.append(
            f"if [ -f {shlex.quote(remote_final_path)} ]; then cp -pf {shlex.quote(remote_final_path)} {shlex.quote(backup_path)}; fi"
        )
    remote_steps.append(f"mv {shlex.quote(remote_tmp_path)} {shlex.quote(remote_final_path)}")
    if remote_mode:
        remote_steps.append(f"chmod {shlex.quote(str(remote_mode))} {shlex.quote(remote_final_path)}")
    if restart_command:
        remote_steps.append(restart_command)
    execute_log = run_dir / "deploy-execute.log"
    execute_result = run_and_log(ssh_base(target, project_root, secrets) + ["; ".join(remote_steps)], execute_log)
    if execute_result.returncode != 0:
        summary["status"] = "failed"
        summary["precheck_log"] = str(precheck_log)
        summary["copy_log"] = str(copy_log)
        summary["execute_log"] = str(execute_log)
        summary_path = run_dir / "deploy-summary.json"
        write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
        print(json.dumps(summary, indent=2, ensure_ascii=True))
        raise SystemExit(1)

    health_results: list[dict[str, object]] = []
    health_log = run_dir / "deploy-health.log"
    if health_checks:
        deadline = time.time() + max(startup_timeout, 1)
        for check in health_checks:
            last_result: subprocess.CompletedProcess[str] | None = None
            while time.time() <= deadline:
                last_result = subprocess.run(ssh_base(target, project_root, secrets) + [check], capture_output=True, text=True)
                if last_result.returncode == 0:
                    break
                time.sleep(max(poll_interval, 1))
            health_results.append(
                {
                    "check": check,
                    "returncode": -1 if last_result is None else last_result.returncode,
                    "stdout": "" if last_result is None else last_result.stdout,
                    "stderr": "" if last_result is None else last_result.stderr,
                }
            )
    health_log_lines = []
    for item in health_results:
        health_log_lines.extend(
            [
                f"Check: {item['check']}",
                f"Return code: {item['returncode']}",
                "STDOUT:",
                str(item["stdout"]),
                "STDERR:",
                str(item["stderr"]),
                "",
            ]
        )
    write_text(health_log, "\n".join(health_log_lines) if health_log_lines else "No health checks configured.\n")

    health_passed = all(item["returncode"] == 0 for item in health_results) if health_results else True
    summary["status"] = "completed" if health_passed else "failed"
    summary["precheck_log"] = str(precheck_log)
    summary["copy_log"] = str(copy_log)
    summary["execute_log"] = str(execute_log)
    summary["health_log"] = str(health_log)
    summary["health_passed"] = health_passed

    summary_path = run_dir / "deploy-summary.json"
    write_text(summary_path, json.dumps(summary, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    raise SystemExit(0 if summary["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
