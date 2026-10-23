import bpy,sys,os,json,time,random,hashlib,zipfile,subprocess,io,contextlib,shutil,traceback,resource
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from release_transport import public_download,release_upload
import import_patch
from rebuild_ops import rebuild,render_review
root=Path.cwd();name=sys.argv[sys.argv.index('--')+1];job=json.loads((root/'wave-input'/f'{name}.json').read_text());sources={s['key']:s for s in json.loads((root/'sources.json').read_text())};wave=os.environ.get('WAVE','0001');tag='candidates-wave-'+wave;out=root/'results'/name;out.mkdir(parents=True,exist_ok=True);start=time.monotonic();last_publish=0;records=[];failed=[];remaining=[];loaded=None
report={'job_id':name,'state':'RUNNING','assigned_mesh_references':len(job['recipes']),'processed':0,'failed':0,'records':records,'failures':failed,'remaining':remaining,'quality_accepted':False,'scope':job.get('scope','geometry_reconstruction_candidate'),'runtime_specs':{'cpu_count':os.cpu_count(),'RAM_GiB':round(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')/2**30,1),'free_disk_GiB':round(shutil.disk_usage(root).free/2**30,1)}}
assert os.cpu_count()>=4 and report['runtime_specs']['RAM_GiB']>=12,'Runner does not meet documented CPU/RAM requirements'
def publish_file(path):
    # Space release writes, then back off on transient publication failures.
    time.sleep(random.uniform(1,12))
    for attempt in range(7):
        result=subprocess.run(['gh','release','upload',tag,str(path),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],capture_output=True)
        if result.returncode==0:return result
        if attempt<6:time.sleep(min(90,3*2**attempt)+random.uniform(1,8))
    return result

def current_rss_mib():
    try:return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')/1024**2
    except Exception:return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024

def checkpoint(force=False):
    global last_publish
    report.update(current_process_RSS_MiB=round(current_rss_mib(),1),peak_process_RSS_MiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),processed=len(records),failed=len(failed),elapsed_seconds=round(time.monotonic()-start,2),updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));p=out/f'{name}-checkpoint.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2));tmp.replace(p)
    if force or time.monotonic()-last_publish>300:
        run=publish_file(p);last_publish=time.monotonic()
        if run.returncode:print('CHECKPOINT_PUBLISH_WARNING',run.stderr.decode(errors='replace'),flush=True)
def operator_progress(info):
    assert current_rss_mib()<12288,'Process RSS exceeded12GiB guard'
    report['operator_progress']=info;checkpoint(False)
checkpoint(True);import_patch.install()
for index,recipe in enumerate(job['recipes']):
    instance_snapshot=None
    if current_rss_mib()>11264:remaining.extend(r['procedure_id'] for r in job['recipes'][index:]);break
    if time.monotonic()-start>4.5*3600 or sum(p.stat().st_size for p in out.iterdir() if p.is_file())>1024**3-32*1024**2:remaining.extend(r['procedure_id'] for r in job['recipes'][index:]);break
    try:
        key=recipe['source_key'];s=sources[key]
        if key!=loaded:
            folder=root/'cache';folder.mkdir(exist_ok=True);archive=folder/s['archive']
            if not archive.exists():public_download(os.environ.get('INPUT_REPOSITORY','Shashanksaraswat123939/mysim-cpu-benchmark'),'inputs-v1',s['archive'],archive)
            with zipfile.ZipFile(archive) as z:data=z.read('source.fbx')
            assert hashlib.sha256(data).hexdigest()==s['sha256'],'Input source SHA mismatch';local=folder/'source.fbx';local.write_bytes(data);del data;bpy.ops.wm.read_factory_settings(use_empty=True);log=io.StringIO()
            with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):bpy.ops.import_scene.fbx(filepath=str(local),use_anim=False)
            errors=[line for line in log.getvalue().splitlines() if any(t in line.lower() for t in ['error','out of bounds','invalid'])]
            if errors:raise RuntimeError('FBX import still has invalid layer data: '+errors[0])
            loaded=key;report['import_repairs']=dict(import_patch.COUNTS)
        obj=bpy.context.scene.objects.get(recipe['mesh']);assert obj is not None,'Mesh not found'
        expected=recipe.get('specification') or {};assert len(obj.data.vertices)==expected.get('vertices',len(obj.data.vertices)),'Source mesh vertex count changed'
        assert current_rss_mib()<12288,'Imported source exceeds12GiB process guard'
        if job.get('independent_source_instances') or recipe.get('reconstruction_mode')=='executable_mesh_program':
            instance_snapshot={o.name for o in bpy.data.objects};instance_mesh_snapshot={m.name for m in bpy.data.meshes};source_obj=obj;obj=source_obj.copy();obj.data=source_obj.data.copy();obj.name=source_obj.name+'__program_'+str(index);obj['original_source_mesh_name']=recipe['mesh'];bpy.context.collection.objects.link(obj)
        if not ((recipe.get('reconstruction_mode')=='executable_mesh_program' and recipe.get('executable_program',{}).get('file')=='mesh_programs/p_'+recipe['procedure_id']+'.py') or (recipe.get('reconstruction_mode')=='dedicated_sign_panel' and recipe['procedure_id'] in {'26d2a66fd51dc1e10a731ebb','e239e5bb0c4164e73b9487a4','17601e0a17d701965ee7ad44'}) or (recipe.get('reconstruction_mode')=='source_surface_refinement' and recipe['category']=='barrier') or (recipe['category']=='barrier' and ('armco' in obj.name.lower() or ('single' in obj.name.lower() and any(w in obj.name.lower() for w in ['tyre','tire'])))) or (recipe['category']=='ground' and any(w in obj.name.lower() for w in ['curb','kerb','ripple','drain']))):raise RuntimeError('Dedicated component reconstruction operator not yet validated for this asset family')
        if recipe.get('prototype_source_tile_only'):
            from drain_patch import extract_source_tile_patch
            report['prototype_source_patch']=extract_source_tile_patch(obj,recipe)
            if recipe.get('expected_source_component_root') is not None:assert report['prototype_source_patch']['selected_component']==recipe['expected_source_component_root'],'Wrong original source component selected'
        recipe['_operator_progress_callback']=operator_progress;recipe['_diagnostic_directory']=str(out);result,extra=rebuild(obj,recipe,root/'wave-input');path=out/(recipe['procedure_id']+'.blend');result['review_images']=render_review(obj,extra,path);bpy.data.libraries.write(str(path),{obj,*extra},compress=True)
        result.update(prototype_source_patch=report.get('prototype_source_patch') if recipe.get('prototype_source_tile_only') else None,source_scope=job.get('scope','full_source_mesh'),procedure_id=recipe['procedure_id'],mesh=recipe['mesh'],source_key=key,category=recipe['category'],output=path.name,output_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());records.append(result)
        # Release added grass geometry after saving this item; its output is already durable.
        for detail in extra:bpy.data.objects.remove(detail,do_unlink=True)
    except Exception as e:failed.append({'procedure_id':recipe['procedure_id'],'mesh':recipe['mesh'],'error':str(e)});traceback.print_exc()
    if instance_snapshot is not None:
        instance_objects=[o for o in bpy.data.objects if o.name not in instance_snapshot];meshes={o.data for o in instance_objects if o.type=='MESH'}
        for o in instance_objects:bpy.data.objects.remove(o,do_unlink=True)
        for mesh in list(bpy.data.meshes):
            if mesh.name not in instance_mesh_snapshot and mesh.users==0:bpy.data.meshes.remove(mesh)
    checkpoint(False);print('MESH_PROGRESS',len(records),len(failed),len(job['recipes']),flush=True)
report['state']='COMPLETE' if not remaining and not failed else 'PARTIAL' if remaining else 'NEEDS_REPAIR';checkpoint(True)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in {'.blend','.png'}};(out/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2));archive=root/f'{name}-{os.environ.get("GITHUB_RUN_ID","local")}.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in out.iterdir():z.write(p,p.name)
run=release_upload(['gh','release','upload',tag,str(archive),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],mandatory=True)
if run.returncode:raise RuntimeError('Output upload failed: '+run.stderr.decode(errors='replace'))
print('JOB_RESULT',json.dumps({k:v for k,v in report.items() if k not in ['records','failures','import_repairs']}),flush=True)

if failed:raise RuntimeError('Rebuild validation failures: '+str(len(failed)))
