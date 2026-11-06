"""Run in portable Blender against the licensed private Rain source; no autoexec."""
import bpy, json, sys
from pathlib import Path
out = Path(sys.argv[sys.argv.index('--') + 1])
report = {'blender': bpy.app.version_string, 'objects': [], 'texts': list(bpy.data.texts.keys())}
for obj in bpy.data.objects:
    item = {'name': obj.name, 'type': obj.type, 'hidden': obj.hide_get()}
    if obj.type == 'MESH':
        item.update(vertices=len(obj.data.vertices), shapes=list(obj.data.shape_keys.key_blocks.keys()) if obj.data.shape_keys else [], modifiers=[{'type': m.type, 'name': m.name} for m in obj.modifiers])
    if obj.type == 'ARMATURE':
        item['bones'] = [{'name': p.name, 'location': list(p.location), 'props': {k: str(v) for k,v in p.items()}} for p in obj.pose.bones]
    report['objects'].append(item)
out.write_text(json.dumps(report, indent=2), encoding='utf8')
print('RAIN_INSPECT', out)
