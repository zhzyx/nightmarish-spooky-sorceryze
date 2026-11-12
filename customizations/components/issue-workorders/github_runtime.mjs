// Discovery and GitHub transport belong to the installed Python runtime (#989).
// The selected project supplies data, never executable adapter code.
import {execFile} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const bridge = fileURLToPath(new URL('./github_runtime_bridge.py', import.meta.url));
const maxBuffer = 4 * 1024 * 1024;
const unknown = '; read remote state before retrying a write';

function invoke(python, request, {cwd, env, timeout}) {
  return new Promise((resolve,reject) => {
    const child = execFile(python, ['-I','-B','-X','utf8',bridge],
      {cwd, env, timeout, killSignal:'SIGKILL', windowsHide:true, maxBuffer}, (error,stdout) => {
        if (error) return reject(Error((error.killed ? 'GITHUB_TIMEOUT: host bridge timed out' :
          'GITHUB_RUNTIME: installed host bridge failed') + unknown));
        let result;
        try {result = JSON.parse(stdout);} catch {return reject(Error('GITHUB_RUNTIME: invalid host bridge response' + unknown));}
        if (result.ok !== true) {
          // Only accept the bridge's bounded, structured errors, never raw child output.
          const allowed = /^GITHUB_(?:RUNTIME|TIMEOUT|NETWORK|COMMAND|HTTP_\d{3}): [^\r\n]{1,240}$/;
          const message = typeof result.error === 'string' && allowed.test(result.error) ? result.error : 'GITHUB_RUNTIME: host bridge rejected request';
          const failure = Error(message + unknown);
          failure.http_status = result.http_status ?? null;
          return reject(failure);
        }
        if (typeof result.value !== 'string') return reject(Error('GITHUB_RUNTIME: invalid host bridge value'));
        resolve(result.value);
      });
    // execFile owns process errors; EPIPE must not expose an unhandled raw error.
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify(request));
  });
}

export async function githubRuntime(config, {env = process.env, timeoutMs = 120000} = {}) {
  if (typeof config.python !== 'string' || !config.python) throw Error('GITHUB_RUNTIME: configured host Python required');
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 120000) throw Error('GITHUB_RUNTIME: invalid request timeout');
  const selectedEnv = {...env};
  if (Object.hasOwn(config,'gh')) {
    if (typeof config.gh !== 'string' || !config.gh) throw Error('GITHUB_RUNTIME: configured gh must be a nonempty executable');
    selectedEnv.GONGGONG_GH = config.gh;
  }
  if (Object.hasOwn(selectedEnv,'GONGGONG_GH') && (typeof selectedEnv.GONGGONG_GH !== 'string' || !selectedEnv.GONGGONG_GH)) {
    throw Error('GITHUB_RUNTIME: configured GONGGONG_GH must be a nonempty executable');
  }
  const options = {cwd:config.workspace,env:selectedEnv,timeout:30000};
  const gh = await invoke(config.python,{operation:'resolve'},options);
  // One session binds one selected executable. New sessions re-read configuration.
  const childEnv = Object.freeze({...selectedEnv,GONGGONG_GH:gh});
  const text = args => invoke(config.python,{operation:'request',args,timeout_ms:timeoutMs},
    {...options,env:childEnv,timeout:timeoutMs + 5000});
  return Object.freeze({gh,env:childEnv,text,json:async args=>{
    const output = await text(args);
    try {return JSON.parse(output);} catch {throw Error('GITHUB_RESPONSE: expected JSON response' + unknown);}
  }});
}
