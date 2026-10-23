"""Executable construction for 504aee54cccd267994044c99.
Mesh: org_tree_x_eucalyptus_a_type_d_025 (vegetation / measured_vegetation)
Source: Assets/RealRacing/Source/Bathurst/processed/high/bathurst.fbx (sha256 8ce82690b5ef61c7a862dfff592d8d6d3d8f26a95f0ca193595d85cad7a095ed)
Design: tapered trunk sleeves on tall thin components, ellipsoid canopy shells on compact foliage components
Retains every original polygon and its UV corner values, adds manufactured
physical thickness and family-specific closed feature volumes.
This implementation is experimental until actual CPU candidate validation.
"""
SOURCE_ID='504aee54cccd267994044c99'
SOURCE_SHA256='8ce82690b5ef61c7a862dfff592d8d6d3d8f26a95f0ca193595d85cad7a095ed'
MESH_NAME='org_tree_x_eucalyptus_a_type_d_025'
EXPECTED_VERTICES=24
EXPECTED_FACES=16
EXPECTED_TRIANGLES=16
EXPECTED_UV_LAYERS=['UVChannel_0', 'UVChannel_1']
EXPECTED_COMPONENTS=4
EXPECTED_BOUNDARY_EDGES=24
EXPECTED_LOCAL_BOUNDS=[[555.8881225585938, 153.52560424804688, 427.4367980957031], [568.1251220703125, 169.783203125, 438.7124938964844]]
LONGITUDINAL_AXIS=1
FAMILY='measured_vegetation'
CATEGORY='vegetation'


import math, collections

def _sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def _add(a,b): return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def _mul(a,s): return (a[0]*s,a[1]*s,a[2]*s)
def _dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _norm(a): return math.sqrt(_dot(a,a))
def _unit(a):
    n=_norm(a)
    if n<1e-18: return (0.0,0.0,1.0)
    return (a[0]/n,a[1]/n,a[2]/n)
def _lerp(a,b,t): return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t)

def _weld(points, faces, tol):
    grid={}; uniq=[]; remap=[0]*len(points); inv=1.0/tol
    for i,p in enumerate(points):
        key=(int(math.floor(p[0]*inv)),int(math.floor(p[1]*inv)),int(math.floor(p[2]*inv)))
        found=None
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    cell=grid.get((key[0]+dx,key[1]+dy,key[2]+dz))
                    if cell:
                        for j in cell:
                            q=uniq[j]
                            if abs(q[0]-p[0])<=tol and abs(q[1]-p[1])<=tol and abs(q[2]-p[2])<=tol:
                                found=j; break
                    if found is not None: break
                if found is not None: break
            if found is not None: break
        if found is None:
            found=len(uniq); uniq.append(p); grid.setdefault(key,[]).append(found)
        remap[i]=found
    return uniq, remap, [[remap[v] for v in f] for f in faces]

def _face_normal(points, f):
    if len(f)<3: return (0.0,0.0,0.0)
    return _cross(_sub(points[f[1]],points[f[0]]),_sub(points[f[2]],points[f[0]]))

