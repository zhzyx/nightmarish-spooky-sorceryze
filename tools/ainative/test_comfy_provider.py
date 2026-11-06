"""HTTP contract/failure tests: real localhost transport, no inference mocks as acceptance."""
import base64
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError

from comfy_provider import ComfyProvider, register, validate_embedded_glb
from executor import Executor
from extensions import NodeRegistry
from editor_host import compile_graph

PNG = b'\x89PNG\r\n\x1a\nfixture'
KEY = 'a'*64

class ComfyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.queue=[]; self.history={}; self.posts=[]; self.fail=False; self.drop=False; self.bad_output=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def send(self,data,code=200,raw=False):
                self.send_response(code); self.end_headers(); self.wfile.write(data if raw else json.dumps(data).encode())
            def do_GET(self):
                if self.path=='/queue': self.send({'queue_pending':owner.queue,'queue_running':[]})
                elif self.path.startswith('/history'): self.send(owner.history)
                elif self.path.startswith('/view?'): self.send(PNG,raw=True)
                else: self.send({},404)
            def do_POST(self):
                data=self.rfile.read(int(self.headers['Content-Length']))
                if self.path=='/upload/image':
                    import re
                    self.send({'name':re.search(b'filename="([^"]+)"',data)[1].decode(),'subfolder':''}); return
                obj=json.loads(data); owner.posts.append((self.path,obj))
                if self.path=='/prompt':
                    if owner.fail: self.send({'error':'bad request'},400); return
                    owner.queue.append([0,'remote',obj['prompt'],obj['extra_data'],['output']])
                    if owner.drop: self.connection.shutdown(2); self.connection.close(); return
                    self.send({'prompt_id':'remote'})
                elif self.path=='/queue': owner.queue=[]; self.send({})
                else: self.send({},404)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.config=dict(endpoint='http://127.0.0.1:'+str(self.server.server_port),storage=self.tmp.name,checkpoints={k:dict(name=k+'.safetensors',sha256='b'*64) for k in ('image','mesh')},backend_revision='test-revision')
        self.p=ComfyProvider(self.config)
        self.request=dict(node='text_to_image',version='1',inputs={},parameters={'prompt':'stone sculpture'},context=[])
        self.manifest=dict(schema_version=1,artifacts=[])
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def complete(self):
        self.history={'remote':dict(prompt=self.queue[0],status=dict(completed=True,status_str='success'),outputs={'output':{'images':[dict(filename=KEY+'_00001_.png',subfolder='ainative',type='output')]}})}
        self.queue=[]
    def image(self):
        sha=hashlib.sha256(PNG).hexdigest()
        return dict(id='input',revision=sha,type='image',payload=dict(content_base64=base64.b64encode(PNG).decode(),content_sha256=sha,extension='.png'))
    def test_restart_outputs_and_fingerprints(self):
        self.assertEqual(self.p.submit(self.request,self.manifest,KEY)['state'],'queued')
        self.complete(); p=ComfyProvider(self.config)
        result=p.poll(KEY); self.assertEqual(result['state'],'succeeded')
        payload=p.result_manifest(KEY)['artifacts'][0]['payload']
        self.assertEqual(payload['bytes'],len(PNG)); self.assertEqual(payload['content_sha256'],hashlib.sha256(PNG).hexdigest())
        self.assertEqual(p.poll(KEY),result)
        for field in ('backend_revision','endpoint','storage'):
            changed=copy.deepcopy(self.config)
            changed[field] += '/changed' if field=='storage' else '-change' if field!='endpoint' else '/'
            self.assertNotEqual(ComfyProvider(changed).describe(),p.describe())
        changed=copy.deepcopy(self.config); changed['checkpoints']['image']['sha256']='c'*64
        self.assertNotEqual(ComfyProvider(changed).describe(),p.describe())
    def test_lost_receipt_reconciles_without_resubmit(self):
        self.drop=True
        with self.assertRaises(Exception): self.p.submit(self.request,self.manifest,KEY)
        p=ComfyProvider(self.config)
        self.assertEqual(p.lookup(KEY)['job_id'],KEY)
        p.submit(self.request,self.manifest,KEY)
        self.assertEqual(len([v for v in self.posts if v[0]=='/prompt']),1)
    def test_missing_receipt_does_not_replay(self):
        self.drop=True
        with self.assertRaises(Exception): self.p.submit(self.request,self.manifest,KEY)
        self.queue=[]
        self.assertIsNone(ComfyProvider(self.config).lookup(KEY))
        self.assertIsNone(self.p.submit(self.request,self.manifest,KEY))
        self.assertEqual(len(self.posts),1)
    def test_only_owned_queue_cancel(self):
        self.p.submit(self.request,self.manifest,KEY); self.p.cancel(KEY)
        self.assertEqual(self.posts[-1],('/queue',{'delete':['remote']}))
        self.assertFalse(any(route=='/interrupt' for route,_ in self.posts))
    def test_foreign_queue_not_cancelled(self):
        self.p.submit(self.request,self.manifest,KEY); self.queue[0][3]={}
        self.p.cancel(KEY); self.assertEqual(len(self.posts),1)
    def test_output_path_and_foreign_url_rejected(self):
        self.p.submit(self.request,self.manifest,KEY); self.complete()
        entry=self.history['remote']['outputs']['output']['images'][0]
        for field,value in [('filename','../secret.png'),('filename','https://evil/output.png'),('subfolder','../secret'),('type','input')]:
            old=entry[field]; entry[field]=value
            with self.assertRaises(ValueError): self.p.poll(KEY)
            entry[field]=old
    def test_foreign_history_and_terminal_race(self):
        self.p.submit(self.request,self.manifest,KEY)
        stale=self.p.read(KEY)
        self.complete(); self.history['remote']['prompt'][3]={}
        with self.assertRaises(ValueError): self.p.poll(KEY)
        cancelled=self.p.cancel(KEY)
        stale['terminal']=self.p.snapshot(KEY,'failed',error='late failure')
        self.assertEqual(self.p.write(KEY,stale)['terminal'],cancelled)
        self.assertEqual(self.p.poll(KEY),cancelled)

    def test_cancel_during_build_prevents_post(self):
        build=self.p.build
        def cancelling(*args):
            result=build(*args)
            self.p.cancel(KEY)
            return result
        self.p.build=cancelling
        self.assertEqual(self.p.submit(self.request,self.manifest,KEY)['state'],'cancelled')
        self.assertEqual(self.posts,[])

    def test_glb_external_dependency_rejected(self):
        import struct
        payload=json.dumps({'asset':{'version':'2.0'},'buffers':[{'uri':'https://foreign/buffer'}]}).encode()
        data=b'glTF'+struct.pack('<IIII',2,20+len(payload),len(payload),0x4e4f534a)+payload
        with self.assertRaises(ValueError): validate_embedded_glb(data)

    def test_four_graphs_and_context_usage(self):
        for kind in ('text_to_image','image_to_image','image_to_mesh','text_to_mesh'):
            req=copy.deepcopy(self.request); req['node']=kind
            manifest=copy.deepcopy(self.manifest)
            if kind.startswith('image_'):
                asset=self.image(); manifest['artifacts']=[asset]; req['inputs']['source']={k:asset[k] for k in ('id','revision')}
            graph,usage=self.p.build(req,manifest,KEY)
            self.assertEqual(graph['output']['class_type'],'SaveGLB' if kind.endswith('mesh') else 'SaveImage')
            if kind.endswith('mesh'):
                self.assertEqual(graph['mesh_latent']['inputs']['resolution'],512)
                self.assertEqual(usage['parameters']['mesh_resolution'],512)
                self.assertEqual(graph['mesh_sample']['inputs']['steps'],20)
                self.assertEqual(graph['mesh_sample']['inputs']['cfg'],5.0)
                self.assertEqual(graph['mesh']['inputs']['algorithm'],'surface net')
                self.assertEqual(graph['normals'],{'class_type':'MeshSmoothNormals','inputs':{'mesh':['mesh',0],'crease_angle':180.0}})
                self.assertEqual(graph['output']['inputs']['mesh'],['normals',0])
            if kind=='image_to_mesh': self.assertIn('decode',graph); self.assertEqual(usage['text_usage'],'image_diffusion')
        req=copy.deepcopy(self.request); asset=self.image(); manifest={'schema_version':1,'artifacts':[asset]}
        req['context']=[dict(artifact={k:asset[k] for k in ('id','revision')},role='reference',scope='node',strength='reference')]
        graph,usage=self.p.build(req,manifest,KEY); self.assertIn('input',graph); self.assertEqual(usage['image_usage'],'img2img_initial_latent')
        req['context']*=2
        result=self.p.submit(req,manifest,KEY); self.assertEqual(result['state'],'failed'); self.assertIn('unsupported_multiple',result['error']); self.assertFalse(self.posts)
    def test_http_error_confirmed_failure(self):
        self.fail=True
        result=self.p.submit(self.request,self.manifest,KEY)
        self.assertEqual(result['state'],'failed')
    def test_mesh_extraction_controls_and_defaults(self):
        req=copy.deepcopy(self.request); req['node']='text_to_mesh'
        graph,usage=self.p.build(req,self.manifest,KEY)
        self.assertEqual(graph['mesh']['inputs']['algorithm'],'surface net')
        self.assertEqual(graph['mesh']['inputs']['threshold'],0.6)
        for algorithm in ('surface net','basic'):
            for threshold in (-1.0,0.0,0.6,1.0):
                req['parameters'].update(mesh_algorithm=algorithm,mesh_threshold=threshold)
                graph,usage=self.p.build(req,self.manifest,KEY)
                self.assertEqual(graph['mesh']['inputs']['algorithm'],algorithm)
                self.assertEqual(graph['mesh']['inputs']['threshold'],threshold)
                self.assertEqual(usage['parameters']['mesh_algorithm'],algorithm)
                self.assertEqual(usage['parameters']['mesh_threshold'],threshold)
        req['parameters'].update(mesh_algorithm='basic',mesh_threshold=0.6)
        registry=NodeRegistry(); register(registry)
        host=Executor(Path(self.tmp.name)/'mesh-controls.sqlite',registry,{'comfy':self.p})
        try:
            graph,manifest=compile_graph({'nodes':[dict(id='mesh',type='text_to_mesh',provider='comfy',parameters=req['parameters'])],'edges':[]})
            host.create(graph,manifest)
        finally: host.close()
    def test_mesh_extraction_invalid_controls(self):
        for key,value in [('mesh_algorithm','marching_cubes'),('mesh_algorithm',''),('mesh_threshold',-1.001),('mesh_threshold',1.001),('mesh_threshold',float('nan')),('mesh_threshold',float('inf'))]:
            req=copy.deepcopy(self.request); req['node']='text_to_mesh'; req['parameters'][key]=value
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError): self.p.build(req,self.manifest,KEY)
        for key,value in [('mesh_algorithm',1),('mesh_algorithm',None),('mesh_threshold','0.6'),('mesh_threshold',True),('mesh_threshold',None)]:
            req=copy.deepcopy(self.request); req['node']='text_to_mesh'; req['parameters'][key]=value
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError): self.p.submit(req,self.manifest,KEY)
        self.assertEqual(self.posts,[])
    def test_host_text_nodes_embedded_context_and_typed_links(self):
        image=self.image()
        model={'nodes':[dict(id='a',type='text_to_image',provider='comfy',parameters={'prompt':'test'},image_context_snapshot=image['payload']),dict(id='b',type='image_to_mesh',provider='comfy',parameters={})],'edges':[{'from':'a','to':'b','input':'source','output':'result'}]}
        graph,manifest=compile_graph(model)
        self.assertEqual(graph[0]['request']['inputs'],{})
        self.assertEqual(len(graph[0]['request']['context']),1)
        registry=NodeRegistry(); register(registry)
        host=Executor(Path(self.tmp.name)/'host.sqlite',registry,{'comfy':self.p})
        try: host.create(graph,manifest)
        finally: host.close()

if __name__=='__main__': unittest.main()
