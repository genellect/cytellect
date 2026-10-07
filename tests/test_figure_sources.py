import json
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from cytellect_analysis.figure_sources import attach_svg_sources, bind_points


@pytest.mark.parametrize("count", [1, 3])
@pytest.mark.parametrize("unfilled", [False, True])
def test_saved_svg_points_retain_observation_identity(tmp_path, count, unfilled):
    figure, axis = plt.subplots()
    rows = [{"field_id": "field", "region_id": index + 1} for index in range(count)]
    options = {"facecolors": "none", "edgecolors": "black", "marker": "s"} if unfilled else {}
    bind_points(axis.scatter(range(count), range(count), **options), rows)
    destination = tmp_path / "figure.svg"
    figure.savefig(destination)
    attach_svg_sources(destination, figure)
    saved = [json.loads(element.attrib["data-cytellect-source"])
             for element in ET.parse(destination).iter()
             if "data-cytellect-source" in element.attrib]
    assert saved == rows
    plt.close(figure)
