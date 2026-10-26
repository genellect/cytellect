"""Prevent unclassified nuclear compartments from disappearing from inference."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction

# Unresolved-nucleoli policy 1.0.0 (requirements Q-05, genellect/cytellect#109): a nucleus whose
# nucleolus could not be established stays in the ledger as missing instead of being removed, once
# the researcher has confirmed the per-field list of reasons. Without the policy every parent must be
# a candidate, as before. Only detector outcomes that say "no established nucleolus" can be kept as
# missing; a failure, an unclassified mask or a parent awaiting review of its saved candidates stops.
MISSING_POLICY = "unresolved-as-missing/1.0.0"
MISSING_STATES = frozenset({"no_candidate", "indeterminate"})
EMPTY_NUCLEOPLASM = "empty_after_subtraction"
# Within one run, groups whose missing fractions differ by at least this many percentage points are
# flagged. Fixed before it was applied to any data; no warning is not evidence of absent bias.
MISSING_RATE_WARNING_POINTS = 10


def comparable_region_recipe(recipe: dict) -> dict:
    """Compare detector settings for cohorts whose per-field parents are separately pinned."""
    value = deepcopy(recipe)
    if value.get("source") == "fiji_nuclear_compartment":
        value.pop("nuclear_revision_id", None)
        value.pop("nucleolar_revision_id", None)
    return value


def _selected(config: dict, report: dict, field_ids) -> list[str]:
    excluded = {item["field_id"] for item in report.get("exclusions", []) if item.get("region_id") is None}
    return sorted(set(field_ids if field_ids is not None else config.get("field_ids", [])) - excluded)


def _engine(provenance: dict, fid: str) -> dict:
    return provenance.get("fields", {}).get(fid, {}).get("detector", {}).get("engine", {})


def compartment_ledger(config: dict, report: dict, provenance: dict, field_ids=None) -> dict[str, dict]:
    """Per selected field: every parent nucleus, those with an established compartment, the missing
    ones by reason and the explicitly excluded ones (nucleoplasm regions are parent nuclei).

    The counts are mutually exclusive: nuclei = resolved + missing; excluded is part of resolved.
    Raises when a parent's state cannot be kept as missing under the policy, or the recorded state
    table is inconsistent (missing parents not all listed)."""
    nucleoplasm = config.get("recipe", {}).get("compartment") == "nucleoplasm"
    excluded_regions = {(item["field_id"], item["region_id"]) for item in report.get("exclusions", [])
                        if item.get("region_id") is not None}
    ledger = {}
    for fid in _selected(config, report, field_ids):
        engine = _engine(provenance, fid)
        states, count, empty = engine.get("nucleolar_states"), engine.get("missing_parent_count"), engine.get("nucleoplasm_missing_reasons") or {}
        if not isinstance(states, dict) or type(count) is not int or not isinstance(empty, dict):
            raise ValueError("compartment_ledger_invalid")
        parents = {int(parent): state for parent, state in states.items()}
        missing = {parent: state for parent, state in parents.items() if state != "candidate"}
        if count != len(missing) or any(reason != EMPTY_NUCLEOPLASM or parents.get(int(parent)) != "candidate"
                                         for parent, reason in empty.items()):
            raise ValueError("compartment_ledger_invalid")
        if any(state not in MISSING_STATES for state in missing.values()):
            raise ValueError("compartment_state_not_missing")
        if nucleoplasm:
            missing.update({int(parent): reason for parent, reason in empty.items()})
        ledger[fid] = {"nuclei": len(parents), "resolved": len(parents) - len(missing),
                       "missing": dict(sorted(Counter(missing.values()).items())),
                       "excluded": sum(1 for parent in parents if parent not in missing and (fid, parent) in excluded_regions)
                       if nucleoplasm else 0}
    return ledger


def assert_complete_compartments(config: dict, report: dict, provenance: dict, field_ids=None, policy=None) -> None:
    recipe = config.get("recipe", {})
    if recipe.get("source") != "fiji_nuclear_compartment":
        return
    if policy is not None:
        if policy != MISSING_POLICY:
            raise ValueError("compartment_missing_policy_unknown")
        compartment_ledger(config, report, provenance, field_ids)
        return
    for fid in _selected(config, report, field_ids):
        engine = _engine(provenance, fid)
        states = engine.get("nucleolar_states")
        count = engine.get("missing_parent_count")
        if (not isinstance(states, dict) or type(count) is not int or count != 0
                or any(state != "candidate" for state in states.values())
                or (recipe.get("compartment") == "nucleoplasm" and engine.get("nucleoplasm_missing_reasons"))):
            raise ValueError("unresolved_nuclear_compartments")


def confirmed_policy(config: dict) -> str | None:
    """The unresolved-nucleoli policy the researcher confirmed when reviewing this revision."""
    record = (config.get("review_record") or {}).get("compartment_missing")
    if record is None:
        return None
    if not isinstance(record, dict) or record.get("policy") != MISSING_POLICY or not isinstance(record.get("fields"), dict):
        raise ValueError("compartment_missing_policy_unknown")
    return MISSING_POLICY


def compartment_missing_summary(config: dict, conditions=None) -> dict | None:
    """The confirmed ledger by condition and experimental unit, shown beside the result sentence
    (Q-05), with the within-run warning. None when the revision was reviewed without the policy."""
    if confirmed_policy(config) is None:
        return None
    fields = config["review_record"]["compartment_missing"]["fields"]
    snapshot = config.get("field_snapshot", {})
    rows: dict[tuple, dict] = {}
    for fid, entry in sorted(fields.items()):
        metadata = (snapshot.get(fid) or {}).get("metadata") or {}
        condition, unit = metadata.get("condition"), metadata.get("experimental_unit")
        if conditions is not None and condition not in conditions:
            continue
        row = rows.setdefault((condition or "", unit or ""), {
            "condition": condition, "experimental_unit": unit, "run": metadata.get("pair"),
            "fields": 0, "nuclei": 0, "resolved": 0, "missing": 0, "excluded": 0, "reasons": {}})
        row["fields"] += 1
        row["nuclei"] += entry["nuclei"]
        row["resolved"] += entry["resolved"]
        row["excluded"] += entry["excluded"]
        for reason, count in entry["missing"].items():
            row["missing"] += count
            row["reasons"][reason] = row["reasons"].get(reason, 0) + count
    ordered = [{**row, "reasons": dict(sorted(row["reasons"].items()))} for _, row in sorted(rows.items())]
    return {"policy": MISSING_POLICY, "warning_points": MISSING_RATE_WARNING_POINTS, "rows": ordered,
            "warnings": missing_rate_warnings(ordered)}


def missing_rate_warnings(rows: list[dict]) -> list[dict]:
    """Runs in which the groups' missing fractions (missing / all nuclei, exclusions not removed from
    the denominator) differ by at least the warning points. Rows without a run form one run; groups
    with no nucleus have no fraction. Exact fractions decide the boundary."""
    runs: dict = {}
    for row in rows:
        total = runs.setdefault(row["run"], {}).setdefault(row["condition"], [0, 0])
        total[0] += row["missing"]
        total[1] += row["nuclei"]
    warnings = []
    for run, groups in sorted(runs.items(), key=lambda item: (item[0] is None, item[0] or "")):
        fractions = {condition: Fraction(missing, nuclei) for condition, (missing, nuclei) in groups.items() if nuclei}
        if len(fractions) < 2:
            continue
        low, high = min(fractions.values()), max(fractions.values())
        if (high - low) * 100 >= MISSING_RATE_WARNING_POINTS:
            warnings.append({"run": run, "difference_points": round(float((high - low) * 100), 1),
                             "fractions": {condition: round(float(value), 4) for condition, value in sorted(fractions.items())}})
    return warnings


def assert_reviewed_compartments(config: dict, report: dict, provenance: dict, field_ids=None) -> None:
    """Statistics on a reviewed revision (``config`` carries its review record): complete compartments,
    or the confirmed policy with the same per-field ledger as at review."""
    if config.get("recipe", {}).get("source") != "fiji_nuclear_compartment":
        return
    policy = confirmed_policy(config)
    assert_complete_compartments(config, report, provenance, field_ids, policy=policy)
    if policy is not None:
        recorded = config["review_record"]["compartment_missing"]["fields"]
        current = compartment_ledger(config, report, provenance, field_ids)
        if any(recorded.get(fid) != entry for fid, entry in current.items()):
            raise ValueError("compartment_missing_ledger_changed")


def with_compartment_missing(result: dict, config: dict, conditions=None) -> dict:
    """Adds the confirmed ledger and its warning to a saved result (descriptive and comparison alike)."""
    summary = compartment_missing_summary(config, conditions)
    if summary is not None:
        result["compartment_missing"] = summary
        if summary["warnings"] and "compartment_missing_rate_differs" not in result["warnings"]:
            result["warnings"].append("compartment_missing_rate_differs")
    return result


def compartment_missing_tables(result):
    """The confirmed unresolved-nucleoli ledger by condition and unit (Q-05), as exported beside the result."""
    summary = result.get("compartment_missing")
    if not summary:
        return {}
    return {"compartment-missing": [
        {"condition": row["condition"], "experimental_unit": row["experimental_unit"], "run": row["run"],
         "fields": row["fields"], "nuclei": row["nuclei"], "resolved": row["resolved"], "missing": row["missing"],
         "excluded": row["excluded"], "missing_fraction": row["missing"] / row["nuclei"] if row["nuclei"] else None,
         "reasons": ";".join(f"{reason}={count}" for reason, count in row["reasons"].items()), "policy": summary["policy"]}
        for row in summary["rows"]]}


def compartment_missing_lines(result):
    """Methods sentences for a result reviewed under the unresolved-nucleoli policy."""
    summary = result.get("compartment_missing")
    if not summary:
        return []
    lines = [f"Unresolved nucleoli ({summary['policy']}): nuclei whose nucleolus was not established "
             "(no candidate, indeterminate, or an empty nucleoplasm) were kept in the ledger as missing, not removed; "
             "values describe the nuclei with an established nucleolus. The researcher confirmed the per-field list of "
             "reasons before the analysis. Missing fractions use all nuclei as the denominator."]
    for row in summary["rows"]:
        lines.append(f"{row['condition']}, {row['experimental_unit']}: {row['missing']} of {row['nuclei']} nuclei missing"
                     + (f" ({row['missing'] / row['nuclei']:.1%})" if row["nuclei"] else "")
                     + f"; {row['excluded']} explicitly excluded.")
    for warning in summary["warnings"]:
        lines.append(f"Within run {warning['run'] or '(all units)'}, the groups' missing fractions differ by "
                     f"{warning['difference_points']} percentage points (warning at {summary['warning_points']}); "
                     "selection related to the treatment may remain.")
    return lines
