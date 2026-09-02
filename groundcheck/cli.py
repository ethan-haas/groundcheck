"""CLI entry point: ``groundcheck INPUT.json --sources DOCS_DIR``.

INPUT.json is a JSON object:

    {"answer": "...", "citations": [ {...}, {...}, ... ]}

(see groundcheck.core module docstring for the citation record shape).

DOCS_DIR is a directory of source documents, one file per document.
Each file's doc_id is its filename with any single trailing ``.txt``
stripped (so both ``brief.txt`` and ``brief`` resolve to doc_id
``brief``); files are read as UTF-8 text. Sub-directories are not
walked (a flat, unambiguous doc_id -> path mapping is easier to reason
about than a recursive one, and this library is deliberately small).

The full report is written as JSON to stdout (and, if ``--out`` is
given, also to that file) with sorted keys, so the output is
byte-identical run over run, process over process.

Exit code: 0 if no claim is ``unresolvable``, 1 if at least one is
(this is `VerificationReport.exit_code`; see its docstring for why
`span-mismatch` / `uncited` alone do not force a non-zero exit).
Exit code 2 is used for usage/input errors (bad JSON, missing dir),
distinguishing "your input was malformed" from "your citations have a
defect" -- both are failures, but a CI pipeline usually wants to
handle them differently.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import GroundcheckError, verify


def _load_sources(sources_dir: Path) -> dict:
    if not sources_dir.is_dir():
        raise GroundcheckError(f"--sources path {str(sources_dir)!r} is not a directory")
    sources = {}
    for path in sorted(sources_dir.iterdir()):
        if not path.is_file():
            continue
        doc_id = path.name[:-4] if path.name.endswith(".txt") else path.name
        sources[doc_id] = path.read_text(encoding="utf-8")
    return sources


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="groundcheck",
        description="Verify that every cited claim in an answer is actually backed by its source.",
    )
    parser.add_argument("input", type=str, help="path to an input JSON file with 'answer' and 'citations'")
    parser.add_argument("--sources", type=str, required=True, help="directory of source documents, one file per doc_id")
    parser.add_argument("--out", type=str, default=None, help="also write the report JSON to this path")
    return parser


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"groundcheck: input file not found: {args.input}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"groundcheck: input file is not valid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict) or "citations" not in payload:
        print("groundcheck: input JSON must be an object with an 'answer' and a 'citations' list", file=sys.stderr)
        return 2

    try:
        sources = _load_sources(Path(args.sources))
    except GroundcheckError as exc:
        print(f"groundcheck: {exc}", file=sys.stderr)
        return 2

    try:
        report = verify(
            answer=payload.get("answer", ""),
            citations=payload["citations"],
            sources=sources,
        )
    except GroundcheckError as exc:
        print(f"groundcheck: {exc}", file=sys.stderr)
        return 2

    output = report.to_json()
    sys.stdout.write(output)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")

    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
