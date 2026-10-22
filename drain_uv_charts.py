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
 return _injective_groups(list(groups.values()),uvpoint)


def _intersection_area(a,b):
 # Convex clipping measures positive-area overlap; shared edges remain valid.
 def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 orient=1 if cross(*b)>0 else -1
 poly=list(a)
 for i in range(3):
  x,y=b[i],b[(i+1)%3];result=[]
  if not poly:return 0.0
  previous=poly[-1];dp=orient*cross(x,y,previous)
  for current in poly:
   dc=orient*cross(x,y,current)
   if (dc>=0)!=(dp>=0):
    t=dp/(dp-dc);result.append(tuple(previous[k]+t*(current[k]-previous[k]) for k in (0,1)))
   if dc>=0:result.append(current)
   previous,dp=current,dc
  poly=result
 return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly))))*.5 if poly else 0.0

def _injective_groups(groups,uvpoint):
 result=[]
 for original in groups:
  bins=[]
  for tri in original:
   uv=[uvpoint(loop) for loop in tri.loops]
   for bucket in bins:
    if all(_intersection_area(uv,other)<=1e-12 for _,other in bucket):
     bucket.append((tri,uv));break
   else:bins.append([(tri,uv)])
  result.extend([[tri for tri,_ in bucket] for bucket in bins])
 return result
