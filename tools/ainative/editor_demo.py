"""Local byte-copy demonstration only; no AI generation or remote service."""
import copy
import time
from extensions import NodeRegistry

class Demo:
    def describe(self):
        return dict(id='local-copy',version='1',model='LOCAL IMPORT / COPY - NOT AI',model_version='1',available=True,capabilities=['copy'],context_types=['text','image'])
    def submit(self, request, manifest, idempotency_key):
        time.sleep(min(max(request['parameters'].get('delay', 0),0),10))
        self.manifest = copy.deepcopy(manifest)
        source = request['inputs']['source']
        self.job = dict(job_id=idempotency_key,state='failed' if request['parameters'].get('fail',False) else 'succeeded',outputs={},error=None)
        if self.job['state']=='failed': self.job['error']='demo_failure'
        else: self.job['outputs']={'result':source}
        return self.job
    def result_manifest(self, job_id): return self.manifest
    def cancel(self, job_id): return None

def factory():
    registry=NodeRegistry()
    registry.register(dict(id='copy',version='1',inputs={'source':{'types':['image','mesh'],'required':True}},outputs={'result':{'types':['image','mesh'],'required':True}},context_types=['text','image'],parameters={'properties':{'delay':{'type':'number'},'fail':{'type':'boolean'}}},capabilities=['copy']))
    return registry, {'local-copy':Demo()}
