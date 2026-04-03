#!/usr/bin/env python3
"""Shared routing helpers for canonical handoff/current surfaces."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class ModeDecision:
    mode: str
    confidence: str
    reason: str


@dataclass(frozen=True)
class WriteTargets:
    primary: list[Path]
    compat: list[Path]


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    return text.replace("`", "").lower()


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_token(text: str, token: str) -> bool:
    pattern = r"(?<![a-z0-9_])" + re.escape(token) + r"(?![a-z0-9_])"
    return re.search(pattern, text) is not None


def _has_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    return any(_has_token(text, token) for token in tokens)


def _has_primary_surface(text: str) -> bool:
    return _has_any_token(text, ("state.yaml", "brief.md"))


def _has_legacy_surface(text: str) -> bool:
    return _has_any_token(text, ("current_state.yaml", "current_handoff.md"))


def _clauses(text: str) -> list[str]:
    return [clause.strip() for clause in re.split(r"(?:[。；\n]+|\.(?=\s|$))", text) if clause.strip()]


def _primary_is_negated(text: str) -> bool:
    negations = (
        "不是本项目默认恢复入口",
        "不是默认恢复入口",
        "不是默认入口",
        "不是主恢复面",
        "不是主入口",
        "not the default entrypoint",
        "not the default resume surface",
        "not the primary surface",
    )
    return any(
        _has_any_token(clause, ("state.yaml", "brief.md")) and _has_any(clause, negations)
        for clause in _clauses(text)
    )


def _legacy_is_negated(text: str) -> bool:
    negations = (
        "不是默认恢复入口",
        "不是默认入口",
        "不是主恢复面",
        "不是主入口",
        "not the default entrypoint",
        "not the default resume surface",
        "not the primary surface",
    )
    return any(
        _has_any_token(clause, ("current_state.yaml", "current_handoff.md", "current_*")) and _has_any(clause, negations)
        for clause in _clauses(text)
    )


def _mentions_primary_default(text: str) -> bool:
    if not _has_primary_surface(text) or _primary_is_negated(text):
        return False
    return _has_any(
        text,
        (
            "默认恢复入口",
            "默认入口",
            "主恢复面",
            "主入口",
            "默认恢复顺序",
            "恢复顺序",
            "canonical path",
            "canonical resume surface",
            "default entrypoint",
            "primary surface",
        ),
    )


def _mentions_legacy_default(text: str) -> bool:
    if not _has_legacy_surface(text) or _legacy_is_negated(text):
        return False
    return _has_any(
        text,
        (
            "默认恢复入口",
            "默认入口",
            "主恢复面",
            "主入口",
            "默认恢复顺序",
            "恢复顺序",
            "default entrypoint",
        ),
    )


def _mentions_hybrid(text: str) -> bool:
    compat_surface = _has_any_token(text, ("current_*", "current_state.yaml", "current_handoff.md")) or "compat" in text
    compat_generation = _has_any(
        text,
        (
            "兼容入口",
            "主入口与兼容入口同时存在",
            "按需生成",
            "允许按需生成",
            "一并刷新",
            "同步刷新",
            "refresh compat",
            "compat generation",
            "compat view is generated",
            "compatibility view is generated",
            "secondary surface",
            "after the primary surface",
            "not the primary one",
        ),
    )
    return (
        _has_any(text, ("主入口与兼容入口同时存在", "primary + compat surfaces", "hybrid-compat"))
        or (_mentions_primary_default(text) and compat_surface and compat_generation)
    )


def _classify_text(text: str, source: str) -> ModeDecision | None:
    normalized = _normalize(text)
    if not normalized.strip():
        return None

    if _mentions_hybrid(normalized):
        return ModeDecision(
            mode="hybrid-compat",
            confidence="high",
            reason=f"{source} declares primary + compat surfaces",
        )

    if _mentions_legacy_default(normalized):
        return ModeDecision(
            mode="legacy-handoff",
            confidence="high",
            reason=f"{source} prefers current_state/current_handoff",
        )

    if _mentions_primary_default(normalized):
        return ModeDecision(
            mode="single-current",
            confidence="high",
            reason=f"{source} declares project current as canonical",
        )

    return None


def detect_mode(project_root: Path) -> ModeDecision:
    agents_path = project_root / "AGENTS.md"
    rules_path = project_root / "rules" / "context-handoff.md"
    agents_text = _read_if_exists(agents_path)
    rules_text = _read_if_exists(rules_path)
    for source, text in (
        ("rules/context-handoff.md", rules_text),
        ("AGENTS.md", agents_text),
    ):
        decision = _classify_text(text, source)
        if decision is not None:
            return decision

    legacy_files_exist = all(
        (project_root / name).exists() for name in ("current_state.yaml", "current_handoff.md")
    )
    project_current_roots = (
        project_root / "codex_version" / "current",
        project_root,
    )
    project_current_files_exist = any(
        all((root / name).exists() for name in ("state.yaml", "brief.md"))
        for root in project_current_roots
    )
    compat_roots = (
        project_root / "codex_version" / "runs",
        project_root / "runs",
        project_root,
    )
    compat_files_exist = any(
        all((root / name).exists() for name in ("current_state.yaml", "current_handoff.md"))
        for root in compat_roots
    )

    if (legacy_files_exist or compat_files_exist) and project_current_files_exist:
        return ModeDecision(
            mode="legacy-handoff",
            confidence="low",
            reason="rules missing or inconclusive; conservative fallback from mixed layout",
        )

    if project_current_files_exist:
        return ModeDecision(
            mode="single-current",
            confidence="low",
            reason="rules missing or inconclusive; inferred from project current layout",
        )

    if legacy_files_exist:
        return ModeDecision(
            mode="legacy-handoff",
            confidence="low",
            reason="rules missing or inconclusive; inferred from legacy handoff files",
        )

    return ModeDecision(
        mode="legacy-handoff",
        confidence="low",
        reason="rules missing or inconclusive; conservative fallback",
    )


def plan_write_outputs(
    decision: ModeDecision,
    *,
    primary_dir: Path,
    compat_dir: Path | None = None,
    include_compat: bool = False,
) -> WriteTargets:
    if include_compat and decision.mode != "legacy-handoff" and compat_dir is None:
        raise ValueError("--compat-dir is required when --include-compat is set for non-legacy modes")

    if decision.mode == "legacy-handoff":
        return WriteTargets(
            primary=[primary_dir / "current_handoff.md", primary_dir / "current_state.yaml"],
            compat=[],
        )

    compat_paths: list[Path] = []
    if include_compat:
        compat_root = compat_dir or primary_dir
        compat_paths = [compat_root / "current_handoff.md", compat_root / "current_state.yaml"]

    return WriteTargets(
        primary=[primary_dir / "state.yaml", primary_dir / "brief.md"],
        compat=compat_paths,
    )


def plan_resume_order(decision: ModeDecision) -> list[str]:
    if decision.mode == "single-current":
        return ["state.yaml", "brief.md", "run-artifacts", "current_*"]
    if decision.mode == "hybrid-compat":
        return ["state.yaml", "brief.md", "current_*", "run-artifacts"]
    return ["current_state.yaml", "current_handoff.md", "artifacts"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect handoff mode and print canonical targets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect")
    detect_parser.add_argument("--project-root", required=True)

    resume_parser = subparsers.add_parser("plan-resume")
    resume_parser.add_argument("--project-root", required=True)

    write_parser = subparsers.add_parser("plan-write")
    write_parser.add_argument("--project-root", required=True)
    write_parser.add_argument("--primary-dir", required=True)
    write_parser.add_argument("--compat-dir")
    write_parser.add_argument("--include-compat", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    decision = detect_mode(project_root)

    print(f"mode={decision.mode}")
    print(f"confidence={decision.confidence}")
    print(f"reason={decision.reason}")

    if args.command == "plan-resume":
        print("resume_order=" + " -> ".join(plan_resume_order(decision)))
        return 0

    if args.command == "plan-write":
        try:
            targets = plan_write_outputs(
                decision,
                primary_dir=Path(args.primary_dir).expanduser().resolve(),
                compat_dir=Path(args.compat_dir).expanduser().resolve() if args.compat_dir else None,
                include_compat=args.include_compat,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        for path in targets.primary:
            print(f"primary={path}")
        for path in targets.compat:
            print(f"compat={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
