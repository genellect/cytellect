"""The recorded tour split into one part per scene (GitHub refuses files above 100 MiB; docs/showcase.md)."""
import json

import pytest


def entry(scene, path):
    return {"scene": scene, "method": "GET", "path": path, "body": None, "status": 200, "headers": [], "file": None}


def test_parts_read_back_as_the_same_tour_in_the_same_order(tmp_path):
    from cytellect_showcase.journal_files import part_names, read_journal, write_journal

    tour = {"version": 1, "entries": [entry("ox:tour", "/a"), entry("ox:walk", "/b"), entry("cis:tour", "/c"),
                                      entry("plk1:tour", "/d"), entry("ox:kept", "/e")]}
    written = write_journal(tmp_path, tour)
    # A scene's walks kept from an earlier tour follow the recorded ones: their own part keeps the order.
    assert written == ["journal.json", "journal-ox.json", "journal-cis.json", "journal-plk1.json", "journal-ox-2.json"]
    assert json.loads((tmp_path / "journal.json").read_text()) == {"version": 2, "parts": written[1:], "counts": [2, 1, 1, 1],
                                                                  "workspaces": [[], [], [], []], "revisions": [[], [], [], []]}
    assert read_journal(tmp_path) == tour
    assert part_names(tmp_path) == written


def test_a_single_file_journal_and_a_single_scene_demo(tmp_path):
    from cytellect_showcase.journal_files import part_names, read_journal, write_journal

    single = {"version": 1, "entries": [entry("tour", "/a")]}
    (tmp_path / "journal.json").write_text(json.dumps(single))
    assert read_journal(tmp_path) == single and part_names(tmp_path) == ["journal.json"]
    # A demo of one scene names no scene in its walks.
    assert write_journal(tmp_path, single) == ["journal.json", "journal-demo.json"]
    assert read_journal(tmp_path) == single


def test_an_index_naming_other_files_or_a_part_over_the_limit_is_refused(tmp_path, monkeypatch):
    import cytellect_showcase.journal_files as files

    (tmp_path / "journal.json").write_text(json.dumps({"version": 2, "parts": ["../seed.zip"]}))
    with pytest.raises(ValueError, match="showcase_journal_index_invalid"):
        files.read_journal(tmp_path)
    monkeypatch.setattr(files, "PART_LIMIT_BYTES", 100)
    with pytest.raises(SystemExit, match="above 100"):
        files.write_journal(tmp_path, {"version": 1, "entries": [entry("ox:tour", "/a" * 100)]})


def test_two_parts_never_share_a_file(tmp_path):
    from cytellect_showcase.journal_files import write_journal

    # A later run of scene "ox" and the first part of a scene named "ox-2" would both be journal-ox-2.json.
    tour = {"version": 1, "entries": [entry("ox:tour", "/a"), entry("ox-2:tour", "/b"), entry("ox:kept", "/c")]}
    with pytest.raises(SystemExit, match="journal-ox-2.json would be written twice"):
        write_journal(tmp_path, tour)


def test_the_index_names_each_part_s_workspaces_only_when_a_change_can_match_one_scene_only(tmp_path):
    """The demo reads the open workspace's scene first and answers a change naming that workspace from it alone
    (transport.ts): exact only when no other scene's part names the workspace, and no path names one by "*"."""
    from cytellect_showcase.journal_files import scene_index, write_journal

    tour = {"version": 1, "entries": [entry("ox:tour", "/v1/workspaces/w1/runs"), entry("ox:tour", "/v1/session"),
                                      entry("cis:tour", "/v1/workspaces/w2/jobs"), entry("ox:kept", "/v1/workspaces/w1/jobs")]}
    write_journal(tmp_path, tour)
    index = json.loads((tmp_path / "journal.json").read_text())
    assert index["counts"] == [2, 1, 1] and index["workspaces"] == [["w1"], ["w2"], ["w1"]]
    shared = [("ox", [entry("ox:a", "/v1/workspaces/w1/runs")]), ("cis", [entry("cis:a", "/v1/workspaces/w1/jobs")])]
    assert scene_index(shared) == {}
    assert scene_index([("ox", [entry("ox:a", "/v1/workspaces/*/runs")])]) == {}
    # Analysis versions likewise: each listed in the parts of its scene, or none listed when one could match elsewhere.
    own = [("ox", [entry("ox:a", "/v1/revisions/r1/region-edits")]), ("cis", [entry("cis:a", "/v1/revisions/r2/descriptive")])]
    assert scene_index(own)["revisions"] == [["r1"], ["r2"]]
    assert "revisions" not in scene_index([*own, ("plk", [entry("plk:a", "/v1/revisions/r1/review")])])
    assert "revisions" not in scene_index([("ox", [entry("ox:a", "/v1/revisions/*/descriptive")])])
