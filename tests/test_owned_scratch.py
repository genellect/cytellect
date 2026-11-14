"""Filesystem ownership tests; byte fixtures are not microscopy or native DLLs."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cytellect_analysis import engine_diagnostics as diagnostics
from cytellect_analysis import temporary_storage as storage
from cytellect_analysis.temporary_storage import claimed_scratch, reap_owned_temporaries, remove_scratch


def test_live_scratch_is_preserved_and_dead_process_creation_is_recovered(tmp_path):
    with claimed_scratch(tmp_path, "owned-") as live:
        (live / "unit.txt").write_text("owned")
        assert reap_owned_temporaries(tmp_path)["recovered"] == 0
        assert live.is_dir()
        remove_scratch(live)
    script = ("import sys,time;from pathlib import Path;"
              "from cytellect_analysis.temporary_storage import claimed_scratch;"
              "ctx=claimed_scratch(Path(sys.argv[1]),'owned-');ctx.__enter__();"
              "print('ready',flush=True);time.sleep(60)")
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], stdout=subprocess.PIPE,
                               text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        assert process.stdout.readline().strip() == "ready"
    finally:
        process.kill()
        process.wait(timeout=5)
        process.stdout.close()
    assert reap_owned_temporaries(tmp_path) == {"recovered": 1, "deferred": 0}
    assert list(tmp_path.iterdir()) == []


def test_unknown_or_redirected_trees_are_never_adopted(tmp_path):
    unknown = tmp_path / "j-00000000"
    unknown.mkdir()
    (unknown / "preserve.txt").write_text("unowned")
    identity = "1" * 32
    journal = tmp_path / f".cytellect-scratch-{identity}.json"
    journal.write_text(json.dumps({"schema": "cytellect-owned-scratch/1", "id": identity, "name": "../data"}))
    assert reap_owned_temporaries(tmp_path)["recovered"] == 0
    assert (unknown / "preserve.txt").read_text() == "unowned"


def test_deferred_capacity_applies_across_jobs_and_recovers_before_next_creation(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    with claimed_scratch(runs / "previous-job", "j-") as previous:
        (previous / "unit.bin").write_bytes(b"x" * 32)
    remove = storage.remove_scratch

    def locked(path):
        if path == previous:
            raise PermissionError("unit cleanup lock")
        remove(path)

    monkeypatch.setattr(storage, "remove_scratch", locked)
    with storage.scratch_ownership_scope(runs, max_deferred_bytes=32):
        with pytest.raises(storage.ScratchCapacityExceeded, match="^fiji_temporary_cleanup_pending$"):
            with claimed_scratch(runs / "next-job", "j-"):
                pytest.fail("new extraction must stop before creating another tree")
        assert list((runs / "next-job").iterdir()) == []
        monkeypatch.setattr(storage, "remove_scratch", remove)
        with claimed_scratch(runs / "next-job", "j-") as current:
            assert not previous.exists()
            remove_scratch(current)
    assert list(runs.rglob(".cytellect-scratch-*.json")) == []


def test_capacity_does_not_count_live_owners_and_rejects_escaping_scope(tmp_path):
    with storage.scratch_ownership_scope(tmp_path, max_deferred_bytes=1):
        with claimed_scratch(tmp_path, "j-") as live:
            (live / "unit.bin").write_bytes(b"large live owner")
            with claimed_scratch(tmp_path, "j-") as other:
                assert live.exists()
                remove_scratch(other)
            remove_scratch(live)
        with storage.scratch_ownership_scope(tmp_path / "scope"):
            for outside in (tmp_path / "outside", tmp_path / "scope" / ".." / "outside"):
                with pytest.raises(ValueError, match="scratch_scope_invalid"):
                    with claimed_scratch(outside, "j-"):
                        pytest.fail("scope boundary must be enforced")
            assert not (tmp_path / "outside").exists()


def test_worker_cleanup_recovers_only_journaled_scratch_after_restart(tmp_path):
    from cytellect_api.db import Store
    from cytellect_worker.main import cleanup

    store = Store(tmp_path)
    runs = store.safe_path("runs")
    with claimed_scratch(runs, "j-") as scratch:
        (scratch / "unit.bin").write_bytes(b"owned temporary fixture")
    preserved = runs / "unregistered-result.txt"
    preserved.write_text("preserve")
    cleanup(store)
    assert not scratch.exists() and preserved.read_text() == "preserve"


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows sharing violation")
def test_success_survives_locked_scratch_and_next_execution_recovers_it(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(diagnostics.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(diagnostics.time, "sleep", lambda value: clock.__setitem__(0, clock[0] + value))
    events = []
    handle = None
    try:
        with diagnostics.installation_execution_policy(120, 300, events.append):
            with diagnostics.owned_temporary_directory(prefix="owned-", directory=tmp_path) as scratch:
                member = scratch / "unit-locked-file.bin"
                member.write_bytes(b"unit filesystem bytes")
                handle = member.open("rb")
        assert events[-1]["state"] == "deferred" and member.exists()
        assert clock[0] == 10
    finally:
        if handle is not None:
            handle.close()
    with diagnostics.owned_temporary_directory(prefix="owned-", directory=tmp_path):
        assert not member.exists()
    assert list(tmp_path.iterdir()) == []


def test_redirection_above_the_scope_is_allowed_but_never_inside_it(tmp_path):
    """A profile folder moved with a link (above the scope) is not the scope's concern; a link inside it is refused."""
    real = tmp_path / "real-home"
    (real / "Cytellect" / "setup-cache").mkdir(parents=True)
    linked = tmp_path / "linked-home"
    linked.symlink_to(real, target_is_directory=True)
    scope = linked / "Cytellect" / "setup-cache"
    with storage.scratch_ownership_scope(scope):
        with claimed_scratch(scope / "attempt", "owned-") as owned:
            (owned / "unit.txt").write_text("owned")
            remove_scratch(owned)
        assert not owned.exists()
    with pytest.raises(ValueError, match="scratch_path_redirected"):
        with claimed_scratch(scope / "attempt", "owned-"):
            pass  # Outside any scope every ancestor is still checked.
    (real / "Cytellect" / "setup-cache" / "inner").symlink_to(tmp_path, target_is_directory=True)
    with storage.scratch_ownership_scope(scope):
        with pytest.raises(ValueError, match="scratch_path_redirected"):
            with claimed_scratch(scope / "inner", "owned-"):
                pass


