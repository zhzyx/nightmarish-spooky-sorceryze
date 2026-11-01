"""Use the same active source locator as the workspace host during integration tests."""
import json
import os


def active_source(workspace, framework):
    local = workspace / '.olympus-local.json'
    if local.is_file():
        configured = json.loads(local.read_text(encoding='utf-8-sig'))
        if 'GONGGONG_FRAMEWORK_SOURCE' in configured:
            return (workspace / configured['GONGGONG_FRAMEWORK_SOURCE']).resolve()
    if os.environ.get('GONGGONG_FRAMEWORK_SOURCE'):
        return (workspace / os.environ['GONGGONG_FRAMEWORK_SOURCE']).resolve()
    binding = json.loads((framework / 'sync/binding.json').read_text(encoding='utf-8'))
    return (framework / binding['source']).resolve()
