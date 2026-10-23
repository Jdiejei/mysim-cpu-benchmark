"""Exact printed-panel substrate: original graphic spans retained, actual frame fit checked.
Proposed substrate thickness is10percent of measured frame-back clearance.
No invented panel joints, fixtures, graphic changes or native-unit claims.
"""
import math,collections,statistics
SOURCE_ID='9bc1e7a2c88884f0013610f1'
SOURCE_SHA256='bfcbd20fe1eae3829e02d232633a8b02551cf5a107d277322e27aedca85a9690'
FRAME_MESH='prop_billboard_a_base_b_001'

def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
 n=math.sqrt(sum(x*x for x in a));assert n>1e-12;return tuple(x/n for x in a)

def construct(vertices,faces,corner_uv,thickness,reference_uv):
 assert len(vertices)==8 and len(faces)==4 and len(corner_uv)==4
 points=[];groups={};mapping={}
 for i,p in enumerate(vertices):
  key=tuple(p)
  if key not in groups:groups[key]=len(points);points.append(key)
  mapping[i]=groups[key]
 assert len(points)==6,'Printed span boundary changed'
 original=[[mapping[v] for v in face] for face in faces];normals=[[0.,0.,0.] for _ in points];edges=collections.defaultdict(list)
 for pid,face in enumerate(original):
  normal=cross(sub(points[face[1]],points[face[0]]),sub(points[face[2]],points[face[0]]))
  for i in face:
   for axis in range(3):normals[i][axis]+=normal[axis]
  for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))].append((pid,a,b))
 assert all(len(records) in [1,2] for records in edges.values());boundary=[records[0] for records in edges.values() if len(records)==1];assert len(boundary)==6
 span=max(max(p[a] for p in points)-min(p[a] for p in points) for a in range(3));assert 0<thickness<=span*.003,'Proposed substrate exceeds existing source envelope'
 normals=[unit(n) for n in normals];back=[tuple(p[a]-normal[a]*thickness for a in range(3)) for p,normal in zip(points,normals)];positions=points+back;result_faces=[];values=[];materials=[];source_ids=[]
 for pid,face in enumerate(original):
  result_faces.append(face);values.append(corner_uv[pid]);materials.append(0);source_ids.append(pid)
  reverse=[v+6 for v in reversed(face)];result_faces.append(reverse);values.append([reference_uv(positions[v],True) for v in reverse]);materials.append(1);source_ids.append(-1)
 for pid,a,b in boundary:
  for face in [[b,a,a+6],[b,a+6,b+6]]:
   result_faces.append(face);values.append([reference_uv(positions[v],False) for v in face]);materials.append(1);source_ids.append(-1)
 incidence=collections.Counter(tuple(sorted((a,b))) for face in result_faces for a,b in zip(face,face[1:]+face[:1]));assert set(incidence.values())=={2},'Panel substrate is not closed'
 return dict(vertices=positions,faces=result_faces,corner_uv=values,materials=materials,source_polygon_ids=source_ids,original_graphics_and_span_shape_unchanged=True,thickness_is_proposed=True)

def apply(obj,recipe):
 import bpy
 from mathutils import Vector
 from mathutils.geometry import closest_point_on_tri,barycentric_transform
 assert recipe['procedure_id']==SOURCE_ID and recipe['source_sha256']==SOURCE_SHA256
 mesh=obj.data;assert len(mesh.vertices)==8 and len(mesh.polygons)==4 and len(mesh.uv_layers)==2
 frame=bpy.context.scene.objects.get(FRAME_MESH);assert frame and len(frame.data.vertices)==78 and len(frame.data.polygons)==44,'Actual matching source frame unavailable'
 transform=obj.matrix_world.inverted()@frame.matrix_world;frame_points=[transform@v.co for v in frame.data.vertices];points=[v.co.copy() for v in mesh.vertices];span=max(max(p[a] for p in points)-min(p[a] for p in points) for a in range(3))
 assert all(min((p-q).length for q in frame_points)<=span*1e-6 for p in points),'Printed boundary no longer matches actual frame opening'
 front_normal=Vector(unit(cross(sub(points[mesh.polygons[0].vertices[1]],points[mesh.polygons[0].vertices[0]]),sub(points[mesh.polygons[0].vertices[2]],points[mesh.polygons[0].vertices[0]]))))
 reference=frame_points[frame.data.polygons[12].vertices[0]];clearances=[(p-reference).dot(front_normal) for p in points];assert min(clearances)>0 and max(clearances)/min(clearances)<1.01,'Unresolved frame-back clearance';thickness=statistics.median(clearances)*.1
 uv=[[[list(layer.data[loop].uv) for layer in mesh.uv_layers] for loop in face.loop_indices] for face in mesh.polygons]
 def reference_uv(point,back):
  point=Vector(point);choices=[]
  for pid in ([12,13] if back else list(range(18))+[42,43]):
   polygon=frame.data.polygons[pid];corners=[frame_points[i] for i in polygon.vertices];near=closest_point_on_tri(point,*corners);choices.append(((near-point).length,pid,near,corners))
  distance,pid,near,corners=min(choices,key=lambda q:q[0]);face=frame.data.polygons[pid];return [tuple(barycentric_transform(near,*corners,*[Vector((*layer.data[loop].uv,0)) for loop in face.loop_indices])[:2]) for layer in frame.data.uv_layers]
 result=construct([list(p) for p in points],[list(p.vertices) for p in mesh.polygons],uv,thickness,reference_uv)
 new=mesh.copy();new.clear_geometry();new.from_pydata(result['vertices'],[],result['faces']);new.update()
 for layer in list(new.uv_layers):new.uv_layers.remove(layer)
 for index,old_layer in enumerate(mesh.uv_layers):
  layer=new.uv_layers.new(name=old_layer.name)
  for face,corners in zip(new.polygons,result['corner_uv']):
   for loop,values in zip(face.loop_indices,corners):layer.data[loop].uv=values[index]
 for face,material in zip(new.polygons,result['materials']):face.material_index=material
 attribute=new.attributes.get('source_polygon_id')
 if attribute:new.attributes.remove(attribute)
 attribute=new.attributes.new(name='source_polygon_id',type='INT',domain='FACE')
 for i,pid in enumerate(result['source_polygon_ids']):attribute.data[i].value=pid
 obj.data=new;obj['validate_source_face_provenance']=True;obj['panel_measured_frame_clearance']=statistics.median(clearances);obj['panel_proposed_thickness']=thickness;obj['drain_source_normal_world']=list((obj.matrix_world.to_3x3().inverted().transposed()@front_normal).normalized());obj['drain_review_target_local']=list(points[4]-front_normal*thickness*.5);obj['drain_review_span']=max(obj.dimensions)*.035
 return ['source_printed_front_spans_and_all_graphic_UVs_retained','substrate_fits_actual_six_point_frame_opening','measured_reference_frame_clearance_drives_explicit_proposed_substrate_thickness','new_back_and_returns_use_actual_source_frame_material_and_UV_lightmap_references','closed_printed_panel_volume_no_invented_printed_joints_or_fittings']
