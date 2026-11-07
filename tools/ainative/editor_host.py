"""File based subprocess transport. Factory is trusted local CLI config, never graph data."""
import argparse, base64, hashlib, importlib, json, math, os, struct
from pathlib import Path
from executor import Executor, snapshot_file
from extensions import NodeRegistry, publish_new, canonical

SECRET_KEYS={'token','api_key','apikey','password','secret','authorization','credentials','factory','python'}
def safe(value):
    if isinstance(value,dict):
        if any(k.lower() in SECRET_KEYS for k in value): raise ValueError('credential/config field forbidden')
        for child in value.values(): safe(child)
    elif isinstance(value,list):
        for child in value: safe(child)

def target_graph(model, target):
    """Select the target's dependency closure before reading files or node schemas.

    Graph identity/edge structure is checked globally so ambiguous IDs cannot
    change what is executed. Unrelated node configuration is not evaluated.
    """
    if not isinstance(model, dict) or not isinstance(model.get('nodes'), list) or not isinstance(model.get('edges'), list):
        raise ValueError('invalid model')
    nodes = {}
    for node in model['nodes']:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or not node['id'] or node['id'] in nodes:
            raise ValueError('invalid or duplicate node id')
        nodes[node['id']] = node
    if not isinstance(target, str) or target not in nodes:
        raise ValueError('unknown target node')
    incoming = {key: [] for key in nodes}
    for edge in model['edges']:
        if not isinstance(edge, dict) or not isinstance(edge.get('from'), str) or not isinstance(edge.get('to'), str):
            raise ValueError('invalid edge')
        if edge['to'] in incoming:
            incoming[edge['to']].append(edge['from'])
    required, pending = set(), [target]
    while pending:
        key = pending.pop()
        if key in required:
            continue
        if key not in nodes:
            raise ValueError('missing dependency')
        required.add(key)
        pending.extend(incoming[key])
    return {**model, 'nodes': [node for node in model['nodes'] if node['id'] in required],
            'edges': [edge for edge in model['edges'] if edge['to'] in required]}


def compile_graph(model):
    safe(model)
    assets=[]; graph=[]
    for n in model['nodes']:
        inputs={}; context=[]
        for field in ('source','image_context'):
            if n.get(field) or n.get(field+'_snapshot'):
                path=Path(n[field]) if n.get(field) else None
                ext=path.suffix.lower() if path else n[field+'_snapshot']['extension']
                if ext not in ('.png','.jpg','.jpeg','.glb','.gltf'): raise ValueError('unsupported asset')
                payload=snapshot_file(path) if path else dict(n[field+'_snapshot']); payload['extension']=ext
                # glTF must be self-contained; external buffers/textures are not snapshotted.
                if field=='image_context' and ext not in ('.png','.jpg','.jpeg'): raise ValueError('image context required')
                if ext in ('.gltf','.glb'):
                    def embedded(v):
                        if isinstance(v,dict):
                            if 'uri' in v and not v['uri'].startswith('data:'): raise ValueError('glTF must embed dependencies')
                            for x in v.values(): embedded(x)
                        elif isinstance(v,list):
                            for x in v: embedded(x)
                    data=base64.b64decode(payload['content_base64'])
                    if ext=='.glb':
                        magic,version,length,chunk_length,chunk_type=struct.unpack_from('<5I',data)
                        if magic!=0x46546c67 or version!=2 or length!=len(data) or chunk_type!=0x4e4f534a: raise ValueError('invalid GLB')
                        data=data[20:20+chunk_length]
                    embedded(json.loads(data))
                aid=n['id']+'-'+field
                assets.append(dict(id=aid,revision=payload['content_sha256'],type='image' if ext in ('.png','.jpg','.jpeg') else 'mesh',payload=payload))
                ref={'id':aid,'revision':payload['content_sha256']}
                if field=='source': inputs['source']=ref
                else: context.append(dict(artifact=ref,role='reference',scope='node',strength='reference'))
        if n.get('text'): context.append(dict(text=n['text'],role='instruction',scope='node',strength='constraint'))
        links={}
        for edge in model['edges']:
            if edge['to']==n['id']:
                port=edge.get('input','source')
                if port in links: raise ValueError('duplicate linked port')
                links[port]={'node':edge['from'],'port':edge.get('output','result')}; inputs.pop(port,None)
        graph.append(dict(id=n['id'],provider=n.get('provider','local-copy'),request=dict(node=n.get('type','copy'),version=n.get('version','1'),inputs=inputs,parameters=n['parameters'],context=context),links=links))
    return graph,dict(schema_version=1,artifacts=assets)


