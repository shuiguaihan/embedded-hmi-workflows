#!/usr/bin/env python3
"""Warn when handoff files become too large for efficient resume."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


HANDOFF_LINE_LIMIT = 60
STATE_LINE_LIMIT = 45
BRIEF_LINE_LIMIT = 40
FILE_COUNT_LIMIT = 5
COMMAND_LIMIT = 4
LIST_LIMIT = 4


def count_section_items(lines: list[str], heading: str) -> int:
    count = 0
    active = False
    for line in lines:
        if line.startswith("## "):
            active = line.strip() == heading
            continue
        if active and line.lstrip().startswith("- "):
            count += 1
    return count


def count_command_lines(lines: list[str]) -> int:
    inside = False
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            inside = not inside
            continue
        if inside and stripped and not stripped.startswith("#"):
            count += 1
    return count


def warn(message: str) -> None:
    print(f"WARN: {message}")


def check_handoff_markdown(path: Path) -> int:
    exit_code = 0
    lines = path.read_text(encoding="utf-8").splitlines()

    if len(lines) > HANDOFF_LINE_LIMIT:
        warn(f"{path.name} has {len(lines)} lines; target is <= {HANDOFF_LINE_LIMIT}")
        exit_code = 2

    checks = [
        ("## 已完成事项", LIST_LIMIT),
        ("## 未完成事项", LIST_LIMIT),
        ("## 当前阻塞点", LIST_LIMIT),
        ("## 已验证事实", LIST_LIMIT),
        ("## 必须重查", LIST_LIMIT),
        ("## 关键文件", FILE_COUNT_LIMIT),
    ]
    for heading, limit in checks:
        count = count_section_items(lines, heading)
        if count > limit:
            warn(f"{path.name} {heading} has {count} items; target is <= {limit}")
            exit_code = 2

    command_count = count_command_lines(lines)
    if command_count > COMMAND_LIMIT:
        warn(f"{path.name} 关键命令 has {command_count} executable lines; target is <= {COMMAND_LIMIT}")
        exit_code = 2

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the active handoff/current surfaces against lean size budgets."
    )
    parser.add_argument(
        "--mode",
        choices=["legacy-handoff", "single-current", "hybrid-compat"],
        required=True,
        help="Canonical handoff mode for the target project.",
    )
    parser.add_argument(
        "--compat-dir",
        help="Directory containing separate compatibility current_* outputs.",
    )
    parser.add_argument(
        "target_dir",
        help="Directory containing the primary resume surface for the selected mode.",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir).expanduser().resolve()
    compat_dir = Path(args.compat_dir).expanduser().resolve() if args.compat_dir else None

    if args.mode == "legacy-handoff":
        handoff_path = target_dir / "current_handoff.md"
        state_path = target_dir / "current_state.yaml"
        if not handoff_path.exists() or not state_path.exists():
            print("Error: current_handoff.md or current_state.yaml is missing", file=sys.stderr)
            return 1
    else:
        state_path = target_dir / "state.yaml"
        brief_path = target_dir / "brief.md"
        if not state_path.exists() or not brief_path.exists():
            print("Error: state.yaml or brief.md is missing", file=sys.stderr)
            return 1

    exit_code = 0
    state_lines = state_path.read_text(encoding="utf-8").splitlines()

    if len(state_lines) > STATE_LINE_LIMIT:
        warn(f"{state_path.name} has {len(state_lines)} lines; target is <= {STATE_LINE_LIMIT}")
        exit_code = 2

    if args.mode == "legacy-handoff":
        exit_code = max(exit_code, check_handoff_markdown(handoff_path))
    else:
        brief_lines = brief_path.read_text(encoding="utf-8").splitlines()
        if len(brief_lines) > BRIEF_LINE_LIMIT:
            warn(f"brief.md has {len(brief_lines)} lines; target is <= {BRIEF_LINE_LIMIT}")
            exit_code = 2

        stray_compat = [target_dir / "current_handoff.md", target_dir / "current_state.yaml"]
        if compat_dir is None and any(path.exists() for path in stray_compat):
            warn("compat current_* files are present in the primary directory; pass --compat-dir or move them out")
            exit_code = 2

        if compat_dir:
            compat_handoff = compat_dir / "current_handoff.md"
            compat_state = compat_dir / "current_state.yaml"
            if not compat_handoff.exists() or not compat_state.exists():
                print("Error: compatibility current_* outputs are missing", file=sys.stderr)
                return 1
            exit_code = max(exit_code, check_handoff_markdown(compat_handoff))
            compat_state_lines = compat_state.read_text(encoding="utf-8").splitlines()
            if len(compat_state_lines) > STATE_LINE_LIMIT:
                warn(f"{compat_state.name} has {len(compat_state_lines)} lines; target is <= {STATE_LINE_LIMIT}")
                exit_code = 2

    if exit_code == 0:
        print("OK: handoff files are within the lean budget")
    else:
        print("HINT: trim duplicated detail and move stable facts to long-lived memory")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
