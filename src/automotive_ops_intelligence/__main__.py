"""Command line entry point.

python -m automotive_ops_intelligence --offline
python -m automotive_ops_intelligence --org "Legend Motors" --process "export docs"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from automotive_ops_intelligence.flow import AutomationBriefFlow, BriefState
from automotive_ops_intelligence.offline import available_fixtures
from automotive_ops_intelligence.render import render_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="automotive-ops-intelligence",
        description=(
            "Produce a ranked, costed automation opportunity brief for a business unit."
        ),
    )
    parser.add_argument(
        "--org",
        default="Legend Motors",
        help="Organisation and business unit to analyse.",
    )
    parser.add_argument(
        "--process",
        action="append",
        default=[],
        dest="processes",
        help="A candidate process to profile. Repeatable. Ignored in offline mode.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Run from validated fixtures instead of calling a model. "
            "Requires no API key and is fully deterministic."
        ),
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="LiteLLM model identifier used by the crew when not offline.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the brief to this path instead of stdout.",
    )
    parser.add_argument(
        "--list-fixtures",
        action="store_true",
        help="List available offline fixtures and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_fixtures:
        for name in available_fixtures():
            print(name)
        return 0

    if not args.offline and not args.processes:
        print(
            "Live mode needs at least one --process to profile. "
            "Use --offline to run the worked example instead.",
            file=sys.stderr,
        )
        return 2

    flow = AutomationBriefFlow()
    flow.kickoff(
        inputs=BriefState(
            scope_hint=args.org,
            process_hints=args.processes,
            model=args.model,
            offline=args.offline,
        ).model_dump()
    )

    brief = flow.state.brief
    if brief is None:
        print("Flow produced no brief.", file=sys.stderr)
        return 1

    rendered = render_brief(brief)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
