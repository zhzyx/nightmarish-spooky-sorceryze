import copy
import json
from pathlib import Path
import tempfile
import unittest
from motion import correct, publish, validate, verify_input, digest


class MotionContractTests(unittest.TestCase):
    def document(self):
        return {'schema': 'ainative.motion.v1', 'fps': 20, 'source_profile': {'id': 'humanml3d-22-v1', 'units':'meters', 'up':'+Y'}, 'provenance': {'provider': 'contract-test', 'model_version':'fixture', 'model_sha256':'0'*64}, 'streams': {'body': {'coordinate_system':'humanml3d_meters', 'time_base':'model_20fps_ms', 'frames': [{'timestamp_ms': 0, 'positions': [[0, 1, 0] for _ in range(22)], 'confidence': [.2]*22, 'missing':False}, {'timestamp_ms': 50, 'positions': [[0, 2, 0] for _ in range(22)], 'confidence': [.3]*22, 'missing':False}]}, 'hands':{'time_base':'model_20fps_ms','frames':[], 'missing_reason':'unobserved'}, 'face':{'time_base':'model_20fps_ms','frames':[], 'missing_reason':'unobserved'}}}

    def test_atomic_immutable_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'v1.json'
            first = self.document()
            publish(first, target)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                publish(first, target)
            self.assertEqual(before, target.read_bytes())

    def test_input_change_refuses_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input.webm'
            path.write_bytes(b'original input fixture, not model evidence')
            expected = digest(path)
            self.assertEqual(verify_input(path,expected),expected)
            path.write_bytes(b'changed while inference was running')
            with self.assertRaisesRegex(ValueError,'Video input changed'): verify_input(path,expected)

    def test_correction_keeps_measurement_and_confidence(self):
        original = self.document()
        result = correct(original, [{'stream': 'body', 'frame': 0, 'point': 0, 'position': [1, 2, 3]}])
        self.assertEqual(original['streams']['body']['frames'][0]['positions'][0], [0, 1, 0])
        frame = result['streams']['body']['frames'][0]
        self.assertEqual(frame['raw_positions'][0], [0, 1, 0])
        self.assertEqual(frame['confidence'], [.2]*22)
        self.assertEqual(frame['positions'][0], [1, 2, 3])

    def test_reject_negative_correction_indices(self):
        for field in ['frame','point']:
            edit = {'stream':'body','frame':0,'point':0,'position':[1,2,3]}
            edit[field] = -1
            with self.assertRaises(ValueError): correct(self.document(), [edit])

    def test_reject_bad_clock_and_nonfinite(self):
        doc = self.document()
        doc['streams']['body']['frames'][1]['timestamp_ms'] = 0
        with self.assertRaises(ValueError): validate(doc)

    def test_reject_incompatible_units_axes_clock_and_negative_stamp(self):
        for key,value in [('coordinate_system','centimeters_z_up'),('time_base','seconds'),('units','centimeters'),('up','+Z')]:
            doc = self.document()
            doc['streams']['body'][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError): validate(doc)
        for key,value in [('units','centimeters'),('up','+Z')]:
            doc = self.document()
            doc['source_profile'][key] = value
            with self.subTest(profile=key), self.assertRaises(ValueError): validate(doc)
        doc = self.document()
        doc['streams']['body']['frames'][0]['timestamp_ms'] = -.5
        with self.assertRaises(ValueError): validate(doc)
        doc = self.document()
        del doc['streams']['body']['coordinate_system']
        with self.assertRaises(ValueError): validate(doc)
        doc = self.document()
        doc['streams']['body']['frames'][0]['positions'][0][0] = float('nan')
        with self.assertRaises(ValueError): validate(doc)


if __name__ == '__main__': unittest.main()
