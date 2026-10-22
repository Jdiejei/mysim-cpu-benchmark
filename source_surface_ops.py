import bpy,bmesh,math

def refine_source_surface(obj):
    # Preserve the actual curved/oriented source instead of assuming an axis-aligned rail or circular tyre.
    mesh=obj.data;bm=bmesh.new();bm.from_mesh(mesh)
    assert bm.faces and len(bm.verts)<600000,'Source surface outside geometry budget'
    assert all(len(e.link_faces)<=2 for e in bm.edges),'Source has branching nonmanifold edges'
    boundary=any(len(e.link_faces)==1 for e in bm.edges)
    assert all(e.link_faces for e in bm.edges),'Source has unsupported loose edges'
    bm.free();changes=['actual_source_orientation_and_shape_preserved','original_UV_channels_preserved']
    if boundary:
        # Keep the original front surface at offset=1; form a small inward backing and close open rims.
        local_span=max(max(v.co[a] for v in mesh.vertices)-min(v.co[a] for v in mesh.vertices) for a in range(3))
        solid=obj.modifiers.new('Source-following closed backing','SOLIDIFY');solid.thickness=local_span*.0002;solid.offset=-1;solid.use_rim=True;solid.use_even_offset=False
        bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=solid.name)
        changes.append('source_following_backing_and_closed_boundary_rims')
    else:changes.append('existing_closed_source_volume_retained')
    obj['source_surface_refinement']=True
    return changes
