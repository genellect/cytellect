from copy import deepcopy

import pytest
from cytellect_analysis.compartment_review import assert_complete_compartments, comparable_region_recipe


def fixture():
    config = {
        "recipe": {
            "source": "fiji_nuclear_compartment",
            "compartment": "nucleoli",
            "nuclear_revision_id": "a",
        },
        "field_ids": ["f"],
    }
    report = {"exclusions": []}
    provenance = {
        "fields": {
            "f": {"detector": {"engine": {"nucleolar_states": {"1": "candidate"}, "missing_parent_count": 0}}}
        }
    }
    return config, report, provenance


def test_complete_compartments_are_usable_but_missing_parents_are_not():
    config, report, provenance = fixture()
    assert_complete_compartments(config, report, provenance)
    provenance["fields"]["f"]["detector"]["engine"]["nucleolar_states"]["2"] = "no_candidate"
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, provenance)
    report["exclusions"] = [{"field_id": "f", "region_id": None, "reason": "reviewed"}]
    assert_complete_compartments(config, report, provenance)


def test_missing_provenance_fails_closed_only_for_compartment_recipe():
    config, report, _ = fixture()
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, {})
    config["recipe"]["source"] = "stardist_nuclear"
    assert_complete_compartments(config, report, {})


def test_empty_nucleoplasm_is_not_a_valid_observation():
    config, report, provenance = fixture()
    config["recipe"]["compartment"] = "nucleoplasm"
    provenance["fields"]["f"]["detector"]["engine"]["nucleoplasm_missing_reasons"] = {
        "1": "empty_after_subtraction"
    }
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, provenance)


def test_cohort_identity_ignores_only_parent_revision_not_parameters():
    config, _, _ = fixture()
    recipe = config["recipe"]
    other = deepcopy(recipe)
    other["nuclear_revision_id"] = "b"
    assert comparable_region_recipe(recipe) == comparable_region_recipe(other)
    other["defining_channel_id"] = "different"
    assert comparable_region_recipe(recipe) != comparable_region_recipe(other)
    assert recipe["nuclear_revision_id"] == "a"


# Unresolved-nucleoli policy 1.0.0 (requirements Q-05, genellect/cytellect#109).
from cytellect_analysis.compartment_review import (  # noqa: E402
    MISSING_POLICY,
    assert_reviewed_compartments,
    compartment_ledger,
    compartment_missing_summary,
    missing_rate_warnings,
    with_compartment_missing,
)


def engine(states, empty=None):
    missing = sum(state != "candidate" for state in states.values())
    return {"detector": {"engine": {"nucleolar_states": {str(k): v for k, v in states.items()},
                                    "missing_parent_count": missing, "nucleoplasm_missing_reasons": empty or {}}}}


def test_policy_keeps_parents_without_an_established_nucleolus_as_missing():
    config, report, provenance = fixture()
    provenance["fields"]["f"] = engine({1: "candidate", 2: "no_candidate", 3: "indeterminate"})
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, provenance)
    assert_complete_compartments(config, report, provenance, policy=MISSING_POLICY)
    assert compartment_ledger(config, report, provenance) == {
        "f": {"nuclei": 3, "resolved": 1, "missing": {"indeterminate": 1, "no_candidate": 1}, "excluded": 0}}


@pytest.mark.parametrize("state", ["processing_failed", "unclassified", "review_required", "not_measured_recipe",
                                   "legacy_candidate", "none_after_edit"])
def test_policy_still_stops_on_failures_and_states_it_cannot_keep_as_missing(state):
    config, report, provenance = fixture()
    provenance["fields"]["f"] = engine({1: "candidate", 2: state})
    with pytest.raises(ValueError, match="compartment_state_not_missing"):
        assert_complete_compartments(config, report, provenance, policy=MISSING_POLICY)


def test_policy_refuses_an_inconsistent_state_table_or_an_unknown_policy():
    config, report, provenance = fixture()
    provenance["fields"]["f"] = engine({1: "candidate", 2: "no_candidate"})
    provenance["fields"]["f"]["detector"]["engine"]["missing_parent_count"] = 0
    with pytest.raises(ValueError, match="compartment_ledger_invalid"):
        assert_complete_compartments(config, report, provenance, policy=MISSING_POLICY)
    with pytest.raises(ValueError, match="compartment_ledger_invalid"):
        assert_complete_compartments(config, report, {}, policy=MISSING_POLICY)
    with pytest.raises(ValueError, match="compartment_missing_policy_unknown"):
        assert_complete_compartments(config, report, provenance, policy="keep-everything")


