"""Null simulation behind the exploratory-model exclusion in docs/workspace-redesign.md.

Treatment is assigned per independent experimental unit; fields and cells are
nested in units and there is no true difference. The script counts how often
each existing statistics mode rejects the null at alpha 0.05, using the actual
cytellect_analysis.statistics.analyze implementation. Deterministic for a seed.

    uv run python scripts/exploratory_model_null_simulation.py --reps 400 --seed 1
"""
from __future__ import annotations

import argparse
import math
import warnings

import numpy as np
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.statistics import analyze


def make_rows(rng, units, fields, cells, sd_unit, sd_field, sd_cell):
    rows = []
    for condition in ("ctrl", "trt"):
        for unit in range(units):
            unit_effect = rng.normal(0, sd_unit)
            for field in range(fields):
                field_effect = rng.normal(0, sd_field)
                for _ in range(cells):
                    rows.append({
                        "condition": condition, "experimental_unit": f"{condition}{unit}", "sample": f"{condition}{unit}s",
                        "field_id": f"{condition}{unit}f{field}", "acquisition_date": "d1",
                        "value": unit_effect + field_effect + rng.normal(0, sd_cell),
                        "gfp_mean_corrected": float(np.exp(rng.normal(3, 0.5))),
                    })
    return rows


def wilson(successes, total, z=1.96):
    if not total:
        return (math.nan, math.nan)
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return centre - half, centre + half


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reps", type=int, default=400)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--units", type=int, default=3, help="independent units per condition")
    parser.add_argument("--fields", type=int, default=3, help="fields per unit")
    parser.add_argument("--cells", type=int, default=30, help="cells per field")
    parser.add_argument("--sd-unit", type=float, default=1.0)
    parser.add_argument("--sd-field", type=float, default=0.3)
    parser.add_argument("--sd-cell", type=float, default=1.0)
    args = parser.parse_args()
    warnings.filterwarnings("ignore")
    rng = np.random.default_rng(args.seed)
    rejected = {"experimental-unit": 0, "exploratory": 0}
    runs = {"experimental-unit": 0, "exploratory": 0}
    for _ in range(args.reps):
        rows = make_rows(rng, args.units, args.fields, args.cells, args.sd_unit, args.sd_field, args.sd_cell)
        for mode in rejected:
            request = StatisticsRequest(metric="value", mode=mode, baseline="ctrl", comparisons=[("trt", "ctrl")],
                                        independent_units_confirmed=True)
            try:
                p_value = analyze(rows, request)["comparisons"][0]["p_value"]
            except ValueError:
                continue
            runs[mode] += 1
            rejected[mode] += p_value < 0.05
    print(f"seed={args.seed} reps={args.reps} units/condition={args.units} fields/unit={args.fields} "
          f"cells/field={args.cells} sd(unit,field,cell)=({args.sd_unit},{args.sd_field},{args.sd_cell})")
    for mode in rejected:
        low, high = wilson(rejected[mode], runs[mode])
        rate = rejected[mode] / runs[mode] if runs[mode] else math.nan
        print(f"{mode:18s} type I error at alpha 0.05 = {rate:.4f} (95% CI {low:.3f}-{high:.3f}, runs {runs[mode]})")


if __name__ == "__main__":
    main()
