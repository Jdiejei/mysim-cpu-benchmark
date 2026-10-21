import bpy,sys,json,hashlib,zipfile,subprocess,os,time,collections,math,io,contextlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));import import_patch
root=Path.cwd();name=sys.argv[sys.argv.index('--')+1];job=json.loads((root/'structure-input'/f'{name}.json').read_text());catalog={x['key']:x for x in json.loads((root/'sources.json').read_text())};out=root/'results'/name;out.mkdir(parents=True,exist_ok=True);start=time.monotonic();records=[];failures=[];tag='candidates-wave-'+os.environ['WAVE'];report=dict(job_id=name,state='RUNNING',assigned_mesh_references=len(job['items']),processed=0,failed=0,records=records,failures=failures,quality_accepted=False,scope='source_structure_inspection_only')
def publish():
 report.update(processed=len(records),failed=len(failures),elapsed_seconds=round(time.monotonic()-start,2),updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));p=out/(name+'-checkpoint.json');p.write_text(json.dumps(report));subprocess.run(['gh','release','upload',tag,str(p),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True)
def inspect(obj):
 mesh=obj.data;n=len(mesh.vertices);parent=list(range(n));sizes=[1]*n
 def find(a):
  while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
  return a
 for edge in mesh.edges:
  a,b=map(find,edge.vertices)
  if a!=b:
   if sizes[a]<sizes[b]:a,b=b,a
   parent[b]=a;sizes[a]+=sizes[b]
 groups={}
 for v in mesh.vertices:groups.setdefault(find(v.index),[]).append(v.index)
 edge_uses=collections.Counter()
 for p in mesh.polygons:
  for key in p.edge_keys:edge_uses[tuple(sorted(key))]+=1
 components=[]
 for ids in sorted(groups.values(),key=len,reverse=True)[:32]:
  lo=[min(mesh.vertices[i].co[a] for i in ids) for a in range(3)];hi=[max(mesh.vertices[i].co[a] for i in ids) for a in range(3)];components.append(dict(vertices=len(ids),minimum=lo,maximum=hi))
 allco=[v.co for v in mesh.vertices];lo=[min(v[a] for v in allco) for a in range(3)];hi=[max(v[a] for v in allco) for a in range(3)];span=[hi[a]-lo[a] for a in range(3)];axis=max(range(3),key=lambda a:span[a]);stations=[]
 if span[axis]>1e-12:
  for k in range(17):
   x=lo[axis]+span[axis]*k/16;near=[v for v in allco if abs(v[axis]-x)<=span[axis]/24]
   stations.append(dict(at=x,vertices=len(near),minimum=[min(v[a] for v in near) for a in range(3)] if near else None,maximum=[max(v[a] for v in near) for a in range(3)] if near else None))
 uv={};mesh.calc_loop_triangles()
 for layer in mesh.uv_layers:
  degenerate=0
  for tri in mesh.loop_triangles:
   a,b,c=[layer.data[i].uv for i in tri.loops];area=abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))
   degenerate+=area<1e-12
  uv[layer.name]=dict(degenerate_triangles=degenerate,triangles=len(mesh.loop_triangles))
 return dict(vertices=n,faces=len(mesh.polygons),components_total=len(groups),largest_components=components,boundary_edges=sum(v==1 for v in edge_uses.values()),nonmanifold_face_edges=sum(v>2 for v in edge_uses.values()),unused_edges=len(mesh.edges)-len(edge_uses),uv_analysis=uv,materials=[m.name if m else None for m in mesh.materials],local_bounds=[lo,hi],world_matrix=[list(row) for row in obj.matrix_world],longitudinal_axis=axis,source_cross_sections=stations,finite=all(math.isfinite(x) for v in allco for x in v),geometry_changed=False)
import_patch.install();publish()
for key in sorted({x['source_key'] for x in job['items']}):
 items=[x for x in job['items'] if x['source_key']==key]
 try:
  s=catalog[key];cache=root/'cache';cache.mkdir(exist_ok=True);archive=cache/s['archive']
  if not archive.exists():subprocess.run(['gh','release','download','inputs-v1','--repo','Shashanksaraswat123939/mysim-cpu-benchmark','--pattern',s['archive'],'--dir',str(cache)],check=True,capture_output=True)
  with zipfile.ZipFile(archive) as z:data=z.read('source.fbx')
  assert hashlib.sha256(data).hexdigest()==s['sha256'];local=cache/'source.fbx';local.write_bytes(data);del data;bpy.ops.wm.read_factory_settings(use_empty=True);log=io.StringIO()
  with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):bpy.ops.import_scene.fbx(filepath=str(local),use_anim=False)
  errors=[v for v in log.getvalue().splitlines() if any(t in v.lower() for t in ['error','out of bounds','invalid'])];assert not errors,errors[:1];done={}
  for item in items:
   try:
    obj=bpy.context.scene.objects.get(item['mesh']);assert obj and obj.type=='MESH','Source mesh missing'
    if obj.name not in done:done[obj.name]=inspect(obj)
    records.append(dict(procedure_id=item['procedure_id'],mesh=item['mesh'],source_key=key,inspection_file=key+'.json',scope='source_structure_inspection_only',quality_accepted=False))
   except Exception as e:failures.append(dict(procedure_id=item['procedure_id'],mesh=item['mesh'],error=str(e)))
  (out/(key+'.json')).write_text(json.dumps(dict(source_sha256=s['sha256'],source_key=key,import_repairs=import_patch.COUNTS,meshes=done)))
 except Exception as e:failures.extend(dict(procedure_id=x['procedure_id'],mesh=x['mesh'],error=str(e)) for x in items if x['procedure_id'] not in {v['procedure_id'] for v in records})
 publish()
report['state']='NEEDS_REPAIR' if failures else 'COMPLETE';publish();manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.json')};(out/'SHA256SUMS.json').write_text(json.dumps(manifest));archive=root/(name+'-'+os.environ['GITHUB_RUN_ID']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in out.iterdir():z.write(p,p.name)
subprocess.run(['gh','release','upload',tag,str(archive),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True)
if failures:raise RuntimeError(str(len(failures))+' source inspection failures')
