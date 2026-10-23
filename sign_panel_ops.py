import math,json,statistics
from pathlib import Path
from mathutils import Vector
from sign_profile_geometry import construct
SUPPORTED={'26d2a66fd51dc1e10a731ebb','e239e5bb0c4164e73b9487a4','17601e0a17d701965ee7ad44'}
def sign_geometry(obj,recipe):
 assert recipe['procedure_id'] in SUPPORTED,'Sign profile operator only validated against explicitly annotated source'
 assert recipe['source_sha256']=='06fdd8a6d522c22d0951024067cf86ff0025c6ad55f61cbc9df41427c013b926','Unannotated source revision'
 bindings=recipe['material_bindings'];assert len(bindings)==1
 base=next(t for t in bindings[0]['textures'] if t['property']=='_BaseMap');assert base['path'].endswith('/prop_laguna_seca_billboard_ground/prop_laguna_seca_billboard_ground.png')
 assert base['scale']=={'x':1.0,'y':-1.0} and base['offset']=={'x':0.0,'y':1.0},'Source texture transform changed'
 mesh=obj.data;assert len(mesh.vertices)==38 and len(mesh.polygons)==28,'Annotated billboard inventory changed';assert len(mesh.uv_layers)==2;frontfaces=set(range(10,18));frontvertices=sorted({i for p in mesh.polygons if p.index in frontfaces for i in p.vertices});assert len(frontvertices)==10;positions=[v.co.copy() for v in mesh.vertices];span=max(max(v[a] for v in positions)-min(v[a] for v in positions) for a in range(3));tol=span*1e-8;normals={i:Vector() for i in frontvertices}
 areas=[]
 for face in mesh.polygons:
  uv=[mesh.uv_layers[0].data[j].uv for j in face.loop_indices];assert len(uv)==3
  a,b,c=uv;area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5;areas.append(area)
  assert (area>1e-8)==(face.index in frontfaces),'Printed-front polygon annotation mismatch'
 assert abs(sum(areas)-1.0)<1e-6,'Printed-front UV domain coverage changed'
 for face in mesh.polygons:
  if face.index in frontfaces:
   for i in face.vertices:normals[i]+=face.normal*face.area
 normals={i:n.normalized() for i,n in normals.items()};pairs={};frontmap={};weights={};vertex_uv={}
 for face in mesh.polygons:
  for i,loop in zip(face.vertices,face.loop_indices):vertex_uv.setdefault(i,[tuple(layer.data[loop].uv) for layer in mesh.uv_layers])
 for i,p in enumerate(positions):
  nearest=min(frontvertices,key=lambda k:(positions[k]-p).length);distance=(positions[nearest]-p).length;frontmap[i]=nearest;weights[i]=1.0 if distance<=tol else 0.0
  if distance>tol:
   assert distance<span*.01,'Source includes unannotated support or separate component';previous=pairs.get(nearest)
   if previous is not None:assert (positions[previous]-p).length<=tol,'Ambiguous measured back rim'
   pairs[nearest]=i
 assert set(pairs)==set(frontvertices),'Measured rear rim incomplete'
 # Open disconnected strips have ambiguous recalculated normals. The actual rear rim fixes orientation.
 for i in frontvertices:
  if (positions[i]-positions[pairs[i]]).dot(normals[i])<0:normals[i].negate()
 thicknesses=[(positions[k]-positions[v]).dot(normals[k]) for k,v in pairs.items()];thickness=statistics.median(thicknesses);assert min(thicknesses)>0 and max(thicknesses)/min(thicknesses)<1.1,'Nonuniform profile requires separate annotation';depth=thickness*.2;surfaces=[]
 for face in mesh.polygons:
  corners=[]
  for i,loop in zip(face.vertices,face.loop_indices):corners.append(dict(position=tuple(positions[i]),u=float(mesh.uv_layers[0].data[loop].uv.x),uv=[tuple(layer.data[loop].uv) for layer in mesh.uv_layers],normal=tuple(normals[frontmap[i]]),front=weights[i]))
  surfaces.append(dict(corners=corners,source_polygon=face.index))
 # Close the actual measured rear rim; no guessed rear thickness or support posts.
 for face in mesh.polygons:
  if face.index not in frontfaces:continue
  corners=[]
  for i in reversed(face.vertices):
   back=pairs[i];uv=vertex_uv[back];corners.append(dict(position=tuple(positions[back]),u=float(vertex_uv[i][0][0]),uv=uv,normal=tuple(normals[i]),front=0.0))
  surfaces.append(dict(corners=corners,source_polygon=-1))
 centres=[(pixel+.5)/512 for pixel in [63,129,195,256,318,382,448]]
 result=construct(surfaces,centres,1/512,depth,tol);folder=Path(recipe['_diagnostic_directory']);(folder/'sign-profile-topology.json').write_text(json.dumps({k:v for k,v in result.items() if k not in ['vertices','faces','corner_uv']},indent=2));assert not result['nonmanifold_edges'],'Sign source-profile shell has nonmanifold edges';assert result['changed_corner_occurrences']>0
 target_u=centres[3];target_v=1.5;target=None;target_normal=None
 for face in mesh.polygons:
  if face.index not in frontfaces:continue
  ids=list(face.vertices);uv=[mesh.uv_layers[0].data[i].uv.copy() for i in face.loop_indices];a,b,c=uv;det=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);assert abs(det)>1e-12
  t=((target_u-a.x)*(c.y-a.y)-(target_v-a.y)*(c.x-a.x))/det;u=((b.x-a.x)*(target_v-a.y)-(b.y-a.y)*(target_u-a.x))/det;weights2=[1-t-u,t,u]
  if min(weights2)>=-1e-8:
   target=sum((positions[i]*w for i,w in zip(ids,weights2)),Vector());target_normal=sum((normals[i]*w for i,w in zip(ids,weights2)),Vector()).normalized();break
 assert target is not None,'Joint close-up target not in original printed surface';target-=target_normal*depth
 old=mesh;new=old.copy();new.clear_geometry();new.from_pydata(result['vertices'],[],result['faces']);new.update()
 for layer in list(new.uv_layers):new.uv_layers.remove(layer)
 for index,original_layer in enumerate(old.uv_layers):
  layer=new.uv_layers.new(name=original_layer.name)
  for face,corners in zip(new.polygons,result['corner_uv']):
   for loop,uv in zip(face.loop_indices,corners):layer.data[loop].uv=uv[index]
 existing=new.attributes.get('source_polygon_id')
 if existing:new.attributes.remove(existing)
 attribute=new.attributes.new(name='source_polygon_id',type='INT',domain='FACE')
 for i,source_polygon in enumerate(result['source_polygons']):attribute.data[i].value=source_polygon
 obj.data=new;obj['validate_source_face_provenance']=True;obj['sign_measured_relative_depth']=depth;obj['sign_measured_backing_thickness']=thickness;obj['sign_joint_count']=7;obj['drain_source_normal_world']=list((obj.matrix_world.to_3x3().inverted().transposed()@target_normal).normalized());obj['drain_review_target_local']=list(target);obj['drain_review_span']=span*max(abs(v) for v in obj.scale)*.04;obj['sign_operator_scope']='one annotated original billboard body only; no invented fixtures';return ['source_billboard_front_and_four_profile_edges_reconstructed','seven_texture_evidenced_rounded_physical_panel_joints','rear_closed_at_original_measured_rim','original_curve_material_ST_and_all_UVs_preserved','no_invented_supports_fasteners_or_branding_changes']
