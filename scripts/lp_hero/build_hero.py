"""Build and render the landing-page hero from real structural data (Blender 5.2 LTS).

Run inside Blender with Molecular Nodes 520.2.0 installed:

    blender -b --python scripts/lp_hero/build_hero.py -- \
        structure=/path/4v6x.cif hdri=/path/white_studio_01.exr out=/path/frames/ [still=1] [w=1920 h=1080] [samples=64]

The scene contains only the deposited atomic model (PDB 4V6X, human 80S ribosome, CC0)
rendered with Molecular Nodes styles, a CC0 Poly Haven HDRI for lighting, two area lights
and a camera. No geometry is authored by hand. Display choices (colours, materials, camera)
are artistic and recorded in the provenance file; atomic coordinates are unchanged.
"""

import importlib
import math
import sys
import time

import addon_utils
import bpy
import numpy as np
from mathutils import Vector

DEFAULTS = {
    "w": "1920", "h": "1080", "samples": "64", "frames": "240", "fps": "24",
    "dist": "2.7", "fstop": "0.25", "focus": "0.86", "exposure": "0.25", "shift": "-0.3",
    "background": "3.0", "transmission": "0.88", "roughness": "0.14", "subsurface": "0.1",
    "key": "1.2e6", "rim": "1.0e6", "look": "AgX - Medium High Contrast",
    "direction": "-0.25,-0.92,0.3", "orbit_deg": "9", "still": "0",
}


def arguments() -> dict:
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    values = dict(DEFAULTS)
    values.update(item.split("=", 1) for item in raw)
    for required in ("structure", "hdri", "out"):
        if required not in values:
            raise SystemExit(f"missing argument: {required}=")
    return values


def principled(name, color, **inputs):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    for key, value in inputs.items():
        shader.inputs[key].default_value = value
    return material


