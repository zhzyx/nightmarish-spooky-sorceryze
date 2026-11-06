"""Publish a staged, self-contained rig scene through the existing atomic adapter."""
import hashlib
import json
import sys
from pathlib import Path
from extensions import publish_new


def publish(staged, target):
    data = Path(staged).read_bytes()
    if Path(target).suffix != '.tscn' or not data.startswith(b'[gd_scene'):
        raise ValueError('Expected a Godot scene and new .tscn destination')
    revision = hashlib.sha256(data).hexdigest()
    manifest = {'schema_version': 1, 'artifacts': [
        {'id': 'character', 'type': 'character', 'revision': revision,
         'payload': {'encoding': 'godot_tscn'}, 'binding': {'level': 'unbound'}}]}
    class Encoded:
        def encode(self, _manifest):
            return data
    return publish_new(Encoded(), manifest, target)


if __name__ == '__main__':
    try:
        print(json.dumps(publish(*sys.argv[1:])))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