def _split_nonmanifold_boundary(points, faces, corner_uv):
    # Boundary vertices where more (or fewer) than two boundary edges meet make
    # per-edge wall construction nonmanifold. Split each such vertex into one
    # copy per wedge of incident faces (a wedge is a maximal set of faces
    # connected through edges at v used by exactly two faces); every wedge has
    # exactly two boundary edges at v, so all copies reach boundary degree 2.
    for _round in range(16):
        adj=_edge_adjacency(faces)
        bdeg=collections.Counter()
        for (a,b),recs in adj.items():
            if len(recs)==1:
                bdeg[a]+=1; bdeg[b]+=1
        bad=[v for v,d in bdeg.items() if d!=2]
        if not bad: return faces
        bads=set(bad)
        inc=collections.defaultdict(list)
        for pid,f in enumerate(faces):
            for v in f:
                if v in bads: inc[v].append(pid)
        newfaces=[list(f) for f in faces]
        for v in bad:
            fids=inc[v]
            if len(fids)<2: continue
            around=collections.defaultdict(list)
            for pid in fids:
                f=faces[pid]
                for k in range(len(f)):
                    if f[k]==v:
                        w1=f[(k-1)%len(f)]; w2=f[(k+1)%len(f)]
                        if w1!=v: around[tuple(sorted((v,w1)))].append(pid)
                        if w2!=v: around[tuple(sorted((v,w2)))].append(pid)
            parent={pid:pid for pid in fids}
            def find(a):
                while parent[a]!=a:
                    parent[a]=parent[parent[a]]; a=parent[a]
                return a
            for e,ps in around.items():
                if len(ps)==2 and len(adj[e])==2:
                    ra,rb=find(ps[0]),find(ps[1])
                    if ra!=rb: parent[rb]=ra
            runs=collections.defaultdict(list)
            for pid in fids: runs[find(pid)].append(pid)
            if len(runs)<=1: continue
            for root,fids2 in runs.items():
                nv=len(points); points.append(list(points[v]))
                for pid in fids2:
                    nf=newfaces[pid]
                    for k in range(len(nf)):
                        if nf[k]==v: nf[k]=nv
        faces=newfaces
    raise AssertionError('Could not split nonmanifold boundary vertices')

def _repair(points, faces, corner_uv, scale):
    # No source polygon may be dropped: provenance validation requires every
    # original polygon to survive, non-degenerate. Repeated-index and
    # nonmanifold edges are unshared with private vertex copies; zero-area
    # faces are nudged by a tiny source-relative epsilon until every fan
    # triangle has area.
    eps=max(1e-4*scale,1e-12)
    private=set()
    newf=[]
    for f in faces:
        if len(set(f))==len(f): newf.append(list(f)); continue
        seen={}; nf=[]
        for v in f:
            if v in seen:
                nv=len(points); points.append(list(points[v])); private.add(nv); nf.append(nv)
            else:
                seen[v]=v; nf.append(v)
        newf.append(nf)
    faces=newf
    uses=collections.Counter()
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]): uses[tuple(sorted((a,b)))]+=1
    nm={e for e,c in uses.items() if c>2}
    if nm:
        newf=[]
        for f in faces:
            orig=list(f); nf=list(f)
            for k in range(len(nf)):
                a,b=orig[k],orig[(k+1)%len(orig)]
                if tuple(sorted((a,b))) in nm:
                    ia=len(points); ib=ia+1
                    points.append(list(points[a])); points.append(list(points[b]))
                    private.add(ia); private.add(ib)
                    nf[k]=ia; nf[(k+1)%len(nf)]=ib
            newf.append(nf)
        faces=newf
    faces=_split_nonmanifold_boundary(points, faces, corner_uv)
    for _pass in range(4):
        bad=[]
        for f in faces:
            for k in range(1,len(f)-1):
                n=_cross(_sub(points[f[k]],points[f[0]]),_sub(points[f[k+1]],points[f[0]]))
                if _norm(n)<=eps*eps: bad.append(f); break
        if not bad: break
        for f in bad:
            vs=list(dict.fromkeys(f))
            priv=[v for v in vs if v in private] or vs
            for j,v in enumerate(priv):
                ang=0.7*_pass+1.3*j+0.31
                d=_unit((math.cos(ang),math.sin(ang),math.cos(ang*0.5)))
                points[v]=_add(points[v],_mul(d,eps*(1+_pass)))
    else:
        raise AssertionError('Could not repair degenerate source faces')
    return points, faces, corner_uv

def _components(n, faces):
    parent=list(range(n)); size=[1]*n
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]; a=parent[a]
        return a
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):
            ra,rb=find(a),find(b)
            if ra!=rb:
                if size[ra]<size[rb]: ra,rb=rb,ra
                parent[rb]=ra; size[ra]+=size[rb]
    groups={}
    for v in range(n): groups.setdefault(find(v),[]).append(v)
    return list(groups.values())

def _edge_adjacency(faces):
    adj=collections.defaultdict(list)
    for pid,f in enumerate(faces):
        for a,b in zip(f,f[1:]+f[:1]): adj[tuple(sorted((a,b)))].append((pid,a,b))
    return adj

