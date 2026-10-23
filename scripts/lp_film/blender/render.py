"""Reproducible, metre-scale Cycles macro photography for LP review.

blender -b -t 6 --python scripts/lp_film/blender/render.py -- --cut droplet
Default output is three stills in .cache/lp_film/blender, never a movie.
See README.md for dimensions, modelling limits and the approval boundary.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
MM = 0.001


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def material(name, ior=None, roughness=0.1, color=(0.8, 0.8, 0.8, 1)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    if ior:
        bsdf.inputs["Transmission Weight"].default_value = 1
        bsdf.inputs["IOR"].default_value = ior
    return mat


def lathe(name, profile, mat, location=(0, 0, 0), segments=128):
    """Revolve an ordered, closed meridian; dimensions are in millimetres."""
    vertices = []
    for r, z in profile:
        for j in range(segments):
            a = 2 * math.pi * j / segments
            vertices.append((MM * r * math.cos(a), MM * r * math.sin(a), MM * z))
    faces = []
    for i in range(len(profile) - 1):
        for j in range(segments):
            k = (j + 1) % segments
            faces.append((i * segments + j, i * segments + k, (i + 1) * segments + k, (i + 1) * segments + j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(mat)
    for p in mesh.polygons:
        p.use_smooth = True
    # Recalculate normals consistently, including the inner walls of hollow glass.
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)
    return obj


def plane(name, size, location, mat):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def plate_deck(mat):
    """Connected 96-hole deck with the ANSI/SLAS 127.76 x 85.48 mm footprint."""
    vertices, faces = [], []
    for row in range(8):
        for col in range(12):
            cx, cy = -50 + col * 9, -27 + row * 9
            start = len(vertices)
            for j in range(64):
                a = 2 * math.pi * j / 64
                x, y = math.cos(a), math.sin(a)
                square = 4.5 / max(abs(x), abs(y))
                for radius in (3.55, square):
                    vertices.append(((cx + radius * x) * MM, (cy + radius * y) * MM, 0.0094))
            for j in range(64):
                k = (j + 1) % 64
                faces.append((start + 2 * j, start + 2 * j + 1, start + 2 * k + 1, start + 2 * k))
    mesh = bpy.data.meshes.new("96-hole deck")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new("Connected plate deck", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    solid = obj.modifiers.new("Moulded deck thickness 0.35 mm", "SOLIDIFY")
    solid.thickness = 0.00035
    for name, center, size in [
        ("Left rim", (-59.44, 4.5, 8.9), (9.88, 85.48, 1)),
        ("Right rim", (58.44, 4.5, 8.9), (9.88, 85.48, 1)),
        ("Front rim", (-0.5, -34.87, 8.9), (108, 6.74, 1)),
        ("Back rim", (-0.5, 43.87, 8.9), (108, 6.74, 1)),
    ]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(v * MM for v in center))
        rim = bpy.context.object
        rim.name = name
        rim.scale = tuple(v * MM for v in size)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        rim.data.materials.append(mat)
        bevel = rim.modifiers.new("Moulded edge", "BEVEL")
        bevel.width, bevel.segments = 0.0002, 3
        rim.select_set(False)


def area(name, location, target, power, size, size_y=None):
    light = bpy.data.lights.new(name, "AREA")
    light.energy = power
    light.shape = "RECTANGLE"
    light.size = size
    light.size_y = size_y or size
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def setup(args):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.adaptive_threshold = 0.015
    scene.cycles.max_bounces = 16
    scene.cycles.transmission_bounces = 12
    scene.cycles.glossy_bounces = 8
    scene.cycles.transparent_max_bounces = 12
    scene.cycles.use_light_tree = True
    scene.cycles.seed = 3127
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = args.scale
    scene.render.fps = 25
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.25
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.world = bpy.data.worlds.new("Neutral daylight studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.8, 0.8, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    scene.frame_start, scene.frame_end = 1, 80
    return scene


def camera(location, target, focus, lens=100, sensor=36, fstop=5.6):
    data = bpy.data.cameras.new("Macro lens")
    obj = bpy.data.objects.new("Camera", data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    data.lens, data.sensor_width = lens, sensor
    data.clip_start, data.clip_end = 0.0001, 10
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    data.dof.aperture_blades = 9
    data.dof.focus_distance = (Vector(focus) - obj.location).length
    bpy.context.scene.camera = obj
    return obj


def light_stage(target, scale=1):
    white = material("Matte white laboratory", roughness=0.32, color=(0.82, 0.82, 0.82, 1))
    floor = plane("White bench", 3, (0, 0, -0.001), white)
    floor.cycles.is_caustics_receiver = True
    key = area(
        "Large diffused window",
        (-0.11 * scale, 0.04 * scale, 0.15 * scale),
        target,
        4 * scale * scale,
        0.17 * scale,
        0.23 * scale,
    )
    key.data.cycles.is_caustics_light = True
    area(
        "Narrow white reflection card",
        (0.08 * scale, -0.02 * scale, 0.10 * scale),
        target,
        1 * scale * scale,
        0.035 * scale,
        0.15 * scale,
    )
    # A neutral grey flag defines transparent edges without black surroundings.
    flag = plane(
        "Grey off-camera flag",
        0.12 * scale,
        (0.10 * scale, 0.07 * scale, 0.07 * scale),
        material("Neutral reflection flag", color=(0.18, 0.18, 0.18, 1)),
    )
    aim(flag, target)
    return key


def pendant_profile(radius, neck=0.26):
    """Axisymmetric Young-Laplace integration in mm, from apex upwards.

    Water capillary length = sqrt(0.072/(998*9.81)) m. Pressure decreases
    with height. This is a quasi-static shape, not a Navier-Stokes solver.
    """
    capillary = math.sqrt(0.072 / (998 * 9.81)) / MM
    step = 0.005
    state = [step, step * step / (2 * radius), step / radius]
    points = [(0.001, 0)]

    def rhs(v):
        r, z, angle = v
        return (
            math.cos(angle),
            math.sin(angle),
            2 / radius - z / capillary**2 - math.sin(angle) / max(r, 1e-6),
        )

    for _ in range(4000):
        r, z, angle = state
        points.append((r, z))
        if angle > math.pi / 2 and r <= neck:
            break
        k1 = rhs(state)
        k2 = rhs([v + step * k / 2 for v, k in zip(state, k1)])
        k3 = rhs([v + step * k / 2 for v, k in zip(state, k2)])
        k4 = rhs([v + step * k for v, k in zip(state, k3)])
        state = [v + step * (a + 2 * b + 2 * c + d) / 6 for v, a, b, c, d in zip(state, k1, k2, k3, k4)]
    else:
        raise ValueError("Pendant profile did not reach the pinned contact line")
    top = points[-1][1]
    return [(r, z - top) for r, z in points] + [(0.001, 0), (0.001, -top)]


def droplet(frame):
    water = material("Water n=1.333", 1.333, 0.015, (1, 1, 1, 1))
    pp = material("Clear polypropylene n=1.49", 1.49, 0.07, (1, 1, 1, 1))
    ps = material("Polystyrene n=1.59", 1.59, 0.035, (1, 1, 1, 1))
    tip_location = (0.004, 0, 0.015)
    # 53 mm 200-uL tip, hollow throughout. Sub-mm bore is an explicit approximation.
    profile = [
        (0.39, 0),
        (0.42, 0.15),
        (0.66, 5),
        (1.7, 26),
        (3.4, 48),
        (3.5, 53),
        (3.15, 53),
        (3.08, 48),
        (1.46, 26),
        (0.45, 5),
        (0.26, 0.15),
        (0.26, 0),
        (0.39, 0),
    ]
    lathe("200 uL hollow tip / 53 mm", profile, pp, tip_location)
    if frame < 55:
        radius = 0.62 + 0.34 * min(frame, 50) / 50
        drop = lathe("Pendant water / Young-Laplace", pendant_profile(radius), water, tip_location)
    else:
        # Pinch-off is a topological cut. Relaxation follows a damped capillary mode.
        t = (frame - 55) / 25
        radius = 1.0
        stretch = 1 + 0.18 * math.exp(-t * 6) * math.cos(t * 22)
        z = 0.0127 - 0.5 * 9.81 * (t / 18) ** 2  # 18x slow-motion fall
        p = [
            (
                max(0.001, radius * math.sin(math.pi * j / 100) / math.sqrt(stretch)),
                radius * math.cos(math.pi * j / 100) * stretch,
            )
            for j in range(101)
        ]
        drop = lathe("Detached water / capillary relaxation", p, water, (0.004, 0, z))
        lathe("Residual meniscus", pendant_profile(0.3), water, tip_location)
    drop.cycles.is_caustics_caster = True
    # 96 wells: 9 mm pitch, 6.4 mm clear opening; deck footprint 127.76 x 85.48 mm.
    well = [
        (0.001, 0),
        (3.55, 0),
        (3.55, 10.5),
        (3.5, 10.7),
        (3.2, 10.7),
        (3.15, 10.5),
        (3.15, 1),
        (0.001, 1),
        (0.001, 0),
    ]
    first = lathe("96 well plate / A1", well, ps, (-0.05, -0.027, -0.001), 64)
    for row in range(8):
        for col in range(12):
            if row == col == 0:
                continue
            obj = first.copy()
            obj.data = first.data
            obj.location = (-0.05 + col * 0.009, -0.027 + row * 0.009, -0.001)
            bpy.context.collection.objects.link(obj)
    plate_deck(ps)
    medium = material("Pale medium / water n=1.333", 1.333, 0.025, (1, 0.88, 0.90, 1))
    liquid = lathe(
        "Medium in well",
        [(0.001, 0), (3.13, 0), (3.13, 3.2), (2.9, 3.0), (0.001, 3.0), (0.001, 0)],
        medium,
        (0.004, 0, 0.0032),
        96,
    )
    for x, y in [(-0.005, 0), (0.013, 0), (0.004, 0.009), (0.013, 0.009)]:
        obj = liquid.copy()
        obj.location.x, obj.location.y = x, y
        bpy.context.collection.objects.link(obj)
    light_stage((0.004, 0, 0.013))
    camera((-0.002, -0.090, 0.023), (0.0005, 0, 0.0120), (0.004, 0, 0.0137), sensor=22, fstop=11)


def glass(frame):
    borosilicate = material("Borosilicate glass n=1.47", 1.47, 0.022, (1, 1, 1, 1))
    water = material("Water n=1.333", 1.333, 0.013, (1, 1, 1, 1))
    # DWK 53061-6015 nominal 60 x 15 mm Petri dish; wall is an explicit approximation.
    dish = lathe(
        "60 x 15 mm borosilicate dish",
        [
            (0.001, 0),
            (29.6, 0),
            (30, 0.4),
            (30, 14.5),
            (29.8, 15),
            (28.9, 15),
            (28.8, 14.5),
            (28.8, 1.4),
            (0.001, 1.4),
            (0.001, 0),
        ],
        borosilicate,
        (0.006, 0.008, 0),
        192,
    )
    dish.cycles.is_caustics_caster = True
    # DWK 40500-200: solid stirring rod, diameter 5 mm, length 200 mm.
    rod_profile = [
        (max(0.001, 2.5 * math.sin(a)), 2.5 - 2.5 * math.cos(a))
        for a in [j * math.pi / 2 / 64 for j in range(65)]
    ]
    rod_profile += [(2.5, 197.5), (2.4, 200), (0.001, 200), rod_profile[0]]
    rod = lathe("5 x 200 mm glass stirring rod", rod_profile, borosilicate, (0.014, 0.008, 0.0088))
    rod.cycles.is_caustics_caster = True
    # Water in the dish, with a shallow wetting rise around the immersed rod.
    vertices, faces = [], []
    rings, segments = 120, 192
    for i in range(rings + 1):
        r = max(0.000001, 0.028805 * i / rings)
        for j in range(segments):
            a = 2 * math.pi * j / segments
            x, y = r * math.cos(a), r * math.sin(a)
            distance = math.hypot(x - 0.008, y)
            rise = 0.00075 * math.exp(-max(0, distance - 0.0022) / 0.0011)
            edge = 0.0005 * math.exp(-(0.028805 - r) / 0.0007)
            vertices.append((x, y, 0.010 + rise + edge))
    for i in range(rings):
        for j in range(segments):
            k = (j + 1) % segments
            faces.append((i * segments + j, (i + 1) * segments + j, (i + 1) * segments + k, i * segments + k))
    bottom_start = len(vertices)
    for j in range(segments):
        a = 2 * math.pi * j / segments
        vertices.append((0.028805 * math.cos(a), 0.028805 * math.sin(a), 0.0013))
    bottom_center = len(vertices)
    vertices.append((0, 0, 0.0013))
    for j in range(segments):
        k = (j + 1) % segments
        faces.append((rings * segments + k, rings * segments + j, bottom_start + j, bottom_start + k))
        faces.append((bottom_center, bottom_start + k, bottom_start + j))
    mesh = bpy.data.meshes.new("Wetting water surface")
    mesh.from_pydata(vertices, [], faces)
    content = bpy.data.objects.new("Water volume", mesh)
    bpy.context.collection.objects.link(content)
    content.location = (0.006, 0.008, 0)
    content.data.materials.append(water)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    content.cycles.is_caustics_caster = True
    key = light_stage((0.014, 0.008, 0.010), scale=1)
    flag = bpy.data.objects["Grey off-camera flag"]
    flag.scale = (0.5, 0.5, 0.5)
    flag.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.4,
        0.4,
        0.4,
        1,
    )
    # Subtle moving window, no coloured lights, no decorative geometry.
    key.location.x += (frame - 40) * 0.00023
    aim(key, (0.014, 0.008, 0.010))
    cam = camera(
        (-0.004 + (frame - 40) * 0.000025, -0.125, 0.062),
        (0.003, 0.008, 0.010),
        (0.014, 0.006, 0.0105),
        lens=90,
        fstop=8,
    )
    return cam


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cut", choices=["droplet", "glass"], required=True)
    parser.add_argument("--frames", type=int, nargs="+")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--scale", type=int, default=100)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/lp_film/blender")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    args.output = args.output.resolve()
    frames = args.frames or ([16, 49, 65] if args.cut == "droplet" else [1, 40, 80])
    args.output.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        scene = setup(args)
        globals()[args.cut](frame)
        scene.frame_set(frame)
        scene.render.filepath = str(args.output / f"{args.cut}-{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
    (args.output / f"{args.cut}-settings.json").write_text(
        json.dumps(
            {
                "blender": bpy.app.version_string,
                "engine": "CYCLES",
                "frames": frames,
                "samples": args.samples,
                "resolution": [1920 * args.scale // 100, 1080 * args.scale // 100],
                "view_transform": "AgX",
                "external_assets": [],
                "approval": "pending",
                "note": "Illustrative artwork; not a validated fluid simulation or research result.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
