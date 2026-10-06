"""Per-nucleus nucleolar/nucleoplasmic summary from saved masks and original pixels.

Primary metric (White et al., Mol Cell 2019, doi:10.1016/j.molcel.2019.03.019):
the ratio of mean intensities in the nucleolar union and in the nucleoplasm of the
same parent nucleus, reported as log2(nucleoplasm / nucleolus) so that larger
values mean relocation towards the nucleoplasm. The nucleolar mean is computed
over union pixels, not as a mean of object means (requirement A05). Integrated
values and the nucleolar area fraction are reported alongside (Potapova et al.,
eLife 2023). No pseudocount is added: an undefined or non-positive value is
missing with a reason (requirement A07).
"""
from __future__ import annotations

import math

import numpy as np

from .masks import validate_labels

PROTOCOL = "compartment-summary/1.0.0"


def compartment_summary(nuclei: np.ndarray, nucleoli: np.ndarray, nucleoplasm: np.ndarray,
                        image: np.ndarray, background: float | None = None) -> dict:
    validate_labels(nuclei, nucleoli)
    if nucleoplasm.shape != nuclei.shape or image.shape != nuclei.shape:
        raise ValueError("compartment_summary_shape_mismatch")
    if np.any((nucleoplasm > 0) & (nucleoli > 0)) or np.any((nucleoplasm > 0) & (nucleoplasm != nuclei)):
        raise ValueError("compartment_summary_masks_inconsistent")
    pixels = image.astype(np.float64)
    corrected = background is not None
    rows = []
    for parent in (int(value) for value in np.unique(nuclei) if value):
        nucleus = nuclei == parent
        union = nucleus & (nucleoli > 0)
        plasm = nucleoplasm == parent
        count = int(len({int(value) for value in np.unique(nucleoli[union]) if value}))
        row = {"nucleus_id": parent, "nucleus_area_px": int(nucleus.sum()), "nucleolar_count": count,
               "nucleolar_area_px": int(union.sum()), "nucleoplasm_area_px": int(plasm.sum()),
               "nucleolar_area_fraction": float(union.sum() / nucleus.sum()) if nucleus.any() else None,
               "nucleolar_mean": None, "nucleoplasm_mean": None, "nucleolar_integrated": None,
               "nucleoplasm_integrated": None, "ratio_nucleoplasm_over_nucleolus": None,
               "log2_nucleoplasm_over_nucleolus": None, "integrated_ratio_nucleolus_over_nucleoplasm": None,
               "missing_reason": None, "background": background,
               "values": "background_corrected" if corrected else "raw"}
        if not union.any():
            row["missing_reason"] = "no_nucleolus"
        elif not plasm.any():
            row["missing_reason"] = "no_nucleoplasm"
        else:
            offset = background if corrected else 0.0
            nucleolar_mean = float(pixels[union].mean()) - offset
            plasm_mean = float(pixels[plasm].mean()) - offset
            nucleolar_integrated = float(pixels[union].sum()) - offset * int(union.sum())
            plasm_integrated = float(pixels[plasm].sum()) - offset * int(plasm.sum())
            row.update({"nucleolar_mean": nucleolar_mean, "nucleoplasm_mean": plasm_mean,
                        "nucleolar_integrated": nucleolar_integrated, "nucleoplasm_integrated": plasm_integrated})
            if nucleolar_mean <= 0 or plasm_mean <= 0:
                row["missing_reason"] = "nonpositive_signal"
            else:
                ratio = plasm_mean / nucleolar_mean
                row["ratio_nucleoplasm_over_nucleolus"] = ratio
                row["log2_nucleoplasm_over_nucleolus"] = math.log2(ratio)
                if nucleolar_integrated > 0 and plasm_integrated > 0:
                    row["integrated_ratio_nucleolus_over_nucleoplasm"] = nucleolar_integrated / plasm_integrated
        rows.append(row)
    return {"protocol": PROTOCOL, "rows": rows,
            "references": ["white-2019", "potapova-2023"],
            "definition": "log2(mean nucleoplasm / mean nucleolar union) per parent nucleus; no pseudocount"}