def _flat_uv(ctx, q):
    # Average per-layer UV of the source face whose centroid is nearest to q.
    best=None; bd=None
    centroids=ctx['centroids']
    for i,c in enumerate(centroids):
        d=_norm(_sub(c,q))
        if bd is None or d<bd: bd=d; best=i
    loops=ctx['corner_uv'][best]
    nl=ctx['nlayers']
    acc=[[0.0,0.0] for _ in range(nl)]
    for loop in loops:
        for l in range(nl): acc[l][0]+=loop[l][0]; acc[l][1]+=loop[l][1]
    n=len(loops)
    return [[acc[l][0]/n, acc[l][1]/n] for l in range(nl)]

def _obox(ctx, c, e0, e1, e2, h0, h1, h2, uv):
    # Closed oriented box, outward winding. Basis orthonormalized, right-handed.
    e0=_unit(e0); e2=_unit(_cross(e0,e1)); e1=_unit(_cross(e2,e0))
    points=ctx['points']; faces=ctx['faces']; cu=ctx['cu']; pids=ctx['pids']; nl=ctx['nlayers']
    b=len(points)
    for i in range(8):
        sx=-h0 if (i&1)==0 else h0
        sy=-h1 if (i&2)==0 else h1
        sz=-h2 if (i&4)==0 else h2
        points.append(_add(c,_add(_mul(e0,sx),_add(_mul(e1,sy),_mul(e2,sz)))))
    for q in ((0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)):
        faces.append([b+i for i in q])
        cu.append([[list(uv[l]) for l in range(nl)] for _ in q])
        pids.append(-1)

def _frustum(ctx, p0, p1, r0, r1, seg, uv):
    # Closed tapered sleeve (cone frustum) between two circles, outward winding.
    points=ctx['points']; faces=ctx['faces']; cu=ctx['cu']; pids=ctx['pids']; nl=ctx['nlayers']
    axis=_unit(_sub(p1,p0))
    ref=(0.0,0.0,1.0) if abs(axis[2])<0.9 else (1.0,0.0,0.0)
    u=_unit(_cross(axis,ref)); v=_cross(axis,u)
    b=len(points)
    for i in range(seg):
        a=2.0*math.pi*i/seg; ca,sa=math.cos(a),math.sin(a)
        points.append(_add(p0,_add(_mul(u,ca*r0),_mul(v,sa*r0))))
    for i in range(seg):
        a=2.0*math.pi*i/seg; ca,sa=math.cos(a),math.sin(a)
        points.append(_add(p1,_add(_mul(u,ca*r1),_mul(v,sa*r1))))
    for i in range(seg):
        j=(i+1)%seg
        faces.append([b+i,b+j,b+seg+j,b+seg+i])
        cu.append([[list(uv[l]) for l in range(nl)] for _ in range(4)])
        pids.append(-1)
    c0=b+2*seg; points.append(p0)
    for i in range(seg):
        faces.append([c0,b+(i+1)%seg,b+i]); cu.append([[list(uv[l]) for l in range(nl)] for _ in range(3)]); pids.append(-1)
    c1=b+2*seg+1; points.append(p1)
    for i in range(seg):
        faces.append([c1,b+seg+i,b+seg+(i+1)%seg]); cu.append([[list(uv[l]) for l in range(nl)] for _ in range(3)]); pids.append(-1)

