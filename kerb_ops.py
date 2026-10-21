import bpy,bmesh,math

def kerb_geometry(obj,recipe):
 old=obj.data;bm=bmesh.new();bm.from_mesh(old);bm.normal_update();edges=[e for e in bm.edges if not e.is_manifold];assert not any(len(e.link_faces)>2 for e in edges),'Kerb contains nonmanifold junctions needing source repair'
 original_uv={layer.name for layer in old.uv_layers};world_lengths=[max(obj.matrix_world.to_3x3().col[i].length,1e-12) for i in range(3)];span=[max(v.co[i] for v in bm.verts)-min(v.co[i] for v in bm.verts) for i in range(3)];positive=[span[i]*world_lengths[i] for i in range(3) if span[i]>1e-9];assert positive,'Empty kerb profile';gauge_world=min(min(positive)*.02,max(positive)*.0005,.002);gauge_local=gauge_world/max(world_lengths);boundary=sum(e.is_boundary for e in bm.edges)
 # Source FBX component paths, slope, top faces and UV islands stay in place.
 # Give open recovered kerb surfaces a closed physical backing, rather than
 # replacing their curved profile with a bounding-box primitive.
 if boundary:
  # Complex recovered stripe surfaces can meet at a single vertex. Blender's
  # constrained shell solver handles these boundary fans without joining rims
  # into nonmanifold sheets, while retaining source surface and UV positions.
  bm.to_mesh(old);bm.free();old.update()
  shell=obj.modifiers.new('Source-profile constrained physical backing','SOLIDIFY');shell.solidify_mode='NON_MANIFOLD';shell.nonmanifold_thickness_mode='CONSTRAINTS';shell.thickness=gauge_local;shell.offset=-1;shell.use_even_offset=True;shell.use_quality_normals=True
  bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.modifier_apply(modifier=shell.name)
  bm=bmesh.new();bm.from_mesh(obj.data)

 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));assert all(e.is_manifold for e in bm.edges),'Closed source-following kerb shell could not be reconstructed: '+str({n:sum(len(e.link_faces)==n for e in bm.edges) for n in [0,1,3,4]})
 mesh=bpy.data.meshes.new(old.name+'__source_profile_kerb');bm.to_mesh(mesh);bm.free();mesh.update();assert {layer.name for layer in mesh.uv_layers}==original_uv,'Source kerb UV channels changed';obj.data=mesh;obj['kerb_backing_gauge_native_world']=gauge_world;obj['source_profile_preserved']=True;obj['source_material_identity_required']=True
 return ['source_following_kerb_profile_and_elevation_preserved','source_component_layout_retained','closed_physical_backing_and_boundary_rims' if boundary else 'existing_closed_kerb_volume_retained','source_UV_islands_and_material_indices_retained','original_driving_collision_preserved_separately']
