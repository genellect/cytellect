"""Derived updates retain the origin of the published workspace and recordings."""
from cytellect_showcase.build import generation_provenance


def test_examples_keep_the_original_capture_commit():
    previous = {"generated_from_commit": "capture", "derived_updates": {"figures": "drawing"}}
    assert generation_provenance(previous, {"reseed", "examples"}, "examples") == {
        "generated_from_commit": "capture", "derived_updates": {"figures": "drawing", "examples": "examples"}}


def test_a_new_recording_sets_a_new_capture_commit():
    assert generation_provenance({"generated_from_commit": "old"}, {"reseed", "publish", "snapshot", "journal"}, "new") == {
        "generated_from_commit": "new"}
