import bpy,bmesh,math,collections
from drain_uv_geometry import area,clip_convex

def extract_source_tile_patch(obj,recipe):
 mesh=obj.data;mesh.calc_loop_triangles();binding=next(t for m in recipe['material_bindings'] for t in m.get('textures',[]) if t['property']=='_BaseMap');sx=binding.get('scale',{}).get('x',1);sy=binding.get('scale',{}).get('y',1);ox=binding.get('offset',{}).get('x',0);oy=binding.get('offset',{}).get('y',0);parent=list(range(len(mesh.vertices)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for edge in mesh.edges:
  a,b=map(find,edge.vertices)
  if a!=b:parent[b]=a
 def uvpoint(i):
  uv=mesh.uv_layers[0].data[i].uv;return (uv.x*sx+ox,uv.y*sy+oy)
 fragments=collections.defaultdict(list);areas=collections.defaultdict(float);UVspan=0
 for tri in mesh.loop_triangles:
  points=[uvpoint(i) for i in tri.loops];a,b,c=points;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-12:continue
  width=max(v[0] for v in points)-min(v[0] for v in points);height=max(v[1] for v in points)-min(v[1] for v in points);UVspan=max(UVspan,width,height);assert (math.ceil(width)+1)*(math.ceil(height)+1)<20000,'Source tile preflight exceeds bounded UV extent'
  for x in range(math.floor(min(v[0] for v in points)),math.floor(max(v[0] for v in points))+1):
   for y in range(math.floor(min(v[1] for v in points)),math.floor(max(v[1] for v in points))+1):
    polygon=clip_convex(points,[(x,y),(x+1,y),(x+1,y+1),(x,y+1)])
    if polygon:
     key=(find(tri.vertices[0]),x,y);fragments[key].append((tri.index,polygon));areas[key]+=abs(area(polygon))
 assert areas,'No source grate UV patch available';key=max(areas,key=lambda k:min(areas[k],1)-max(0,areas[k]-1)*.1);vertices=[];faces=[];values=[[] for _ in mesh.uv_layers];materials=[]
 for index,polygon in fragments[key]:
  tri=mesh.loop_triangles[index];a,b,c=[uvpoint(i) for i in tri.loops];den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);base=len(vertices)
  for p in polygon:
   wa=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den;wb=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;blend=(wa,wb,1-wa-wb);vertices.append(tuple(sum(blend[j]*mesh.vertices[tri.vertices[j]].co[k] for j in range(3)) for k in range(3)))
   for layer_index,layer in enumerate(mesh.uv_layers):values[layer_index].append(tuple(sum(blend[j]*layer.data[tri.loops[j]].uv[k] for j in range(3)) for k in range(2)))
  for i in range(1,len(polygon)-1):faces.append((base,base+i,base+i+1));materials.append(tri.material_index)
 patch=bpy.data.meshes.new(mesh.name+'__one_source_cover_reference');patch.from_pydata(vertices,[],faces);patch.update()
 for n,source_layer in enumerate(mesh.uv_layers):
  layer=patch.uv_layers.new(name=source_layer.name)
  for loop in patch.loops:layer.data[loop.index].uv=values[n][loop.vertex_index]
 for p,index in zip(patch.polygons,materials):p.material_index=index
 obj.data=patch;bpy.context.view_layer.update();return dict(scope='one_source_component_UV_tile_only',parent_procedure_id=recipe['prototype_parent_procedure_id'],parent_mesh=recipe['mesh'],source_components=len({find(i) for i in range(len(parent))}),source_UV_tile_patches=len(areas),source_max_UV_span=UVspan,selected_component=key[0],selected_tile=list(key[1:]),selected_UV_area=areas[key],reference_faces=len(faces),reference_vertices=len(vertices),full_source_mesh_upgraded=False)