def _ellipsoid(ctx, c, r, su, sv, uv):
    # Closed ellipsoid shell, outward winding. Poles are single welded vertices
    # so every edge is shared by exactly two faces.
    points=ctx['points']; faces=ctx['faces']; cu=ctx['cu']; pids=ctx['pids']; nl=ctx['nlayers']
    b=len(points)
    np_=b; points.append((c[0], c[1], c[2]+r[2]))
    for iu in range(1,su-1):
        phi=math.pi*iu/(su-1)
        for iv in range(sv):
            th=2.0*math.pi*iv/sv
            points.append((c[0]+r[0]*math.sin(phi)*math.cos(th), c[1]+r[1]*math.sin(phi)*math.sin(th), c[2]+r[2]*math.cos(phi)))
    sp=b+1+(su-2)*sv; points.append((c[0], c[1], c[2]-r[2]))
    def vid(iu,iv):
        if iu<=0: return np_
        if iu>=su-1: return sp
        return b+1+(iu-1)*sv+(iv%sv)
    for iu in range(su-1):
        for iv in range(sv):
            a=vid(iu,iv); bb=vid(iu+1,iv); cc=vid(iu+1,iv+1); d=vid(iu,iv+1)
            if a==d:
                faces.append([a,bb,cc]); cu.append([[list(uv[l]) for l in range(nl)] for _ in range(3)])
            elif bb==cc:
                faces.append([a,bb,d]); cu.append([[list(uv[l]) for l in range(nl)] for _ in range(3)])
            else:
                faces.append([a,bb,cc,d]); cu.append([[list(uv[l]) for l in range(nl)] for _ in range(4)])
            pids.append(-1)

def _thicken(ctx):
    # Manufactured physical thickness: inward offset surface plus boundary walls.
    # Every source polygon is retained unchanged at its original position and UVs.
    points=ctx['points']; faces=ctx['faces']; cu=ctx['cu']; pids=ctx['pids']
    lo,hi=ctx['bounds']; scale=max(max(hi[a]-lo[a] for a in range(3)),1e-12)
    comps=ctx['components']
    gauge={}
    for vs in comps:
        spans=[max(points[v][a] for v in vs)-min(points[v][a] for v in vs) for a in range(3)]
        pos=sorted(s for s in spans if s>1e-12)
        flat=(len(pos)==0) or (min(spans)<0.01*scale)
        if flat: g=min(0.002*scale,0.4*pos[0]) if pos else 0.002*scale
        else: g=min(0.05*pos[0],0.02*scale)
        g=max(g,1e-9*scale)
        for v in vs: gauge[v]=g
    nsum=[[0.0,0.0,0.0] for _ in points]
    for f in faces:
        n=_face_normal(points,f)
        for v in f:
            for ax in range(3): nsum[v][ax]+=n[ax]
    base=len(points)
    for i in range(base):
        p=points[i]
        n=_unit(nsum[i]); g=gauge.get(i,0.002*scale)
        q=list(_sub(p,_mul(n,g)))
        # The inward offset must never leave the original bounds: the runner's
        # bounds guard rejects any silhouette change beyond 0.2% of world scale.
        for a in range(3):
            if q[a]<lo[a]: q[a]=lo[a]
            elif q[a]>hi[a]: q[a]=hi[a]
        points.append(tuple(q))
    nfaces=len(faces)
    for pid in range(nfaces):
        f=faces[pid]
        faces.append([v+base for v in reversed(f)])
        cu.append([list(loop) for loop in reversed(cu[pid])])
        pids.append(-1)
    adj=_edge_adjacency(faces[:nfaces])
    originals=len(faces)
    walls=0
    for edge,records in adj.items():
        if len(records)!=1: continue
        pid,a,b=records[0]; face=faces[pid]
        ia=face.index(a); ib=face.index(b)
        uv_a=cu[pid][ia]; uv_b=cu[pid][ib]
        faces.extend([[b,a,a+base],[b,a+base,b+base]])
        cu.extend([[list(uv_b),list(uv_a),list(uv_a)],[list(uv_b),list(uv_a),list(uv_b)]])
        pids.extend([-1,-1]); walls+=1
    assert len(faces)==originals+2*walls, 'Wall construction count mismatch'
    return ['manufactured_physical_thickness_with_closed_wall_returns','all_source_polygons_uv0_and_encoded_uv1_retained']

def _assert_closed(points, faces):
    incidence=collections.Counter()
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]): incidence[tuple(sorted((a,b)))]+=1
    bad=[e for e,c in incidence.items() if c!=2]
    assert not bad, 'Constructed mesh is not closed manifold: %d nonmanifold edges' % len(bad)

def _scale(ctx):
    lo,hi=ctx['bounds']
    return max(max(hi[a]-lo[a] for a in range(3)),1e-12)