def build(a: dict):
    addon_utils.enable("bl_ext.user_default.molecularnodes", default_set=True)
    mn = importlib.import_module("bl_ext.user_default.molecularnodes")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    protein = principled("Protein", (0.95, 0.99, 0.98), **{
        "Transmission Weight": float(a["transmission"]), "Roughness": float(a["roughness"]), "IOR": 1.38,
        "Subsurface Weight": float(a["subsurface"]), "Coat Weight": 0.5, "Coat Roughness": 0.08})
    rrna_large = principled("rRNA large subunit", (0.0, 0.33, 0.29), **{"Roughness": 0.3, "Subsurface Weight": 0.3})
    rrna_small = principled("rRNA small subunit", (0.78, 0.40, 0.08), **{"Roughness": 0.3, "Subsurface Weight": 0.3})

    mol = mn.Molecule.load(a["structure"])
    nucleic = mol.named_attribute("is_nucleic").astype(bool)
    chain = mol.named_attribute("chain_id")
    sizes = {c: int(((chain == c) & nucleic).sum()) for c in np.unique(chain[nucleic])}
    # The second-largest RNA chain is the small-subunit (18S) rRNA in 4V6X.
    small = sorted(sizes, key=sizes.get, reverse=True)[1]
    mol.store_named_attribute(~nucleic, "sel_protein", atype="BOOLEAN")
    mol.store_named_attribute(nucleic & (chain != small), "sel_rrna_large", atype="BOOLEAN")
    mol.store_named_attribute(nucleic & (chain == small), "sel_rrna_small", atype="BOOLEAN")
    mol.add_style("surface", material=protein, name="protein")
    mol.add_style("ribbon", material=rrna_large, name="rrna_large")
    mol.add_style("ribbon", material=rrna_small, name="rrna_small")
    tree = mol.node_group
    styles = [n for n in tree.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.name.startswith("Style ")]
    for style, attribute in zip(styles, ("sel_protein", "sel_rrna_large", "sel_rrna_small")):
        selection = tree.nodes.new("GeometryNodeInputNamedAttribute")
        selection.data_type = "BOOLEAN"
        selection.inputs["Name"].default_value = attribute
        tree.links.new(selection.outputs[0], style.inputs["Selection"])
        if style.node_tree.name.startswith("Style Surface"):
            style.inputs["Scale"].default_value = 1.7
            style.inputs["Relax"].default_value = 20
        else:
            style.inputs["Nucleic Backbone Radius"].default_value = 1.4

    bpy.context.view_layer.update()
    evaluated = mol.object.evaluated_get(bpy.context.evaluated_depsgraph_get())
    corners = [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    center = sum(corners, Vector()) / 8
    size = (corners[6] - corners[0]).length

    world = bpy.data.worlds.new("Light studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    links, nodes = world.node_tree.links, world.node_tree.nodes
    environment = nodes.new("ShaderNodeTexEnvironment")
    environment.image = bpy.data.images.load(a["hdri"])
    lighting = nodes.new("ShaderNodeBackground")
    links.new(environment.outputs["Color"], lighting.inputs["Color"])
    backdrop = nodes.new("ShaderNodeBackground")
    backdrop.inputs["Strength"].default_value = float(a["background"])
    coordinates, split, ramp = nodes.new("ShaderNodeTexCoord"), nodes.new("ShaderNodeSeparateXYZ"), nodes.new("ShaderNodeValToRGB")
    links.new(coordinates.outputs["Window"], split.inputs[0])
    links.new(split.outputs["Y"], ramp.inputs[0])
    ramp.color_ramp.elements[0].color = (0.90, 0.89, 0.86, 1)
    ramp.color_ramp.elements[1].color = (0.985, 0.985, 0.975, 1)
    links.new(ramp.outputs[0], backdrop.inputs["Color"])
    path, mix = nodes.new("ShaderNodeLightPath"), nodes.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    links.new(lighting.outputs[0], mix.inputs[1])
    links.new(backdrop.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], nodes["World Output"].inputs["Surface"])

    def area(name, offset, energy, color, extent):
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.color, light.size = energy, color, extent
        obj = bpy.data.objects.new(name, light)
        bpy.context.collection.objects.link(obj)
        obj.location = center + Vector(offset) * size
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()

    area("Key", (-1.2, -1.0, 1.4), float(a["key"]), (1.0, 0.96, 0.9), size * 1.2)
    area("Rim", (1.1, 1.2, 0.6), float(a["rim"]), (0.85, 0.95, 1.0), size * 0.8)

    data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", data)
    bpy.context.collection.objects.link(camera)
    data.lens, data.shift_x = 85, float(a["shift"])
    data.dof.use_dof, data.dof.aperture_fstop = True, float(a["fstop"])
    direction = Vector(tuple(float(x) for x in a["direction"].split(","))).normalized()
    distance = size * float(a["dist"])
    frames = int(a["frames"])
    amplitude = math.radians(float(a["orbit_deg"]))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, frames
    scene.render.fps = int(a["fps"])
    # A sinusoidal sway around the vertical axis returns exactly to the first frame, so the clip loops.
    for frame in range(1, frames + 1):
        angle = amplitude * math.sin(2 * math.pi * (frame - 1) / frames)
        rotated = Vector((direction.x * math.cos(angle) - direction.y * math.sin(angle),
                          direction.x * math.sin(angle) + direction.y * math.cos(angle), direction.z))
        camera.location = center - rotated * distance
        camera.rotation_euler = rotated.to_track_quat("-Z", "Y").to_euler()
        data.dof.focus_distance = distance * (float(a["focus"]) + 0.02 * math.sin(2 * math.pi * (frame - 1) / frames))
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
        data.dof.keyframe_insert("focus_distance", frame=frame)

    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(a["samples"])
    scene.cycles.use_denoising = True
    scene.cycles.transmission_bounces, scene.cycles.max_bounces = 12, 16
    scene.render.resolution_x, scene.render.resolution_y = int(a["w"]), int(a["h"])
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = a["look"]
    scene.view_settings.exposure = float(a["exposure"])
    return scene


def main():
    a = arguments()
    scene = build(a)
    if a.get("save"):
        bpy.ops.wm.save_as_mainfile(filepath=a["save"])
    started = time.time()
    if a["still"] == "1":
        scene.render.filepath = a["out"]
        bpy.ops.render.render(write_still=True)
    else:
        scene.render.filepath = a["out"].rstrip("/") + "/frame_"
        scene.render.image_settings.file_format = "PNG"
        bpy.ops.render.render(animation=True)
    print(f"rendered in {time.time() - started:.1f} s")


main()
