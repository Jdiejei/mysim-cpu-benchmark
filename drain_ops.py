import bpy,bmesh,math,json,statistics,time
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.geometry import delaunay_2d_cdt
from drain_uv_geometry import area,clip_convex,capsule
from drain_uv_charts import partition_uv_charts

def drain_geometry(obj,recipe):
 start=time.monotonic();last_emit=0;callback=recipe.get('_operator_progress_callback')
 def emit(stage,force=False,**data):
  nonlocal last_emit
  if not callback or (not force and time.monotonic()-last_emit<20):return
  try:
   import resource
   data['peak_RSS_MiB']=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1)
  except ImportError:pass
  data.update(stage=stage,operator_elapsed_seconds=round(time.monotonic()-start,2));callback(data);last_emit=time.monotonic()
 emit('reading_source_grate_reference',force=True)
 bindings=[t for m in recipe['material_bindings'] for t in m.get('textures',[]) if t['property']=='_BaseMap'];assert len(bindings)==1,'Dedicated grate requires one resolved base reference';binding=bindings[0];trench_kind=recipe.get('dedicated_trench_reference');trench=trench_kind in {'trench_01','trench_04'};reference_path={'trench_01':'/gnd_drain_trench_01.png','trench_04':'/gnd_drain_trench_04.png'}.get(trench_kind,'/gnd_base_drain_01.png');assert binding['path'].endswith(reference_path),'Dedicated grate reference not supported';pattern=json.loads((Path(__file__).parent/({'trench_01':'trench-01-pattern.json','trench_04':'trench-04-pattern.json'}.get(trench_kind,'drain-pattern.json'))).read_text());w=pattern['width'];h=pattern['height'];weights=pattern['weights'];raw_boxes=pattern['slot_regions'];full_height=statistics.median(y1-y0 for x0,y0,x1,y1 in raw_boxes if y0>.001 and y1<.999);boxes=[]
 for x0,y0,x1,y1 in raw_boxes:
  if y0<.001:y0=y1-full_height
  if y1>.999:y1=y0+full_height
  boxes.append((x0,y0,x1,y1))
 sx=binding.get('scale',{}).get('x',1);sy=binding.get('scale',{}).get('y',1);ox=binding.get('offset',{}).get('x',0);oy=binding.get('offset',{}).get('y',0);old=obj.data;old.calc_loop_triangles();names=[u.name for u in old.uv_layers];assert names and sx and sy,'Source grate UV transform invalid';matrix=obj.matrix_world.copy();linear=matrix.to_3x3();scale=max(obj.dimensions);origin=Vector(tuple((min(v.co[i] for v in old.vertices)+max(v.co[i] for v in old.vertices))/2 for i in range(3)));ratios=[]
 def uvpoint(index):
  uv=old.uv_layers[0].data[index].uv;return (uv.x*sx+ox,uv.y*sy+oy)
 for tri in old.loop_triangles:
  for a,b in [(0,1),(1,2),(2,0)]:
   distance=math.dist(uvpoint(tri.loops[a]),uvpoint(tri.loops[b]))
   if distance>1e-6:ratios.append((linear@(old.vertices[tri.vertices[a]].co-old.vertices[tri.vertices[b]].co)).length/distance)
 assert ratios,'No resolved source UV-to-surface scale';depth=statistics.median(ratios)*.0006;source_normal=sum(((linear@(old.vertices[t.vertices[1]].co-old.vertices[t.vertices[0]].co)).cross(linear@(old.vertices[t.vertices[2]].co-old.vertices[t.vertices[0]].co)) for t in old.loop_triangles),Vector()).normalized();assert source_normal.length>.9,'Unresolved source cover normal';down=linear.inverted()@(-source_normal*depth);vertices=[];faces=[];materials=[];uv_values=[[] for _ in names];tile_count=0;max_uv_span=0;maximum_weight=0;moved=0
 def sample(point):
  x=(point[0]%1)*w-.5;y=(point[1]%1)*h-.5;ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
  return sum(weights[((iy+dy)%h)*w+(ix+dx)%w]*(fx if dx else 1-fx)*(fy if dy else 1-fy) for dx,dy in [(0,0),(1,0),(0,1),(1,1)])
 # Blender4.5 CDT API verified against official mathutils_geometry.cc.
 # Tile clipping avoids raster subdivision of long/repeated source UV spans.
 if recipe.get('prototype_source_tile_only'):
  # One CDT across the source cover keeps every source triangle seam conforming.
  chart_groups=partition_uv_charts(old.loop_triangles,uvpoint);emit('source_uv_chart_partition',force=True,chart_count=len(chart_groups))
  for chart in chart_groups:
   triangles=[];points=[];edges=[];chart_vertex_cache={}
   for tri in chart:
    uv=[uvpoint(i) for i in tri.loops];a,b,c=uv;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(den)<1e-12:continue
    triangles.append((tri,uv,den));base=len(points);points.extend(uv);edges.extend((base+i,base+(i+1)%3) for i in range(3))
   assert triangles,'Empty cover source UV domain'
   min_tx=math.floor(min(p[0] for p in points)+1e-6);min_ty=math.floor(min(p[1] for p in points)+1e-6);max_tx=math.ceil(max(p[0] for p in points)-1e-6);max_ty=math.ceil(max(p[1] for p in points)-1e-6);tile_area=(max_tx-min_tx)*(max_ty-min_ty);assert 1<=tile_area<=64,'Component bounded tile limit exceeded'
   for tx in range(min_tx,max_tx):
    for ty in range(min_ty,max_ty):
     domain=[(tx,ty),(tx+1,ty),(tx+1,ty+1),(tx,ty+1)]
     for box in boxes:
      radius=(box[3]-box[1])/2
      for ring in range(6):
       contour=clip_convex([(x+tx,y+ty) for x,y in capsule(*box,inset=radius*.4*ring/5,segments=16)],domain)
       if contour:
        # Ignore slot contours with no positive-area intersection with this actual source chart.
        relevant=any(abs(area(clip_convex(contour,t[1])))>1e-14 for t in triangles)
        if not relevant:continue
        base=len(points);points.extend(contour);edges.extend((base+i,base+(i+1)%len(contour)) for i in range(len(contour)))
   result=delaunay_2d_cdt([Vector(p) for p in points],edges,[],0,1e-8,False)
   def bary(p,uv,den):
    a,b,c=uv;wa=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den;wb=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;return (wa,wb,1-wa-wb)
   for face in result[2]:
    uvface=[tuple(result[0][i]) for i in face];center=tuple(sum(p[k] for p in uvface)/3 for k in range(2));matches=[t for t in triangles if min(bary(center,t[1],t[2]))>=-1e-6]
    if not matches:continue
    assert sum(min(bary(center,t[1],t[2]))>=1e-5 for t in matches)<=1,'Overlapping source UV triangles in cover:'+json.dumps(dict(face=uvface,center=center,matches=[dict(uv=t[1],den=t[2],bary=bary(center,t[1],t[2])) for t in matches]))
    tri,uv,den=max(matches,key=lambda t:min(bary(center,t[1],t[2])));face_indices=[]
    for point in uvface:
     blend=bary(point,uv,den);normal_local=sum((old.vertices[tri.vertices[j]].normal*blend[j] for j in range(3)),Vector()).normalized();normal_world=(linear.inverted().transposed()@normal_local).normalized();point_down=linear.inverted()@(-normal_world*depth);amount=sample(point);maximum_weight=max(maximum_weight,amount);position=tuple(sum(blend[j]*old.vertices[tri.vertices[j]].co[k] for j in range(3))-origin[k]+point_down[k]*amount for k in range(3));layers=tuple(tuple(sum(blend[j]*layer.data[tri.loops[j]].uv[k] for j in range(3)) for k in range(2)) for layer in old.uv_layers);vertex_key=(position,layers)
     if vertex_key not in chart_vertex_cache:
      chart_vertex_cache[vertex_key]=len(vertices);vertices.append(position);moved+=amount>1e-6
      for layer_index,value in enumerate(layers):uv_values[layer_index].append(value)
     face_indices.append(chart_vertex_cache[vertex_key])
    faces.append(tuple(face_indices));materials.append(tri.material_index);assert len(vertices)<600000 and len(faces)<1000000,'Component geometry budget exceeded'
   tile_count+=tile_area;max_uv_span=max(max_uv_span,max_tx-min_tx,max_ty-min_ty);emit('globally_constrained_source_cover',force=True,generated_vertices=len(vertices),generated_faces=len(faces),source_triangles=len(triangles))
 else:
  for tri in old.loop_triangles:
   uv=[uvpoint(i) for i in tri.loops];a,b,c=uv;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);coords=[tuple(old.vertices[i].co) for i in tri.vertices];layer_values=[[tuple(layer.data[i].uv) for i in tri.loops] for layer in old.uv_layers]
   if abs(den)<1e-12:
    base=len(vertices)
    for j in range(3):
     vertices.append(tuple(coords[j][k]-origin[k] for k in range(3)))
     for layer_index in range(len(names)):uv_values[layer_index].append(layer_values[layer_index][j])
    faces.append((base,base+1,base+2));materials.append(tri.material_index);continue
   span_u=max(p[0] for p in uv)-min(p[0] for p in uv);span_v=max(p[1] for p in uv)-min(p[1] for p in uv);max_uv_span=max(max_uv_span,span_u,span_v);assert (math.ceil(span_u)+1)*(math.ceil(span_v)+1)<20000,'Source UV tile bounding budget exceeded:'+str((span_u,span_v))
   for tx in range(math.floor(min(p[0] for p in uv)),math.floor(max(p[0] for p in uv))+1):
    for ty in range(math.floor(min(p[1] for p in uv)),math.floor(max(p[1] for p in uv))+1):
     domain=clip_convex(uv,[(tx,ty),(tx+1,ty),(tx+1,ty+1),(tx,ty+1)])
     if not domain:continue
     tile_count+=1;emit('building_physical_slot_tiles',tile_fragments=tile_count,generated_vertices=len(vertices),generated_faces=len(faces));assert time.monotonic()-start<4*3600,'Single-grate prototype compute budget exceeded';assert tile_count<=10000,'Source grate tile-fragment budget exceeded';domain=[(x-tx,y-ty) for x,y in domain];points=list(domain);edges=[(i,(i+1)%len(points)) for i in range(len(points))]
     for box in boxes:
      radius=(box[3]-box[1])/2
      for ring in range(6):
       contour=clip_convex(capsule(*box,inset=radius*.4*ring/5,segments=16),domain)
       if not contour:continue
       base=len(points);points.extend(contour);edges.extend((base+i,base+(i+1)%len(contour)) for i in range(len(contour)))
     result=delaunay_2d_cdt([Vector(p) for p in points],edges,[],0,1e-8,False);base=len(vertices)
     for point in result[0]:
      p=(point.x+tx,point.y+ty);wa=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den;wb=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;blend=(wa,wb,1-wa-wb);amount=sample(p);maximum_weight=max(maximum_weight,amount);moved+=amount>1e-6;vertices.append(tuple(sum(blend[j]*coords[j][k] for j in range(3))-origin[k]+down[k]*amount for k in range(3)))
      for layer_index in range(len(names)):uv_values[layer_index].append(tuple(sum(blend[j]*layer_values[layer_index][j][k] for j in range(3)) for k in range(2)))
     for face in result[2]:faces.append(tuple(base+i for i in face));materials.append(tri.material_index)
     assert len(vertices)<600000 and len(faces)<1000000,'Constrained grate geometry budget exceeded; no automatic quality downgrade'
 emit('closing_source_following_backing',force=True,tile_fragments=tile_count,generated_vertices=len(vertices),generated_faces=len(faces))
 preserved_gutter=trench_kind=='trench_01' and recipe.get('preserved_gutter_source_component')==5
 if preserved_gutter:
  assert recipe.get('prototype_component_index')==5 and recipe.get('prototype_parent_procedure_id')=='9c0fd01c5398b78cf220f753','Unsupported preserved gutter identity'
  assert maximum_weight==0 and moved==0,'Preserved gutter unexpectedly intersects grate mask'
  assert max(uvpoint(i)[0] for t in old.loop_triangles for i in t.loops)<.5,'Preserved gutter extends into grate panel'
 if not (moved and maximum_weight>.5) and not preserved_gutter:
  bounds=[[min(uvpoint(i)[k] for t in old.loop_triangles for i in t.loops) for k in range(2)],[max(uvpoint(i)[k] for t in old.loop_triangles for i in t.loops) for k in range(2)]]
  emit('no_slot_source_context',force=True,transformed_UV_bounds=bounds,maximum_slot_weight=maximum_weight)
  if recipe.get('diagnose_no_slot_context'):
   from detail_ops import make_material
   from rebuild_ops import render_review
   obj.data.materials.clear()
   for binding in recipe['material_bindings']:obj.data.materials.append(make_material(binding,Path(__file__).parent/'wave-input',recipe['category']))
   obj['drain_source_normal_world']=list(source_normal)
   directory=Path(recipe['_diagnostic_directory']);images=render_review(obj,[],directory/(recipe['procedure_id']+'-source-context.blend'))
   (directory/'source-context.json').write_text(json.dumps(dict(transformed_UV_bounds=bounds,maximum_slot_weight=maximum_weight,source_only_images=images,geometry_not_upgraded=True)))
  raise AssertionError('No physical slot recesses resolved; source context retained')
 mesh=bpy.data.meshes.new(old.name+'__physical_grate');mesh.from_pydata(vertices,[],faces);mesh.update()
 for layer_index,name in enumerate(names):
  layer=mesh.uv_layers.new(name=name)
  for loop in mesh.loops:layer.data[loop.index].uv=uv_values[layer_index][loop.vertex_index]
 for poly,material in zip(mesh.polygons,materials):poly.material_index=material
 obj.data=mesh;obj.matrix_world=matrix@Matrix.Translation(origin);bpy.context.view_layer.update();bm=bmesh.new();bm.from_mesh(mesh);tolerance=max(max(abs(v) for v in obj.dimensions)/max(linear.col[i].length for i in range(3))*2e-7,1e-7);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance*.1);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));# Adjacent independently constrained source triangles can introduce boundary T junctions.
 boundary_vertices=list({v for e in bm.edges if e.is_boundary for v in e.verts});splits=0
 for edge in list(bm.edges):
  if not edge.is_valid or not edge.is_boundary:continue
  pending=[edge]
  while pending:
   current=pending.pop();a,b=current.verts;direction=b.co-a.co;length2=direction.length_squared
   if length2<=tolerance*tolerance:continue
   for v in boundary_vertices:
    if v in current.verts:continue
    factor=(v.co-a.co).dot(direction)/length2
    if tolerance/math.sqrt(length2)<factor<1-tolerance/math.sqrt(length2) and (a.co+direction*factor-v.co).length<tolerance:
     new_edge,new_vertex=bmesh.utils.edge_split(current,a,factor);new_vertex.co=v.co;pending.extend([current,new_edge]);splits+=1;assert splits<20000,'Boundary conformity split budget exceeded';break
 bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance)
 # Degenerate dissolution can leave collinear multi-edge polygons along long source constraints.
 # Only discard zero-width ngons below the existing positional tolerance, with a strict area budget.
 slivers=[];total_area=sum(f.calc_area() for f in bm.faces)
 for face in bm.faces:
  if len(face.verts)<=3:continue
  a,b=max(((a,b) for a in face.verts for b in face.verts),key=lambda pair:(pair[0].co-pair[1].co).length_squared);direction=b.co-a.co
  if direction.length_squared and max((v.co-a.co).cross(direction).length/direction.length for v in face.verts)<=tolerance:slivers.append(face)
 removed_area=sum(f.calc_area() for f in slivers);assert removed_area<=total_area*1e-5,'Zero-width cleanup exceeded source area budget'
 if slivers:
  bmesh.ops.delete(bm,geom=slivers,context='FACES_ONLY');loose=[e for e in bm.edges if not e.link_faces]
  if loose:bmesh.ops.delete(bm,geom=loose,context='EDGES')
 emit('zero_width_constraint_polygon_cleanup',force=True,removed_zero_width_ngons=len(slivers),removed_area_fraction=removed_area/max(total_area,1e-20));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));boundaries=sum(e.is_boundary for e in bm.edges);excess=sum(len(e.link_faces)>2 for e in bm.edges);emit('top_surface_edge_incidence',force=True,edges=len(bm.edges),vertices=len(bm.verts),faces=len(bm.faces),boundary_edges=boundaries,excess_incidence_edges=excess)
 if excess:
  rejected=[dict(edge_length=e.calc_length(),vertices=[list(v.co) for v in e.verts],linked_face_areas=[f.calc_area() for f in e.link_faces],linked_face_vertices=[[list(v.co) for v in f.verts] for f in e.link_faces]) for e in bm.edges if len(e.link_faces)>2];emit('rejected_top_surface_diagnostics',force=True,excess_incidence_edges=excess,rejected_edges=rejected[:8]);directory=recipe.get('_diagnostic_directory')
  if directory:
   diag=bpy.data.meshes.new('rejected_topology_diagnostic');bm.to_mesh(diag);previous=obj.data;obj.data=diag;bpy.data.libraries.write(str(Path(directory)/(recipe['procedure_id']+'-rejected-topology.blend')),{obj},compress=True);obj.data=previous
  raise AssertionError('Top surface has overlapping or multiply incident faces; diagnostic retained')
 emit('conforming_source_triangle_seams',force=True,boundary_T_junction_splits=splits,boundary_edges=boundaries);top_vertices=len(bm.verts);top_faces=len(bm.faces);bm.to_mesh(mesh);bm.free();mesh.update()
 if boundaries:
  shell=obj.modifiers.new('Closed physical grate backing','SOLIDIFY');shell.solidify_mode='NON_MANIFOLD';shell.nonmanifold_thickness_mode='CONSTRAINTS';shell.thickness=depth*.5/max(linear.col[i].length for i in range(3));shell.offset=-1;shell.use_even_offset=True;shell.use_quality_normals=True;bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=shell.name)
 emit('physical_slot_geometry_complete',force=True,tile_fragments=tile_count,generated_vertices=top_vertices,generated_faces=top_faces)
 candidates=[i for i,p in enumerate(uv_values[0]) if sample((p[0]*sx+ox,p[1]*sy+oy))>.7];assert candidates or preserved_gutter,'Missing physical well review target';candidates=candidates or list(range(len(vertices)));review_index=min(candidates,key=lambda i:((uv_values[0][i][0]*sx+ox)%1-.5)**2+((uv_values[0][i][1]*sy+oy)%1-.5)**2);obj['drain_review_target_local']=list(vertices[review_index]);obj['drain_review_span']=statistics.median(ratios)*.3;obj['drain_source_normal_world']=list(source_normal)
 obj['drain_source_UV_charts']=len(chart_groups) if recipe.get('prototype_source_tile_only') else 0;obj['drain_relative_slot_depth']=depth;obj['drain_displaced_vertices']=moved;obj['drain_top_vertices']=top_vertices;obj['drain_top_faces']=top_faces;obj['drain_UV_tile_fragments']=tile_count;obj['drain_max_source_UV_span']=max_uv_span;obj['drain_local_origin_offset']=list(origin);obj['drain_geometry_seconds']=time.monotonic()-start
 return [('source_context_verified_gutter_only_preserved_without_invented_slots' if preserved_gutter else 'source_reference_right_panel_27_slot_regions_left_gutter_preserved' if trench else 'source_reference12_slot_regions'),'UV_tile_clipped_constrained_triangulation','six_ring_rounded_physical_slot_lips_and_recessed_wells','source_weathering_UV0_and_lightmap_UV1_preserved_without_repacking','local_origin_precision_recenter_with_original_world_placement_preserved','closed_source_following_backing','original_driving_collision_retained']