def _cbounds(ctx, ci):
    vs=ctx['components'][ci]; pts=ctx['points']
    lo=[min(pts[v][a] for v in vs) for a in range(3)]
    hi=[max(pts[v][a] for v in vs) for a in range(3)]
    return lo,hi

def _beam(ctx, p0, p1, r, uv):
    d=_sub(p1,p0); L=_norm(d)
    if L<2e-12: return
    e0=_mul(d,1.0/L)
    ref=(0.0,0.0,1.0) if abs(e0[2])<0.9 else (1.0,0.0,0.0)
    e1=_unit(_cross(e0,ref))
    _obox(ctx,_lerp(p0,p1,0.5),e0,e1,(0.0,0.0,1.0),0.5*L,r,r,uv)

def _block(ctx, c, h, uv):
    _obox(ctx,c,(1.0,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0),h[0],h[1],h[2],uv)

def _box_axes(ctx, lo, hi, inset, uv):
    c=[(lo[a]+hi[a])*0.5 for a in range(3)]
    h=[max((hi[a]-lo[a])*0.5-inset,1e-9) for a in range(3)]
    _obox(ctx,c,(1.0,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0),h[0],h[1],h[2],uv)

def _corner_blocks(ctx, lo, hi, s, uv):
    n=0
    for cx in (lo[0],hi[0]):
        for cy in (lo[1],hi[1]):
            for cz in (lo[2],hi[2]):
                hx=min(0.5*s,max(hi[0]-lo[0],1e-12)*0.5)
                hy=min(0.5*s,max(hi[1]-lo[1],1e-12)*0.5)
                hz=min(0.5*s,max(hi[2]-lo[2],1e-12)*0.5)
                _block(ctx,(cx+hx if cx==lo[0] else cx-hx, cy+hy if cy==lo[1] else cy-hy, cz+hz if cz==lo[2] else cz-hz),(hx,hy,hz),uv)
                n+=1
    return n

def _rect_frame(ctx, lo, hi, a0, a1, a2, at_hi, r, uv):
    # Four beams around the (a0,a1) rectangle at the a2 face, inset by r so the
    # frame stays inside the bounds.
    c2=(hi[a2]-r) if at_hi else (lo[a2]+r)
    def mk(v0,v1):
        p=[0.0,0.0,0.0]; p[a0]=v0; p[a1]=v1; p[a2]=c2; return p
    A=mk(lo[a0],lo[a1]); B=mk(hi[a0],lo[a1]); C=mk(hi[a0],hi[a1]); D=mk(lo[a0],hi[a1])
    A[a0]+=r; A[a1]+=r; B[a0]-=r; B[a1]+=r; C[a0]-=r; C[a1]-=r; D[a0]+=r; D[a1]-=r
    if _norm(_sub(B,A))<=2e-12 or _norm(_sub(D,A))<=2e-12: return 0
    n=0
    for p,q in ((A,B),(B,C),(C,D),(D,A)):
        _beam(ctx,p,q,r,uv); n+=1
    return n

def _ranked_components(ctx, cap):
    order=sorted(range(len(ctx['components'])), key=lambda ci: -len(ctx['comp_faces'][ci]))
    return order[:cap]

def _boundary_edges(ctx, cap):
    adj=_edge_adjacency(ctx['faces'][:ctx['source_face_count']])
    out=[(a,b) for (a,b),recs in adj.items() if len(recs)==1]
    if len(out)>cap: out=out[:cap]
    return out

def _mid(p0,p1):
    return ((p0[0]+p1[0])*0.5,(p0[1]+p1[1])*0.5,(p0[2]+p1[2])*0.5)

