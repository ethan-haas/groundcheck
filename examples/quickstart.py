"""Runnable, no-setup, no-network quickstart.

    python examples/quickstart.py

reads the vendored `examples/input.json` and `examples/docs/`, calls
`groundcheck.verify()`, and prints the resulting report plus the exit
code the CLI would use. This mirrors what
`groundcheck examples/input.json --sources examples/docs` does on the
command line, but as a plain library call.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # allow running from a source checkout with no install

import groundcheck  # noqa: E402


def main() -> int:
    payload = json.loads((HERE / "input.json").read_text(encoding="utf-8"))
    sources = {
        p.name[:-4] if p.name.endswith(".txt") else p.name: p.read_text(encoding="utf-8")
        for p in sorted((HERE / "docs").iterdir())
    }

    report = groundcheck.verify(
        answer=payload["answer"],
        citations=payload["citations"],
        sources=sources,
    )

    print(report.to_json())
    print(f"exit_code would be: {report.exit_code}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
