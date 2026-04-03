#!/usr/bin/env python3
"""Render minimal handoff skeleton files for a task directory."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

from handoff_mode import ModeDecision, plan_write_outputs


def build_handoff_markdown(args: argparse.Namespace, target_dir: Path) -> str:
    project_root = args.project_root or "[pending]"
    return f"""# 当前交接

## 当前目标
- {args.current_goal or '[pending]'}

## 已完成事项
- [pending]

## 未完成事项
- [pending]

## 当前阻塞点
- [pending]

## 已验证事实
- [pending]

## 未验证假设
- [pending]

## 必须重查
- [pending]

## 关键文件
- {project_root}
- {target_dir / 'current_state.yaml'}

## 关键命令
```bash
# [pending]
```

## 下一步建议动作
- [pending]
"""


def build_brief_markdown(args: argparse.Namespace, target_dir: Path) -> str:
    project_root = args.project_root or "[pending]"
    goal = args.current_goal or "[pending]"
    return (
        f"# Brief\n\n"
        f"- project_root: `{project_root}`\n"
        f"- handoff_dir: `{target_dir}`\n"
        f"- current_goal: {goal}\n"
        f"- next_action: [pending]\n"
    )


def build_state_yaml(args: argparse.Namespace, target_dir: Path) -> str:
    project_root = args.project_root or "[pending]"
    stage = args.stage or "[pending]"
    task_id = args.task_id or "[pending]"
    current_goal = (args.current_goal or "[pending]").replace('"', '\\"')
    owner = (args.owner or "codex").replace('"', '\\"')
    return f"""project_root: "{project_root}"
owner: "{owner}"
handoff_generated_at: "{date.today().isoformat()}"
task_id: "{task_id}"
stage: "{stage}"
current_goal: "{current_goal}"
handoff_dir: "{target_dir}"
environment_entry: {{}}
must_recheck:
  - "[pending]"
confirmed_facts:
  - "[pending]"
unverified_assumptions:
  - "[pending]"
next_priority_actions:
  - "[pending]"
residual_risks:
  - "[pending]"
"""


def write_file(path: Path, content: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; use --overwrite to replace it")
    path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create mode-aware handoff/current skeletons.",
    )
    parser.add_argument(
        "--mode",
        choices=["legacy-handoff", "single-current", "hybrid-compat"],
        required=True,
        help="Canonical handoff mode for the target project.",
    )
    parser.add_argument("--target-dir", required=True, help="Directory for handoff files.")
    parser.add_argument("--compat-dir", help="Directory for compatibility current_* outputs.")
    parser.add_argument(
        "--include-compat",
        action="store_true",
        help="Also render compatibility current_* views when mode supports it.",
    )
    parser.add_argument("--project-root", help="Absolute project root recorded in the files.")
    parser.add_argument("--task-id", help="Task, run, or issue identifier.")
    parser.add_argument("--stage", help="Current task stage.")
    parser.add_argument("--current-goal", help="Short description of the current goal.")
    parser.add_argument("--owner", default="codex", help="Owner recorded in current_state.yaml.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_dir = Path(args.target_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    compat_dir = Path(args.compat_dir).expanduser().resolve() if args.compat_dir else None

    if args.include_compat and args.mode != "legacy-handoff" and compat_dir is None:
        print("Error: --compat-dir is required when --include-compat is set for non-legacy modes", file=sys.stderr)
        return 2

    targets = plan_write_outputs(
        ModeDecision(args.mode, "explicit", "CLI override"),
        primary_dir=target_dir,
        compat_dir=compat_dir,
        include_compat=args.include_compat,
    )

    try:
        written_paths: list[Path] = []
        for path in targets.primary:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name == "state.yaml":
                write_file(path, build_state_yaml(args, path.parent), args.overwrite)
            elif path.name == "brief.md":
                write_file(path, build_brief_markdown(args, path.parent), args.overwrite)
            elif path.name.endswith(".md"):
                write_file(path, build_handoff_markdown(args, path.parent), args.overwrite)
            else:
                write_file(path, build_state_yaml(args, path.parent), args.overwrite)
            written_paths.append(path)

        for path in targets.compat:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name.endswith(".md"):
                write_file(path, build_handoff_markdown(args, path.parent), args.overwrite)
            else:
                write_file(path, build_state_yaml(args, path.parent), args.overwrite)
            written_paths.append(path)
    except FileExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for path in written_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
