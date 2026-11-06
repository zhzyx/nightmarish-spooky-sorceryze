import bpy, json, sys
from pathlib import Path
rig=bpy.data.objects['RIG-rain']
names=['MSTR-Jaw','MSTR-Mouth','MSTR-Eyebrow.L','ACT-Eyelid_Upper.L','TGT-Eyes','FK-Head','FK-Neck']
out={n:{'head':list(rig.pose.bones[n].head),'tail':list(rig.pose.bones[n].tail),'matrix':[list(r) for r in rig.pose.bones[n].matrix],'props':{k:str(v) for k,v in rig.pose.bones[n].items()}} for n in names}
out['mouth_controls']=[p.name for p in rig.pose.bones if any(w in p.name for w in ['Lips','Lip_','Corner']) and not p.name.startswith(('DEF','MCH','N-','P-','AIM','TAN','BB-','GRP','COR','ROT','SCL','STR'))]
out['bounds']={o.name:[list(v) for v in o.bound_box] for o in bpy.data.objects if o.name in ['GEO-rain-head','GEO-rain-body','GEO-rain-eyes']}
out['readme']=bpy.data.texts['ReadMe.txt'].as_string()
Path(sys.argv[-1]).write_text(json.dumps(out,indent=2))
