"""Generate enum-only cross-language parity cases, never experimental data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cytellect_analysis.planning import evaluate_plan
from pydantic import ValidationError

DESTINATION = Path(__file__).resolve().parents[1] / "fixtures" / "planning" / "decisions-v2.json"
CATALOG = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "lib" / "planning-catalog.json"


def payload(**answers):
    return {"format": "cytellect-analysis-plan", "version": "2.0.0", "answers": {
        "measurement": "mean", "region": "custom", "definition": "manual", "signal": "other",
        "input": "grayscale-2d", **answers,
    }}


def cases():
    specifications = [
        ("unknown", {"version": "2.0.0", "answers": {}}),
        ("manual-area-no-marker", payload(measurement="area", signal="unknown", nuclear_stain="no", comparison="descriptive")),
        ("imported-area", payload(measurement="area", definition="imported", signal="unknown")),
        ("manual-other-mean", payload()),
        ("imported-other-integrated", payload(measurement="integrated", definition="imported")),
        ("nuclear-other-mean", payload(region="nucleus", definition="nuclear-stain", nuclear_stain="yes")),
        ("nuclear-area", payload(measurement="area", region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="unknown")),
        ("nuclear-gfp-two-paths", payload(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp")),
        ("gfp-negative-control", payload(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp", gating="negative-control")),
        ("manual-gating-unsupported", payload(gating="exploratory")),
        ("ncl-nucleus", payload(region="nucleus", definition="ncl-enrichment", nuclear_stain="yes", signal="ncl")),
        ("ncl-nucleolus", payload(region="nucleolus", definition="ncl-enrichment", nuclear_stain="yes", signal="ncl")),
        ("ncl-nucleoplasm-integrated", payload(region="nucleoplasm", measurement="integrated", definition="ncl-enrichment", nuclear_stain="yes", signal="ncl")),
        ("ncl-ratio-gfp-gate", payload(region="nucleolus", measurement="ncl-ratio", definition="ncl-enrichment", nuclear_stain="yes", signal="ncl", gating="exploratory")),
        ("ratio-other-rejected", payload(region="nucleolus", measurement="ncl-ratio", definition="ncl-enrichment", nuclear_stain="yes")),
        ("nuclear-model-not-nucleolus", payload(region="nucleolus", definition="nuclear-stain", nuclear_stain="yes")),
        ("rgb-no-recipe", payload(input="rgb")),
        ("zt-no-recipe", payload(input="zt")),
        ("no-stain-no-auto", payload(region="nucleus", definition="nuclear-stain", nuclear_stain="no")),
        ("paired-unknown-allocation", payload(comparison="paired", allocation="fields")),
        ("independent-intent-only", payload(comparison="independent", allocation="biological", background="yes", acquisition="matched")),
        ("paired-intent-only", payload(comparison="paired", allocation="biological", background="yes", acquisition="matched")),
        ("legacy-unadopted", {"format": "cytellect-analysis-plan", "version": "1.0.1",
                              "status": "planning-only-not-adopted", "answers": {"region": "nucleus", "signal": "gfp"}}),
        ("untrusted-guidance", {**payload(), "guidance": {"recipe": "arbitrary"}}),
    ]
    result = []
    for identifier, source in specifications:
        try:
            row = {"id": identifier, "input": source, "decision": evaluate_plan(source).model_dump(mode="json")}
        except ValidationError as exc:
            error = "planning_legacy_requires_review" if any(
                "planning_legacy_requires_review" in item["msg"] for item in exc.errors()
            ) else "planning_invalid_input"
            row = {"id": identifier, "input": source, "error": error}
        result.append(row)
    return {"format": "cytellect-planning-parity", "version": "2.0.0",
            "scope": "Enumerated planning examples; no images, experiment labels or biological validation.",
            "cases": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = cases()
    catalog = {"version": "2.0.0", "references": [], "findings": {}, "candidates": {}}
    for row in data["cases"]:
        if "decision" not in row:
            continue
        decision = row["decision"]
        catalog["references"] = decision["references"]
        for finding in decision["questions"] + decision["decisions"] + decision["limits"]:
            previous = catalog["findings"].setdefault(finding["id"], finding)
            if previous != finding:
                raise ValueError("planning_finding_id_must_have_one_definition")
        for candidate in decision["candidates"]:
            static = {key: candidate[key] for key in ("id", "label", "workflow", "recipe_id", "recipe_version", "source", "selection_source")}
            previous = catalog["candidates"].setdefault(candidate["id"], static)
            if previous != static:
                raise ValueError("planning_candidate_static_properties_changed")
    for destination, value in ((DESTINATION, data), (CATALOG, catalog)):
        content = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not destination.is_file() or destination.read_text(encoding="utf-8") != content:
                raise SystemExit("planning_parity_fixture_outdated")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
    print(f"planning parity: {len(data['cases'])} cases; {len(catalog['findings'])} findings")


if __name__ == "__main__":
    main()
