"""Dependency-free motion stream contract; providers run in an isolated interpreter."""
import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def text_context(text, consumed):
    """Inline ContextBundle compatible entry with immutable origin identity."""
    if not text:
        return []
    return [{'role': 'motion_context', 'scope': 'generation', 'strength': 'reference', 'text': text,
             'source': {'authority': 'user:inline', 'version': hashlib.sha256(text.encode()).hexdigest()},
             'consumption': 'concatenated_to_model_prompt' if consumed else 'metadata_only_not_model_conditioning'}]


def verify_input(path, expected):
    actual = digest(path)
    if actual != expected:
        raise ValueError('Video input changed; refusing inference provenance')
    return actual


def validate(doc):
    json.dumps(doc, allow_nan=False)
    if doc.get('schema') != 'ainative.motion.v1':
        raise ValueError('Unsupported motion schema')
    profile = doc.get('source_profile', {})
    provenance = doc.get('provenance', {})
    if not isinstance(profile, dict) or profile.get('id') not in ('humanml3d-22-v1', 'mediapipe-pose33-v1') or not isinstance(provenance, dict) or not provenance.get('provider'):
        raise ValueError('Explicit source profile and provenance required')
    def sha(value):
        return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
    if provenance['provider']=='official-MDM':
        if profile['id']!='humanml3d-22-v1' or not all(sha(provenance.get(k)) for k in ['source_sha256','checkpoint_sha256','mean_sha256','std_sha256']):
            raise ValueError('MDM source/model/statistics hashes required')
    elif provenance['provider']=='mediapipe':
        if profile['id']!='mediapipe-pose33-v1' or not provenance.get('version') or not sha(provenance.get('input_sha256')) or not isinstance(provenance.get('models'),dict) or set(provenance['models'])!={'pose','hand','face'} or not all(sha(v) for v in provenance['models'].values()):
            raise ValueError('MediaPipe source/model hashes and version required')
    else:
        # Cloud adapters must explicitly describe compatible output semantics.
        if not provenance.get('model_version') or not sha(provenance.get('model_sha256')):
            raise ValueError('Provider model identity required')
    if type(doc.get('fps')) not in (int, float) or not 0 < doc['fps'] <= 240:
        raise ValueError('Invalid frame rate')
    streams = doc.get('streams')
    if not isinstance(streams, dict) or set(streams) != {'body', 'hands', 'face'} or not streams['body'].get('frames'):
        raise ValueError('Body observations and separate body/hands/face streams required')
    humanml = profile['id']=='humanml3d-22-v1'
    if humanml and (profile.get('units')!='meters' or profile.get('up')!='+Y'):
        raise ValueError('HumanML3D requires explicit meters and +Y up')
    if not humanml and ('units' in profile or 'up' in profile):
        raise ValueError('MediaPipe has per-stream coordinates; global units/axis overrides unsupported')
    coordinates = {'body':'humanml3d_meters'} if humanml else {
        'body':'hip_relative_meters_x_right_y_down_z_away',
        'hands':'per_hand_local_meters', 'face':'normalized_image_coordinates'}
    clock = 'model_20fps_ms' if humanml else 'decoded_video_pts_ms'
    if humanml and doc['fps']!=20: raise ValueError('HumanML3D source clock is 20 Hz')
    for name, stream in streams.items():
        if not isinstance(stream, dict) or not isinstance(stream.get('frames'), list) or not stream.get('time_base'):
            raise ValueError('Stream frames and time base required')
        if stream['time_base']!=clock:
            raise ValueError('Unsupported clock for source profile: '+name)
        if humanml and name!='body':
            # No coordinate default is inferred for unobserved model outputs.
            if stream['frames'] or not stream.get('missing_reason') or 'coordinate_system' in stream:
                raise ValueError('HumanML3D hands/face must be explicitly unobserved')
        elif stream.get('coordinate_system')!=coordinates[name]:
            raise ValueError('Unsupported coordinates for source profile: '+name)
        if any(key in stream for key in ('units','up','axes')):
            raise ValueError('Coordinate overrides unsupported; use the canonical coordinate_system')
        previous = -1
        for frame in stream['frames']:
            stamp = frame['timestamp_ms']
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0 or stamp <= previous:
                raise ValueError('Timestamps must be nonnegative, finite and strictly increasing: ' + name)
            previous = stamp
            points = frame.get('positions')
            if not isinstance(points, list) or type(frame.get('missing')) is not bool or frame['missing'] != (not points):
                raise ValueError('Missing observations must contain no positions')
            size = 22 if profile['id']=='humanml3d-22-v1' else 33
            if points and ((name == 'body' and len(points) != size) or (name == 'face' and len(points) != 478) or (name == 'hands' and len(points) not in (21, 42))):
                raise ValueError('Incorrect landmark count: ' + name)
            for point in points:
                if not isinstance(point, list) or len(point) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in point):
                    raise ValueError('Invalid point')
            confidence = frame.get('confidence')
            if confidence is not None and (not isinstance(confidence, list) or len(confidence) != len(points) or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in confidence)):
                raise ValueError('Invalid per-landmark confidence')
            if 'groups' in frame and [p for group in frame['groups'] for p in group] != points:
                raise ValueError('Grouped and flattened positions disagree')
    if not any(not frame['missing'] for frame in streams['body']['frames']) and doc.get('quality',{}).get('body_usable') is not False:
        raise ValueError('No observed body motion; explicit partial-result status required')
    return doc


def publish(doc, destination):
    validate(doc)
    data = json.dumps(doc, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, stage = tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.link(stage, target)  # atomic publication; existing versions cannot be replaced
    finally:
        os.unlink(stage)
    return hashlib.sha256(data).hexdigest()


def correct(doc, edits):
    """Explicit point edits retain the original measurement and confidence."""
    result = copy.deepcopy(validate(doc))
    result['parent_revision'] = hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    for edit in edits:
        if not isinstance(edit, dict) or edit.get('stream') not in result['streams']:
            raise ValueError('Unknown correction stream')
        frames = result['streams'][edit['stream']]['frames']
        if type(edit.get('frame')) not in (int,float) or not math.isfinite(edit['frame']) or edit['frame'] != int(edit['frame']) or not 0 <= edit['frame'] < len(frames):
            raise ValueError('Correction frame outside stream')
        frame = frames[int(edit['frame'])]
        index = edit['point']
        if type(index) not in (int,float) or not math.isfinite(index) or index != int(index) or not 0 <= index < len(frame['positions']):
            raise ValueError('Correction point outside observation')
        index = int(index)
        value = edit['position']
        if len(value) != 3 or not all(math.isfinite(v) for v in value):
            raise ValueError('Correction must be a finite XYZ point')
        frame.setdefault('raw_positions', copy.deepcopy(frame['positions']))
        frame['positions'][index] = value
        if 'groups' in frame:
            frame.setdefault('raw_groups', copy.deepcopy(frame['groups']))
            offset = index
            for group in frame['groups']:
                if offset < len(group):
                    group[offset] = value
                    break
                offset -= len(group)
        frame.setdefault('corrections', []).append(edit)
    return validate(result)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--edits', default='[]')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    original = json.loads(Path(args.source).read_text(encoding='utf-8'))
    print(json.dumps({'revision': publish(correct(original, json.loads(args.edits)), args.output)}))
