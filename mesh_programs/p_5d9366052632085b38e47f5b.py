"""Executable construction for exact source5d9366052632085b38e47f5b.
Design proposal: metal wall returns based on individually measured support sections
and folded-tray lip. Retains every original polygon and its UV corner values.
This implementation is experimental until actual CPU candidate validation.
"""
import math,collections
SOURCE_ID='5d9366052632085b38e47f5b'
SOURCE_SHA256='8ce82690b5ef61c7a862dfff592d8d6d3d8f26a95f0ca193595d85cad7a095ed'
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
 # Recover actual boundary loops in each member's intrinsic frame: no world-Y or fixed-size assumptions.
 def cycles(pairs):
  adjacency={}
  for a,b in pairs:adjacency.setdefault(a,set()).add(b);adjacency.setdefault(b,set()).add(a)
  assert all(len(v)==2 for v in adjacency.values()),'Source member boundary is open or branching'
  todo=set(adjacency);loops=[]
  while todo:
   first=min(todo);loop=[first];previous=None;current=first
   while True:
    following=min(adjacency[current]-({previous} if previous is not None else set()))
    if following==first:break
    assert following not in loop,'Boundary repeats before closure';loop.append(following);previous,current=current,following
   todo-=set(loop);loops.append(loop)
  return loops
 ring_ids=set(range(2,12));ring_edges=[edge for edge,records in adj.items() if sum(pid in ring_ids for pid,a,b in records)==1];ring_loops=cycles(ring_edges);assert sorted(map(len,ring_loops))==[4,6],'Source folded tray profile changed'
 outer=next(loop for loop in ring_loops if len(loop)==4);opening=next(loop for loop in ring_loops if len(loop)==6)
 def segment_distance(p,a,b):
  delta=sub(b,a);t=max(0,min(1,sum((p[k]-a[k])*delta[k] for k in range(3))/sum(x*x for x in delta)));return math.dist(p,tuple(a[k]+t*delta[k] for k in range(3)))
 lip=min(segment_distance(points[i],points[a],points[b]) for i in opening for a,b in zip(outer,outer[1:]+outer[:1]));outer_width=min(math.dist(points[a],points[b]) for a,b in zip(outer,outer[1:]+outer[:1]));assert 0<lip<outer_width*.1,'Unannotated tray lip proportion'
 gauges={0:lip*.1};profiles=[]
 for part,ids in enumerate(POST_FACES,1):
  ids=set(ids);ends=cycles([edge for edge,records in adj.items() if len(records)==1 and records[0][0] in ids]);assert len(ends)==2 and all(len(loop)==4 for loop in ends),'Support does not have two actual four-corner ends'
  lengths=[];centres=[];end_normals=[]
  for loop in ends:
   p=[points[i] for i in loop];vectors=[sub(b,a) for a,b in zip(p,p[1:]+p[:1])];edges=[norm(v) for v in vectors];assert min(edges)>0,'Collapsed support end'
   normal=cross(vectors[0],vectors[1]);normal=tuple(x/norm(normal) for x in normal);assert abs(sum((p[3][k]-p[0][k])*normal[k] for k in range(3)))<=max(edges)*.02,'Source support end is nonplanar'
   assert max(abs(sum(vectors[i][k]*vectors[(i+1)%4][k] for k in range(3)))/(edges[i]*edges[(i+1)%4]) for i in range(4))<.05,'Source section is not rectangular'
   assert max(abs(edges[0]-edges[2]),abs(edges[1]-edges[3]))<max(edges)*.05,'Source opposite section edges differ'
   lengths.append(edges);centres.append(tuple(sum(p[j][k] for j in range(4))/4 for k in range(3)));end_normals.append(normal)
  assert math.dist(*centres)>max(sum(lengths,[]))*5,'Source member is not an elongated support'
  assert max(abs(a-b)/max(a,b) for a,b in zip(sorted(lengths[0]),sorted(lengths[1])))<.05,'Unannotated support taper'
  gauges[part]=min(sum(lengths,[]))*.05;profiles.append(dict(endpoint_centres=centres,endpoint_normals=end_normals,edge_lengths=lengths,proposed_inward_corner_offset=gauges[part]))
 inner=[]
 for i,p in enumerate(points):
  n=normal_sums[i];length=norm(n);assert length>1e-12
  inner.append(tuple(p[a]-n[a]/length*gauges[point_parts[i]] for a in range(3)))
 count=len(points);result_points=points+inner;result_faces=[];result_uv=[];source_ids=[];parameter_triangles=[];parameter_weights=[]
 for pid,face in enumerate(faces):
  result_faces.append(face);result_uv.append(corner_uv[pid]);source_ids.append(pid);parameter_triangles.append(pid);parameter_weights.append([(1,0,0),(0,1,0),(0,0,1)])
  result_faces.append([v+count for v in reversed(face)]);result_uv.append(list(reversed(corner_uv[pid])));source_ids.append(-1);parameter_triangles.append(pid);parameter_weights.append([(0,0,1),(0,1,0),(1,0,0)])
 for edge,records in adj.items():
  if len(records)!=1:continue
  pid,a,b=records[0];face=faces[pid];ia=face.index(a);ib=face.index(b);uv_a=corner_uv[pid][ia];uv_b=corner_uv[pid][ib]
  result_faces.extend([[b,a,a+count],[b,a+count,b+count]]);result_uv.extend([[uv_b,uv_a,uv_a],[uv_b,uv_a,uv_b]]);source_ids.extend([-1,-1]);basis=[(1,0,0),(0,1,0),(0,0,1)];parameter_triangles.extend([pid,pid]);parameter_weights.extend([[basis[ib],basis[ia],basis[ia]],[basis[ib],basis[ia],basis[ib]]])
 incidence=collections.Counter(tuple(sorted((a,b))) for face in result_faces for a,b in zip(face,face[1:]+face[:1]));assert all(n==2 for n in incidence.values()),'Manufactured wall return failed topology'
 assert {i for i in source_ids if i>=0}==set(range(44))
 return dict(vertices=result_points,faces=result_faces,corner_uv=result_uv,source_polygon_ids=source_ids,proposal_wall_gauges_local=gauges,physical_parts=4,measured_member_profiles=profiles,parameter_triangles=parameter_triangles,parameter_weights=parameter_weights,original_outer_surfaces_unchanged=True,tray_opening_retained=True)


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
 for name,kind,domain in [('source_parameter_triangle','INT','FACE'),('source_parameter_barycentric','FLOAT_VECTOR','CORNER')]:
  old_attribute=new.attributes.get(name)
  if old_attribute:new.attributes.remove(old_attribute)
  new.attributes.new(name=name,type=kind,domain=domain)
 for face,index,weights in zip(new.polygons,result['parameter_triangles'],result['parameter_weights']):
  new.attributes['source_parameter_triangle'].data[face.index].value=index
  for loop,weight in zip(face.loop_indices,weights):new.attributes['source_parameter_barycentric'].data[loop].vector=weight
 obj.data=new;obj['validate_source_face_provenance']=True;obj['require_source_parameter_audit']=True;obj['require_all_source_triangles_parameter_coverage']=True
 profile=result['measured_member_profiles'][0];tray=set(v for p in old.polygons if p.index in TRAY_FACES for v in p.vertices);tray_centre=sum((old.vertices[v].co for v in tray),Vector())/len(tray);ends=[Vector(p) for p in profile['endpoint_centres']];selected=max(range(2),key=lambda i:(ends[i]-tray_centre).length);target=ends[selected];normal=Vector(profile['endpoint_normals'][selected])
 if normal.dot(ends[selected]-ends[1-selected])<0:normal.negate()
 obj['drain_source_normal_world']=list((obj.matrix_world.to_3x3().inverted().transposed()@normal).normalized());obj['drain_review_target_local']=list(target);obj['drain_review_span']=max(profile['edge_lengths'][selected])*3*max(abs(v) for v in obj.scale)
 obj['frame_wall_gauge_design_proposal']=True
 return ['three_individually_measured_support_member_wall_returns','separate_folded_tray_wall_return_preserving_open_recess','all44_original_polygons_and_all_loop_UVs_unchanged_on_outer_surface','four_closed_manufactured_member_volumes','wall_gauges_explicit_design_proposal_not_original_measurements','no_invented_fasteners_or_welds']
