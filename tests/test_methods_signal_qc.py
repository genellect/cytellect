from cytellect_analysis.exports import methods_text


def test_methods_record_optional_warning_only_signal_qc():
    recipe = {"id": "ncl-native-2d", "native_signal_qc_minimum_ratio": 2.5}
    text = methods_text({"recipe": recipe}, {}, {
        "cells": [{"signal_qc_protocol_version": "1.0.0"}],
    })
    assert "1.4826 times the background ROI median absolute deviation" in text
    assert "optional weak-signal threshold is 2.5" in text
    assert "never automatically change" in text
    assert "without epsilon" in text


def test_methods_do_not_backfill_qc_for_old_results_or_legacy():
    for recipe, cells in [
        ({"id": "ncl-native-2d"}, [{}]),
        ({"id": "ncl-legacy-rgb"}, [{"signal_qc_protocol_version": "1.0.0"}]),
    ]:
        assert "Native signal QC protocol" not in methods_text(
            {"recipe": recipe}, {}, {"cells": cells})
