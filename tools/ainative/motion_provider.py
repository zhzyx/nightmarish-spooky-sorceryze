"""Motion adapter for the existing NodeRegistry/Provider execution contract.

ML imports stay in configured child interpreters. Trusted local configuration is
never embedded in published motion or artifact manifests.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from extensions import NodeRegistry, canonical, require, validate_invocation
from motion import digest, publish, validate
from motion_jobs import exclusive, write_new, process_identity, alive


def register(registry):
    for kind in ['text_to_motion', 'video_to_motion']:
        registry.register({'id': kind, 'version': '1', 'inputs': {'source': {'types': ['video'], 'required': True}} if kind=='video_to_motion' else {}, 'outputs': {'result': {'types': ['animation'], 'required': True}}, 'context_types': ['text'], 'parameters': {'properties': {'prompt': {'type':'string'}, 'seconds': {'type':'number'}, 'seed': {'type':'integer'}}}, 'capabilities':[kind]})


class MotionProvider:
    def __init__(self, config):
        self.config = config
        self.root = Path(config['runtime']).resolve()
        self.storage = self.root / 'jobs'
        self.storage.mkdir(exist_ok=True)
        self.fingerprint = hashlib.sha256(canonical(config).encode()).hexdigest()
        sources = [self.root/config['checkpoint'], self.root/config['mean'], self.root/config['std'], self.root/'models/ViT-B-32.pt', self.root/'mdm/model/mdm.py']
        sources += [self.root/'models'/name for name in ['pose.task','hand.task','face.task']]
        sources += [Path(__file__).with_name(name) for name in ['motion_mdm.py','motion_video.py','motion.py','motion_provider.py','motion_jobs.py']]
        sources.append((self.root/config['checkpoint']).with_name('args.json'))
        if (self.root/'dependencies-lock.txt').exists(): sources.append(self.root/'dependencies-lock.txt')
        self.model_version = hashlib.sha256(canonical([self.fingerprint,[digest(path) for path in sources]]).encode()).hexdigest()

    def describe(self):
        return {'id':'local-motion','version':'1','model':'MDM50+MediaPipe','model_version':self.model_version,'capabilities':['text_to_motion','video_to_motion'],'context_types':['text'],'available':True}

    def read(self, key):
        require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'Invalid job key')
        return json.loads((self.storage / key / 'receipt.json').read_text())

    def snapshot(self, key, state, error=None, outputs=None):
        return {'job_id':key,'state':state,'outputs':outputs or {},'error':error}

    def submit(self, request, manifest, idempotency_key):
        registry = NodeRegistry()
        register(registry)
        validate_invocation(registry, request, manifest, self.describe())
        if request['node']=='text_to_motion':
            require(bool(request['parameters'].get('prompt','').strip()),'Natural language prompt required')
        else:
            ref = request['inputs']['source']
            asset = next(a for a in manifest['artifacts'] if a['id']==ref['id'])
            require(digest(asset['payload']['local_path'])==asset['revision'],'Video content changed since invocation')
        key = idempotency_key
        require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'Invalid job key')
        directory = self.storage / key
        intent = {'request':request,'manifest':manifest,'configuration_sha256':self.fingerprint,'provider':self.describe()}
        directory.mkdir(exist_ok=True)
        with exclusive(directory/'dispatch.lock'):
            if (directory/'intent.json').exists():
                require(json.loads((directory/'intent.json').read_text())==intent,'Idempotency conflict')
            else:
                write_new(directory/'intent.json',intent)
                write_new(directory/'config.json',self.config)
                with open(directory/'worker.log','wb') as log:
                    worker = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(directory)],stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
                write_new(directory/'launch.json',{'process':process_identity(worker.pid)})
        return self.poll(key)

    def execute(self, key):
        directory = self.storage/key
        with exclusive(directory/'worker.lock'):
            if (directory/'receipt.json').exists(): return
            intent = json.loads((directory/'intent.json').read_text())
            require(intent['configuration_sha256']==self.fingerprint,'Worker configuration changed')
            write_new(directory/'started.json',{'process':process_identity(os.getpid())})
            try:
                self._infer(key,intent['request'],intent['manifest'])
                self._finish(key)
            except Exception as exc:
                with exclusive(directory/'publication.lock'):
                    if not (directory/'receipt.json').exists(): write_new(directory/'receipt.json',self.snapshot(key,'failed',error=str(exc)))

    def _infer(self, key, request, manifest):
        directory = self.storage/key
        path = directory / 'motion.json'
        params = request['parameters']
        context = '\n'.join(entry['text'] for entry in request['context'])
        scripts = Path(__file__).parent
        if request['node']=='text_to_motion':
            args = [str(scripts/'motion_mdm.py'),'--repo',str(self.root/'mdm'),'--checkpoint',str(self.root/self.config['checkpoint']),'--mean',str(self.root/self.config['mean']),'--std',str(self.root/self.config['std']),'--prompt',params.get('prompt',''),'--seconds',str(params.get('seconds',4)),'--seed',str(params.get('seed',10)),'--device',self.config.get('device','cpu')]
        else:
            ref = request['inputs']['source']
            asset = next(a for a in manifest['artifacts'] if a['id']==ref['id'])
            video = Path(asset['payload']['local_path'])
            require(digest(video)==asset['revision'],'Video content changed since invocation')
            args = [str(scripts/'motion_video.py'),'--video',str(video),'--models',str(self.root/'models'),'--expected-input-sha256',asset['revision']]
        args += ['--context',context,'--output',str(path)]
        with open(directory/'inference.log','wb') as log:
            process = subprocess.Popen([self.config['python'],*args],stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
            write_new(directory/'model-process.json',{'process':process_identity(process.pid)})
            returncode = process.wait()
        write_new(directory/'model-exit.json',{'returncode':returncode})
        require(returncode==0,'Model subprocess failed; inspect local inference.log')

    def _finish(self, key):
        directory = self.storage/key
        with exclusive(directory/'publication.lock'):
            if (directory/'receipt.json').exists(): return self.read(key)
            intent = json.loads((directory/'intent.json').read_text())
            require(intent.get('provider')==self.describe(),'Provider changed since durable intent')
            request, manifest = intent['request'], intent['manifest']
            path = directory/'motion.json'
            doc = validate(json.loads(path.read_text(encoding='utf-8')))
            if request['node']=='video_to_motion':
                require(doc['provenance'].get('input_sha256')==request['inputs']['source']['revision'],'Video result provenance differs from invocation source')
            doc['context_bundle'] = request['context']
            doc['invocation_sha256'] = hashlib.sha256(canonical([request,manifest]).encode()).hexdigest()
            enriched = directory/'result.json'
            if enriched.exists():
                require(json.loads(enriched.read_text(encoding='utf-8'))==doc,'Recovered result conflicts with source')
                revision = digest(enriched)
            else: revision = publish(doc,enriched)
            aid = 'motion-'+key
            artifact = {'id':aid,'revision':revision,'type':'animation','payload':{'encoding':'ainative.motion.v1','motion':doc},'binding':{'level':'unbound'}}
            output_manifest = {'schema_version':1,'artifacts':[artifact]}
            if (directory/'manifest.json').exists():
                require(json.loads((directory/'manifest.json').read_text(encoding='utf-8'))==output_manifest,'Recovered manifest conflicts')
            else: write_new(directory/'manifest.json',output_manifest)
            receipt = self.snapshot(key,'succeeded',outputs={'result':{'id':aid,'revision':revision}})
            write_new(directory/'receipt.json',receipt)
            return receipt

    def poll(self, key):
        require(len(key)==64 and all(c in '0123456789abcdef' for c in key),'Invalid job key')
        directory = self.storage/key
        if (directory/'receipt.json').exists(): return self.read(key)
        if (directory/'motion.json').exists(): return self._finish(key)
        # A child may outlive a killed parent. Only actual OS process identity or
        # an exclusive worker lock is evidence of running; stale intent is not.
        for name in ['model-process.json','started.json','launch.json']:
            if (directory/name).exists() and alive(json.loads((directory/name).read_text()).get('process')):
                return self.snapshot(key,'running')
        try:
            with exclusive(directory/'worker.lock',blocking=False): pass
        except BlockingIOError: return self.snapshot(key,'running')
        if (directory/'model-process.json').exists() and json.loads((directory/'model-process.json').read_text()).get('process'):
            with exclusive(directory/'publication.lock'):
                if not (directory/'receipt.json').exists(): write_new(directory/'receipt.json',self.snapshot(key,'failed',error='Recorded model process terminated without a complete result'))
            return self.read(key)
        raise ValueError('reconciliation_required: launch outcome unknown; no live worker or complete result proven; do not resubmit')

    def lookup(self, key):
        return self.poll(key) if (self.storage/key).exists() else None

    def result_manifest(self, key):
        require(self.poll(key)['state']=='succeeded','Job has no successful result')
        return json.loads((self.storage/key/'manifest.json').read_text(encoding='utf-8'))

    def cancel(self, key):
        receipt = self.poll(key)
        if receipt['state'] in ['succeeded','failed','cancelled']: return receipt
        raise ValueError('Local inference is not interrupted; wait for its durable terminal receipt')


def factory():
    config = json.loads(Path(os.environ['AINATIVE_MOTION_CONFIG']).read_text(encoding='utf-8-sig'))
    registry = NodeRegistry()
    register(registry)
    return registry, {'local-motion':MotionProvider(config)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    p.add_argument('--mode',choices=['text_to_motion','video_to_motion'],required=True)
    p.add_argument('--prompt',default='')
    p.add_argument('--context',default='')
    p.add_argument('--video',default='')
    p.add_argument('--output',required=True)
    args = p.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    # A future configured provider implements the same contract; the panel does
    # not know model architecture, checkpoint layout, or transport details.
    if config.get('provider_factory'):
        module, name = config['provider_factory'].split(':')
        registry, providers = getattr(importlib.import_module(module),name)()
        provider = providers[config['provider_id']]
    else:
        registry = NodeRegistry(); register(registry)
        provider = MotionProvider(config)
    manifest = {'schema_version':1,'artifacts':[]}
    request = {'node':args.mode,'version':'1','inputs':{},'parameters':{'prompt':args.prompt},'context':[]}
    if args.context: request['context'] = [{'text':args.context,'role':'motion_context','scope':'generation','strength':'reference'}]
    if args.mode=='video_to_motion':
        revision = digest(args.video)
        manifest['artifacts'].append({'id':'input-video','revision':revision,'type':'video','payload':{'local_path':str(Path(args.video).resolve())}})
        request['inputs']['source'] = {'id':'input-video','revision':revision}
    key = validate_invocation(registry,request,manifest,provider.describe())
    receipt = provider.submit(request,manifest,key)
    print(json.dumps({'job_id':key,'state':receipt['state']}),flush=True)
    while receipt['state'] in ('queued','running'):
        time.sleep(.25)
        receipt = provider.poll(key)
    require(receipt['state']=='succeeded',receipt.get('error') or 'Provider job still running')
    result = provider.result_manifest(key)['artifacts'][0]['payload']['motion']
    print(json.dumps({'job_id':key,'revision':publish(result,args.output)}))


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        directory = Path(sys.argv[2])
        MotionProvider(json.loads((directory/'config.json').read_text(encoding='utf-8'))).execute(directory.name)
    else: main()