def normalize_editor_integers(graph, registry):
    """Godot JSON numbers arrive as floats; normalize only schema integer fields.

    This transport accepts integers exactly representable by JSON/IEEE doubles.
    Executor and direct CLI contracts retain their strict original type rules.
    """
    maximum = 2**53 - 1
    for node in graph:
        request = node['request']
        schema = registry.get(request['node'], request['version'])['parameters']
        params = request['parameters']
        if not isinstance(params, dict):
            raise ValueError('parameters must be object')
        params = dict(params)
        for name, spec in schema.get('properties', {}).items():
            if spec['type'] != 'integer' or name not in params:
                continue
            value = params[name]
            if type(value) is int:
                if abs(value) > maximum:
                    raise ValueError('editor integer exceeds JSON safe range: ' + name)
            elif type(value) is float and math.isfinite(value) and value.is_integer() and abs(value) <= maximum:
                params[name] = int(value)
            else:
                raise ValueError('editor integer must be a finite JSON safe integer: ' + name)
        request['parameters'] = params

def selected(host, request, preview=False):
    exported=host.export_node(request['run'], request['node']) if preview else host.export(request['run'])
    ref=exported['outputs'][request['node']]['result']
    asset=next(a for a in exported['manifest']['artifacts'] if a['id']==ref['id'] and a['revision']==ref['revision'])
    token=hashlib.sha256(canonical([request['run'],ref,asset]).encode()).hexdigest()
    return exported,asset,token

def dispatch(args,request):
    registry,providers=NodeRegistry(),{}
    if args.command in ('create','step'):
        module,func=args.factory.split(':'); registry,providers=getattr(importlib.import_module(module),func)()
    host=Executor(args.db,registry,providers)
    try:
        if args.command=='create':
            model = target_graph(request['model'], request['target']) if 'target' in request else request['model']
            graph,manifest=compile_graph(model)
            normalize_editor_integers(graph,registry)
            return {'run_id':host.create(graph,manifest)}
        if args.command=='retry': host.retry(request['run'],request['node']); return host.status(request['run'])
        if args.command=='preview':
            exported,asset,token=selected(host,request,preview=True)
            data=base64.b64decode(asset['payload']['content_base64'],validate=True)
            if hashlib.sha256(data).hexdigest()!=asset['payload']['content_sha256']: raise ValueError('digest')
            extension=asset['payload']['extension']
            if extension not in ('.png','.jpg','.jpeg','.glb','.gltf'): raise ValueError('unsupported preview format')
            path=Path(args.db).parent/(token+extension)
            try:
                with path.open('xb') as stream: stream.write(data)
            except FileExistsError:
                if path.read_bytes()!=data: raise ValueError('preview collision')
            return {'path':str(path),'token':token,'type':asset['type']}
        if args.command=='publish':
            exported,asset,token=selected(host,request)
            if request['confirmation']!=token: raise ValueError('stale confirmation')
            target=Path(request['target'])
            if target.suffix.lower() not in ('.tres','.tscn'): raise ValueError('Godot target required')
            data=Path(request['staged']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=request['staged_sha256']: raise ValueError('staged bytes changed')
            expected=b'[gd_resource ' if target.suffix.lower()=='.tres' else b'[gd_scene '
            if not data.startswith(expected): raise ValueError('encoded type mismatch')
            class Encoded:
                def encode(self,manifest): return data
            return publish_new(Encoded(),exported['manifest'],target)
        return getattr(host,args.command)(request['run'])
    finally: host.close()

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['create','step','status','cancel','retry','preview','publish']); p.add_argument('--db',required=True); p.add_argument('--factory',default='editor_demo:factory'); p.add_argument('--spec',required=True); p.add_argument('--result',required=True); args=p.parse_args()
    try: result={'ok':True,'result':dispatch(args,json.loads(Path(args.spec).read_text(encoding='utf-8')))}
    except Exception: result={'ok':False,'error':'editor_command_failed'}
    path=Path(args.result); temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(result),encoding='utf-8'); os.replace(temp,path)
    return 0 if result['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
