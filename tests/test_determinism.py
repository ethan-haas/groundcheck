"""Gate: determinism must hold ACROSS PROCESSES, not just within one.

Same-process repetition can't see hash-randomization effects (PYTHONHASHSEED
differs per interpreter start-up unless pinned), so this spawns three
independent `python -m` subprocesses and diffs their stdout byte-for-byte.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RUNNER = """
import sys
sys.path.insert(0, {repo_root!r})
import groundcheck

sources = {{
    "brief": "Acme Corp reported full-year revenue growth of 18% for fiscal 2024. "
              "Employee headcount increased from 320 to 401. Customer satisfaction "
              "scores averaged 4.6 out of 5. The board approved $3,400,000.",
}}
citations = [
    {{"claim_id": "c1", "text": "Revenue grew 18%.", "doc_id": "brief", "quote": "full-year revenue growth of 18%"}},
    {{"claim_id": "c2", "text": "Headcount rose to 401.", "doc_id": "brief", "quote": "increased from 320 to 401"}},
    {{"claim_id": "c3", "text": "No citation here."}},
    {{"claim_id": "c4", "text": "Wrong doc.", "doc_id": "does-not-exist", "quote": "x"}},
    {{"claim_id": "c5", "text": "Score was 9.9.", "doc_id": "brief", "quote": "scores averaged 9.9"}},
]
report = groundcheck.verify(answer="whatever", citations=citations, sources=sources)
sys.stdout.write(report.to_json())
"""


def _run_once() -> str:
    script = RUNNER.format(repo_root=str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        # deliberately vary the hash seed per subprocess so a
        # dict/set-ordering dependency, if one existed, would show up
        env={**_env_with_random_hashseed()},
    )
    assert result.returncode in (0, 1), result.stderr
    return result.stdout


def _env_with_random_hashseed():
    import os

    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)  # let each subprocess pick its own random seed
    return env


def test_three_independent_processes_produce_byte_identical_reports():
    outputs = [_run_once() for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]
    assert len(outputs[0]) > 0
    # sanity: it really did parse as the expected structure, not an empty/error output
    parsed = json.loads(outputs[0])
    assert parsed["counts"]["total"] == 5
