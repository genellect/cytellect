"""Author a microscopy-inspired artwork, not a measured or reconstructed cell.

Blender 4.5.14: blender --background --factory-startup --threads 4 --python
scripts/create_cell_sculpture.py -- --output-dir <build-directory>
The output GLB uses embedded PBR textures and a +Z presentation face (glTF Y-up).
The PNG poster can be losslessly read and encoded as WebP with Pillow.
Own source and artwork: Apache-2.0. Blender is a separate GPL-licensed tool.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

SEED = 1404
TAU = math.tau


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", dest="output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=48)
    parser.add_argument("--resolution", type=int, default=100)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def microtexture():
    """Periodic authored surface relief; it contains no image or biological data."""
    n = 512
    rng = np.random.default_rng(SEED)
    y, x = np.mgrid[0:n, 0:n].astype(np.float64) / n
    h = np.zeros((n, n))
    for frequency, amplitude in ((18, .42), (37, .22), (69, .13), (109, .07)):
        phase = rng.uniform(0, TAU, 3)
        h += amplitude * np.sin(TAU * frequency * x + phase[0]) * np.sin(
            TAU * (frequency - 3) * y + phase[1]
        )
        h += .3 * amplitude * np.sin(TAU * (frequency * x + (frequency + 4) * y) + phase[2])
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * .8
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * .8
    normal = np.stack((-dx, -dy, np.ones_like(h)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    rgba = np.ones((n, n, 4), dtype=np.float32)
    rgba[:, :, :3] = normal * .5 + .5
    image = bpy.data.images.new("Authored membrane microrelief", width=n, height=n)
    image.colorspace_settings.name = "Non-Color"
    image.pixels.foreach_set(rgba.ravel())
    image.pack()
    return image


def material(name, color, roughness, relief, normal_image, metallic=.12):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Coat Weight"].default_value = .025
    p.inputs["Coat Roughness"].default_value = .48
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = normal_image
    tex.label = "Deterministic generated microrelief, not microscopy"
    normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
    normal.inputs["Strength"].default_value = relief
    mat.node_tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
    mat.node_tree.links.new(normal.outputs["Normal"], p.inputs["Normal"])
    return mat


def mesh_object(name, vertices, faces, uv, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    layer = mesh.uv_layers.new(name="SurfaceUV")
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            layer.data[loop_index].uv = uv[mesh.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def membrane_point(theta, phi, inset=0):
    # Oblique, pinched, non-spherical silhouette. A variable aperture reveals folds.
    radial = 1 + .11 * math.cos(3 * phi + .45) + .055 * math.sin(5 * phi - theta)
    radial *= 1 + .025 * math.sin(13 * phi + 8 * theta)
    x = (1.94 - inset) * math.sin(theta) * math.cos(phi) * radial
    z = (1.55 - inset) * math.sin(theta) * math.sin(phi) * radial
    y = -(1.00 - inset) * math.cos(theta)
    x += .13 * math.sin(2 * theta) + .08 * z
    y += .095 * math.cos(3 * phi) * math.sin(theta) ** 3
    return (x, y, z)


def create_membrane(outside, inside, lip):
    n, m = 112, 38
    vertices, faces, uvs = [], [], []
    for inset in (0, .045):
        for j in range(m + 1):
            for i in range(n):
                phi = TAU * i / n
                opening = 1.10 + .13 * math.sin(phi + .5) + .05 * math.sin(3 * phi)
                theta = opening + (math.pi - .015 - opening) * j / m
                vertices.append(membrane_point(theta, phi, inset))
                uvs.append((i / n, j / m))
    sheet = (m + 1) * n
    for side in range(2):
        for j in range(m):
            for i in range(n):
                a = side * sheet + j * n + i
                b = side * sheet + j * n + (i + 1) % n
                face = (a, b, b + n, a + n)
                faces.append(tuple(reversed(face)) if side == 0 else face)
    for i in range(n):
        ni = (i + 1) % n
        faces.append((i, sheet + i, sheet + ni, ni))
    obj = mesh_object("Membrane | continuous cutaway shell", vertices, faces, uvs, outside)
    obj.data.materials.append(inside)
    obj.data.materials.append(lip)
    for polygon in obj.data.polygons:
        polygon.material_index = 0 if polygon.index < m * n else (1 if polygon.index < 2 * m * n else 2)
    return obj


def nucleus(mat):
    n, m = 88, 40
    vertices, faces, uv = [], [], []
    for j in range(m + 1):
        theta = .002 + (math.pi - .004) * j / m
        for i in range(n):
            phi = TAU * i / n
            qx = math.sin(theta) * math.cos(phi)
            qy = -math.cos(theta)
            qz = math.sin(theta) * math.sin(phi)
            # Cartesian relief has no polar convergence/starburst at the front.
            wrinkle = 1 + .10 * math.sin(3 * qx + .4) * math.cos(2 * qz)
            wrinkle += .065 * math.sin(12 * qx + 1.8 * math.sin(5 * qz)) * math.cos(9 * qz - 3 * qy)
            wrinkle += .026 * math.sin(20 * qz + 4 * qx) * math.sin(13 * qy + qx)
            vertices.append((.12 + .72 * qx * wrinkle,
                             -.24 + .46 * qy * wrinkle,
                             .18 + .63 * qz * wrinkle))
            uv.append((i / n, j / m))
    for j in range(m):
        for i in range(n):
            a = j * n + i
            b = j * n + (i + 1) % n
            faces.append((a + n, b + n, b, a))
    return mesh_object("Folded internal body", vertices, faces, uv, mat)


def lamella(name, layer, mat):
    n, m = 152, 9
    vertices, faces, uv = [], [], []
    # Incomplete interlocking ribbons, not concentric spheres; the gaps disclose depth.
    for i in range(n + 1):
        t = i / n
        angle = -.3 + (4.6 + .12 * layer) * t + .18 * layer
        radius = 1.0 + layer * .135 + .105 * math.sin(3 * angle + .3 * layer)
        radius += .026 * math.sin(11 * angle + layer)
        width = .066 + .025 * math.sin(math.pi * t)
        for j in range(m + 1):
            s = 2 * j / m - 1
            r = radius + s * width
            x = -.08 + r * math.cos(angle)
            z = .08 + .83 * r * math.sin(angle)
            y = -.19 + layer * .028 + .115 * math.sin(5 * angle + layer * .6)
            y += .11 * s * s + .025 * math.sin(19 * angle + 2 * s)
            vertices.append((x, y, z))
            uv.append((t * 3, j / m))
    for i in range(n):
        for j in range(m):
            a = i * (m + 1) + j
            faces.append((a, a + 1, a + m + 2, a + m + 1))
    obj = mesh_object(name, vertices, faces, uv, mat)
    mod = obj.modifiers.new("Visible folded sheet edge", "SOLIDIFY")
    mod.thickness = .025
    mod.offset = 0
    return obj


def tube(name, points, mat, radius):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, xyz in zip(spline.points, points):
        p.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def area(name, location, energy, color, size, target):
    bpy.ops.object.light_add(type="AREA", location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.energy = energy
    obj.data.color = color
    obj.data.shape = "DISK"
    obj.data.size = size
    aim(obj, target)


def main():
    args = arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    normal = microtexture()
    outer = material("Blue membrane | rough microrelief", (.009, .070, .25), .55, .90, normal, .015)
    inner = material("Blue inner membrane", (.018, .20, .40), .53, .65, normal, .015)
    edge = material("Exposed thin membrane edge", (.024, .18, .48), .48, .50, normal, .015)
    core = material("Indigo convoluted core", (.019, .050, .22), .51, .80, normal, .015)
    folds = material("Blue folded lamellae", (.016, .16, .44), .50, .65, normal, .015)
    art = [create_membrane(outer, inner, edge), nucleus(core)]
    for i in range(3):
        art.append(lamella(f"Lamellar fold {i + 1}", i, folds if i != 1 else inner))
    # A rim follows the same irregular cut, never a screen-space or billboard ring.
    rim = []
    for i in range(225):
        phi = TAU * i / 224
        theta = 1.10 + .13 * math.sin(phi + .5) + .05 * math.sin(3 * phi)
        rim.append(membrane_point(theta, phi, .020))
    art.append(tube("Continuous membrane rim", rim, edge, .012))
    # Apply geometry modifiers and export exactly the geometry used in the render.
    for obj in art:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
    art = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    vertices = [obj.matrix_world @ v.co for obj in art for v in obj.data.vertices]
    low = Vector(tuple(min(v[a] for v in vertices) for a in range(3)))
    high = Vector(tuple(max(v[a] for v in vertices) for a in range(3)))
    center = (low + high) / 2
    scale = 4 / max(high - low)
    for obj in art:
        for v in obj.data.vertices:
            v.co = (v.co - center) * scale
    triangles = 0
    for obj in art:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
    if triangles > 50000:
        raise RuntimeError(f"Mesh budget exceeded: {triangles}")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in art:
        obj.select_set(True)
        obj["artwork_kind"] = "Cytellect-authored microscopy-inspired sculpture"
        obj["scientific_measurement"] = False
    glb = args.output / "cell-sculpture.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_materials="EXPORT", export_extras=True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = args.resolution
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .5
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.002, .006, .024, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .28
    for obj in art:
        obj.location.x = 1.85
        obj.rotation_euler.y = -.18
        obj.rotation_euler.z = -.08
    target = (1.85, 0, 0)
    area("Blue key", (-1.4, -3.0, 4.7), 400, (.34, .62, 1.0), 3.2, target)
    area("Cyan contour", (5.0, .8, 2.3), 600, (.11, .57, 1.0), 3.0, target)
    area("Deep blue separation", (-.2, 1.8, -1.0), 520, (.09, .23, 1.0), 2.5, target)
    area("Soft frontal fill", (1.4, -4.0, -2.8), 25, (.25, .45, 1.0), 3.2, target)
    bpy.ops.object.camera_add(location=(0, -12.6, .35))
    camera = bpy.context.object
    aim(camera, (0, 0, 0))
    camera.data.type = "PERSP"
    camera.data.lens = 55
    scene.camera = camera
    scene.render.filepath = str(args.output / "cell-sculpture-poster.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output / "cell-sculpture-source.blend"))
    bpy.ops.render.render(write_still=True)
    receipt = {"generator": "create_cell_sculpture.py", "seed": SEED,
               "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "blender_version": bpy.app.version_string, "triangles": triangles,
               "mesh_count": len(art), "max_axis_diameter": 4.0,
               "gltf_up": "+Y", "presentation_face": "+Z", "texture_size": [512, 512],
               "scientific_data": False, "kind": "authored microscopy-inspired sculpture",
               "artwork_license": "Apache-2.0", "external_textures_or_models": [],
               "render_engine": "Cycles CPU", "render_threads": 4,
               "render_samples": args.samples, "render_resolution_percentage": args.resolution,
               "glb_sha256": hashlib.sha256(glb.read_bytes()).hexdigest()}
    (args.output / "render-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
