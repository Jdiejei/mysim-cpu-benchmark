import bpy,bmesh,math,time
from mathutils import Vector
from detail_ops import make_material,grass_detail
from armco_ops import armco_geometry,armco_material
from tyre_ops import tyre_geometry,tyre_material
from kerb_ops import kerb_geometry
from source_fidelity import source_fidelity
from drain_ops import drain_geometry
from source_surface_ops import refine_source_surface

def rebuild(obj,recipe,root):
 start=time.monotonic();original=obj.data;before={'vertices':len(original.vertices),'faces':len(original.polygons),'uv_layers':len(original.uv_layers),'bounds':list(obj.dimensions)};assert before['vertices']>2 and before['faces']>0,'Empty source'
 collision=obj.copy();collision.data=original.copy();collision.name=obj.name+'__original_collision';collision.hide_render=True;bpy.context.collection.objects.link(collision)
 obj.data=original.copy();
 if recipe.get('validate_source_face_provenance'):
  attribute=obj.data.attributes.new(name='source_polygon_id',type='INT',domain='FACE')
  for polygon in obj.data.polygons:attribute.data[polygon.index].value=polygon.index
  obj['validate_source_face_provenance']=True
 bm=bmesh.new();bm.from_mesh(obj.data);scale=max(max(obj.dimensions),.001);tolerance=min(.00001,scale*.000001)/max(max(abs(v) for v in obj.scale),1e-8)
 
 if recipe.get('reconstruction_mode')!='source_surface_refinement':
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance*.1)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
 bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
 category=recipe['category'];is_drain=category=='ground' and 'drain' in obj.name.lower();is_kerb=category=='ground' and any(t in obj.name.lower() for t in ['curb','kerb','ripple']);is_tyre=any(t in obj.name.lower() for t in ['tyre','tire']) and 'single' in obj.name.lower();source_refinement=recipe.get('reconstruction_mode')=='source_surface_refinement';component_changes=refine_source_surface(obj) if source_refinement else armco_geometry(obj) if category=='barrier' and 'armco' in obj.name.lower() else tyre_geometry(obj) if is_tyre else kerb_geometry(obj,recipe) if is_kerb else drain_geometry(obj,recipe) if is_drain else [];changes=['separate_original_collision_preserved',('source_connectivity_preserved_without_cross_surface_welding' if source_refinement else 'scale_aware_duplicate_and_degenerate_repair'),'consistent_surface_normals'];extras=[collision];changes.extend(component_changes)
 rebuilt_bm=bmesh.new();rebuilt_bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(rebuilt_bm,faces=list(rebuilt_bm.faces));nonmanifold=sum(not e.is_manifold for e in rebuilt_bm.edges);rebuilt_bm.to_mesh(obj.data);rebuilt_bm.free();assert nonmanifold==0,'Reconstructed component has nonmanifold edges';changes.append('closed_manifold_and_outward_normals_checked')
 # Surface thickness and road shape are never invented. Structural edges are dimensioned in world units.
 if not (source_refinement and recipe.get('preserve_source_front_edges')) and (category not in {'ground','grass','decal','vegetation','crowd'} or any(x in obj.name.lower() for x in ['curb','kerb','ripple','drain'])):
  edge=obj.modifiers.new('Dimensioned six-segment manufactured edge','BEVEL');edge.width=min(.003,scale*.001)/max(max(abs(v) for v in obj.scale),1e-8);edge.segments=6;edge.limit_method='ANGLE';edge.angle_limit=math.radians(35);edge.use_clamp_overlap=True;edge.harden_normals=True;bpy.ops.object.modifier_apply(modifier=edge.name);changes.append('six_segment_dimensioned_edge_geometry')
  normals=obj.modifiers.new('Area weighted manufactured normals','WEIGHTED_NORMAL');normals.keep_sharp=True
  try:bpy.ops.object.modifier_apply(modifier=normals.name)
  except RuntimeError:obj.modifiers.remove(normals)
 obj.data.materials.clear()
 for binding in recipe['material_bindings']:obj.data.materials.append(make_material(binding,root,category))
 if component_changes and not (is_kerb or is_drain or source_refinement):
  obj.data.materials.clear();obj.data.materials.append(tyre_material() if is_tyre else armco_material());changes.append('new_family_material_source_atlas_retained_as_provenance_not_stretched_onto_new_UVs')
 if category=='grass':
  grass,_=grass_detail(obj,recipe)
  if grass:extras.append(grass);changes.append('curved_blade_cluster_geometry')
 assert all(math.isfinite(x) for v in obj.data.vertices for x in v.co),'Nonfinite mesh'
 assert len(obj.data.uv_layers)==before['uv_layers'],'UV layers lost'
 delta=max(abs(obj.dimensions[i]-before['bounds'][i]) for i in range(3));callback=recipe.get('_operator_progress_callback');callback(dict(stage='bounds_diagnostic',before_bounds=before['bounds'],after_bounds=list(obj.dimensions),delta=delta,relative_depth=obj.get('drain_relative_slot_depth'),source_normal=list(obj.get('drain_source_normal_world',[])))) if callback else None;assert delta<=max(.01,scale*.002),f'Silhouette bounds changed excessively: before={before["bounds"]}, after={list(obj.dimensions)}, delta={delta}'
 for poly in obj.data.polygons:assert 0<=poly.material_index<max(1,len(obj.data.materials)),'Material index out of range'
 fidelity=source_fidelity(obj,collision) if (is_kerb or is_drain or source_refinement) else None
 if fidelity:assert fidelity['source_profile_within_tolerance'],'Source surface distances exceed source-relative profile tolerance: '+str(fidelity)
 if source_refinement:assert fidelity['uv1_unambiguous_page_mismatches']==0,'Encoded UV1 page changed in source refinement'
 if source_refinement:assert max(fidelity.get('uv0_max_error') or 0,fidelity.get('uv1_max_error') or 0)<=.001,'Source UV projection is ambiguous or changed beyond0.001; hold for dedicated review: '+str(fidelity)
 lodstats=[]
 for level,ratio in enumerate([.65,.3,.12],1):
  lod=obj.copy();lod.data=obj.data.copy();lod.name=obj.name+'__LOD'+str(level);bpy.context.collection.objects.link(lod);bpy.context.view_layer.objects.active=lod;mod=lod.modifiers.new('Runtime simplification','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
  try:bpy.ops.object.modifier_apply(modifier=mod.name)
  except RuntimeError:lod.modifiers.remove(mod)
  lod.hide_render=True;extras.append(lod);lodstats.append({'level':level,'vertices':len(lod.data.vertices),'faces':len(lod.data.polygons)})
 obj['rebuild_procedure_id']=recipe['procedure_id'];obj['quality_accepted']=False;obj['collision_reference']=collision.name
 return {'before':before,'after':{'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'uv_layers':len(obj.data.uv_layers)},'changes':changes,'lods':lodstats,'bounds_max_delta':delta,'source_fidelity':fidelity,'operator_telemetry':{k:obj[k] if isinstance(obj[k],(str,int,float,bool)) else list(obj[k]) for k in obj.keys() if k.startswith('drain_')},'automated_checks_passed':True,'scope':'procedural_geometry_reconstruction_candidate','semantic_redesign_validated':False,'quality_accepted':False,'seconds':time.monotonic()-start,'review_required':['visual_detail_and_reference_fidelity','category_specific_missing_components','Unity_material_collision_LOD_performance']},extras

def render_review(obj,extra,path,detail_only=False):
 # Inspect only this candidate, on CPU, from three views; preserve generated scene objects in saved asset.
 scene=bpy.context.scene;visibility={o.name:o.hide_render for o in scene.objects}
 for o in scene.objects:o.hide_render=True
 obj.hide_render=False
 for o in extra:
  if 'grass_detail' in o.name:o.hide_render=False
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.render.resolution_x=384;scene.render.resolution_y=384;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
 if scene.world is None:scene.world=bpy.data.worlds.new('Review world')
 bpy.context.view_layer.update();scene.world.color=(.15,.15,.15);centre=obj.matrix_world@(sum((Vector(corner) for corner in obj.bound_box),Vector())/8);radius=max(max(obj.dimensions),.0001)
 review_normal=Vector(obj['drain_source_normal_world']) if 'drain_source_normal_world' in obj else None
 lampdata=bpy.data.lights.new('Review key','AREA');lampdata.energy=1000*radius*radius;lampdata.shape='DISK';lampdata.size=radius*2;lamp=bpy.data.objects.new('Review key',lampdata);scene.collection.objects.link(lamp);lamp.location=centre+Vector((radius,-radius,radius*2));lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler();lamp.hide_render=False
 if review_normal is not None:
  light_tangent=review_normal.cross(Vector((0,0,1))) if abs(review_normal.z)<.9 else review_normal.cross(Vector((0,1,0)));light_tangent.normalize();lamp.location=centre+review_normal*radius*2+light_tangent*radius;lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler()
 camdata=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;camdata.clip_start=radius*.001;camdata.clip_end=radius*100;camdata.type='ORTHO';camdata.ortho_scale=radius*1.5
 images=[]
 for i,direction in enumerate([] if detail_only else [(1,-1,.8),(-1,-1,.35),(0,0,2)]):
  cam.location=centre+Vector(direction)*radius*2;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(path.parent/(path.stem+f'-review-{i}.png'));bpy.ops.render.render(write_still=True);images.append(scene.render.filepath)
 # Close-up evidence complements full silhouettes of long, thin track assets.
 normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
 upward=[p for p in obj.data.polygons if (normal_matrix@p.normal).normalized().z>.2]
 polygon=max(upward or list(obj.data.polygons),key=lambda p:p.area)
 target=obj.matrix_world@polygon.center;normal=(normal_matrix@polygon.normal).normalized()
 corners=[obj.matrix_world@obj.data.vertices[i].co for i in polygon.vertices];longest=max((a-b).length for a,b in zip(corners,corners[1:]+corners[:1]));area=sum((corners[i]-corners[0]).cross(corners[i+1]-corners[0]).length/2 for i in range(1,len(corners)-1));width=2*area/max(longest,1e-12)
 if 'drain_review_target_local' in obj:
  target=obj.matrix_world@Vector(obj['drain_review_target_local']);normal=Vector(obj['drain_source_normal_world']);width=float(obj['drain_review_span'])/6
 camdata.ortho_scale=max(radius*.025,min(radius*.25,width*6));tangent=normal.cross(Vector((0,0,1))) if abs(normal.z)<.9 else normal.cross(Vector((0,1,0)));tangent.normalize();cam.location=target+normal*radius*1.5+tangent*radius;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.resolution_x=512;scene.render.resolution_y=512;scene.cycles.samples=64;scene.render.filepath=str(path.parent/(path.stem+'-review-detail.png'));bpy.ops.render.render(write_still=True);images.append(scene.render.filepath)
 bpy.data.objects.remove(cam,do_unlink=True);bpy.data.objects.remove(lamp,do_unlink=True)
 for o in scene.objects:
  if o.name in visibility:o.hide_render=visibility[o.name]
 return images
