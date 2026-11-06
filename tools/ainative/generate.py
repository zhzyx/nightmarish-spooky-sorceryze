"""Run/resume a real local-configured provider job. Does not install/start a backend."""
import argparse
import json
from pathlib import Path
import time
from comfy_provider import factory, KINDS
from editor_host import compile_graph
from executor import Executor


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True); p.add_argument('--kind',choices=KINDS,default='text_to_image')
    p.add_argument('--prompt',default=''); p.add_argument('--source'); p.add_argument('--image-context')
    p.add_argument('--seed',type=int,default=1); p.add_argument('--run'); p.add_argument('--output',required=True)
    p.add_argument('--timeout',type=float,default=1800)
    args=p.parse_args()
    registry,providers=factory(); host=Executor(args.db,registry,providers)
    try:
        run=args.run
        if not run:
            node=dict(id='generate',type=args.kind,provider='comfy',parameters=dict(prompt=args.prompt,seed=args.seed),source=args.source,image_context=args.image_context)
            graph,manifest=compile_graph({'nodes':[node],'edges':[]}); run=host.create(graph,manifest)
        print(json.dumps({'run_id':run}),flush=True)
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            state=host.step(run)
            if state['state']=='succeeded':
                target=Path(args.output)
                with target.open('x',encoding='utf-8') as stream: json.dump(host.export(run),stream,ensure_ascii=False)
                print(json.dumps({'state':'succeeded','package':str(target.resolve())})); return 0
            if state['state'] in ('failed','cancelled','reconcile'):
                print(json.dumps({'state':state['state'],'run_id':run})); return 2
            time.sleep(0.5)
        print(json.dumps({'state':'timeout','run_id':run,'resume':'use --run with same --db and local config'})); return 3
    finally: host.close()

if __name__=='__main__': raise SystemExit(main())
