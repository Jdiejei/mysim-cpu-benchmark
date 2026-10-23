"""Executable construction for exact sourcec063f053341bdc555ad3080d.
Design proposal: metal wall returns based on individually measured support sections
and folded-tray lip. Retains every original polygon and its UV corner values.
This implementation is experimental until actual CPU candidate validation.
"""
import math,collections
SOURCE_ID='c063f053341bdc555ad3080d'
SOURCE_SHA256='0a712f92007785a76c62275724ddbbe877c986f33b0118fe403272a43bf37d22'
POST_FACES=[list(range(18,26)),list(range(26,34)),list(range(34,42))]
TRAY_FACES=list(range(18))+[42,43]

def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def norm(v):return math.sqrt(sum(x*x for x in v))

def construct(vertices,polygons,corner_uv):
 assert len(vertices)==78 and len(polygons)==44 and len(corner_uv)==44
 assert sorted(TRAY_FACES+sum(POST_FACES,[]))==list(range(44))
 grouped={};lookup={};points=[]
 for i,p in enumerate(vertices):
  key=tuple(p)
  if key not in grouped:grouped[key]=len(points);points.append(key)
  lookup[i]=grouped[key]
 assert len(points)==38,'Actual geometric source inventory changed'
 faces=[[lookup[v] for v in face] for face in polygons];adj=collections.defaultdict(list)
 for pid,face in enumerate(faces):
  assert len(face)==3
  for a,b in zip(face,face[1:]+face[:1]):adj[tuple(sorted((a,b)))].append((pid,a,b))
 assert all(len(v)<=2 for v in adj.values()),'Original geometric source nonmanifold'
 ownership={pid:part for part,ids in enumerate([TRAY_FACES]+POST_FACES) for pid in ids};normal_sums=[[0.,0.,0.] for _ in points];point_parts={}
 for pid,face in enumerate(faces):
  normal=cross(sub(points[face[1]],points[face[0]]),sub(points[face[2]],points[face[0]]))
  for i in face:
   assert i not in point_parts or point_parts[i]==ownership[pid],'Unannotated interface between members'
   point_parts[i]=ownership[pid]
   for axis in range(3):normal_sums[i][axis]+=normal[axis]
 # Explicit proposed design dimensions in source-local units, not original wall gauges.
 # Each support uses its own measured endpoint edge minimum. Tray gauge uses measured0.05lip.
 tray_vertices={v for pid in TRAY_FACES for v in faces[pid]};opening=set(v for (a,b),records in adj.items() if len(records)==1 and records[0][0] in TRAY_FACES for v in [a,b])
 assert len(opening)==6,'Measured six-point tray opening changed'
 tray_y=[points[v][1] for v in tray_vertices];opening_y=[points[v][1] for v in opening];lip=min(max(tray_y)-max(opening_y),min(opening_y)-min(tray_y))
 assert 0<lip<(max(tray_y)-min(tray_y))*.1,'Tray lip requires individual annotation'
 gauges={0:lip*.1}
 for part,ids in enumerate(POST_FACES,1):
  vs={v for pid in ids for v in faces[pid]};low=min(points[v][1] for v in vs)
  edges=[math.dist(points[a],points[b]) for (a,b),records in adj.items() if a in vs and b in vs and abs(points[a][1]-low)<1e-7 and abs(points[b][1]-low)<1e-7]
  assert len(edges)==4 and .09<min(edges)<.11
  gauges[part]=min(edges)*.05
 inner=[]
 for i,p in enumerate(points):
  n=normal_sums[i];length=norm(n);assert length>1e-12
  inner.append(tuple(p[a]-n[a]/length*gauges[point_parts[i]] for a in range(3)))
 count=len(points);result_points=points+inner;result_faces=[];result_uv=[];source_ids=[]
 for pid,face in enumerate(faces):
  result_faces.append(face);result_uv.append(corner_uv[pid]);source_ids.append(pid)
  result_faces.append([v+count for v in reversed(face)]);result_uv.append(list(reversed(corner_uv[pid])));source_ids.append(-1)
 for edge,records in adj.items():
  if len(records)!=1:continue
  pid,a,b=records[0];face=faces[pid];ia=face.index(a);ib=face.index(b);uv_a=corner_uv[pid][ia];uv_b=corner_uv[pid][ib]
  result_faces.extend([[b,a,a+count],[b,a+count,b+count]]);result_uv.extend([[uv_b,uv_a,uv_a],[uv_b,uv_a,uv_b]]);source_ids.extend([-1,-1])
 incidence=collections.Counter(tuple(sorted((a,b))) for face in result_faces for a,b in zip(face,face[1:]+face[:1]));assert all(n==2 for n in incidence.values()),'Manufactured wall return failed topology'
 assert {i for i in source_ids if i>=0}==set(range(44))
 return dict(vertices=result_points,faces=result_faces,corner_uv=result_uv,source_polygon_ids=source_ids,proposal_wall_gauges_local=gauges,physical_parts=4,original_outer_surfaces_unchanged=True,tray_opening_retained=True)


def apply(obj,recipe):
 from mathutils import Vector
 assert recipe['procedure_id']==SOURCE_ID and recipe['source_sha256']==SOURCE_SHA256,'Wrong original source for executable procedure'
 mesh=obj.data;assert len(mesh.uv_layers)==2
 uv=[[[list(layer.data[loop].uv) for layer in mesh.uv_layers] for loop in face.loop_indices] for face in mesh.polygons]
 result=construct([list(v.co) for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons],uv)
 old=mesh;new=old.copy();new.clear_geometry();new.from_pydata(result['vertices'],[],result['faces']);new.update()
 for layer in list(new.uv_layers):new.uv_layers.remove(layer)
 for index,old_layer in enumerate(old.uv_layers):
  layer=new.uv_layers.new(name=old_layer.name)
  for face,corners in zip(new.polygons,result['corner_uv']):
   for loop,values in zip(face.loop_indices,corners):layer.data[loop].uv=values[index]
 attribute=new.attributes.get('source_polygon_id')
 if attribute:new.attributes.remove(attribute)
 attribute=new.attributes.new(name='source_polygon_id',type='INT',domain='FACE')
 for i,pid in enumerate(result['source_polygon_ids']):attribute.data[i].value=pid
 obj.data=new;obj['validate_source_face_provenance']=True
 post=set(v for p in old.polygons if p.index in POST_FACES[0] for v in p.vertices);top=max(old.vertices[v].co.y for v in post);ids=[v for v in post if abs(old.vertices[v].co.y-top)<1e-7];target=sum((old.vertices[v].co for v in ids),Vector())/len(ids)
 obj['drain_source_normal_world']=list((obj.matrix_world.to_3x3().inverted().transposed()@Vector((0,1,0))).normalized());obj['drain_review_target_local']=list(target);obj['drain_review_span']=.35*max(abs(v) for v in obj.scale)
 obj['frame_wall_gauge_design_proposal']=True
 return ['three_individually_measured_support_member_wall_returns','separate_folded_tray_wall_return_preserving_open_recess','all44_original_polygons_and_all_loop_UVs_unchanged_on_outer_surface','four_closed_manufactured_member_volumes','wall_gauges_explicit_design_proposal_not_original_measurements','no_invented_fasteners_or_welds']
