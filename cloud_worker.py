import bpy,bmesh,time,json,math,hashlib,os,sys,zipfile,subprocess,statistics,traceback
from pathlib import Path
root=Path.cwd();args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [];pilot='--pilot' in args;group=int(args[0]) if args and args[0].isdigit() else 0
out=root/'results';out.mkdir(exist_ok=True);started=time.monotonic();budget=420 if pilot else 4.5*3600
sources=json.loads((root/('pilot-inputs.json' if pilot else 'sources.json')).read_text());plans=json.loads((root/'groups.json').read_text()) if not pilot else None
assigned=[{'key':s['key'],'part':0,'parts':1} for s in sources] if pilot else plans[group]['shards'];source_map={s['key']:s for s in sources};records=[];failures=[];remaining=[];timings=[]
def category(name):return name.lower().split('_')[0]
def improve(obj):
    # Conservative candidate pass; originals and driving surface positions are retained.
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    before=(len(obj.data.vertices),len(obj.data.polygons));kind=category(obj.name);start=time.monotonic();changes=[]
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();changes.append('recalculate_normals')
    if kind not in {'gnd','geo','org','billboarded','overlay','overlays','crowd'} and len(obj.data.polygons)>12:
        spans=[max(v.co[a] for v in obj.data.vertices)-min(v.co[a] for v in obj.data.vertices) for a in range(3)];width=max(spans)*.0005
        if width>0:
            m=obj.modifiers.new('CandidateEdgeDetail','BEVEL');m.width=width;m.segments=3;m.limit_method='ANGLE';m.angle_limit=.8;m.use_clamp_overlap=True
            bpy.ops.object.modifier_apply(modifier=m.name);changes.append('three_segment_angle_bevel')
    detailed_faces=len(obj.data.polygons)
    lod=None
    if detailed_faces>100 and kind not in {'gnd','geo','overlay','overlays','billboarded'}:
        lod=obj.copy();lod.data=obj.data.copy();bpy.context.collection.objects.link(lod);lod.name=obj.name+'__candidate_LOD1';obj.select_set(False);lod.select_set(True);bpy.context.view_layer.objects.active=lod
        m=lod.modifiers.new('CandidateLOD','DECIMATE');m.ratio=.5;bpy.ops.object.modifier_apply(modifier=m.name);lod.hide_render=True;changes.append('separate_50_percent_LOD')
    valid=all(math.isfinite(v) for vert in obj.data.vertices for v in vert.co)
    if not valid:raise ValueError('Nonfinite geometry')
    return {'name':obj.name,'category':kind,'before_vertices':before[0],'before_faces':before[1],'candidate_faces':detailed_faces,'lod_faces':len(lod.data.polygons) if lod else None,'seconds':time.monotonic()-start,'changes':changes,'validation':'finite coordinates; no artistic or game acceptance'}
for assignment_index,a in enumerate(assigned):
    s=source_map[a['key']];archive=root/'cache'/s['archive'];archive.parent.mkdir(exist_ok=True)
    if time.monotonic()-started>budget:remaining.extend(assigned[assignment_index:]);break
    if not archive.exists():subprocess.run(['gh','release','download','inputs-v1','--repo',os.environ['GITHUB_REPOSITORY'],'--pattern',s['archive'],'--dir',str(archive.parent)],check=True)
    with zipfile.ZipFile(archive) as z:data=z.read('source.fbx')
    if hashlib.sha256(data).hexdigest()!=s['sha256']:raise RuntimeError('Source hash mismatch')
    local=archive.with_suffix('.fbx');local.write_bytes(data);del data;bpy.ops.wm.read_factory_settings(use_empty=True);t=time.monotonic();bpy.ops.import_scene.fbx(filepath=str(local),use_anim=False)
    objs=sorted([o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.polygons],key=lambda o:o.name);selected=[o for o in objs if int(hashlib.sha256(o.name.encode()).hexdigest(),16)%a['parts']==a['part']]
    if pilot:
        strata={}
        for o in selected:strata.setdefault(category(o.name),[]).append(o)
        selected=[]
        for kind,items in sorted(strata.items()):
            items.sort(key=lambda o:len(o.data.polygons));indices=sorted({int((len(items)-1)*j/9) for j in range(10)})
            selected.extend(items[j] for j in indices)
    import_seconds=time.monotonic()-t;processed=[]
    for i,obj in enumerate(selected):
        if time.monotonic()-started>budget:
            remaining.append({**a,'resume_names':[o.name for o in selected[i:]]});break
        try:
            r=improve(obj);r['source_key']=s['key'];records.append(r);processed.append(r['name']);print('PROGRESS',len(records),round(time.monotonic()-started,1),flush=True)
        except Exception as e:failures.append({'source_key':s['key'],'name':obj.name,'error':str(e)})
    if not pilot:
        keep=set(processed)
        for obj in list(bpy.context.scene.objects):
            if obj.type=='MESH' and obj.name not in keep and not any(obj.name.startswith(n+'__candidate_LOD1') for n in keep):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/f"{s['key']}-part{a['part']}.blend"),compress=True)
    timings.append({'source_key':s['key'],'import_seconds':import_seconds,'available_meshes':len(objs),'selected_meshes':len(selected)})
    report={'group':group,'pilot':pilot,'seconds':time.monotonic()-started,'records':records,'failures':failures,'remaining':remaining,'sources':timings,'scope':'Conservative normals/bevel/LOD candidate pass. Ground/grass, decals and vegetation need category-specific design work. Not maximum detail, not final acceptance.'};(out/'checkpoint.json').write_text(json.dumps(report,indent=2))
    local.unlink(missing_ok=True);archive.unlink(missing_ok=True)
if pilot:
    by={}
    for r in records:by.setdefault(r['category'],[]).append(r['seconds'])
    report['category_seconds']={k:{'n':len(v),'mean':statistics.mean(v),'max':max(v)} for k,v in by.items()};(out/'checkpoint.json').write_text(json.dumps(report,indent=2))
