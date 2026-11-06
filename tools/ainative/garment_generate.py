"""Generate an independent garment with immutable bytes and provenance."""
import argparse, base64, hashlib, json, time
from pathlib import Path
from comfy_provider import factory
from editor_host import compile_graph
from executor import Executor
from extensions import publish_new

def publish_bytes(path,data):
    class BytesAdapter:
        def encode(self,manifest): return data
    return publish_new(BytesAdapter(),{'schema_version':1,'artifacts':[]},path)

def finalize_output(out,data,receipt,resume=False):
    if out.exists():
        if not resume or out.read_bytes()!=data: raise FileExistsError('Existing source differs or was not explicitly resumed')
    else: publish_bytes(out,data)
    publish_bytes(out.with_suffix('.receipt.json'),json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf-8'))

def argument_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True); p.add_argument('--prompt',default='')
    p.add_argument('--context',default=''); p.add_argument('--image-context')
    p.add_argument('--source'); p.add_argument('--seed',type=int,default=148)
    p.add_argument('--mesh-algorithm',choices=['surface net','basic'],default='surface net')
    p.add_argument('--mesh-threshold',type=float,default=0.5)
    p.add_argument('--mesh-resolution',type=int,default=512)
    p.add_argument('--octree-resolution',type=int,default=256)
    p.add_argument('--run',help='Resume the existing run in the same output directory')
    p.add_argument('--timeout',type=float,default=1800)
    return p

def main():
    a=argument_parser().parse_args(); out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    if (out.exists() and not a.run) or out.with_suffix('.receipt.json').exists(): raise ValueError('immutable output already exists')
    registry, providers=factory(); host=Executor(str(out.parent/'executor.sqlite'),registry,providers)
    kind='image_to_mesh' if a.source else 'text_to_image'
    node=dict(id='garment',type=kind,provider='comfy',parameters=dict(prompt=a.prompt,seed=a.seed,mesh_algorithm=a.mesh_algorithm,mesh_threshold=a.mesh_threshold,mesh_resolution=a.mesh_resolution,octree_resolution=a.octree_resolution),text=a.context,source=a.source,image_context=a.image_context)
    if a.run:
        run=a.run
        if json.loads(out.with_suffix('.run.json').read_text(encoding='utf-8'))['run_id']!=run: raise ValueError('resume output/run mismatch')
    else:
        if out.with_suffix('.run.json').exists(): raise FileExistsError('Use --run to resume this output intent')
        graph,manifest=compile_graph({'nodes':[node],'edges':[]}); run=host.create(graph,manifest)
        with out.with_suffix('.run.json').open('x',encoding='utf-8') as stream:
            json.dump({'run_id':run,'kind':kind,'source':a.source,'context':a.context},stream)
    print(json.dumps({'run_id':run,'output':str(out)}),flush=True)
    try:
        deadline=time.monotonic()+a.timeout
        while True:
            state=host.step(run)
            if state['state']=='succeeded':
                package=host.export(run); ref=package['outputs']['garment']['result']
                asset=next(x for x in package['manifest']['artifacts'] if x['id']==ref['id'] and x['revision']==ref['revision'])
                payload=asset['payload']; data=base64.b64decode(payload['content_base64'],validate=True)
                assert hashlib.sha256(data).hexdigest()==payload['content_sha256']
                job_id=ref['id'].removeprefix('comfy-'); job=providers['comfy'].read(job_id)
                receipt=dict(run_id=run,job_id=job_id,prompt_id=job['remote'],source_sha256=payload['content_sha256'],provenance=payload['provenance'])
                finalize_output(out,data,receipt,resume=bool(a.run))
                print(json.dumps({'state':'succeeded','sha256':payload['content_sha256']}),flush=True); return
            if state['state'] in ('failed','cancelled','reconcile'):
                out.with_suffix('.failure.json').write_text(json.dumps(state),encoding='utf-8')
                raise RuntimeError(state)
            if time.monotonic()>=deadline: raise TimeoutError('Run remains active; resume using --run '+run)
            time.sleep(1)
    finally: host.close()

if __name__=='__main__': main()
