"""Bridge regression tests: immutable sources, no-clobber and configuration isolation."""
import argparse, hashlib, json, struct, tempfile, unittest, zlib
from pathlib import Path
from editor_host import dispatch, compile_graph

def fixtures(folder):
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0\0\xff\0\0\0\0\xff\xff\xff\xff'))+chunk(b'IEND',b'')
    (folder/'sample.png').write_bytes(png)
    import base64
    vertices=struct.pack('<9f',-1,0,0,1,0,0,0,1,0)
    gltf={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}], 'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}], 'buffers':[{'byteLength':len(vertices),'uri':'data:application/octet-stream;base64,'+base64.b64encode(vertices).decode()}], 'bufferViews':[{'buffer':0,'byteLength':len(vertices)}], 'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[-1,0,0],'max':[1,1,0]}]}
    (folder/'sample.gltf').write_text(json.dumps(gltf))
    gltf['buffers']=[{'byteLength':len(vertices)}]
    chunk=json.dumps(gltf).encode(); chunk+=b' '*((-len(chunk))%4)
    (folder/'sample.glb').write_bytes(struct.pack('<5I',0x46546c67,2,28+len(chunk)+len(vertices),len(chunk),0x4e4f534a)+chunk+struct.pack('<2I',len(vertices),0x004e4942)+vertices)

def model(path, fail=False):
    return {'format':1,'edges':[],'nodes':[{'id':'first','source':str(path),'image_context':'','text':'reference','parameters':{'fail':fail,'delay':0},'x':10,'y':20}]}

def reconcile_factory():
    """Fault-injection provider for the actual Godot replay; not a production provider."""
    import os
    from editor_demo import factory, Demo
    registry, _ = factory()
    class Unknown(Demo):
        def record(self, value):
            with open(os.environ['AINATIVE_LOOKUP_MARKER'], 'a') as stream: stream.write(value+'\n')
        def submit(self, request, manifest, idempotency_key):
            self.record('submit')
            raise RuntimeError('simulated lost receipt')
        def lookup(self, key):
            self.record('lookup')
            return None
    return registry, {'local-copy':Unknown()}

class BridgeTests(unittest.TestCase):
    def test_bound_publish_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); fixtures(root); source=root/'sample.png'; before=source.read_bytes()
            args=argparse.Namespace(db=str(root/'db'),factory='editor_demo:factory',command='create')
            run=dispatch(args,{'model':model(source)})['run_id']; req={'run':run,'node':'first'}
            args.command='step'; self.assertEqual(dispatch(args,req)['state'],'succeeded')
            args.command='preview'; preview=dispatch(args,req)
            stage=root/'stage.tres'; stage.write_text('[gd_resource type="Resource" format=3]\n[resource]\n')
            args.command='publish'; request={**req,'confirmation':preview['token'],'staged':str(stage),'staged_sha256':hashlib.sha256(stage.read_bytes()).hexdigest(),'target':str(root/'published.tres')}
            dispatch(args,request)
            with self.assertRaises(FileExistsError): dispatch(args,request)
            with self.assertRaises(ValueError): dispatch(args,{**request,'confirmation':'stale'})
            stage.write_text('changed after confirmation')
            with self.assertRaises(ValueError): dispatch(args,{**request,'target':str(root/'tampered.tres')})
            self.assertFalse((root/'tampered.tres').exists())
            self.assertEqual(source.read_bytes(),before)
            args.command='create'; failed=dispatch(args,{'model':model(source,True)})['run_id']
            args.command='step'; self.assertEqual(dispatch(args,{'run':failed})['state'],'failed')
            args.command='retry'; state=dispatch(args,{'run':failed,'node':'first'}); self.assertEqual(state['nodes']['first']['attempt'],1)
            args.command='cancel'; self.assertEqual(dispatch(args,{'run':failed})['state'],'cancelled')
            self.assertEqual(source.read_bytes(),before)
    def test_config_and_external_gltf_rejected(self):
        with self.assertRaises(ValueError): compile_graph({'factory':'evil','nodes':[],'edges':[]})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.gltf'; path.write_text('{"buffers":[{"uri":"other.bin"}]}')
            with self.assertRaises(ValueError): compile_graph(model(path))
            chunk=path.read_bytes(); chunk+=b' ' * ((-len(chunk))%4)
            glb=Path(tmp)/'bad.glb'; glb.write_bytes(struct.pack('<5I',0x46546c67,2,20+len(chunk),len(chunk),0x4e4f534a)+chunk)
            with self.assertRaises(ValueError): compile_graph(model(glb))

if __name__=='__main__': unittest.main()
