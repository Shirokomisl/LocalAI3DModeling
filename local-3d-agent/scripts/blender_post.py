import bpy, sys, math
from pathlib import Path
from mathutils import Vector

src=Path(sys.argv[-2]).resolve()
out=Path(sys.argv[-1]).resolve()
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(src))
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
if not meshes: raise RuntimeError("No mesh in generated GLB")

for o in meshes:
    bpy.context.view_layer.objects.active=o; o.select_set(True)
    bpy.ops.object.shade_smooth()
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.00005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

# Center and ground the complete figure without changing proportions.
all_pts=[]
for o in meshes:
    for v in o.data.vertices:
        all_pts.append(o.matrix_world @ v.co)
mn=Vector((min(v.x for v in all_pts),min(v.y for v in all_pts),min(v.z for v in all_pts)))
mx=Vector((max(v.x for v in all_pts),max(v.y for v in all_pts),max(v.z for v in all_pts)))
center=(mn+mx)/2
for o in meshes: o.location.x-=center.x; o.location.y-=center.y; o.location.z-=mn.z

# Neutral studio material only when source mesh has no material.
mat=bpy.data.materials.new("Studio gray"); mat.diffuse_color=(0.55,0.55,0.55,1)
for o in meshes:
    if not o.data.materials: o.data.materials.append(mat)

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:o.select_set(True)
bpy.ops.object.convert(target="MESH")

# Actually write the processed mesh to the requested GLB path.
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True)

# Four diagnostic renders: front, left, back, right.
# The camera always targets the model center so QA can inspect volume from every side.
target=Vector((0,0,(mx.z-mn.z)*.48))
radius=max(6,(mx-mn).length*2.2)
views=[
    ("front",(0,-radius,max(1,(mx.z-mn.z)*.45))),
    ("left",(-radius,0,max(1,(mx.z-mn.z)*.45))),
    ("back",(0,radius,max(1,(mx.z-mn.z)*.45))),
    ("right",(radius,0,max(1,(mx.z-mn.z)*.45)))
]
bpy.ops.object.camera_add(location=views[0][1])
cam=bpy.context.object
bpy.context.scene.camera=cam
for loc,energy,size in [((4,-6,6),1000,5),((-4,-3,3),600,4),((0,2,5),400,3)]:
    bpy.ops.object.light_add(type="AREA",location=loc)
    bpy.context.object.data.energy=energy; bpy.context.object.data.size=size
sc=bpy.context.scene; sc.render.engine="BLENDER_EEVEE"
sc.render.resolution_x=700; sc.render.resolution_y=850; sc.render.resolution_percentage=100
sc.world.color=(.025,.025,.03)
for name,loc in views:
    cam.location=loc
    cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
    preview=out.with_name(out.stem+f"_preview_{name}.png")
    sc.render.filepath=str(preview)
    bpy.ops.render.render(write_still=True)
# Keep the old filename as the front-view compatibility output.
front=out.with_name(out.stem+"_preview_front.png")
compat=out.with_name(out.stem+"_preview.png")
try:
    import shutil
    shutil.copy2(front,compat)
except Exception:
    pass
bpy.ops.wm.save_as_mainfile(filepath=str(out.with_suffix(".blend")))
# Blender selects the newly-created camera; reselect only the mesh before STL export.
bpy.ops.object.select_all(action="DESELECT")
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.wm.stl_export(filepath=str(out.with_suffix(".stl")), export_selected_objects=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out.with_suffix(".blend")))
print("POSTPROCESS_OK",out)
