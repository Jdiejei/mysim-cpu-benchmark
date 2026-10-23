"""Narrow repair for recovered RGB colour buffers incorrectly encoded as RGBA FBX layers."""
import array
import numpy as np
from io_scene_fbx import import_fbx
COUNTS={'rgb_colour_layers_expanded':0,'constant_tail_components_recovered':0,'approximate_tail_components':0,'unrepaired':[]}
_original=import_fbx.blen_read_geom_array_foreach_set_indexed
def _indexed(*args,**kwargs):
    a=list(args)
    if a[7]==b'LayerElementColor' and a[6]==4 and len(a[4]):
        indices=np.asarray(a[4]);highest=int(indices.max());mesh=a[0][0].id_data if len(a[0]) and hasattr(a[0][0],'id_data') else None
        expected={highest+1}
        if mesh is not None and hasattr(mesh,'vertices'):expected.update((len(mesh.vertices),len(mesh.loops)))
        candidates=sorted(n for n in expected if n>highest and 0<=3*n-len(a[3])<=3)
        if candidates and highest>=len(a[3])//4:
            n=candidates[0];raw=np.asarray(a[3],dtype=np.float64);missing=3*n-len(raw)
            if missing:
                constant=bool(np.all(raw==raw[0]));last_complete=raw[:len(raw)//3*3].reshape((-1,3))[-1];tail=[raw[0]]*missing if constant else list(last_complete[len(raw)%3:])
                raw=np.concatenate((raw,np.asarray(tail)));COUNTS['constant_tail_components_recovered' if constant else 'approximate_tail_components']+=missing
            rgb=raw.reshape((-1,3));rgba=np.ones((len(rgb),4),dtype=np.float64);rgba[:,:3]=rgb;a[3]=array.array('d',rgba.ravel());a[5]=4;COUNTS['rgb_colour_layers_expanded']+=1
        elif highest>=len(a[3])//4 and len(COUNTS['unrepaired'])<10:COUNTS['unrepaired'].append({'floats':len(a[3]),'index_max':highest})
    return _original(*a,**kwargs)
def install():
    if import_fbx.blen_read_geom_array_foreach_set_indexed is not _indexed:import_fbx.blen_read_geom_array_foreach_set_indexed=_indexed
