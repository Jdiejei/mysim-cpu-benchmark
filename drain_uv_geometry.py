import math

def area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2 if len(poly)>2 else 0

def clip_convex(subject,boundary):
 boundary=list(boundary)
 if area(boundary)<0:boundary.reverse()
 result=list(subject)
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):
  if not result:break
  previous=result[-1];previous_distance=(b[0]-a[0])*(previous[1]-a[1])-(b[1]-a[1])*(previous[0]-a[0]);output=[]
  for current in result:
   distance=(b[0]-a[0])*(current[1]-a[1])-(b[1]-a[1])*(current[0]-a[0]);inside=distance>=-1e-10;was_inside=previous_distance>=-1e-10
   if inside!=was_inside:
    t=previous_distance/(previous_distance-distance);output.append((previous[0]+t*(current[0]-previous[0]),previous[1]+t*(current[1]-previous[1])))
   if inside:output.append(current)
   previous=current;previous_distance=distance
  result=[]
  for p in output:
   if not result or math.dist(p,result[-1])>1e-9:result.append(p)
  if len(result)>1 and math.dist(result[0],result[-1])<1e-9:result.pop()
 return result if len(result)>=3 and abs(area(result))>1e-12 else []

def capsule(x0,y0,x1,y1,inset=0,segments=16):
 radius=(y1-y0)/2-inset;cy=(y0+y1)/2;left=x0+(y1-y0)/2;right=x1-(y1-y0)/2
 if radius<=0:return []
 return [(right+radius*math.cos(-math.pi/2+math.pi*i/segments),cy+radius*math.sin(-math.pi/2+math.pi*i/segments)) for i in range(segments+1)]+[(left+radius*math.cos(math.pi/2+math.pi*i/segments),cy+radius*math.sin(math.pi/2+math.pi*i/segments)) for i in range(segments+1)]

def slot_weight(point,boxes):
 value=0
 for x0,y0,x1,y1 in boxes:
  r=(y1-y0)/2;cx=min(max(point[0],x0+r),x1-r);distance=r-math.hypot(point[0]-cx,point[1]-(y0+y1)/2);t=min(1,max(0,distance/max(r*.4,1e-12)));value=max(value,t*t*(3-2*t))
 return value
