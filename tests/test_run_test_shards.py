"""scripts/run_test_shards.py: parallel shards on one machine add up to one full run."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_test_shards import MAX_SHARDS, default_shards, shard_command  # noqa: E402

RUNNER = [sys.executable, str(ROOT / "scripts/run_test_shards.py")]
# One has a recorded weight (tests/shard_weights.json) and goes first, so each of two shards receives one.
MODULES = ["tests/test_dev_commands.py", "tests/test_merge_test_shards.py"]


def test_each_shard_gets_its_own_directories(tmp_path):
    command = shard_command(["tests", "-m", "not fiji"], 1, 4, tmp_path)
    assert command[1:6] == ["-m", "pytest", "tests", "-m", "not fiji"]
    assert command[6:] == ["--shard=1/4", f"--basetemp={tmp_path / 'tmp'}", f"--junitxml={tmp_path / 'junit.xml'}",
                           f"--scientific-collection={tmp_path / 'collection.json'}"]
    assert 1 <= default_shards() <= MAX_SHARDS


def test_two_shards_merge_into_the_receipt_of_one_full_run(tmp_path):
    junit, collection = tmp_path / "out/tests.xml", tmp_path / "out/collection.json"
    result = subprocess.run([*RUNNER, *MODULES, "-q", "--shards", "2", f"--junitxml={junit}",
                             f"--scientific-collection={collection}"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "shard 0/2 exit 0" in result.stdout and "shard 1/2 exit 0" in result.stdout
    receipt = json.loads(collection.read_text(encoding="utf-8"))
    assert "shard" not in receipt and receipt["exit_status"] == 0
    assert sorted(receipt["selected_modules"]) == MODULES
    assert receipt["selected"] == receipt["collected"] - receipt["deselected"] > 0
    # Two named modules are not the whole tree, which the receipt keeps saying after the merge.
    assert receipt["selection_issues"] == ["full_tests_tree_required"] and not receipt["full_collection"]
    assert junit.read_bytes().count(b"<testcase") == receipt["selected"]


def test_a_shard_without_tests_fails_the_run_and_shows_its_output():
    result = subprocess.run([*RUNNER, *MODULES, "-q", "--shards", "2", "-k", "no_such_test_anywhere"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 5
    assert "deselected" in result.stdout and "received no test" in result.stdout


def test_receipt_paths_go_together():
    result = subprocess.run([*RUNNER, "tests", "--junitxml=/tmp/x.xml"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2 and "go together" in result.stderr
