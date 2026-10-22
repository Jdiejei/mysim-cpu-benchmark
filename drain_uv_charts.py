import collections,math

def partition_uv_charts(triangles,uvpoint,tolerance=1e-6):
 triangles=list(triangles);parent=list(range(len(triangles)));edges=collections.defaultdict(list);uvs=[[uvpoint(loop) for loop in tri.loops] for tri in triangles]
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def signed(points):
  a,b,c=points;return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 for i,tri in enumerate(triangles):
  for a,b in [(0,1),(1,2),(2,0)]:edges[tuple(sorted((tri.vertices[a],tri.vertices[b])))].append((i,{tri.vertices[a]:uvs[i][a],tri.vertices[b]:uvs[i][b]}))
 for edge,adjacent in edges.items():
  for a,(i,first) in enumerate(adjacent):
   for j,second in adjacent[a+1:]:
    if signed(uvs[i])*signed(uvs[j])<=0:continue
    if all(math.dist(first[v],second[v])<=tolerance for v in edge):
     x,y=find(i),find(j)
     if x!=y:parent[y]=x
 groups=collections.defaultdict(list)
 for i,tri in enumerate(triangles):groups[find(i)].append(tri)
 return list(groups.values())
