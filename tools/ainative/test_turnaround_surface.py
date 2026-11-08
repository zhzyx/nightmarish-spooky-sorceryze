"""Portable registration tests plus native bundled-dependency construction."""

import copy
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from turnaround_surface import TurnaroundError, build, validate_registration

MODULE = Path(__file__).with_name("turnaround_surface.py")
BLENDER = Path(os.environ.get("AINATIVE_TEST_BLENDER") or shutil.which("blender") or "__blender_unavailable__")


def registration():
    return dict(
        version=1,
        source_sha256="a" * 64,
        source_plan_sha256="b" * 64,
        height=1.2,
        panels=[
            dict(view=view, box=[index / 3, 0, (index + 1) / 3, 1])
            for index, view in enumerate(("front", "back", "profile_left_facing"))
        ],
    )


class RegistrationTests(unittest.TestCase):
    def test_fixed_face_loader_executes_verified_bytes_even_with_stale_bytecode(self):
        import turnaround_surface

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "turnaround_face.py"
            source.write_bytes(b"VERSION = 1\n")
            timestamp = source.stat().st_mtime_ns
            py_compile.compile(str(source), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
            old_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            source.write_bytes(b"VERSION = 2\n")
            os.utime(source, ns=(timestamp, timestamp))
            with patch.object(turnaround_surface, "__file__", str(source.with_name("turnaround_surface.py"))):
                new_sha = hashlib.sha256(source.read_bytes()).hexdigest()
                self.assertEqual(turnaround_surface._fixed_face_module("turnaround_face", new_sha).VERSION, 2)
                with self.assertRaisesRegex(TurnaroundError, "face_prior_source_mismatch"):
                    turnaround_surface._fixed_face_module("turnaround_face", old_sha)

    def test_valid_and_unmodified(self):
        value = registration()
        before = copy.deepcopy(value)
        self.assertIs(validate_registration(value), value)
        self.assertEqual(value, before)
        value["panels"][2]["view"] = "profile_right_facing"
        validate_registration(value)

    def test_reject_bad_scalars_fields_and_digests(self):
        for key, value in (
            ("version", True),
            ("version", 2),
            ("height", True),
            ("height", float("nan")),
            ("height", float("inf")),
            ("height", 10**1000),
            ("height", 0.199),
            ("height", 3.001),
            ("source_sha256", "A" * 64),
            ("source_plan_sha256", "0" * 63),
        ):
            candidate = registration()
            candidate[key] = value
            with self.assertRaises(TurnaroundError):
                validate_registration(candidate)
        candidate = registration()
        candidate["script"] = "forbidden"
        with self.assertRaisesRegex(TurnaroundError, "fields"):
            validate_registration(candidate)

    def test_reject_duplicate_role_or_reused_observation(self):
        candidate = registration()
        candidate["panels"][1]["view"] = "front"
        with self.assertRaisesRegex(TurnaroundError, "unique"):
            validate_registration(candidate)
        candidate = registration()
        for panel in candidate["panels"]:
            panel["box"] = [0, 0, 0.3, 1]
        with self.assertRaisesRegex(TurnaroundError, "overlap"):
            validate_registration(candidate)

    def test_reject_bad_boxes_and_model_paths(self):
        for box in ([0, 0, 0, 1], [0, 0, 1, True], [-0.1, 0, 1, 1], [0, 0, 1, float("inf")], [0, 0, 1], "all"):
            value = registration()
            value["panels"][0]["box"] = box
            with self.assertRaises(TurnaroundError):
                validate_registration(value)
        value = registration()
        value["panels"][0]["path"] = "not accepted"
        with self.assertRaisesRegex(TurnaroundError, "fields"):
            validate_registration(value)

    def test_import_is_stdlib_only(self):
        script = """import importlib.abc,importlib.util,sys
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','bpy','bmesh','OpenImageIO','openvdb','scipy','skimage','PIL','openai','requests'}:
   raise RuntimeError('forbidden import '+fullname)
sys.meta_path.insert(0,Guard())
spec=importlib.util.spec_from_file_location('isolated_turnaround',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print('STDLIB_IMPORT_OK')
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", script, str(MODULE.resolve())], capture_output=True, text=True, timeout=20
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STDLIB_IMPORT_OK", result.stdout)

    def test_overwrite_and_digest_fail_before_native_import(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            image, config, output = folder / "source.png", folder / "config.json", folder / "asset.glb"
            image.write_bytes(b"\x89PNG\r\n\x1a\nnot-an-image")
            value = registration()
            config.write_text(json.dumps(value), encoding="utf8")
            with self.assertRaisesRegex(TurnaroundError, "digest_mismatch"):
                build(image, config, output)
            output.write_bytes(b"keep-original")
            with self.assertRaisesRegex(TurnaroundError, "output_exists"):
                build(image, config, output)
            self.assertEqual(output.read_bytes(), b"keep-original")


NATIVE_PROBE = r"""
import hashlib,json,sys,struct
from pathlib import Path
import numpy as np
import OpenImageIO as oiio
sys.path.insert(0,sys.argv[sys.argv.index('--')+1])
import turnaround_surface as core
out=Path(sys.argv[sys.argv.index('--')+2])
# Exact distance transform and feature coordinates, compared to brute force.
features=np.zeros((7,9),bool);features[1,2]=True;features[5,7]=True
d,ny,nx=core._distance_to(features,np)
yy,xx=np.indices(features.shape);exact=np.minimum((yy-1)**2+(xx-2)**2,(yy-5)**2+(xx-7)**2)**.5
assert np.max(abs(d-exact))<1e-6 and features[ny,nx].all()
# All standard EXIF orientations in displayed-pixel coordinates.
a=np.arange(6).reshape(2,3)
expected=[[[0,1,2],[3,4,5]],[[2,1,0],[5,4,3]],[[5,4,3],[2,1,0]],[[3,4,5],[0,1,2]],[[0,3],[1,4],[2,5]],[[3,0],[4,1],[5,2]],[[5,2],[4,1],[3,0]],[[2,5],[1,4],[0,3]]]
for index,value in enumerate(expected,1):assert core._display_orientation(a,index,np).tolist()==value
# Background-proportional floor shadow removed; warm foot and black shoe stay.
bg=np.array([.45,.47,.48],dtype='f4');rgb=np.broadcast_to(bg,(80,80,3)).copy();rgb[10:73,30:50]=[.65,.27,.16];rgb[73:77,:]=bg*.65;rgb[70:76,31:40]=[.55,.25,.13];rgb[70:76,41:50]=[.02,.02,.02]
mask=np.linalg.norm(rgb-bg,axis=2)>.04;clean,count=core._reject_ground_shadow(rgb,mask,bg,np,'synthetic')
assert count>0 and not clean[74,0] and clean[74,35] and clean[74,45]
ambiguous=np.broadcast_to(bg,(80,80,3)).copy();ambiguous[10:65,30:50]=[.65,.27,.16];ambiguous[65:79,30:50]=bg*.65
try:core._reject_ground_shadow(ambiguous,np.linalg.norm(ambiguous-bg,axis=2)>.04,bg,np,'gray-shoe')
except core.TurnaroundError as error:assert error.code=='foreground_ground_shadow_ambiguous'
else:raise AssertionError('Ambiguous gray foreground accepted')
# Occluded actual triangles cannot borrow the nearer surface's colors.
screen=np.array([0,2,2,0,0,2,2,0.],dtype='f4');down=np.array([0,0,2,2,0,0,2,2.],dtype='f4');depth=np.array([2]*4+[-3]*4,dtype='f4');faces=np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
visible=core._projection_visibility(screen,down,depth,faces,np);assert (visible[:4]>.99).all() and (visible[4:]<1e-4).all()
# A non-human asymmetric colored vase: no reference person, model, or weights.
im=np.broadcast_to(np.array([.46,.48,.50],dtype='f4'),(256,768,3)).copy();yy,xx=np.indices((256,256));t=(yy-20)/210
body_r=58*np.sqrt(np.maximum(0,1-((t-.58)/.43)**2));radius=np.where(t<.23,19,body_r);radius=np.where(t>.88,26,radius)
for panel,color in enumerate(([.8,.12,.08],[.08,.15,.8],[.12,.7,.20])):
 r=radius*(.65 if panel==2 else 1);mask=(t>=0)&(t<=1)&(abs(xx-128)<=r)
 im[:,panel*256:(panel+1)*256][mask]=color
 if panel==0:im[110:126,panel*256+138:panel*256+148]=[.95,.95,.95]
source=out/'synthetic-vase.png';writer=oiio.ImageOutput.create(str(source));writer.open(str(source),oiio.ImageSpec(768,256,3,oiio.UINT8));writer.write_image(np.rint(im*255).astype('u1'));writer.close()
panels=[dict(view=view,box=[i/3,0,(i+1)/3,1]) for i,view in enumerate(('front','back','profile_left_facing'))]
plan=dict(purpose='fixed non-human unit-test fixture',height=1.2,panels=panels);raw=json.dumps(plan,sort_keys=True).encode();(out/'source-plan.json').write_bytes(raw)
config=dict(version=1,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_plan_sha256=hashlib.sha256(raw).hexdigest(),height=1.2,panels=panels);registration=out/'registration.json';registration.write_text(json.dumps(config),encoding='utf8')
output=out/'synthetic-vase.glb';receipt=core.build(source,registration,output)
assert receipt['body_components']==1 and receipt['body_manifold'] and receipt['body_volume']>0
assert receipt['vertices']<=core.MAX_VERTICES and receipt['triangles']<=core.MAX_TRIANGLES and output.stat().st_size<=core.MAX_GLB_BYTES
assert receipt['observed_colors'] and not receipt['exact_hidden_surface_recovery_claimed'] and receipt['removed_3d_components']==0
assert abs(receipt['bounds_max'][1]-1.2)<1e-6 and abs(receipt['bounds_min'][1])<1e-6
blob=output.read_bytes();length=struct.unpack_from('<I',blob,12)[0];doc=json.loads(blob[20:20+length]);primitive=doc['meshes'][0]['primitives'][0];color_accessor=doc['accessors'][primitive['attributes']['COLOR_0']]
assert color_accessor['componentType']==5126 and color_accessor['type']=='VEC4' and color_accessor['count']==receipt['vertices']
before=hashlib.sha256(blob).hexdigest()
try:core.build(source,registration,output)
except core.TurnaroundError as error:assert error.code=='output_exists'
else:raise AssertionError('Overwrote exported GLB')
assert hashlib.sha256(output.read_bytes()).hexdigest()==before
print('TURNAROUND_NATIVE_TESTS_OK',json.dumps({key:receipt[key] for key in ('vertices','triangles','bytes','body_components','body_volume','elapsed_seconds')}))
"""


@unittest.skipUnless(BLENDER.is_file(), "Set AINATIVE_TEST_BLENDER for bundled native image/volume tests")
class NativeTests(unittest.TestCase):
    def test_native_kernels_shadow_orientation_visibility_and_nonhuman_build(self):
        temporary = tempfile.TemporaryDirectory(prefix="maliang-turnaround-native-")
        self.addCleanup(temporary.cleanup)
        work = Path(temporary.name)
        script = work / "native-probe.py"
        script.write_bytes(NATIVE_PROBE.encode("utf8"))
        before = hashlib.sha256(MODULE.read_bytes()).hexdigest()
        result = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--threads",
                "4",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
                "--",
                str(MODULE.parent),
                str(work),
            ],
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-2500:])
        self.assertIn("TURNAROUND_NATIVE_TESTS_OK", result.stdout)
        self.assertEqual(hashlib.sha256(MODULE.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
