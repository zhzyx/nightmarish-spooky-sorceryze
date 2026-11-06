"""Real CPU MediaPipe inference; body, hands and face keep separate clocks/units."""
import argparse
import json
from pathlib import Path
from motion import digest, publish, text_context, verify_input


def run(video, models, context='', expected_sha256=None):
    input_sha256 = expected_sha256 or digest(video)
    verify_input(video,input_sha256)
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision
    base = lambda name: BaseOptions(model_asset_path=str(Path(models) / (name + '.task')), delegate=BaseOptions.Delegate.CPU)
    mode = vision.RunningMode.VIDEO
    pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=base('pose'), running_mode=mode))
    hand = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(base_options=base('hand'), running_mode=mode, num_hands=2))
    face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=base('face'), running_mode=mode, output_face_blendshapes=True, output_facial_transformation_matrixes=True))
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    streams = {name: {'time_base': 'decoded_video_pts_ms', 'coordinate_system': units, 'frames': []} for name, units in [('body', 'hip_relative_meters_x_right_y_down_z_away'), ('hands', 'per_hand_local_meters'), ('face', 'normalized_image_coordinates')]}
    previous = -1
    index = 0
    try:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)
            stamp = round(pts)
            if stamp <= previous:
                raise ValueError('Decoder did not provide strictly increasing timestamps; transcode input with preserved PTS')
            previous = stamp
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            p, h, f = pose.detect_for_video(image, stamp), hand.detect_for_video(image, stamp), face.detect_for_video(image, stamp)
            for name, groups in [('body', p.pose_world_landmarks), ('hands', h.hand_world_landmarks), ('face', f.face_landmarks)]:
                frame = {'timestamp_ms': stamp, 'decoder_pts_ms': pts, 'frame_index': index, 'missing': not bool(groups), 'positions': [], 'confidence': None, 'occlusion': 'unknown', 'groups': []}
                for group in groups:
                    points = [[v.x, v.y, v.z] for v in group]
                    frame['groups'].append(points)
                    frame['positions'].extend(points)
                if name == 'body' and groups:
                    frame['confidence'] = [v.visibility for v in groups[0]]
                    frame['presence'] = [v.presence for v in groups[0]]
                    frame['occlusion'] = ['low_visibility' if v.visibility < .5 else 'not_reported' for v in groups[0]]
                    frame['image_positions'] = [[v.x, v.y, v.z] for v in p.pose_landmarks[0]]
                if name == 'hands':
                    frame['handedness'] = [[{'label': c.category_name, 'score': c.score} for c in group] for group in h.handedness]
                    frame['confidence_note'] = 'Per-landmark confidence not exposed; handedness score is not landmark confidence'
                if name == 'face':
                    frame['blendshapes'] = [[{'name': c.category_name, 'coefficient': c.score} for c in group] for group in f.face_blendshapes]
                    frame['transforms'] = [matrix.tolist() for matrix in f.facial_transformation_matrixes]
                    frame['confidence_note'] = 'Per-landmark confidence not exposed; blendshape coefficients are not confidence'
                streams[name]['frames'].append(frame)
            index += 1
    finally:
        cap.release()
        pose.close()
        hand.close()
        face.close()
    if not index:
        raise ValueError('No decoded frames')
    verify_input(video,input_sha256)
    quality = {'body_usable': any(not frame['missing'] for frame in streams['body']['frames']), 'subject_selection': 'single highest detection; no persistent identity guarantee in multi-person video', 'face_binding': 'unbound separate stream', 'low_visibility_body_frames': sum(any(v < .5 for v in frame.get('confidence') or []) for frame in streams['body']['frames'])}
    return {'schema': 'ainative.motion.v1', 'quality': quality, 'fps': fps, 'context': text_context(context, False), 'source_profile': {'id': 'mediapipe-pose33-v1', 'body_landmarks': 33, 'hands': 'separate-21-per-hand', 'face': 'separate-478', 'root_motion': 'unobserved: hip-relative monocular reconstruction'}, 'provenance': {'provider': 'mediapipe', 'version': mp.__version__, 'input_sha256': input_sha256, 'models': {name: digest(Path(models) / (name + '.task')) for name in ['pose', 'hand', 'face']}}, 'streams': streams}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', required=True)
    parser.add_argument('--models', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--context', default='')
    parser.add_argument('--expected-input-sha256')
    args = parser.parse_args()
    print(json.dumps({'revision': publish(run(args.video, args.models, args.context,args.expected_input_sha256), args.output)}))