def construct_family(ctx):
    changes=[]
    scale=_scale(ctx)
    sleeves=0; shells=0
    for ci in _ranked_components(ctx,32):
        if len(ctx['comp_faces'][ci])<3: continue
        flo,fhi=_cbounds(ctx,ci)
        span=[fhi[a]-flo[a] for a in range(3)]
        ax=max(range(3), key=lambda a: span[a])
        if span[ax]<0.03*scale: continue
        others=[span[a] for a in range(3) if a!=ax]
        r=max(0.4*min(others),1e-4*scale) if min(others)>1e-9 else 1e-4*scale
        c0=[(flo[a]+fhi[a])*0.5 for a in range(3)]; c1=list(c0)
        c0[ax]=flo[ax]+0.02*span[ax]; c1[ax]=fhi[ax]-0.02*span[ax]
        if span[ax]>=2.0*max(others):
            _frustum(ctx,c0,c1,r,max(r*0.6,1e-4*scale),12,_flat_uv(ctx,c0)); sleeves+=1
        else:
            top=[(flo[a]+fhi[a])*0.5 for a in range(3)]; top[ax]=flo[ax]+0.75*span[ax]
            rr=[0.5*span[0],0.5*span[1],0.5*span[2]]; rr[ax]=0.25*span[ax]
            _ellipsoid(ctx,top,rr,10,12,_flat_uv(ctx,top)); shells+=1
        if sleeves+shells>=24: break
    changes.append('tapered_trunk_sleeves=%d'%sleeves)
    changes.append('foliage_canopy_shells=%d'%shells)
    return changes

def construct(uniq, wf, corner_uv, nlayers, up, axis):
    points=list(uniq); faces=[list(f) for f in wf]
    cu=[[[list(x) for x in loop] for loop in face] for face in corner_uv]
    pids=list(range(len(faces)))
    centroids=[]
    for f in faces:
        c=[0.0,0.0,0.0]
        for v in f: c[0]+=points[v][0]; c[1]+=points[v][1]; c[2]+=points[v][2]
        centroids.append((c[0]/len(f),c[1]/len(f),c[2]/len(f)))
    lo=[min(p[a] for p in points) for a in range(3)]
    hi=[max(p[a] for p in points) for a in range(3)]
    comps=_components(len(points), faces)
    v2c={}
    for ci,vs in enumerate(comps):
        for v in vs: v2c[v]=ci
    comp_faces=[[] for _ in comps]
    face_comp=[-1]*len(faces)
    for fi,f in enumerate(faces):
        ci=v2c[f[0]]; face_comp[fi]=ci; comp_faces[ci].append(fi)
    ctx=dict(points=points, faces=faces, cu=cu, corner_uv=cu, pids=pids, nlayers=nlayers,
             components=comps, centroids=centroids, bounds=(lo,hi),
             source_face_count=len(faces), up=up, axis=axis,
             face_comp=face_comp, comp_faces=comp_faces, v2c=v2c)
    base0=len(points)
    changes=_thicken(ctx)
    changes.extend(construct_family(ctx))
    # Manufactured feature vertices (index >= 2*base0: after source and inward
    # offset copies) get a deterministic micro-jitter and an inset clamp so no
    # feature face is exactly coplanar with a source face and every feature
    # stays strictly inside the original bounds.
    lo,hi=ctx['bounds']; pts=ctx['points']
    scale=max(max(hi[a]-lo[a] for a in range(3)),1e-12)
    d=max(1e-6*scale,1e-12); jm=max(1e-5*scale,1e-12)
    for i in range(2*base0,len(pts)):
        q=list(pts[i])
        for a in range(3):
            if hi[a]-lo[a]>2*d: vlo,vhi=lo[a]+d,hi[a]-d
            else: vlo=vhi=(lo[a]+hi[a])*0.5
            v=q[a]+(((i*2654435761+a*40503)%2001)/1000.0-1.0)*jm
            if v<vlo: v=vlo
            elif v>vhi: v=vhi
            q[a]=v
        pts[i]=tuple(q)
    _assert_closed(ctx['points'], ctx['faces'])
    return dict(points=ctx['points'], faces=ctx['faces'], corner_uv=ctx['cu'],
                source_polygon_ids=ctx['pids']), changes

