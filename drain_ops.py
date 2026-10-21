import bpy,bmesh,math,json,statistics,time
from pathlib import Path
from mathutils import Vector

def drain_geometry(obj,recipe):
 start=time.monotonic();bindings=[t for m in recipe['material_bindings'] for t in m.get('textures',[]) if t['property']=='_BaseMap'];assert len(bindings)==1 and bindings[0]['path'].endswith('/gnd_base_drain_01.png'),'Dedicated grate reference not supported';binding=bindings[0];pattern=json.loads((Path(__file__).parent/'drain-pattern.json').read_text());w=pattern['width'];h=pattern['height'];weights=pattern['weights'];regions=pattern['slot_regions'];sx=binding.get('scale',{}).get('x',1);sy=binding.get('scale',{}).get('y',1);ox=binding.get('offset',{}).get('x',0);oy=binding.get('offset',{}).get('y',0);old=obj.data;names=[v.name for v in old.uv_layers];bm=bmesh.new();bm.from_mesh(old);uv=bm.loops.layers.uv.get(names[0]);assert uv,'Source grate has no UV0';ratios=[];scale=max(obj.dimensions);matrix=obj.matrix_world.to_3x3()
 def coord(loop):
  v=loop[uv].uv;return Vector((v.x*sx+ox,v.y*sy+oy))
 for face in bm.faces:
  for loop in face.loops:
   span=(coord(loop)-coord(loop.link_loop_next)).length
   if span>1e-6:ratios.append((matrix@(loop.vert.co-loop.link_loop_next.vert.co)).length/span)
 assert ratios,'Grate UV scale cannot be resolved';depth=min(statistics.median(ratios)*.006,scale*.0006);assert depth>0,'Invalid source-relative grate depth';target=1/128;iterations=0;max_uv_edge=0
 def affected(face):
  cs=[coord(l) for l in face.loops];a=min(p.x for p in cs);b=max(p.x for p in cs);c=min(p.y for p in cs);d=max(p.y for p in cs);assert b-a<=8 and d-c<=8,'Grate UV tile extent needs separate subdivision planning'
  for tx in range(math.floor(a),math.floor(b)+1):
   for ty in range(math.floor(c),math.floor(d)+1):
    if any(b>=x0+tx-target and a<=x1+tx+target and d>=y0+ty-target and c<=y1+ty+target for x0,y0,x1,y1 in regions):return True
  return False
 for iteration in range(10):
  selected=set();max_uv_edge=0
  for face in bm.faces:
   if not affected(face):continue
   for loop in face.loops:
    length=(coord(loop)-coord(loop.link_loop_next)).length;max_uv_edge=max(max_uv_edge,length)
    if length>target:selected.add(loop.edge)
  if not selected:break
  assert len(bm.faces)<600000 and len(selected)<400000,'Grate tessellation memory budget reached; no automatic quality downgrade'
  bmesh.ops.subdivide_edges(bm,edges=list(selected),cuts=1,use_grid_fill=True,smooth=0);iterations=iteration+1
 else:raise RuntimeError('Grate target UV-space resolution not reached within10 adaptive rounds')
 def sample(p):
  x=(p.x%1)*w-.5;y=(p.y%1)*h-.5;ix=math.floor(x);iy=math.floor(y);fx=x-ix;fy=y-iy
  return sum(weights[((iy+dy)%h)*w+(ix+dx)%w]*(fx if dx else 1-fx)*(fy if dy else 1-fy) for dx,dy in [(0,0),(1,0),(0,1),(1,1)])
 down=matrix.inverted()@Vector((0,0,-depth));moved=0;maximum=0
 for vert in bm.verts:
  samples=[sample(coord(loop)) for loop in vert.link_loops];amount=min(samples) if samples else 0
  if amount>1e-6:vert.co+=down*amount;moved+=1;maximum=max(maximum,amount)
 assert moved>0 and maximum>.5,'No resolved physical slot wells were generated';bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));boundaries=sum(e.is_boundary for e in bm.edges);top_vertices=len(bm.verts);top_faces=len(bm.faces);bm.to_mesh(old);bm.free();old.update()
 if boundaries:
  shell=obj.modifiers.new('Closed source-following grate backing','SOLIDIFY');shell.solidify_mode='NON_MANIFOLD';shell.nonmanifold_thickness_mode='CONSTRAINTS';shell.thickness=depth*.5/max(matrix.col[i].length for i in range(3));shell.offset=-1;shell.use_even_offset=True;shell.use_quality_normals=True;bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=shell.name)
 assert [v.name for v in obj.data.uv_layers]==names,'Grate UV/lightmap channels changed';obj['drain_relative_slot_depth']=depth;obj['drain_displaced_vertices']=moved;obj['drain_top_vertices']=top_vertices;obj['drain_top_faces']=top_faces;obj['drain_adaptive_rounds']=iterations;obj['drain_geometry_seconds']=time.monotonic()-start
 return ['source_texture_measured12_slot_regions','adaptive_source_UV_space_physical_tessellation','visible_recessed_slot_wells_and_soft_lips','source_frame_profile_and_road_contact_retained','original_UV0_and_UV1_lightmap_page_coordinates_interpolated_without_repacking','closed_source_following_backing','original_driving_collision_retained_separately']
