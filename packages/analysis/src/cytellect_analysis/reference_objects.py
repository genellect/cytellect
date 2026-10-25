"""Compare adopted nuclear labels with another method's published object centres.

Used to show where two segmentations of the same image agree. Each reference object is
located by its centre pixel; nothing is re-segmented, resized or thresholded here.
Nuclei touching the image border are kept apart, because pipelines differ in whether
they count them (CellProfiler's Count_Nuclei excludes them).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np

STATUSES = ("both", "split", "reference_only", "labels_only")


def border_labels(labels: np.ndarray) -> set[int]:
    edge = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    return {int(value) for value in np.unique(edge) if value}


def match_reference_centres(labels: np.ndarray, centres: Sequence[tuple[float, float]]) -> dict:
    """Classify reference objects (x, y centres in pixels) against an integer label image.

    - ``both``: the centre lies in a label that holds exactly one reference centre;
    - ``split``: the centre lies in a label holding two or more centres (the reference
      method divided what the labels hold as one nucleus);
    - ``reference_only``: the centre lies on background;
    - ``labels_only``: a label away from the border that holds no reference centre.
    Centres outside the image are rejected.
    """
    if labels.ndim != 2:
        raise ValueError("reference_labels_not_2d")
    height, width = labels.shape
    hits: list[int] = []
    for x, y in centres:
        column, row = int(round(x)), int(round(y))
        if not (0 <= row < height and 0 <= column < width):
            raise ValueError("reference_centre_outside_image")
        hits.append(int(labels[row, column]))
    counts = Counter(value for value in hits if value)
    reference = ["reference_only" if value == 0 else "both" if counts[value] == 1 else "split" for value in hits]
    border = border_labels(labels)
    ids = {int(value) for value in np.unique(labels) if value}
    labels_only = sorted(value for value in ids - border if counts[value] == 0)
    return {"reference": reference, "labels_only": labels_only, "border_labels": sorted(border),
            "summary": {"reference_objects": len(hits), "both": reference.count("both"), "split": reference.count("split"),
                        "reference_only": reference.count("reference_only"), "labels_only": len(labels_only),
                        "labels": len(ids), "labels_away_from_border": len(ids - border)}}
