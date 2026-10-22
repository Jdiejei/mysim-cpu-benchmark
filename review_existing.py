import bpy,sys,json,os,time,zipfile,hashlib,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from rebuild_ops import render_review
from source_fidelity import source_fidelity
root=Path.cwd();name=sys.argv[sys.argv.index('--')+1];job=json.loads((root/'quality-input'/f'{name}.json').read_text());out=root/'results'/name;out.mkdir(parents=True,exist_ok=True);cache=root/'quality-cache';cache.mkdir(exist_ok=True);start=time.monotonic();records=[];failures=[];tag='candidates-wave-'+os.environ['WAVE'];report=dict(job_id=name,state='RUNNING',scope='existing_candidate_quality_review',assigned_mesh_references=len(job['candidates']),records=records,failures=failures,quality_accepted=False)
def publish():
 report.update(processed=len(records),failed=len(failures),elapsed_seconds=round(time.monotonic()-start,2),updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));p=out/(name+'-checkpoint.json');p.write_text(json.dumps(report));subprocess.run(['gh','release','upload',tag,str(p),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True)
publish()
for item in job['candidates']:
 try:
  archive=cache/(item['repo'].split('/')[0]+'-'+item['archive'])
  if not archive.exists():
   folder=cache/item['repo'].split('/')[0];folder.mkdir(exist_ok=True);subprocess.run(['gh','release','download',item['release'],'--repo',item['repo'],'--pattern',item['archive'],'--dir',str(folder),'--clobber'],check=True,capture_output=True);(folder/item['archive']).replace(archive)
  with zipfile.ZipFile(archive) as z:
   manifest=json.loads(z.read('SHA256SUMS.json'));data=z.read(item['candidate_file']);assert hashlib.sha256(data).hexdigest()==item['candidate_sha256']==manifest[item['candidate_file']],'Candidate source SHA mismatch'
  local=cache/'candidate.blend';local.write_bytes(data);del data;bpy.ops.wm.read_factory_settings(use_empty=True)
  with bpy.data.libraries.load(str(local),link=False) as (available,loaded):loaded.objects=available.objects
  objects=[o for o in loaded.objects if o]
  for obj in objects:bpy.context.scene.collection.objects.link(obj)
  bpy.context.view_layer.update()
  obj=next(o for o in objects if o.get('rebuild_procedure_id')==item['procedure_id']);source=next(o for o in objects if o.name==obj['collision_reference']);metrics=source_fidelity(obj,source);assert metrics['source_profile_within_tolerance'],'Candidate source profile exceeds source-relative distance threshold:'+json.dumps(metrics)
  comparison_images=[];material_review=None
  if item.get('enhanced_texture'):
   spec=item['enhanced_texture'];texture=root/spec['path'];assert hashlib.sha256(texture.read_bytes()).hexdigest()==spec['sha256'],'Enhanced texture SHA mismatch'
   before_geometry=[tuple(v.co) for v in obj.data.vertices];before_uvs=[[tuple(d.uv) for d in u.data] for u in obj.data.uv_layers]
   comparison_images=render_review(obj,[o for o in objects if o!=obj],out/(item['procedure_id']+'-original.blend'),detail_only=True)
   replacement=bpy.data.images.load(str(texture),check_existing=False);replaced=0
   for mat in obj.data.materials:
    if mat and mat.use_nodes:
     for node in mat.node_tree.nodes:
      if node.type=='TEX_IMAGE' and node.image and 'gnd_base_drain_01' in (node.image.name+' '+node.image.filepath):node.image=replacement;replaced+=1
   assert replaced>0,'Exact source texture image node not found:'+json.dumps([dict(material=m.name,node=n.name,image=n.image.name,path=n.image.filepath,size=list(n.image.size),packed=bool(n.image.packed_file)) for m in obj.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image])
   assert before_geometry==[tuple(v.co) for v in obj.data.vertices] and before_uvs==[[tuple(d.uv) for d in u.data] for u in obj.data.uv_layers],'Read-only review changed geometry or UVs'
   material_review=dict(texture_sha256=spec['sha256'],replaced_exact_source_nodes=replaced,saved_candidate_modified=False,geometry_and_UVs_unchanged=True)
  images=render_review(obj,[o for o in objects if o!=obj],out/(item['procedure_id']+'.blend'),detail_only=True);image=bpy.data.images.load(images[-1],check_existing=False);pixels=image.pixels[:];stride=max(4,(image.size[0]*image.size[1]//4096)*4);channels=[[pixels[i+c] for i in range(0,len(pixels)-3,stride)] for c in range(3)];variance=sum(sum(v*v for v in channel)/len(channel)-(sum(channel)/len(channel))**2 for channel in channels);bpy.data.images.remove(image);assert variance>1e-7,'Close-up render is blank or lacks measurable image variation';images=comparison_images+images;record=dict(material_review=material_review,render_pixel_variance=variance,procedure_id=item['procedure_id'],mesh=item['mesh'],source_candidate=item,source_fidelity=metrics,review_images=images,scope='existing_candidate_quality_review',geometry_unchanged=True,quality_accepted=False,final_game_accepted=False);records.append(record);(out/(item['procedure_id']+'-quality.json')).write_text(json.dumps(record))
 except Exception as e:failures.append(dict(procedure_id=item['procedure_id'],mesh=item['mesh'],error=str(e)))
 publish()
report['state']='NEEDS_REPAIR' if failures else 'COMPLETE';publish();manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()};(out/'SHA256SUMS.json').write_text(json.dumps(manifest));archive=root/(name+'-'+os.environ['GITHUB_RUN_ID']+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in out.iterdir():z.write(p,p.name)
subprocess.run(['gh','release','upload',tag,str(archive),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True)
if failures:raise RuntimeError(str(len(failures))+' source quality checks failed')
