"""Run pytest as parallel shards on one machine and rebuild the receipt of one full run.

    uv run python scripts/run_test_shards.py tests -m "not fiji" [--shards N]
        [--junitxml FILE --scientific-collection FILE]

Every other argument goes to pytest unchanged. Each shard is the same command with
``--shard=I/N`` (whole test modules, tests/conftest.py) and its own temporary and data
directories. merge_test_shards.merge accepts the shards only when they cover the collection
exactly once, so scientific_review.py checks the merged receipt like a single run. N defaults to
the CPU count, at most 4; with 1, pytest runs once without sharding. A shard that receives no
test fails the run, as pytest does when nothing is selected: it is meant for the whole suite.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from merge_test_shards import merge

MAX_SHARDS = 4


def default_shards() -> int:
    return max(1, min(MAX_SHARDS, os.cpu_count() or 1))


def shard_command(pytest_args: list[str], index: int, count: int, work: Path) -> list[str]:
    return [sys.executable, "-m", "pytest", *pytest_args, f"--shard={index}/{count}",
            f"--basetemp={work / 'tmp'}", f"--junitxml={work / 'junit.xml'}",
            f"--scientific-collection={work / 'collection.json'}"]


def run_shards(pytest_args: list[str], count: int, scratch: Path) -> list[int]:
    """Start every shard at once; report each as it ends and print the output of the failed ones."""
    started, running = time.monotonic(), {}
    for index in range(count):
        work = scratch / str(index)
        (work / "data").mkdir(parents=True)
        log = (work / "log.txt").open("wb")
        env = {**os.environ, "CYTELLECT_DATA_DIR": str(work / "data")}
        running[index] = (subprocess.Popen(shard_command(pytest_args, index, count, work), env=env,
                                           stdout=log, stderr=subprocess.STDOUT), log)
    codes = [0] * count
    while running:
        time.sleep(0.5)
        for index in [index for index, (process, _) in running.items() if process.poll() is not None]:
            process, log = running.pop(index)
            log.close()
            codes[index] = process.returncode
            output = (scratch / str(index) / "log.txt").read_text(encoding="utf-8", errors="replace")
            summary = output.strip().splitlines()[-1] if output.strip() else ""
            print(f"shard {index}/{count} exit {codes[index]} after {time.monotonic() - started:.0f} s: {summary}",
                  flush=True)
            if codes[index]:
                print(output, flush=True)
            if codes[index] == 5:  # pytest: no tests collected
                print(f"shard {index}/{count} received no test: select more modules or pass fewer --shards", flush=True)
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shards", type=int, default=default_shards(), metavar="N")
    parser.add_argument("--junitxml", type=Path)
    parser.add_argument("--scientific-collection", type=Path)
    args, pytest_args = parser.parse_known_args()
    if (args.junitxml is None) != (args.scientific_collection is None):
        parser.error("--junitxml and --scientific-collection go together")
    if args.shards < 1:
        parser.error("--shards must be at least 1")
    if args.shards == 1:
        receipts = [f"--junitxml={args.junitxml}", f"--scientific-collection={args.scientific_collection}"] if args.junitxml else []
        return subprocess.run([sys.executable, "-m", "pytest", *pytest_args, *receipts]).returncode
    scratch = Path(tempfile.mkdtemp(prefix="cytellect-shards-"))
    try:
        codes = run_shards(pytest_args, args.shards, scratch)
        produced = [(scratch / str(index) / "junit.xml", scratch / str(index) / "collection.json")
                    for index in range(args.shards)]
        if args.junitxml and all(junit.is_file() and collection.is_file() for junit, collection in produced):
            junit, collection = merge([(junit.read_bytes(), json.loads(collection.read_text(encoding="utf-8")))
                                       for junit, collection in produced])
            for target, data in ((args.junitxml, junit), (args.scientific_collection, json.dumps(collection, indent=2).encode())):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        elif args.junitxml:
            print("A shard ended without its receipt; no merged receipt was written.", flush=True)
            return max(1, *codes)
        return max(codes)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
