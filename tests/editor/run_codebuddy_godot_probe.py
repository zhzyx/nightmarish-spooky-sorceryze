import argparse
import os
import secrets
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GODOT = ROOT / 'bin/godot.windows.editor.dev.x86_64.dotnet.mono.console.exe'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tools', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ai_cli_probe_', dir=ROOT) as directory:
        project = Path(directory)
        (project / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="CodeBuddy Native Connection Probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
        shutil.copyfile(Path(__file__).with_name('probe_codebuddy_godot.gd'), project / 'probe.gd')
        env = os.environ.copy()
        env['DOTNET_ROOT'] = str(ROOT / '.dotnet')
        env['DOTNET_ROOT_X64'] = env['DOTNET_ROOT']
        env['PATH'] = env['DOTNET_ROOT'] + os.pathsep + env.get('PATH', '')
        env['AI_CHAT_TEST_NODE'] = shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
        env['AI_CHAT_TEST_BRIDGE'] = str(ROOT / 'tools/codebuddy_cli/godot_bridge.js')
        env['AI_CHAT_TEST_ENTRY'] = str(ROOT / 'tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/codebuddy')
        env['AI_CHAT_PROBE_TOOLS'] = '1' if args.tools else '0'
        if args.tools:
            expected = 'REAL_TOOL_REPLY_' + secrets.token_hex(12)
            (project / 'tool_fixture.txt').write_text(expected, encoding='utf-8')
            env['AI_CHAT_PROBE_EXPECTED'] = expected
        try:
            result = subprocess.run([str(GODOT), '--headless', '--editor', '--path', str(project), '--script', 'res://probe.gd'], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=275 if args.tools else 155)
        except subprocess.TimeoutExpired:
            print('CODEBUDDY_GODOT_FAILED: editor probe timed out')
            return 1
        for line in (result.stdout + '\n' + result.stderr).splitlines():
            if 'CODEBUDDY_GODOT_' in line or 'were leaked' in line:
                print(line)
        return 0 if result.returncode == 0 and 'CODEBUDDY_GODOT_OK: native dock' in result.stdout else 1


if __name__ == '__main__':
    raise SystemExit(main())