def test_creation_waits_for_a_recovery_pass_that_holds_the_new_journal(tmp_path, monkeypatch):
    """Recovery can lock the still-empty journal for an instant; the creator waits instead of failing."""
    acquire, refused = storage._acquire, []

    def contended(handle):
        if len(refused) < 3:
            refused.append(handle.name)
            raise BlockingIOError("unit: recovery holds the journal")
        acquire(handle)

    monkeypatch.setattr(storage, "_acquire", contended)
    with claimed_scratch(tmp_path, "owned-") as owned:
        assert owned.is_dir() and len(refused) == 3
        remove_scratch(owned)
    assert list(tmp_path.iterdir()) == []


def test_creation_gives_up_after_the_bounded_wait_and_leaves_nothing(tmp_path, monkeypatch):
    def held(handle):
        raise BlockingIOError("unit: never released")

    monkeypatch.setattr(storage, "_acquire", held)
    monkeypatch.setattr(storage, "CREATION_LOCK_WAIT_SECONDS", 0.05)
    with pytest.raises(BlockingIOError):
        with claimed_scratch(tmp_path, "owned-"):
            pytest.fail("no scratch without its lock")
    assert list(tmp_path.iterdir()) == []


def test_creation_survives_concurrent_recovery_of_the_same_scope(tmp_path):
    """Real locks: another thread recovers the scope continuously while scratch trees are claimed."""
    import threading

    stop, errors = threading.Event(), []

    def recover():
        while not stop.is_set():
            try:
                reap_owned_temporaries(tmp_path, recursive=True)
            except Exception as error:  # noqa: BLE001 - the test reports any failure of the recovery pass
                errors.append(error)

    workers = [threading.Thread(target=recover) for _ in range(2)]
    for worker in workers:
        worker.start()
    try:
        with storage.scratch_ownership_scope(tmp_path):
            for _ in range(300):
                with claimed_scratch(tmp_path / "job", "j-") as owned:
                    remove_scratch(owned)
    finally:
        stop.set()
        for worker in workers:
            worker.join(timeout=10)
    assert errors == []
    assert list(tmp_path.rglob(".cytellect-scratch-*.json")) == []


def test_creation_walks_the_scope_once(tmp_path, monkeypatch):
    """Recovery and the deferred-capacity measurement share one walk of the scope."""
    runs = tmp_path / "runs"
    (runs / "job" / "results").mkdir(parents=True)
    walked = []
    walk = storage.os.walk

    def counted(top, *args, **kwargs):
        walked.append(top)
        return walk(top, *args, **kwargs)

    monkeypatch.setattr(storage.os, "walk", counted)
    with storage.scratch_ownership_scope(runs):
        with claimed_scratch(runs / "job", "j-") as owned:
            creation = [top for top in walked if Path(top) == runs.resolve()]
            remove_scratch(owned)
    assert len(creation) == 1
