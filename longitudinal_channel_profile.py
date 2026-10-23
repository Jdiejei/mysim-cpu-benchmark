"""Measured trench03 longitudinal joints: no oval grate mask and no transverse invented slots."""
import math
# Pixel bounds are measured from source128px dark lanes. Peak is darkest pixel centre.
LANES=[(12/128,14/128,13.5/128),(37/128,41/128,37.5/128),(63/128,67/128,63.5/128),(88/128,92/128,88.5/128),(113/128,115/128,113.5/128)]
def sample_channel(point):
 u=point[0]%1
 for left,right,peak in LANES:
  if left<u<right:
   distance=(peak-u)/(peak-left) if u<=peak else (u-peak)/(right-peak)
   return .5*(1+math.cos(math.pi*distance))
 return 0.
def channel_contour(x0,y0,x1,y1,inset=0,segments=0):
 peak=next(c for a,b,c in LANES if abs(a-x0)<1e-10 and abs(b-x1)<1e-10);fraction=min(.95,inset/(((x1-x0)/2)*.4)*.95);left=x0+fraction*(peak-x0);right=x1-fraction*(x1-peak)
 return [(left,y0),(right,y0),(right,y1),(left,y1)]
