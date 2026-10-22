import bpy,bmesh,sys,os,json,time,hashlib,zipfile,subprocess,resource,math,statistics,gc
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
sys.path.insert(0,str(Path(__file__).resolve().parent))
import import_patch
from rebuild_ops import render_review
root=Path.cwd();name=sys.argv[sys.argv.index('--')+1];manifest=json.loads((root/'wave-input'/f'{name}.json').read_text());out=root/'results'/name;out.mkdir(parents=True,exist_ok=True);start=time.monotonic();wave=os.environ['WAVE'];tag='candidates-wave-'+wave;report=dict(job_id=name,state='RUNNING',assigned_mesh_references=1,processed=0,failed=0,records=[],failures=[],scope='full_source_assembly_candidate',quality_accepted=False);parts=[];extras=[];expected_components=len(manifest['components']);expected_triangle_count=len(manifest['expected_original_triangle_ids']);expected_LOD_count=sum(e.get('expected_lod_count',3) for e in manifest['components'])
def checkpoint(stage,**kwargs):
 report.update(elapsed_seconds=round(time.monotonic()-start,2),updated_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),operator_progress=dict(stage=stage,peak_RSS_MiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),**kwargs));p=out/f'{name}-checkpoint.json';p.write_text(json.dumps(report));subprocess.run(['gh','release','upload',tag,str(p),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True);assert time.monotonic()-start<4.5*3600,'Assembly compute budget exceeded';assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<12*1024*1024,'Assembly process exceeded12GiB safety budget'
def download(owner,release,filename,sha=None):
 folder=root/'assembly-cache'/owner;folder.mkdir(parents=True,exist_ok=True);path=folder/filename
 if not path.exists():subprocess.run(['gh','release','download',release,'--repo',owner+'/mysim-cpu-benchmark','--pattern',filename,'--dir',str(folder)],check=True,capture_output=True)
 if sha:assert hashlib.sha256(path.read_bytes()).hexdigest()==sha,'Archive SHA mismatch'
 return path
try:
 checkpoint('loading_original_source');source=manifest['source'];archive=download('Shashanksaraswat123939','inputs-v1',source['archive']);data=zipfile.ZipFile(archive).read('source.fbx');assert hashlib.sha256(data).hexdigest()==source['sha256'];fbx=root/'assembly-cache/source.fbx';fbx.write_bytes(data);del data;import_patch.install();bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(fbx),use_anim=False);original=bpy.context.scene.objects.get(manifest['source_mesh']);assert original is not None;original.data.calc_loop_triangles();assert len(original.data.loop_triangles)==len(manifest['expected_original_triangle_ids']);source_matrix=original.matrix_world.copy();source_parent=original.parent.name if original.parent else None;original.parent=None;original.matrix_world=source_matrix;original.name=manifest['parent_procedure_id']+'__full_original_collision';original.hide_render=True
 for obj in list(bpy.data.objects):
  if obj!=original:bpy.data.objects.remove(obj,do_unlink=True)
 for mesh in list(bpy.data.meshes):
  if not mesh.users:bpy.data.meshes.remove(mesh)
 bodytriangles=[];loaded_indices=[]
 for entry in manifest['components']:
  archive=download(entry['owner'],entry['release'],entry['archive'],entry['archive_sha256']);folder=root/'assembly-cache'/('component-'+str(entry['component_index']));folder.mkdir(exist_ok=True)
  with zipfile.ZipFile(archive) as z:
   hashes=json.loads(z.read('SHA256SUMS.json'));assert all(hashlib.sha256(z.read(n)).hexdigest()==v for n,v in hashes.items());assert hashes[entry['blend']]==entry['blend_sha256'];blend=folder/entry['blend'];blend.write_bytes(z.read(entry['blend']));q=json.loads(z.read(next(n for n in z.namelist() if n.endswith('-checkpoint.json'))));coverage=q['prototype_source_patch']['source_coverage'];assert not coverage['uncovered_nonzero_area_source_triangles'] and coverage['area_relative_error']<1e-5;assert q['prototype_source_patch']['selected_component']==entry['source_component_root']
  with bpy.data.libraries.load(str(blend),link=False) as (src,dst):dst.objects=list(src.objects)
  loaded=[o for o in dst.objects if o is not None];bodies=[o for o in loaded if o.get('rebuild_procedure_id')==entry['procedure_id'] and '__LOD' not in o.name];assert len(bodies)==1,'Ambiguous candidate body';body=bodies[0]
  for o in loaded:bpy.context.scene.collection.objects.link(o);o.hide_render=o!=body;o['assembly_component_index']=entry['component_index']
  assert len(body.data.uv_layers)==len(original.data.uv_layers),'UV layers lost in assembly';assert all(math.isfinite(v) for row in body.matrix_world for v in row);assert all(math.isfinite(x) for v in body.data.vertices for x in v.co);assert len(body.data.materials)==manifest['expected_material_count'] and all(body.data.materials),'Missing component material binding';bm=bmesh.new();bm.from_mesh(body.data);bad=sum(not e.is_manifold for e in bm.edges);bm.free();assert bad==0,'Loaded component nonmanifold';parts.append(body);extras.extend(o for o in loaded if o!=body);bodytriangles.extend(entry['original_triangle_ids']);loaded_indices.append(entry['component_index']);checkpoint('loading_verified_components',components_loaded=len(parts),components_expected=expected_components,generated_vertices=sum(len(o.data.vertices) for o in parts),generated_faces=sum(len(o.data.polygons) for o in parts))
 assert sorted(loaded_indices)==list(range(expected_components));assert len(bodytriangles)==len(set(bodytriangles)) and sorted(bodytriangles)==sorted(manifest['expected_original_triangle_ids']),'Original source triangle coverage incomplete/duplicated';bpy.context.view_layer.update()
 original.data.calc_loop_triangles();sourceverts=[source_matrix@v.co for v in original.data.vertices];samples=[(p,None) for p in sourceverts]
 for tri in original.data.loop_triangles:samples.append((sum((sourceverts[i] for i in tri.vertices),Vector())/3,tri))
 nearest=[None]*len(samples)
 for count,part in enumerate(parts):
  part.data.calc_loop_triangles();world=[part.matrix_world@v.co for v in part.data.vertices];tree=BVHTree.FromPolygons(world,[tuple(t.vertices) for t in part.data.loop_triangles],all_triangles=True)
  for i,(point,source_tri) in enumerate(samples):
   near,normal,index,distance=tree.find_nearest(point)
   if near is not None and (nearest[i] is None or distance<nearest[i]['distance']):
    uv=[]
    if source_tri:
     target=part.data.loop_triangles[index];corners=[world[j] for j in target.vertices]
     for layer in part.data.uv_layers:
      p=barycentric_transform(near,*corners,*[Vector((*layer.data[j].uv,0)) for j in target.loops]);uv.append((p.x,p.y))
    nearest[i]=dict(distance=distance,uv=uv)
  del tree,world;gc.collect();checkpoint('validating_global_source_profile',components_checked=count+1,components_expected=expected_components)
 assert max(abs(original.matrix_world[i][j]-source_matrix[i][j]) for i in range(4) for j in range(4))<1e-8,'Full source collision transform changed';assert all(v is not None for v in nearest);distances=[v['distance'] for v in nearest];scale=max(max(original.dimensions),1e-8);assert max(distances)<=scale*.003,'Full-source envelope/profile changed';uv_errors=[[],[]];pages=[]
 for (point,tri),near in zip(samples,nearest):
  if tri:
   for k,layer in enumerate(original.data.uv_layers[:2]):
    expected=sum((layer.data[i].uv for i in tri.loops),Vector((0,0)))/3;actual=Vector(near['uv'][k]);uv_errors[k].append((actual-expected).length)
    if k==1 and 1e-4<expected.y%1<1-1e-4:pages.append(math.floor(actual.y)==math.floor(expected.y))
 assert not any(not p for p in pages),'Assembly sampled encoded lightmap page mismatch'
 bounds=[part.matrix_world@Vector(c) for part in parts for c in part.bound_box];sourcebounds=[source_matrix@Vector(c) for c in original.bound_box];delta=max(abs(f([v[k] for v in bounds])-f([v[k] for v in sourcebounds])) for k in range(3) for f in [min,max]);assert delta<=max(.01,scale*.002),'Full-source bounds changed';checkpoint('rendering_full_source_assembly')
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world=scene.world or bpy.data.worlds.new('Assembly review world');scene.world.color=(.15,.15,.15);center=(Vector(tuple(min(v[k] for v in bounds) for k in range(3)))+Vector(tuple(max(v[k] for v in bounds) for k in range(3))))/2;radius=max(max(v[k] for v in bounds)-min(v[k] for v in bounds) for k in range(3));tri=max(original.data.loop_triangles,key=lambda t:t.area);normal=(sourceverts[tri.vertices[1]]-sourceverts[tri.vertices[0]]).cross(sourceverts[tri.vertices[2]]-sourceverts[tri.vertices[0]]).normalized();tangent=normal.cross(Vector((0,0,1))) if abs(normal.z)<.9 else normal.cross(Vector((0,1,0)));tangent.normalize();bitangent=normal.cross(tangent);lampdata=bpy.data.lights.new('Assembly review light','AREA');lampdata.energy=1000*radius*radius;lampdata.size=radius*2;lamp=bpy.data.objects.new('Assembly review light',lampdata);scene.collection.objects.link(lamp);lamp.location=center+normal*radius*2+tangent*radius;lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler();camdata=bpy.data.cameras.new('Assembly review camera');camdata.type='ORTHO';camdata.ortho_scale=radius*1.25;camdata.clip_start=radius*.001;camdata.clip_end=radius*100;cam=bpy.data.objects.new('Assembly review camera',camdata);scene.collection.objects.link(cam);scene.camera=cam;images=[]
 for index,direction in enumerate([normal*2+tangent*.8+bitangent*.3,normal*2]):
  cam.location=center+direction*radius;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'assembly-review-{index}.png');bpy.ops.render.render(write_still=True);images.append(Path(scene.render.filepath).name)
 bpy.data.objects.remove(cam,do_unlink=True);bpy.data.objects.remove(lamp,do_unlink=True)
 for index in sorted({0,min(1,expected_components-1),expected_components-1}):
  body=next(p for p in parts if p['assembly_component_index']==index);path=out/f'assembly-component-{index:02}.blend';images.extend(Path(p).name for p in render_review(body,[],path,detail_only=True))
 image_variance={}
 for filename in images:
  image=bpy.data.images.load(str(out/filename),check_existing=False);pixels=image.pixels[:];stride=max(4,(image.size[0]*image.size[1]//4096)*4);channels=[[pixels[i+c] for i in range(0,len(pixels)-3,stride)] for c in range(3)];variance=sum(statistics.pvariance(channel) for channel in channels);bpy.data.images.remove(image);assert variance>1e-7,'Assembly review image is blank';image_variance[filename]=variance
 assert sum('__LOD' in o.name for o in extras)==expected_LOD_count,'Assembly missing expected per-component LODs'
 for body in parts:body.hide_render=False
 original.hide_render=True;bundle=bpy.data.objects.new(manifest['parent_procedure_id']+'__candidate_assembly',None);scene.collection.objects.link(bundle);bundle['parent_procedure_id']=manifest['parent_procedure_id'];bundle['final_game_accepted']=False
 for obj in parts+extras+[original]:world=obj.matrix_world.copy();obj.parent=bundle;obj.matrix_world=world
 path=out/(manifest['parent_procedure_id']+'-assembly.blend');checkpoint('saving_full_source_candidate');bpy.data.libraries.write(str(path),{bundle,*parts,*extras,original},compress=True);record=dict(procedure_id=manifest['parent_procedure_id'],mesh=manifest['source_mesh'],scope='full_source_assembly_candidate',components=len(parts),original_triangles_covered=len(bodytriangles),vertices=sum(len(p.data.vertices) for p in parts),faces=sum(len(p.data.polygons) for p in parts),source_profile_samples=len(samples),source_to_candidate_max=max(distances),source_relative_tolerance=scale*.003,bounds_max_delta=delta,uv0_max_error=max(uv_errors[0]),uv1_max_error=max(uv_errors[1]),uv1_page_samples=len(pages),uv1_page_mismatches=sum(not p for p in pages),full_original_collision_retained=True,source_original_parent=source_parent,full_collision_world_matrix=[list(row) for row in original.matrix_world],source_world_matrix=[list(row) for row in source_matrix],all_original_source_triangles_covered_exactly_once=True,LOD_objects=[dict(name=o.name,vertices=len(o.data.vertices),faces=len(o.data.polygons)) for o in extras if '__LOD' in o.name],review_images=images,render_pixel_variance=image_variance,output=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),output_bytes=path.stat().st_size,peak_RSS_MiB=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),lightmap_array_appearance_validated=False,quality_accepted=False,automated_checks_passed=True);report['records']=[record];report.update(state='COMPLETE',processed=1);checkpoint('full_source_candidate_saved')
except Exception as error:
 import traceback;traceback.print_exc();report.update(state='NEEDS_REPAIR',failed=1,failures=[dict(procedure_id=manifest['parent_procedure_id'],error=str(error))]);checkpoint('assembly_validation_failed')
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in {'.blend','.png'}};(out/'SHA256SUMS.json').write_text(json.dumps(hashes));archive=root/f'{name}-{os.environ["GITHUB_RUN_ID"]}.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for path in out.iterdir():z.write(path,path.name)
subprocess.run(['gh','release','upload',tag,str(archive),'--repo',os.environ['GITHUB_REPOSITORY'],'--clobber'],check=True,capture_output=True)
if report['failed']:raise RuntimeError('Assembly validation failed; evidence retained')
