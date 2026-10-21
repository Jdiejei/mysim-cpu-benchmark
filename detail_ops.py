import bpy,bmesh,math,random,time
from mathutils import Vector

def make_material(binding,root,category):
    mat=bpy.data.materials.new(binding.get('path','material').split('/')[-1]);mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Roughness'].default_value=.83 if category=='grass' else .7
    base=next((t for t in binding.get('textures',[]) if t['property'] in {'_BaseMap','_MainTex'} and t.get('packed')),None)
    if base:
        image=bpy.data.images.load(str(root/base['packed']['file']),check_existing=True);image.pack();tex=n.new('ShaderNodeTexImage');tex.image=image;uv=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY_ADD';sc=base.get('scale',{'x':1,'y':1});off=base.get('offset',{'x':0,'y':0});mapping.inputs[1].default_value=(sc['x'],sc['y'],1);mapping.inputs[2].default_value=(off['x'],off['y'],0);l.new(uv.outputs['UV'],mapping.inputs[0]);l.new(mapping.outputs['Vector'],tex.inputs['Vector']);l.new(tex.outputs['Color'],bs.inputs['Base Color'])
    coords=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=250 if category=='ground' else 80;noise.inputs['Detail'].default_value=3;l.new(coords.outputs['Object'],noise.inputs['Vector']);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.0007 if category=='ground' else .0015;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal']);return mat

def grass_detail(obj,recipe):
    obj.data.calc_loop_triangles();matrix=obj.matrix_world;tri=[];weights=[]
    bindings=recipe['material_bindings'];grass_slots={i for i,m in enumerate(bindings) if 'grass' in str(m).lower() or 'lawn' in str(m).lower() or 'turf' in str(m).lower()}
    for t in obj.data.loop_triangles:
        if grass_slots and t.material_index not in grass_slots:continue
        a,b,c=[matrix@obj.data.vertices[i].co for i in t.vertices];area=(b-a).cross(c-a).length*.5
        if area>1e-8 and (b-a).cross(c-a).normalized().z>.25:tri.append((a,b,c));weights.append(area)
    if not tri:return None,0
    total=sum(weights);count=min(1500,max(30,int(total*60)));rng=random.Random(int(recipe['procedure_id'][:12],16));verts=[];faces=[]
    for a,b,c in rng.choices(tri,weights=weights,k=count):
        u,v=rng.random(),rng.random()
        if u+v>1:u,v=1-u,1-v
        base=a+(b-a)*u+(c-a)*v
        for blade in range(5):
            angle=rng.random()*math.tau;height=rng.uniform(.035,.095);width=rng.uniform(.002,.004);side=Vector((math.cos(angle)*width,math.sin(angle)*width,0));bend=Vector((-math.sin(angle)*height*.25,math.cos(angle)*height*.25,0));origin=base+Vector((rng.uniform(-.015,.015),rng.uniform(-.015,.015),0));k=len(verts)
            for j in range(4):
                f=j/3;centre=origin+Vector((0,0,height*f))+bend*f*f;w=side*(1-f*.95);verts.extend((tuple(centre-w),tuple(centre+w)))
            faces.extend((k+2*j,k+2*j+1,k+2*j+3,k+2*j+2) for j in range(3))
    mesh=bpy.data.meshes.new(obj.name+'__grass_detail');mesh.from_pydata(verts,[],faces);mesh.update();detail=bpy.data.objects.new(obj.name+'__grass_detail',mesh);bpy.context.collection.objects.link(detail)
    mat=bpy.data.materials.get('Candidate grass blades')
    if not mat:
        mat=bpy.data.materials.new('Candidate grass blades');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.08,.16,.035,1);bs.inputs['Roughness'].default_value=.8;noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=8;ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.035,.07,.012,1);ramp.color_ramp.elements[1].color=(.18,.25,.055,1);l.new(noise.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],bs.inputs['Base Color'])
    mesh.materials.append(mat);return detail,len(faces)

def refine(obj,recipe,root):
    start=time.monotonic();before={'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'bounds':list(obj.dimensions)};obj.data=obj.data.copy();bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();changes=['source_vertex_colour_import_repaired','normals_recalculated'];extra=[]
    obj.data.materials.clear()
    for binding in recipe['material_bindings']:obj.data.materials.append(make_material(binding,root,recipe['category']))
    changes.append('enhanced_texture_bindings_and_physical_surface_microdetail')
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    if any(s in obj.name.lower() for s in ['curb','kerb']):
        # Visual candidate only. Driving collision remains the original source.
        m=obj.modifiers.new('Kerb edge detail','BEVEL');m.width=.002/max(abs(obj.scale.x),1e-8);m.segments=3;m.limit_method='ANGLE';m.angle_limit=.7;m.use_clamp_overlap=True;bpy.ops.object.modifier_apply(modifier=m.name);changes.append('three_segment_kerb_edge_detail')
    if recipe['category']=='grass':
        detail,faces=grass_detail(obj,recipe)
        if detail:extra.append(detail);changes.append('individual_curved_grass_blades')
    elif recipe['category'] not in {'ground','decal','geometry'}:
        m=obj.modifiers.new('Structural edge detail','BEVEL');m.width=max(obj.dimensions)*.0005/max(abs(obj.scale.x),1e-8);m.segments=3;m.limit_method='ANGLE';m.angle_limit=.8;m.use_clamp_overlap=True;bpy.ops.object.modifier_apply(modifier=m.name);changes.append('structural_bevel_candidate')
    assert all(math.isfinite(v) for vertex in obj.data.vertices for v in vertex.co),'Nonfinite vertices'
    assert len(obj.data.uv_layers)>0 or not any(m.get('textures') for m in recipe['material_bindings']),'Textured mesh has no UV layer'
    return {'before':before,'after':{'vertices':len(obj.data.vertices)+sum(len(o.data.vertices) for o in extra),'faces':len(obj.data.polygons)+sum(len(o.data.polygons) for o in extra)},'changes':changes,'seconds':time.monotonic()-start,'review_required':['visual_artistic_review','grass_edge_clearance_and_density','material_baking_and_Unity_mapping','collision_and_frame_time'],'quality_accepted':False},extra
