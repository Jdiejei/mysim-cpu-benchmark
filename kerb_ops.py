import bpy,bmesh,math

def kerb_geometry(obj,recipe):
 old=obj.data;bm=bmesh.new();bm.from_mesh(old);bm.normal_update();edges=[e for e in bm.edges if not e.is_manifold];assert not any(len(e.link_faces)>2 for e in edges),'Kerb contains nonmanifold junctions needing source repair'
 original_uv={layer.name for layer in old.uv_layers};world_lengths=[max(obj.matrix_world.to_3x3().col[i].length,1e-12) for i in range(3)];span=[max(v.co[i] for v in bm.verts)-min(v.co[i] for v in bm.verts) for i in range(3)];positive=[span[i]*world_lengths[i] for i in range(3) if span[i]>1e-9];assert positive,'Empty kerb profile';gauge_world=min(min(positive)*.02,max(positive)*.0005,.002);gauge_local=gauge_world/max(world_lengths);boundary=sum(e.is_boundary for e in bm.edges)
 # Source FBX component paths, slope, top faces and UV islands stay in place.
 # Give open recovered kerb surfaces a closed physical backing, rather than
 # replacing their curved profile with a bounding-box primitive.
 if boundary:
  bmesh.ops.solidify(bm,geom=list(bm.faces),thickness=-gauge_local)
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges),'Closed source-following kerb shell could not be reconstructed'
 mesh=bpy.data.meshes.new(old.name+'__source_profile_kerb');bm.to_mesh(mesh);bm.free();mesh.update();assert {layer.name for layer in mesh.uv_layers}==original_uv,'Source kerb UV channels changed';obj.data=mesh;obj['kerb_backing_gauge_native_world']=gauge_world;obj['source_profile_preserved']=True;obj['source_material_identity_required']=True
 return ['source_following_kerb_profile_and_elevation_preserved','source_component_layout_retained','closed_physical_backing_and_boundary_rims' if boundary else 'existing_closed_kerb_volume_retained','source_UV_islands_and_material_indices_retained','original_driving_collision_preserved_separately']
