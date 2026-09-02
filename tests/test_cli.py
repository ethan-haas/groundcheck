import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(input_path, sources_dir, extra_args=()):
    cmd = [sys.executable, "-m", "groundcheck.cli", str(input_path), "--sources", str(sources_dir), *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))


def test_vendored_quickstart_input_exits_nonzero_and_has_unresolvable(tmp_path):
    result = _run_cli(REPO_ROOT / "examples" / "input.json", REPO_ROOT / "examples" / "docs")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["counts"]["unresolvable"] >= 1


def test_all_supported_input_exits_zero(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc1.txt").write_text("The sky over the harbor was clear on Tuesday.", encoding="utf-8")

    input_path = tmp_path / "in.json"
    input_path.write_text(
        json.dumps(
            {
                "answer": "The sky was clear.",
                "citations": [
                    {"claim_id": "c1", "text": "clear sky", "doc_id": "doc1", "quote": "sky over the harbor was clear"}
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _run_cli(input_path, docs_dir)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["counts"]["unresolvable"] == 0
    assert payload["counts"]["supported"] == 1


def test_one_unresolvable_claim_forces_nonzero_exit(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc1.txt").write_text("Some source text.", encoding="utf-8")

    input_path = tmp_path / "in.json"
    input_path.write_text(
        json.dumps({"answer": "x", "citations": [{"claim_id": "c1", "text": "x", "doc_id": "no-such-doc"}]}),
        encoding="utf-8",
    )

    result = _run_cli(input_path, docs_dir)
    assert result.returncode == 1


def test_missing_input_file_is_usage_error_exit_2(tmp_path):
    result = _run_cli(tmp_path / "does-not-exist.json", tmp_path)
    assert result.returncode == 2


def test_bad_json_input_is_usage_error_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    result = _run_cli(bad, tmp_path / "docs")
    assert result.returncode == 2


def test_out_flag_writes_same_report_to_file(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "doc1.txt").write_text("Alpha beta gamma.", encoding="utf-8")
    input_path = tmp_path / "in.json"
    input_path.write_text(
        json.dumps({"answer": "x", "citations": [{"claim_id": "c1", "text": "x", "doc_id": "doc1", "quote": "Alpha beta"}]}),
        encoding="utf-8",
    )
    out_path = tmp_path / "report.out.json"
    result = _run_cli(input_path, docs_dir, extra_args=["--out", str(out_path)])
    assert result.returncode == 0
    assert out_path.read_text(encoding="utf-8") == result.stdout
