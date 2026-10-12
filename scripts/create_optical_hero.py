"""Author the original Cytellect optical hero with Blender 4.5 LTS.

Original optical architecture. No microscopy, cells or image textures are used.
Usage: blender -b --python scripts/create_optical_hero.py -- --output-dir PATH
"""
import argparse
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--samples", type=int, default=48)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    world = scene.world.node_tree.nodes.get("Background")
    world.inputs["Color"].default_value = (0.48, 0.51, 0.55, 1)
    world.inputs["Strength"].default_value = 0.55
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"

    def material(name, color, metal, rough):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*color, 1)
        shader.inputs["Metallic"].default_value = metal
        shader.inputs["Roughness"].default_value = rough
        return mat

    glass = material("Smoked teal optical glass", (0.14, 0.38, 0.34), 0.04, 0.085)
    shader = glass.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Transmission Weight"].default_value = 0.88
    shader.inputs["IOR"].default_value = 1.46
    shader.inputs["Coat Weight"].default_value = 0.45
    clear = material("Clear optical glass", (0.82, 0.9, 0.87), 0.04, 0.075)
    clear.node_tree.nodes.get("Principled BSDF").inputs["Transmission Weight"].default_value = 0.9
    clear.node_tree.nodes.get("Principled BSDF").inputs["IOR"].default_value = 1.46
    bronze = material("Satin champagne metal", (0.56, 0.36, 0.16), 0.86, 0.24)
    mineral = material("Warm mineral studio", (0.68, 0.66, 0.60), 0.04, 0.46)
    silver = material("Brushed silver", (0.54, 0.59, 0.6), 0.86, 0.3)
    root = bpy.data.objects.new("Cytellect optical assembly", None)
    scene.collection.objects.link(root)
    architecture = bpy.data.objects.new("Optical architecture", None)
    scene.collection.objects.link(architecture)

    def prism(name, polygon, depth, mat, position, rotation, parent):
        count = len(polygon)
        vertices = [(x, y, z) for y in (-depth/2, depth/2) for x, z in polygon]
        faces = [tuple(range(count-1, -1, -1)), tuple(range(count, count*2))]
        faces += [(i, (i+1)%count, (i+1)%count+count, i+count) for i in range(count)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        editable = bmesh.new()
        editable.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(editable, faces=editable.faces)
        editable.to_mesh(mesh)
        editable.free()
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.data.materials.append(mat)
        obj.location = position
        obj.rotation_euler = rotation
        obj.parent = parent
        bevel = obj.modifiers.new("Precision polished edges", "BEVEL")
        bevel.width = 0.065
        bevel.segments = 5
        obj.modifiers.new("Weighted surface normals", "WEIGHTED_NORMAL")
        return obj

    # Monumental translucent planes form a continuous spatial composition.
    prism("Main optical prism", [(-1.8,-3.1),(1.8,-3.1),(1.4,5.8),(-0.7,5.1)],
        0.85, glass, (1.0,-0.3,0), (0.02,-0.16,0.06), root)
    prism("Clear refracting plane", [(-1.4,-3.2),(1.4,-3.2),(1.4,4.9),(-1.4,5.5)],
        0.58, clear, (3.4,1.0,0.1), (-0.06,0.20,-0.28), root)
    prism("Champagne light blade", [(-0.28,-3.2),(0.28,-3.2),(0.28,5.3),(-0.28,5.3)],
        0.16, bronze, (-1.4,0.75,0), (0,-0.26,0.1), root)
    # Large off-axis studio planes provide depth behind every content chapter.
    prism("Distant silver plane", [(-2.5,-6),(2.5,-6),(2.5,7),(-2.5,7)],
        0.18, silver, (6,8,1.5), (0,-0.12,0.38), architecture)
    prism("Distant mineral plane", [(-4,-5),(4,-5),(4,7),(-4,7)],
        0.35, mineral, (-7,13,1.8), (0,0.16,-0.3), architecture)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-3.1))
    floor = bpy.context.object
    floor.name = "Continuous mineral floor"
    floor.data.materials.append(mineral)
    floor.parent = architecture

    def area(name, position, power, color, size, target=(0, 0, 0)):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.color, data.shape, data.size = power, color, "DISK", size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()

    area("Large softbox", (0, -4, 7), 2300, (0.94, 0.97, 1.0), 7)
    area("Warm strip reflection", (6, -1, 2), 2600, (1, 0.78, 0.56), 6)
    area("Cool edge", (-4, 2, 4), 2000, (0.46, 0.70, 1), 5)
    area("Front fill", (-3, -6, 1), 1600, (0.87, 0.92, 1), 7)

    # Export model only; browser owns lighting, camera and motion.
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for child in root.children:
        child.select_set(True)
    architecture.select_set(True)
    for child in architecture.children:
        child.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=str(output / "optical-assembly.glb"),
        export_format="GLB", use_selection=True, export_yup=True, export_apply=True,
        export_cameras=False, export_lights=False)

    camera_data = bpy.data.cameras.new("Editorial camera")
    camera = bpy.data.objects.new("Editorial camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 11.4
    camera.location = (4.8, -12, 3.8)
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    # Lens on the right; the left is reserved for the unchanged headline.
    camera_data.shift_x = -0.20
    scene.render.filepath = str(output / "optical-poster.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "optical-assembly.blend"))
    bpy.ops.render.render(write_still=True)
    camera_data.shift_x = 0
    camera_data.ortho_scale = 6.9
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1100
    scene.render.filepath = str(output / "optical-mobile-poster.png")
    bpy.ops.render.render(write_still=True)
    (output / "render-receipt.json").write_text(json.dumps({"blender": bpy.app.version_string,
        "source": "scripts/create_optical_hero.py", "textures": "none",
        "model": "optical-assembly.glb", "samples": args.samples,
        "artwork": "Original light-and-material architecture; no depiction of product hardware."}, indent=2))


if __name__ == "__main__":
    main()
