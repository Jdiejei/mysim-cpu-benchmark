import bpy,bmesh,math
from mathutils import Matrix,Vector

def armco_geometry(obj):
 # Source-sized procedural Armco candidate. It still requires visual/context acceptance.
 old=obj.data;co=[v.co.copy() for v in old.vertices];lo=[min(v[i] for v in co) for i in range(3)];hi=[max(v[i] for v in co) for i in range(3)];span=[hi[i]-lo[i] for i in range(3)];units=[max(obj.matrix_world.to_3x3().col[i].length,1e-8) for i in range(3)]
 assert span[0]*units[0]>.3 and span[2]*units[2]>.3,'Armco axes require source inspection'
 bm=bmesh.new();centre=(lo[1]+hi[1])/2;full_assembly=span[2]*units[2]>=.6;height=min(.31,span[2]*units[2]*.4)/units[2] if full_assembly else span[2]*.98;railcentre=lo[2]+span[2]*(.72 if full_assembly else .5);depth=span[1]*.49
 profile=[(-.5,0),(-.4,1),(-.23,-1),(0,.85),(.23,-1),(.4,1),(.5,0)];sections=25;rings=[]
 for j in range(sections):
  x=lo[0]+span[0]*j/(sections-1);near=[v.y for v in co if abs(v.x-x)<span[0]/12];path=sum(near)/len(near) if near else centre;path=max(lo[1]+depth,min(hi[1]-depth,path));rings.append([bm.verts.new((x,path+y*depth,railcentre+z*height)) for z,y in profile])
 for a,b in zip(rings,rings[1:]):
  for k in range(len(profile)-1):bm.faces.new((a[k],b[k],b[k+1],a[k+1]))
 def box(location,size):
  verts=bmesh.ops.create_cube(bm,size=1)['verts']
  for v in verts:v.co=Vector((v.co[i]*size[i]+location[i] for i in range(3)))
 def bolt(location):
  verts=bmesh.ops.create_cone(bm,cap_ends=True,cap_tris=False,segments=12,radius1=.006/units[0],radius2=.006/units[0],depth=.004/units[1])['verts'];rot=Matrix.Rotation(math.pi/2,4,'X')
  for v in verts:v.co=rot@v.co+Vector(location)
 if full_assembly:
  for fraction in [(.1+.8*i/max(1,math.ceil(span[0]*units[0]/2))) for i in range(math.ceil(span[0]*units[0]/2)+1)]:
   x=lo[0]+span[0]*fraction;z=(lo[2]+hi[2])/2;postwidth=min(.07/units[0],span[0]*.08);postdepth=min(.048/units[1],span[1]*.8);gauge=.004/units[0]
   # I-section: web and two flanges, with base and mounting plates.
   box((x,centre,z),(gauge,postdepth,span[2]));box((x,centre-postdepth/2,z),(postwidth,gauge,span[2]));box((x,centre+postdepth/2,z),(postwidth,gauge,span[2]));box((x,centre,lo[2]+.004/units[2]),(postwidth*1.5,postdepth,.008/units[2]));box((x,centre,railcentre),(postwidth,postdepth,.2/units[2]))
   for dz in [-.085,.085]:bolt((x,centre-depth*.9,railcentre+dz/units[2]))
 # Rounded exposed edges carry physical highlights rather than surface-only noise.
 bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));mesh=bpy.data.meshes.new(old.name+'__reconstructed_armco');bm.to_mesh(mesh);bm.free();obj.data=mesh
 for layer in old.uv_layers:
  uv=mesh.uv_layers.new(name=layer.name)
  for poly in mesh.polygons:
   for index in poly.loop_indices:
    p=mesh.vertices[mesh.loops[index].vertex_index].co;uv.data[index].uv=((p.x-lo[0])/max(span[0],1e-8),(p.z-lo[2])/max(span[2],1e-8))
 return ['source_sized_corrugated_W_rail','I_section_posts','mounting_and_base_plates','twelve_sided_bolt_heads','reconstructed_UV_channels_require_artistic_review']


def armco_material():
 mat=bpy.data.materials.get('Reconstructed white painted steel')
 if mat:return mat
 mat=bpy.data.materials.new('Reconstructed white painted steel');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.72,.73,.70,1);bs.inputs['Metallic'].default_value=.55;bs.inputs['Roughness'].default_value=.4
 nodes=mat.node_tree.nodes;links=mat.node_tree.links;geom=nodes.new('ShaderNodeNewGeometry');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=900;noise.inputs['Detail'].default_value=2;links.new(geom.outputs['Position'],noise.inputs['Vector']);bump=nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.00008;bump.inputs['Strength'].default_value=.1;links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal']);return mat
