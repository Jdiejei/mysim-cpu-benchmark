import bpy,bmesh,math
from mathutils import Vector

def tyre_geometry(obj):
 old=obj.data;lo=[min(v.co[i] for v in old.vertices) for i in range(3)];hi=[max(v.co[i] for v in old.vertices) for i in range(3)];span=[hi[i]-lo[i] for i in range(3)];axle=min(range(3),key=lambda i:span[i]);plane=[i for i in range(3) if i!=axle];assert min(span)>1e-9 and max(span[i] for i in plane)/min(span[i] for i in plane)<1.25,'Single tyre shape requires further context';centre=[(lo[i]+hi[i])/2 for i in range(3)];verts=[];faces=[]
 def point(u,radial,depth):
  p=centre.copy();p[plane[0]]+=math.cos(u)*radial*span[plane[0]];p[plane[1]]+=math.sin(u)*radial*span[plane[1]];p[axle]+=depth*span[axle];return tuple(p)
 # Elliptical source envelope retained in its native FBX units; no guessed metric scale.
 segments=96;profile=24
 for a in range(segments):
  u=math.tau*a/segments
  for b in range(profile):
   v=math.tau*b/profile;verts.append(point(u,.36+.14*math.cos(v),.5*math.sin(v)))
 for a in range(segments):
  for b in range(profile):faces.append((a*profile+b,((a+1)%segments)*profile+b,((a+1)%segments)*profile+(b+1)%profile,a*profile+(b+1)%profile))
 # Raised, staggered tread blocks: real surfaces, not a colour/noise substitute.
 for row,depth in enumerate([-.3,0,.3]):
  radial=.36+.14*math.sqrt(1-4*depth*depth)
  for k in range(64):
   u=math.tau*(k+(row%2)*.5)/64;base=len(verts)
   for rr in [radial-.001,radial+.004]:
    for du,dz in [(-.033,-.06),(.033,-.06),(.033,.06),(-.033,.06)]:verts.append(point(u+du+dz*.12,rr,depth+dz))
   faces.extend(tuple(base+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
 # Raised moulded sidewall rings on both faces.
 for side in [-1,1]:
  start=len(verts)
  for a in range(96):
   for b in range(6):
    v=math.tau*b/6;verts.append(point(math.tau*a/96,.32+.004*math.cos(v),side*(.42+.004*math.sin(v))))
  for a in range(96):
   for b in range(6):faces.append((start+a*6+b,start+((a+1)%96)*6+b,start+((a+1)%96)*6+(b+1)%6,start+a*6+(b+1)%6))
 mesh=bpy.data.meshes.new(old.name+'__reconstructed_tyre');mesh.from_pydata(verts,[],faces);mesh.update();obj.data=mesh
 for layer in old.uv_layers:
  uv=mesh.uv_layers.new(name=layer.name)
  for poly in mesh.polygons:
   for index in poly.loop_indices:
    p=mesh.vertices[mesh.loops[index].vertex_index].co;u=math.atan2((p[plane[1]]-centre[plane[1]])/span[plane[1]],(p[plane[0]]-centre[plane[0]])/span[plane[0]])/math.tau;uv.data[index].uv=(u%1,(p[axle]-lo[axle])/span[axle])
 for face in mesh.polygons:face.use_smooth=face.index<segments*profile
 return ['source_unit_and_envelope_preserved','96x24_carcass_geometry','192_staggered_raised_tread_blocks','moulded_sidewall_rings','new_UV_channels_require_artistic_review']

def tyre_material():
 mat=bpy.data.materials.get('Reconstructed trackside tyre rubber')
 if mat:return mat
 mat=bpy.data.materials.new('Reconstructed trackside tyre rubber');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.018,.02,.019,1);bs.inputs['Roughness'].default_value=.78;return mat
