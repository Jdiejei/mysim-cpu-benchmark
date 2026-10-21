import bpy,sys,os,json,time,hashlib,zipfile,subprocess,io,contextlib,shutil,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import import_patch
from rebuild_ops import rebuild,render_review
root=Path.cwd();name=sys.argv[sys.argv.index('--')+1];job=json.loads((root/'wave-input'/f'{name}.json').read_text());sources={s['key']:s for s in json.loads((root/'sources.json').read_text())};wave=os.environ.get('WAVE','0001');tag='candidates-wave-'+wave;out=root/'results'/name;out.mkdir(parents=True,exist_ok=True);start=time.monotonic();last_publish=0;records=[];failed=[];remaining=[];loaded=None
report={'job_id':name,'state':'RUNNING','assigned_mesh_references':len(job['recipes']),'processed':0,'failed':0,'records':records,'failures':failed,'remaining':remaining,'quality_accepted':False,'runtime_specs':{'cpu_count':os.cpu_count(),'RAM_GiB':round(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')/2**30,1),'free_disk_GiB':round(shutil.disk_usage(root).free/2**30,1)}}
assert os.cpu_count()>=4 and report['runtime_specs']['RAM_GiB']>=12,'Runner does not meet documented CPU/RAM requirements'
def checkpoint(force=False):
    global last_publish
    report.update(processed=len(records),failed=len(failed),elapsed_seconds=round(time.monotonic()-start,2),updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));p=out/f'{name}-checkpoint.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));tmp.replace(p)
    if force or time.monotonic()-last_publish>300:
        run=subprocess.run(['gh','release','upload',tag,str(p),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],capture_output=True);last_publish=time.monotonic()
        if run.returncode:print('CHECKPOINT_PUBLISH_WARNING',run.stderr.decode(errors='replace'),flush=True)
checkpoint(True);import_patch.install()
for index,recipe in enumerate(job['recipes']):
    if time.monotonic()-start>4.5*3600:remaining.extend(r['procedure_id'] for r in job['recipes'][index:]);break
    try:
        key=recipe['source_key'];s=sources[key]
        if key!=loaded:
            folder=root/'cache';folder.mkdir(exist_ok=True);archive=folder/s['archive']
            if not archive.exists():subprocess.run(['gh','release','download','inputs-v1','--repo',os.environ.get('INPUT_REPOSITORY','Shashanksaraswat123939/mysim-cpu-benchmark'),'--pattern',s['archive'],'--dir',str(folder)],check=True)
            with zipfile.ZipFile(archive) as z:data=z.read('source.fbx')
            assert hashlib.sha256(data).hexdigest()==s['sha256'],'Input source SHA mismatch';local=folder/'source.fbx';local.write_bytes(data);del data;bpy.ops.wm.read_factory_settings(use_empty=True);log=io.StringIO()
            with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):bpy.ops.import_scene.fbx(filepath=str(local),use_anim=False)
            errors=[line for line in log.getvalue().splitlines() if any(t in line.lower() for t in ['error','out of bounds','invalid'])]
            if errors:raise RuntimeError('FBX import still has invalid layer data: '+errors[0])
            loaded=key;report['import_repairs']=dict(import_patch.COUNTS)
        obj=bpy.context.scene.objects.get(recipe['mesh']);assert obj is not None,'Mesh not found'
        expected=recipe.get('specification') or {};assert len(obj.data.vertices)==expected.get('vertices',len(obj.data.vertices)),'Source mesh vertex count changed'
        if recipe['category']!='barrier' or 'armco' not in obj.name.lower():raise RuntimeError('Dedicated component reconstruction operator not yet validated for this asset family')
        result,extra=rebuild(obj,recipe,root/'wave-input');path=out/(recipe['procedure_id']+'.blend');result['review_images']=render_review(obj,extra,path);bpy.data.libraries.write(str(path),{obj,*extra},compress=True)
        result.update(procedure_id=recipe['procedure_id'],mesh=recipe['mesh'],source_key=key,category=recipe['category'],output=path.name,output_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());records.append(result)
        # Release added grass geometry after saving this item; its output is already durable.
        for detail in extra:bpy.data.objects.remove(detail,do_unlink=True)
    except Exception as e:failed.append({'procedure_id':recipe['procedure_id'],'mesh':recipe['mesh'],'error':str(e)});traceback.print_exc()
    checkpoint(True);print('MESH_PROGRESS',len(records),len(failed),len(job['recipes']),flush=True)
report['state']='COMPLETE' if not remaining and not failed else 'PARTIAL' if remaining else 'NEEDS_REPAIR';checkpoint(True)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in {'.blend','.png'}};(out/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2));archive=root/f'{name}-{os.environ.get("GITHUB_RUN_ID","local")}.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in out.iterdir():z.write(p,p.name)
run=subprocess.run(['gh','release','upload',tag,str(archive),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],capture_output=True)
if run.returncode:raise RuntimeError('Output upload failed: '+run.stderr.decode(errors='replace'))
print('JOB_RESULT',json.dumps({k:v for k,v in report.items() if k not in ['records','failures','import_repairs']}),flush=True)

if failed:raise RuntimeError('Rebuild validation failures: '+str(len(failed)))
