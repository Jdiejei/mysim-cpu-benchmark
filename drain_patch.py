import bpy,bmesh,math,collections
from mathutils import Vector,Matrix
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
 fragments=collections.defaultdict(list);areas=collections.defaultdict(float);UVspan=0;source_triangles=collections.defaultdict(list);triangle_areas={};UV_areas={}
 for tri in mesh.loop_triangles:
  points=[uvpoint(i) for i in tri.loops];a,b,c=points;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  root=find(tri.vertices[0]);source_triangles[root].append(tri.index);v=[mesh.vertices[i].co for i in tri.vertices];triangle_areas[tri.index]=(v[1]-v[0]).cross(v[2]-v[0]).length/2;UV_areas[tri.index]=abs(den)/2
  if abs(den)<1e-12:continue
  width=max(v[0] for v in points)-min(v[0] for v in points);height=max(v[1] for v in points)-min(v[1] for v in points);UVspan=max(UVspan,width,height);assert (math.ceil(width)+1)*(math.ceil(height)+1)<20000,'Source tile preflight exceeds bounded UV extent'
  for x in range(math.floor(min(v[0] for v in points)),math.floor(max(v[0] for v in points))+1):
   for y in range(math.floor(min(v[1] for v in points)),math.floor(max(v[1] for v in points))+1):
    polygon=clip_convex(points,[(x,y),(x+1,y),(x+1,y+1),(x,y+1)])
    if polygon:
     key=(find(tri.vertices[0]),x,y);fragments[key].append((tri.index,polygon));areas[key]+=abs(area(polygon))
 assert areas,'No source grate UV patch available';key=max(areas,key=lambda k:min(areas[k],1)-max(0,areas[k]-1)*.1);selected=[key]
 if recipe.get('prototype_adjacent_tiles'):
  pairs=[(k,(k[0],k[1]+dx,k[2]+dy)) for k in areas for dx,dy in [(1,0),(0,1)] if (k[0],k[1]+dx,k[2]+dy) in areas and .999<areas[k]<1.001 and .999<areas[(k[0],k[1]+dx,k[2]+dy)]<1.001];assert pairs,'No adjacent complete UV tiles in one source component';selected=list(pairs[0]);key=selected[0]
 if recipe.get('prototype_full_component'):
  roots=sorted(source_triangles);component_index=int(recipe.get('prototype_component_index',0));assert 0<=component_index<len(roots),'Unknown actual component index';root=roots[component_index];eligible=[k for k in areas if k[0]==root];assert eligible,'Selected source component has no usable UV0 surface';key=eligible[0]
  selected=[k for k in areas if k[0]==key[0]];assert len(selected)<=64,'Component tile count exceeds bounded prototype limit'
 inventory=[dict(component_index=i,root=root,source_triangles=source_triangles[root],source_area=sum(triangle_areas[t] for t in source_triangles[root]),UV0_degenerate_nonzero_area_triangles=[t for t in source_triangles[root] if UV_areas[t]<1e-12 and triangle_areas[t]>1e-12],tile_fragments=sum(k[0]==root for k in areas)) for i,root in enumerate(sorted(source_triangles))]
 vertices=[];faces=[];values=[[] for _ in mesh.uv_layers];materials=[];covered_UV=collections.defaultdict(float)
 for index,polygon in [item for tile in selected for item in fragments[tile]]:
  covered_UV[index]+=abs(area(polygon));tri=mesh.loop_triangles[index];a,b,c=[uvpoint(i) for i in tri.loops];den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);base=len(vertices)
  for p in polygon:
   wa=((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/den;wb=((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/den;blend=(wa,wb,1-wa-wb);vertices.append(tuple(sum(blend[j]*mesh.vertices[tri.vertices[j]].co[k] for j in range(3)) for k in range(3)))
   for layer_index,layer in enumerate(mesh.uv_layers):values[layer_index].append(tuple(sum(blend[j]*layer.data[tri.loops[j]].uv[k] for j in range(3)) for k in range(2)))
  for i in range(1,len(polygon)-1):faces.append((base,base+i,base+i+1));materials.append(tri.material_index)
 reference_origin=tuple((min(v[k] for v in vertices)+max(v[k] for v in vertices))*.5 for k in range(3));vertices=[tuple(v[k]-reference_origin[k] for k in range(3)) for v in vertices];original_matrix=obj.matrix_world.copy()
 original_area=sum(triangle_areas[t] for t in source_triangles[key[0]]);patch_area=sum((Vector(vertices[b])-Vector(vertices[a])).cross(Vector(vertices[c])-Vector(vertices[a])).length/2 for a,b,c in faces);uncovered=[t for t in source_triangles[key[0]] if triangle_areas[t]>max(original_area*1e-9,1e-12) and (UV_areas[t]<1e-12 or abs(covered_UV[t]-UV_areas[t])>UV_areas[t]*1e-6)];coverage=dict(source_area=original_area,patch_area=patch_area,area_relative_error=abs(patch_area-original_area)/max(original_area,1e-20),uncovered_nonzero_area_source_triangles=uncovered,source_triangle_inventory=inventory)
 if recipe.get('prototype_full_component'):assert not uncovered and coverage['area_relative_error']<1e-5,'Source component coverage failed:'+str(coverage)
 patch=bpy.data.meshes.new(mesh.name+'__one_source_cover_reference');patch.from_pydata(vertices,[],faces);patch.update()
 for n,source_layer in enumerate(mesh.uv_layers):
  layer=patch.uv_layers.new(name=source_layer.name)
  for loop in patch.loops:layer.data[loop.index].uv=values[n][loop.vertex_index]
 for p,index in zip(patch.polygons,materials):p.material_index=index
 obj.data=patch;obj.matrix_world=original_matrix@Matrix.Translation(Vector(reference_origin));bpy.context.view_layer.update();return dict(scope='selected_source_component_partial_mesh',parent_procedure_id=recipe['prototype_parent_procedure_id'],parent_mesh=recipe['mesh'],source_components=len({find(i) for i in range(len(parent))}),source_UV_tile_patches=len(areas),source_max_UV_span=UVspan,selected_component=key[0],selected_tile=list(key[1:]),selected_tiles=[list(k[1:]) for k in selected],selected_UV_area=sum(areas[k] for k in selected),reference_faces=len(faces),reference_vertices=len(vertices),source_coverage=coverage,reference_local_origin_offset=list(reference_origin),full_source_mesh_upgraded=False)