def test_nucleoplasm_counts_empty_regions_as_missing_and_excluded_parents_in_the_denominator():
    config, report, provenance = fixture()
    config["recipe"]["compartment"] = "nucleoplasm"
    provenance["fields"]["f"] = engine({1: "candidate", 2: "candidate", 3: "candidate", 4: "no_candidate"},
                                       {"2": "empty_after_subtraction"})
    report["exclusions"] = [{"field_id": "f", "region_id": 3, "reason": "out of focus"}]
    assert compartment_ledger(config, report, provenance) == {
        "f": {"nuclei": 4, "resolved": 2, "missing": {"empty_after_subtraction": 1, "no_candidate": 1}, "excluded": 1}}
    # An empty nucleoplasm of a parent that is not a candidate is not a recorded outcome.
    provenance["fields"]["f"]["detector"]["engine"]["nucleoplasm_missing_reasons"] = {"4": "empty_after_subtraction"}
    with pytest.raises(ValueError, match="compartment_ledger_invalid"):
        compartment_ledger(config, report, provenance)


def reviewed(fields, metadata):
    return {"field_snapshot": {fid: {"metadata": value} for fid, value in metadata.items()},
            "review_record": {"confirmed_at": 1.0, "compartment_missing": {"policy": MISSING_POLICY, "fields": fields}}}


def entry(nuclei, missing, excluded=0, reason="no_candidate"):
    return {"nuclei": nuclei, "resolved": nuclei - missing, "missing": {reason: missing} if missing else {}, "excluded": excluded}


def meta(condition, run):
    return {"condition": condition, "experimental_unit": f"{run} · {condition}", "pair": run}


def test_summary_counts_each_group_and_run_with_all_nuclei_as_the_denominator():
    config = reviewed({"a1": entry(20, 2, excluded=5), "a2": entry(10, 1), "b1": entry(30, 3, reason="indeterminate")},
                      {"a1": meta("Untreated", "Rep1"), "a2": meta("Untreated", "Rep1"), "b1": meta("ActD", "Rep1")})
    summary = compartment_missing_summary(config)
    assert [(row["condition"], row["fields"], row["nuclei"], row["resolved"], row["missing"], row["excluded"])
            for row in summary["rows"]] == [("ActD", 1, 30, 27, 3, 0), ("Untreated", 2, 30, 27, 3, 5)]
    assert summary["rows"][0]["reasons"] == {"indeterminate": 3}
    # Exclusions do not shrink the denominator: 3 / 30 for both groups, no warning.
    assert summary["warnings"] == []
    assert compartment_missing_summary(config, ["ActD"])["rows"][0]["condition"] == "ActD"
    assert compartment_missing_summary({"review_record": {"confirmed_at": 1.0}}) is None


def rows(*values):
    return [{"condition": condition, "experimental_unit": f"{run}·{condition}", "run": run, "missing": missing,
             "nuclei": nuclei} for condition, run, missing, nuclei in values]


def test_warning_starts_at_exactly_ten_points_within_a_run():
    exactly = missing_rate_warnings(rows(("A", "R1", 10, 100), ("B", "R1", 20, 100)))
    assert exactly == [{"run": "R1", "difference_points": 10.0, "fractions": {"A": 0.1, "B": 0.2}}]
    assert missing_rate_warnings(rows(("A", "R1", 10, 100), ("B", "R1", 1999, 10000))) == []


def test_runs_that_cancel_out_are_each_warned_and_empty_groups_have_no_fraction():
    # Overall both groups miss 20 %, but each run differs by 20 points.
    warned = missing_rate_warnings(rows(("A", "R1", 10, 100), ("B", "R1", 30, 100), ("A", "R2", 30, 100), ("B", "R2", 10, 100)))
    assert [(item["run"], item["difference_points"]) for item in warned] == [("R1", 20.0), ("R2", 20.0)]
    assert missing_rate_warnings(rows(("A", "R1", 0, 0), ("B", "R1", 9, 10))) == []
    # Without runs (no pair layout), the groups are compared as one run.
    assert missing_rate_warnings(rows(("A", None, 0, 10), ("B", None, 5, 10)))[0]["run"] is None


def test_reviewed_ledger_must_still_match_and_results_carry_it():
    config, report, provenance = fixture()
    provenance["fields"]["f"] = engine({1: "candidate", 2: "no_candidate"})
    config.update(reviewed(compartment_ledger(config, report, provenance), {"f": meta("A", "R1")}))
    assert_reviewed_compartments(config, report, provenance)
    provenance["fields"]["f"] = engine({1: "candidate", 2: "indeterminate"})
    with pytest.raises(ValueError, match="compartment_missing_ledger_changed"):
        assert_reviewed_compartments(config, report, provenance)
    result = with_compartment_missing({"warnings": []}, config)
    assert result["compartment_missing"]["rows"][0]["missing"] == 1 and result["warnings"] == []
    # A revision reviewed without the policy still needs complete compartments.
    del config["review_record"]["compartment_missing"]
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_reviewed_compartments(config, report, provenance)
