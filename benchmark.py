import bpy,time,json,math,statistics,os
from pathlib import Path
root=Path.cwd();start=time.perf_counter();bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(root/'input/sample.fbx'),use_anim=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and len(o.data.polygons)>0];import_seconds=time.perf_counter()-start
records=[];output=root/'results';output.mkdir(exist_ok=True)
for i,o in enumerate(meshes):
    if time.perf_counter()-start>180:break
    t=time.perf_counter();bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    verts=len(o.data.vertices);faces=len(o.data.polygons);extent=max(o.dimensions)
    bevel=o.modifiers.new('EdgeDetail','BEVEL');bevel.width=max(extent*.0005,.000001);bevel.segments=2;bevel.limit_method='ANGLE';bevel.angle_limit=.7
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    tri=o.modifiers.new('Triangulate','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
    detailed_faces=len(o.data.polygons)
    # Export evaluated detailed geometry, then create one lower-detail copy.
    bpy.ops.export_scene.gltf(filepath=str(output/f'mesh-{i}.glb'),export_format='GLB',use_selection=True,export_materials='NONE')
    dec=o.modifiers.new('LOD','DECIMATE');dec.ratio=.5;bpy.ops.object.modifier_apply(modifier=dec.name)
    records.append({'source_vertices':verts,'source_faces':faces,'detailed_faces':detailed_faces,'lod_faces':len(o.data.polygons),'seconds':time.perf_counter()-t})
    print('BENCH_PROGRESS',len(records),round(time.perf_counter()-start,2),flush=True)
times=[r['seconds'] for r in records];mean=statistics.mean(times);p95=sorted(times)[min(len(times)-1,math.ceil(.95*len(times))-1)]
result={'scope':'Measured car-mesh bevel + triangulation + GLB export + one decimated LOD. Not bespoke redesign, ground/grass improvement, material work, manual review or Unity integration. Car-only sample is not representative of all categories.','runner':{'cpu_count':os.cpu_count()},'import_seconds':import_seconds,'available_meshes':len(meshes),'processed_meshes':len(records),'processing_seconds':sum(times),'total_seconds':time.perf_counter()-start,'mean_seconds_per_mesh':mean,'p95_seconds_per_mesh':p95,'projection_mesh_references':98572,'five_hour_jobs_at_mean':math.ceil(98572*mean/18000),'five_hour_jobs_at_p95':math.ceil(98572*p95/18000),'records':records}
(output/'benchmark.json').write_text(json.dumps(result,indent=2));print('BENCH_RESULT',json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)
