import math,statistics
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,closest_point_on_tri

def source_fidelity(candidate,source,limit=1200):
 mesh=candidate.data;original=source.data;mesh.calc_loop_triangles();original.calc_loop_triangles();vertices=[candidate.matrix_world@v.co for v in mesh.vertices];triangles=[tuple(t.vertices) for t in mesh.loop_triangles];tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);distances=[];uv_errors=[];uv1_errors=[];page_matches=[]
 provenance=mesh.attributes.get('source_polygon_id') if candidate.get('validate_source_face_provenance') else None;provenance_faces={}
 if provenance:
  for index,target in enumerate(mesh.loop_triangles):provenance_faces.setdefault(provenance.data[target.polygon_index].value,[]).append(index)
 source_vertices=list(original.vertices);step=max(1,math.ceil(len(source_vertices)/limit))
 for v in source_vertices[::step]:
  nearest=tree.find_nearest(source.matrix_world@v.co)
  if nearest[0] is None:raise RuntimeError('No reconstructed source-nearest surface')
  distances.append(nearest[3])
 source_uv=original.uv_layers[0] if original.uv_layers else None;target_uv=mesh.uv_layers.get(source_uv.name) if source_uv else None;tris=list(original.loop_triangles);step=max(1,math.ceil(len(tris)/limit))
 for tri in tris[::step]:
  point=sum((source.matrix_world@original.vertices[i].co for i in tri.vertices),Vector())/3;near,normal,index,distance=tree.find_nearest(point)
  if near is None:raise RuntimeError('Missing reconstructed face-nearest surface')
  distances.append(distance)
  if candidate.get('validate_source_face_provenance'):
   assert provenance,'Source polygon provenance lost'
   indices=provenance_faces.get(tri.polygon_index,[]);assert indices,'Original source polygon missing from candidate'
   choices=[]
   for target_index in indices:
    target=mesh.loop_triangles[target_index];a,b,c=[vertices[i] for i in target.vertices]
    if (b-a).cross(c-a).length_squared<=1e-24:continue
    projected_point=closest_point_on_tri(point,a,b,c);choices.append(((projected_point-point).length,target_index,projected_point))
   assert choices,'No nondegenerate candidate source polygon';distance,index,near=min(choices,key=lambda x:x[0]);assert distance<=max(max(source.dimensions),1e-8)*.003,'Corresponding source polygon moved beyond source profile tolerance'
  if source_uv and target_uv:
   expected=sum((source_uv.data[i].uv for i in tri.loops),Vector((0,0)))/3;target=mesh.loop_triangles[index];corners=[vertices[i] for i in target.vertices];uvs=[Vector((*target_uv.data[i].uv,0)) for i in target.loops]
   if (corners[1]-corners[0]).cross(corners[2]-corners[0]).length_squared>1e-24:
    projected=barycentric_transform(near,*corners,*uvs);uv_errors.append((Vector((projected.x,projected.y))-expected).length)
  if len(original.uv_layers)>1 and len(mesh.uv_layers)>1:
   layer=original.uv_layers[1];target_layer=mesh.uv_layers.get(layer.name);target=mesh.loop_triangles[index];corners=[vertices[i] for i in target.vertices]
   if target_layer and (corners[1]-corners[0]).cross(corners[2]-corners[0]).length_squared>1e-24:
    expected=sum((layer.data[i].uv for i in tri.loops),Vector((0,0)))/3;projected=barycentric_transform(near,*corners,*[Vector((*target_layer.data[i].uv,0)) for i in target.loops]);uv1_errors.append((Vector((projected.x,projected.y))-expected).length)
    if 1e-4<expected.y%1<1-1e-4:page_matches.append(math.floor(projected.y)==math.floor(expected.y))
 scale=max(max(source.dimensions),1e-8);tolerance=scale*.003;ordered=sorted(distances);return dict(scope='sampled_source_surface_and_UV_fidelity',sample_count=len(distances),source_to_candidate_max=max(distances,default=0),source_to_candidate_mean=statistics.fmean(distances) if distances else 0,source_to_candidate_p95=ordered[min(len(ordered)-1,int(len(ordered)*.95))] if ordered else 0,source_relative_tolerance=tolerance,source_profile_within_tolerance=bool(distances) and max(distances)<=tolerance,uv0_samples=len(uv_errors),uv0_mean_error=statistics.fmean(uv_errors) if uv_errors else None,uv0_max_error=max(uv_errors,default=None),uv1_samples=len(uv1_errors),uv1_mean_error=statistics.fmean(uv1_errors) if uv1_errors else None,uv1_max_error=max(uv1_errors,default=None),uv1_unambiguous_page_samples=len(page_matches),uv1_unambiguous_page_mismatches=sum(not v for v in page_matches),lightmap_array_appearance_validated=False,UV_metrics_advisory=True,final_visual_or_Unity_acceptance=False)
