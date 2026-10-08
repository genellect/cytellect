"""Attach saved observation identities to SVG marks without changing measurements."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE_KEYS = ("field_id", "region_id", "nucleus_id", "condition", "sample", "experimental_unit")
SVG = "http://www.w3.org/2000/svg"


def bind_points(collection, rows):
    sources = [{key: row[key] for key in SOURCE_KEYS if row.get(key) is not None} for row in rows]
    if not sources or any(not row for row in sources):
        return collection
    figure = collection.figure
    bindings = getattr(figure, "_cytellect_point_sources", {})
    gid = f"cytellect-source-points-{len(bindings)}"
    collection.set_gid(gid)
    bindings[gid] = sources
    figure._cytellect_point_sources = bindings
    return collection


def attach_svg_sources(path: Path, figure):
    bindings = getattr(figure, "_cytellect_point_sources", {})
    if not bindings:
        return
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    tree = ET.parse(path)
    for group in tree.getroot().iter(f"{{{SVG}}}g"):
        rows = bindings.get(group.get("id"))
        if rows is None:
            continue
        marks = list(group.iter(f"{{{SVG}}}use"))
        # Matplotlib may write markers directly (single points or unfilled
        # collections) rather than references to a definition in <defs>.
        if not marks:
            marks = [child for child in group if child.tag == f"{{{SVG}}}path"]
        if len(marks) != len(rows):
            raise ValueError("figure_source_mark_mismatch")
        for mark, source in zip(marks, rows, strict=True):
            mark.set("data-cytellect-source", json.dumps(source, ensure_ascii=True, separators=(",", ":")))
            mark.set("tabindex", "0")
            mark.set("role", "button")
            mark.set("aria-label", "元データを表示")
    tree.write(path, encoding="utf-8", xml_declaration=True)