def apply(obj, recipe):
    from mathutils import Vector
    assert recipe['procedure_id']==SOURCE_ID and recipe['source_sha256']==SOURCE_SHA256, 'Wrong original source for executable procedure'
    mesh=obj.data
    src_name=obj.get('original_source_mesh_name') or obj.name
    assert src_name==MESH_NAME, 'Mesh name mismatch: %s' % src_name
    assert len(mesh.vertices)==EXPECTED_VERTICES, 'Source mesh vertex count changed'
    assert len(mesh.polygons)==EXPECTED_FACES, 'Source mesh face count changed'
    assert sorted(l.name for l in mesh.uv_layers)==sorted(EXPECTED_UV_LAYERS), 'Source UV layers changed'
    raw_points=[list(v.co) for v in mesh.vertices]
    raw_faces=[list(p.vertices) for p in mesh.polygons]
    raw_uv=[[[list(l.data[i].uv) for l in mesh.uv_layers] for i in p.loop_indices] for p in mesh.polygons]
    tris=sum(max(0,len(f)-2) for f in raw_faces)
    assert tris==EXPECTED_TRIANGLES, 'Source triangle count changed'
    raw_comps=_components(len(raw_points), raw_faces)
    assert len(raw_comps)==EXPECTED_COMPONENTS, 'Source component count changed: %d' % len(raw_comps)
    raw_adj=_edge_adjacency(raw_faces)
    boundary=sum(1 for r in raw_adj.values() if len(r)==1)
    assert boundary==EXPECTED_BOUNDARY_EDGES, 'Source boundary edge count changed: %d' % boundary
    lo=[min(p[a] for p in raw_points) for a in range(3)]
    hi=[max(p[a] for p in raw_points) for a in range(3)]
    for a in range(3):
        assert abs(lo[a]-EXPECTED_LOCAL_BOUNDS[0][a])<1e-4 and abs(hi[a]-EXPECTED_LOCAL_BOUNDS[1][a])<1e-4, 'Source bounds changed'
    scale=max(max(hi[a]-lo[a] for a in range(3)),1e-12)
    tol=min(0.00001,scale*0.000001)
    uniq, remap, wf=_weld(raw_points, raw_faces, tol)
    uniq, wf, wuv=_repair(uniq, wf, raw_uv, scale)
    mw=obj.matrix_world.to_3x3()
    up=max(range(3), key=lambda a: abs(mw[2][a]))
    result, changes=construct(uniq, wf, wuv, len(EXPECTED_UV_LAYERS), up, LONGITUDINAL_AXIS)
    new=mesh.copy(); new.clear_geometry(); new.from_pydata(result['points'],[],result['faces']); new.update()
    for layer in list(new.uv_layers): new.uv_layers.remove(layer)
    for index,old_layer in enumerate(mesh.uv_layers):
        layer=new.uv_layers.new(name=old_layer.name)
        for face,corners in zip(new.polygons,result['corner_uv']):
            for loop,values in zip(face.loop_indices,corners): layer.data[loop].uv=values[index]
    nbind=len(recipe['material_bindings'])
    for poly in new.polygons:
        pid=result['source_polygon_ids'][poly.index]
        mi=mesh.polygons[pid].material_index if pid>=0 else 0
        poly.material_index=mi if 0<=mi<max(1,nbind) else 0
    attribute=new.attributes.get('source_polygon_id')
    if attribute: new.attributes.remove(attribute)
    attribute=new.attributes.new(name='source_polygon_id',type='INT',domain='FACE')
    for i,pid in enumerate(result['source_polygon_ids']): attribute.data[i].value=pid
    obj.data=new
    obj['validate_source_face_provenance']=True
    # Review annotations: aim the close-up render at the largest source face.
    best=max(range(len(raw_faces)), key=lambda i: _norm(_face_normal(raw_points,raw_faces[i])))
    nrm=_unit(_face_normal(raw_points,raw_faces[best]))
    wn=(obj.matrix_world.to_3x3().inverted().transposed()@Vector(nrm)).normalized()
    obj['drain_source_normal_world']=list(wn)
    cen=[0.0,0.0,0.0]
    for v in raw_faces[best]: cen[0]+=raw_points[v][0]; cen[1]+=raw_points[v][1]; cen[2]+=raw_points[v][2]
    cen=[cen[0]/len(raw_faces[best]),cen[1]/len(raw_faces[best]),cen[2]/len(raw_faces[best])]
    obj['drain_review_target_local']=cen
    obj['drain_review_span']=scale
    return changes
