import math,statistics
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,closest_point_on_tri


def corner_uv_error(cand_pts,cand_uvs,src_pts,src_uvs,tol):
 # Exact per-corner UV comparison: match each candidate corner to the source corner at the same position
 # (within the existing geometry tolerance) and compare UVs directly. Returns None when corners cannot be
 # matched one-to-one, so the sampled projection below still applies. Slivers make barycentric projection
 # ill-conditioned (a 1e-7 position change moves the UV by whole units); corner matching does not.
 err=0.0
 for c,u in zip(cand_pts,cand_uvs):
  near=[k for k in range(len(src_pts)) if (c-src_pts[k]).length<=tol]
  if not near:return None
  # corners farther apart than the tolerance are told apart by position; corners closer than it (tiny or
  # collapsed triangles) cannot be, so the candidate UV is compared with the closest source UV among them.
  err=max(err,min((Vector((u[0],u[1]))-Vector((src_uvs[k][0],src_uvs[k][1]))).length for k in near))
 return err

def source_fidelity(candidate,source,limit=1200):
 mesh=candidate.data;original=source.data;mesh.calc_loop_triangles();original.calc_loop_triangles()
 recentered=bool(candidate.get('source_fidelity_double_precision_origin'));reference=original.vertices[0].co
 origin=tuple(sum(float(source.matrix_world[i][j])*float(reference[j]) for j in range(3))+float(source.matrix_world[i][3]) for i in range(3))
 def world_point(obj,point):
  if not recentered:return obj.matrix_world@point
  # Compute transforms/subtraction in Python doubles before conversion to mathutils float vectors.
  # Translation is distance-preserving; geometry/UVs and all tolerance checks remain unchanged.
  return Vector(tuple(sum(float(obj.matrix_world[i][j])*float(point[j]) for j in range(3))+float(obj.matrix_world[i][3])-origin[i] for i in range(3)))
 vertices=[world_point(candidate,v.co) for v in mesh.vertices];triangles=[tuple(t.vertices) for t in mesh.loop_triangles];tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True);distances=[];uv_errors=[];uv1_errors=[];page_matches=[];corner_matched=[]
 provenance=mesh.attributes.get('source_polygon_id') if candidate.get('validate_source_face_provenance') else None;provenance_faces={}
 if provenance:
  for index,target in enumerate(mesh.loop_triangles):provenance_faces.setdefault(provenance.data[target.polygon_index].value,[]).append(index)
 source_vertices=list(original.vertices);step=max(1,math.ceil(len(source_vertices)/limit))
 for v in source_vertices[::step]:
  nearest=tree.find_nearest(world_point(source,v.co))
  if nearest[0] is None:raise RuntimeError('No reconstructed source-nearest surface')
  distances.append(nearest[3])
 source_uv=original.uv_layers[0] if original.uv_layers else None;target_uv=mesh.uv_layers.get(source_uv.name) if source_uv else None;tris=list(original.loop_triangles);step=max(1,math.ceil(len(tris)/limit))
 for tri in tris[::step]:
  point=sum((world_point(source,original.vertices[i].co) for i in tri.vertices),Vector())/3;near,normal,index,distance=tree.find_nearest(point)
  if near is None:raise RuntimeError('Missing reconstructed face-nearest surface')
  distances.append(distance)
  if candidate.get('validate_source_face_provenance'):
   assert provenance,'Source polygon provenance lost'
   indices=provenance_faces.get(tri.polygon_index,[]);assert indices,'Original source polygon missing from candidate'
   choices=[]
   for target_index in indices:
    target=mesh.loop_triangles[target_index];a,b,c=[vertices[i] for i in target.vertices]
    if (b-a).cross(c-a).length_squared<=1e-24:continue
    projected_point=closest_point_on_tri(point,a,b,c);dist_c=(projected_point-point).length
    # Exact identity first: a candidate triangle whose three corners coincide with the source triangle's
    # corners has not moved at all. closest_point_on_tri runs in float32 and mislocates points on
    # collinear/sliver source triangles (an identical triangle measured 1.8e-3 away), so identity decides.
    src_c=[world_point(source,original.vertices[i].co) for i in tri.vertices];eps_id=max(max(source.dimensions),1e-8)*1e-6
    if all(min((s-q).length for q in (a,b,c))<=eps_id for s in src_c):projected_point=point;dist_c=0.0
    else:
     # Corner-offset bound: if the candidate triangle's corners sit within d of the source triangle's corners
     # (best one-to-one pairing), the source centroid is within d of the candidate triangle, whatever the
     # float32 closest-point routine says on a collapsed or sliver triangle.
     import itertools
     d_best=min(max((src_c[i]-cc[j]).length for i,j in enumerate(perm)) for perm in itertools.permutations(range(3)) for cc in [(a,b,c)])
     if d_best<dist_c:dist_c=d_best;projected_point=point
    choices.append((dist_c,target_index,projected_point))
   assert choices,'No nondegenerate candidate source polygon';distance,index,near=min(choices,key=lambda x:x[0]);assert distance<=max(max(source.dimensions),1e-8)*.003,'Corresponding source polygon moved beyond source profile tolerance'
  if source_uv and target_uv:
   expected=sum((source_uv.data[i].uv for i in tri.loops),Vector((0,0)))/3;target=mesh.loop_triangles[index];corners=[vertices[i] for i in target.vertices];uvs=[Vector((*target_uv.data[i].uv,0)) for i in target.loops]
   if (corners[1]-corners[0]).cross(corners[2]-corners[0]).length_squared>1e-24:
    projected=barycentric_transform(near,*corners,*uvs);proj_err=(Vector((projected.x,projected.y))-expected).length;ce=corner_uv_error(corners,uvs,[world_point(source,original.vertices[original.loops[i].vertex_index].co) for i in original.polygons[tri.polygon_index].loop_indices],[source_uv.data[i].uv for i in original.polygons[tri.polygon_index].loop_indices],max(max(source.dimensions),1e-8)*.003);uv_errors.append(proj_err if ce is None else ce);corner_matched.append(ce is not None)
  if len(original.uv_layers)>1 and len(mesh.uv_layers)>1:
   layer=original.uv_layers[1];target_layer=mesh.uv_layers.get(layer.name);target=mesh.loop_triangles[index];corners=[vertices[i] for i in target.vertices]
   if target_layer and (corners[1]-corners[0]).cross(corners[2]-corners[0]).length_squared>1e-24:
    expected=sum((layer.data[i].uv for i in tri.loops),Vector((0,0)))/3;projected=barycentric_transform(near,*corners,*[Vector((*target_layer.data[i].uv,0)) for i in target.loops]);proj_err1=(Vector((projected.x,projected.y))-expected).length;ce1=corner_uv_error(corners,[target_layer.data[i].uv for i in target.loops],[world_point(source,original.vertices[original.loops[i].vertex_index].co) for i in original.polygons[tri.polygon_index].loop_indices],[layer.data[i].uv for i in original.polygons[tri.polygon_index].loop_indices],max(max(source.dimensions),1e-8)*.003);uv1_errors.append(proj_err1 if ce1 is None else ce1)
    if 1e-4<expected.y%1<1-1e-4:page_matches.append(math.floor(projected.y)==math.floor(expected.y))
 scale=max(max(source.dimensions),1e-8);tolerance=scale*.003;ordered=sorted(distances);result=dict(scope='sampled_source_surface_and_UV_fidelity',coordinate_frame=('double_precision_source_anchored' if recentered else 'original_world'),sample_count=len(distances),source_to_candidate_max=max(distances,default=0),source_to_candidate_mean=statistics.fmean(distances) if distances else 0,source_to_candidate_p95=ordered[min(len(ordered)-1,int(len(ordered)*.95))] if ordered else 0,source_relative_tolerance=tolerance,source_profile_within_tolerance=bool(distances) and max(distances)<=tolerance,uv0_samples=len(uv_errors),uv0_mean_error=statistics.fmean(uv_errors) if uv_errors else None,uv0_max_error=max(uv_errors,default=None),uv1_samples=len(uv1_errors),uv1_mean_error=statistics.fmean(uv1_errors) if uv1_errors else None,uv1_max_error=max(uv1_errors,default=None),uv1_unambiguous_page_samples=len(page_matches),uv1_unambiguous_page_mismatches=sum(not v for v in page_matches),lightmap_array_appearance_validated=False,UV_metrics_advisory=True,uv_method='per_corner_exact_with_projection_fallback',uv0_corner_matched_samples=sum(corner_matched),final_visual_or_Unity_acceptance=False)

 if candidate.get('require_source_parameter_audit'):
  from parameter_uv_fidelity import audit_source_parameters
  try:audit=audit_source_parameters(candidate,source,world_point)
  except Exception:
   if candidate.get('parameter_diagnostic_directory'):
    import bpy
    from pathlib import Path
    bpy.data.libraries.write(str(Path(candidate['parameter_diagnostic_directory'])/'rejected-source-parameters.blend'),{candidate,source},compress=True)
   raise
  result['source_parameter_audit']=audit;result['nearest_projection_uv0_max_error']=result['uv0_max_error'];result['nearest_projection_uv1_max_error']=result['uv1_max_error'];result.update({k:audit[k] for k in ['uv0_samples','uv0_max_error','uv0_mean_error','uv1_samples','uv1_max_error','uv1_mean_error','uv1_unambiguous_page_samples','uv1_unambiguous_page_mismatches']});result['strict_UV_measure']='All output corners against their original triangle source parameters'
 return result
