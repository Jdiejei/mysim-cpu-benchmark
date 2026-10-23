"""Source-constrained rounded panel joints; pure geometry helpers for regression tests."""
import math,collections
def mix(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
def length(v):return math.sqrt(sum(x*x for x in v))
def unit(v):
 n=length(v);assert n>1e-15;return tuple(x/n for x in v)
def interpolate(a,b,t):
 return dict(position=mix(a['position'],b['position'],t),u=a['u']+(b['u']-a['u'])*t,uv=[mix(x,y,t) for x,y in zip(a['uv'],b['uv'])],normal=mix(a['normal'],b['normal'],t),front=a['front']+(b['front']-a['front'])*t)
def half(poly,cut,keep_greater):
 result=[]
 for a,b in zip(poly,poly[1:]+poly[:1]):
  inside_a=a['u']>=cut-1e-12 if keep_greater else a['u']<=cut+1e-12;inside_b=b['u']>=cut-1e-12 if keep_greater else b['u']<=cut+1e-12
  if inside_a:result.append(a)
  if inside_a!=inside_b:
   t=(cut-a['u'])/(b['u']-a['u']);p=interpolate(a,b,t);p['u']=cut;result.append(p)
 cleaned=[]
 for p in result:
  if not cleaned or length(tuple(x-y for x,y in zip(p['position'],cleaned[-1]['position'])))>1e-12:cleaned.append(p)
 if len(cleaned)>1 and length(tuple(x-y for x,y in zip(cleaned[0]['position'],cleaned[-1]['position'])))<1e-12:cleaned.pop()
 return cleaned
def area(a,b,c):
 u=tuple(y-x for x,y in zip(a,b));v=tuple(y-x for x,y in zip(a,c));return length((u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))*.5
def construct(surfaces,centres,halfwidth,depth,tolerance):
 assert 0<halfwidth<.02 and depth>0 and tolerance>0
 cuts=sorted(set(c+d*halfwidth*f for c in centres for f in [0,.1666666667,.3333333333,.5,.6666666667,.8333333333,1] for d in [-1,1]));vertices=[];faces=[];uv=[];provenance=[];lookup={};changed=0
 for surface in surfaces:
  pieces=[surface['corners']]
  for cut in cuts:
   split=[]
   for poly in pieces:
    if min(p['u'] for p in poly)+1e-11<cut<max(p['u'] for p in poly)-1e-11:
     split.extend(p for p in [half(poly,cut,False),half(poly,cut,True)] if len(p)>=3)
    else:split.append(poly)
   pieces=split
  for poly in pieces:
   for k in range(1,len(poly)-1):
    corners=[poly[0],poly[k],poly[k+1]];positions=[]
    for p in corners:
     d=min(abs(p['u']-c) for c in centres)/halfwidth;profile=.5*(1+math.cos(math.pi*d)) if d<1 else 0;offset=depth*profile*p['front'];normal=unit(p['normal']);positions.append(tuple(x-offset*n for x,n in zip(p['position'],normal)));changed+=offset>0
    if area(*positions)<=tolerance*tolerance:continue
    indices=[]
    for p in positions:
     key=tuple(round(x/tolerance) for x in p)
     if key not in lookup:lookup[key]=len(vertices);vertices.append(p)
     indices.append(lookup[key])
    if len(set(indices))<3:continue
    faces.append(indices);uv.append([p['uv'] for p in corners]);provenance.append(surface['source_polygon'])
 edges=collections.Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face,face[1:]+face[:1]));bad=[dict(edge=list(e),incident_faces=n) for e,n in edges.items() if n!=2]
 return dict(vertices=vertices,faces=faces,corner_uv=uv,source_polygons=provenance,nonmanifold_edges=bad,changed_corner_occurrences=changed,joint_count=len(centres))
