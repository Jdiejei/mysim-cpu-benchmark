import bpy,bmesh,math,time
from mathutils import Vector
from detail_ops import make_material,grass_detail
from armco_ops import armco_geometry

def rebuild(obj,recipe,root):
 start=time.monotonic();original=obj.data;before={'vertices':len(original.vertices),'faces':len(original.polygons),'uv_layers':len(original.uv_layers),'bounds':list(obj.dimensions)};assert before['vertices']>2 and before['faces']>0,'Empty source'
 collision=obj.copy();collision.data=original.copy();collision.name=obj.name+'__original_collision';collision.hide_render=True;bpy.context.collection.objects.link(collision)
 obj.data=original.copy();bm=bmesh.new();bm.from_mesh(obj.data);scale=max(max(obj.dimensions),.001);tolerance=min(.00001,scale*.000001)/max(max(abs(v) for v in obj.scale),1e-8)
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance*.1);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
 category=recipe['category'];component_changes=armco_geometry(obj) if category=='barrier' and 'armco' in obj.name.lower() else [];changes=['separate_original_collision_preserved','scale_aware_duplicate_and_degenerate_repair','consistent_surface_normals'];extras=[collision];changes.extend(component_changes)
 # Surface thickness and road shape are never invented. Structural edges are dimensioned in world units.
 if category not in {'ground','grass','decal','vegetation','crowd'} or any(x in obj.name.lower() for x in ['curb','kerb']):
  edge=obj.modifiers.new('Dimensioned six-segment manufactured edge','BEVEL');edge.width=min(.003,scale*.001)/max(max(abs(v) for v in obj.scale),1e-8);edge.segments=6;edge.limit_method='ANGLE';edge.angle_limit=math.radians(35);edge.use_clamp_overlap=True;edge.harden_normals=True;bpy.ops.object.modifier_apply(modifier=edge.name);changes.append('six_segment_dimensioned_edge_geometry')
  normals=obj.modifiers.new('Area weighted manufactured normals','WEIGHTED_NORMAL');normals.keep_sharp=True
  try:bpy.ops.object.modifier_apply(modifier=normals.name)
  except RuntimeError:obj.modifiers.remove(normals)
 obj.data.materials.clear()
 for binding in recipe['material_bindings']:obj.data.materials.append(make_material(binding,root,category))
 if category=='grass':
  grass,_=grass_detail(obj,recipe)
  if grass:extras.append(grass);changes.append('curved_blade_cluster_geometry')
 assert all(math.isfinite(x) for v in obj.data.vertices for x in v.co),'Nonfinite mesh'
 assert len(obj.data.uv_layers)==before['uv_layers'],'UV layers lost'
 delta=max(abs(obj.dimensions[i]-before['bounds'][i]) for i in range(3));assert delta<=max(.01,scale*.002),'Silhouette bounds changed excessively'
 for poly in obj.data.polygons:assert 0<=poly.material_index<max(1,len(obj.data.materials)),'Material index out of range'
 lodstats=[]
 for level,ratio in enumerate([.65,.3,.12],1):
  lod=obj.copy();lod.data=obj.data.copy();lod.name=obj.name+'__LOD'+str(level);bpy.context.collection.objects.link(lod);bpy.context.view_layer.objects.active=lod;mod=lod.modifiers.new('Runtime simplification','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
  try:bpy.ops.object.modifier_apply(modifier=mod.name)
  except RuntimeError:lod.modifiers.remove(mod)
  lod.hide_render=True;extras.append(lod);lodstats.append({'level':level,'vertices':len(lod.data.vertices),'faces':len(lod.data.polygons)})
 obj['rebuild_procedure_id']=recipe['procedure_id'];obj['quality_accepted']=False;obj['collision_reference']=collision.name
 return {'before':before,'after':{'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'uv_layers':len(obj.data.uv_layers)},'changes':changes,'lods':lodstats,'bounds_max_delta':delta,'automated_checks_passed':True,'scope':'procedural_geometry_reconstruction_candidate','semantic_redesign_validated':False,'quality_accepted':False,'seconds':time.monotonic()-start,'review_required':['visual_detail_and_reference_fidelity','category_specific_missing_components','Unity_material_collision_LOD_performance']},extras

def render_review(obj,extra,path):
 # Inspect only this candidate, on CPU, from three views; preserve generated scene objects in saved asset.
 scene=bpy.context.scene;visibility={o.name:o.hide_render for o in scene.objects}
 for o in scene.objects:o.hide_render=True
 obj.hide_render=False
 for o in extra:
  if 'grass_detail' in o.name:o.hide_render=False
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.render.resolution_x=384;scene.render.resolution_y=384;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
 if scene.world is None:scene.world=bpy.data.worlds.new('Review world')
 scene.world.color=(.15,.15,.15);centre=obj.matrix_world@(sum((Vector(corner) for corner in obj.bound_box),Vector())/8);radius=max(max(obj.dimensions),.1)
 lampdata=bpy.data.lights.new('Review key','AREA');lampdata.energy=1000;lampdata.shape='DISK';lampdata.size=radius*2;lamp=bpy.data.objects.new('Review key',lampdata);scene.collection.objects.link(lamp);lamp.location=centre+Vector((radius,-radius,radius*2));lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler();lamp.hide_render=False
 camdata=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.type='ORTHO';camdata.ortho_scale=radius*1.5
 images=[]
 for i,direction in enumerate([(1,-1,.8),(-1,-1,.35),(0,0,2)]):
  cam.location=centre+Vector(direction)*radius*2;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(path.parent/(path.stem+f'-review-{i}.png'));bpy.ops.render.render(write_still=True);images.append(scene.render.filepath)
 bpy.data.objects.remove(cam,do_unlink=True);bpy.data.objects.remove(lamp,do_unlink=True)
 for o in scene.objects:
  if o.name in visibility:o.hide_render=visibility[o.name]
 return images
