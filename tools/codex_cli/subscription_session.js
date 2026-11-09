'use strict';

// An app-server instance is private to one editor worker. No external model client or key.
const {spawn, spawnSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const {mkdtempSync, rmdirSync, lstatSync} = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const disabled = [
    'shell_tool', 'unified_exec', 'plugins', 'hooks', 'apps', 'multi_agent', 'computer_use', 'image_generation',
    'memories', 'apply_patch_freeform', 'view_image', 'web_search_request', 'web_search_cached'
];
function assistantKey(message) {
    if (!message || message.role !== 'assistant') return null;
    return hash([
        message.content ?? '',
        (message.tool_calls || []).map(call => [call.id, call.type, call.function?.name, call.function?.arguments])
    ]);
}
const fault = () => new Error('SUBSCRIPTION_SESSION_UNAVAILABLE');
function fileIdentity(file) {
    try {
        const s = lstatSync(file, {bigint: true});
        if (!s.isFile() || s.isSymbolicLink()) return null;
        return [s.dev, s.ino, s.size, s.mtimeNs, s.ctimeNs].map(String).join(':');
    } catch {
        return null;
    }
}
const itemTypes = new Set(['userMessage', 'agentMessage', 'reasoning', 'contextCompaction']);

class Channel {
    constructor(child) {
        this.child = child;
        this.id = 0;
        this.pending = new Map();
        this.closed = false;
        let buffer = '';
        child.stdout.setEncoding('utf8');
        child.stdout.on('data', chunk => {
            buffer += chunk;
            if (Buffer.byteLength(buffer) > 2 * 1024 * 1024) return this.close();
            let i;
            while ((i = buffer.indexOf('\n')) >= 0) {
                const line = buffer.slice(0, i);
                buffer = buffer.slice(i + 1);
                try {
                    if (line.trim()) this.packet(JSON.parse(line));
                } catch {
                    return this.close();
                }
            }
        });
        child.stdin.on('error', () => this.close());
        child.on('error', () => this.close());
        child.on('close', () => this.close());
    }
    close() {
        if (this.closed) return;
        this.closed = true;
        this.child.kill();
        for (const [, p] of this.pending) {
            clearTimeout(p.timer);
            p.reject(fault());
        }
        this.pending.clear();
        this.onclose?.();
    }
    packet(p) {
        if (this.closed) return;
        if (p.method && p.id !== undefined) throw fault();  // Never approve a native request.
        if (p.method) {
            this.notify?.(p);
            return;
        }
        const q = this.pending.get(p.id);
        if (!q) throw fault();
        this.pending.delete(p.id);
        clearTimeout(q.timer);
        if (p.error || !p.result)
            q.reject(fault());
        else
            q.resolve(p.result);
    }
    call(method, params) {
        if (this.closed) return Promise.reject(fault());
        const id = ++this.id;
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => this.close(), 15000);
            this.pending.set(id, {resolve, reject, timer});
            this.child.stdin.write(JSON.stringify({id, method, params}) + '\n');
        });
    }
}

class Subscription {
    constructor(channel, cwd, features = disabled) {
        this.rpc = channel;
        this.cwd = cwd;
        this.features = features;
    }
    async initialize() {
        const rpc = this.rpc;
        await rpc.call('initialize', {clientInfo: {name: 'godot_tianshu', version: '1.0'}});
        rpc.child.stdin.write('{"method":"initialized","params":{}}\n');
        const {config} = await rpc.call('config/read', {});
        if (!config || this.features.some(f => config.features?.[f] !== false) || config.notify?.length ||
            config.approval_policy !== 'never' || config.sandbox_mode !== 'read-only' ||
            config.web_search !== 'disabled' || config.model_provider !== 'openai' ||
            config.project_doc_max_bytes !== 0)
            throw fault();
        const m = await rpc.call('mcpServerStatus/list', {});
        if (!Array.isArray(m.data) || m.nextCursor ||
            m.data.some(
                x => config.mcp_servers?.[x.name]?.enabled !== false ||
                    [x.tools, x.resources, x.resourceTemplates].some(v => !v || Object.keys(v).length)))
            throw fault();
        this.account = await this.identity();
    }
    accepted(message) {
        this.reply = assistantKey(message);
    }
    async identity() {
        const {account} = await this.rpc.call('account/read', {});
        if (account?.type !== 'chatgpt' || !account.email ||
            !['free', 'plus', 'pro', 'promax', 'go'].includes(account.planType))
            throw fault();
        const home = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
        const auth = fileIdentity(path.join(home, 'auth.json'));
        if (!auth) throw fault();  // Keyring-only or unidentifiable workspace: keep the compatible exec path.
        return hash([
            account.type, account.email, account.planType, account.workspaceName, auth,
            fileIdentity(path.join(home, 'config.toml'))
        ]);
    }
    async turn(input, scope, schema, prompt, progress) {
        if (await this.identity() !== this.account) throw fault();
        const history = input.messages.filter(m => m.role !== 'system'),
              system = input.messages.filter(m => m.role === 'system');
        const keys = history.map(hash), currentSystem = hash(system);
        const controls = {...input.tool_context};
        delete controls.tool_rounds;
        const binding = hash([scope, input.model, input.reasoning_effort, controls, input.available_tools]);
        const reuse = this.thread && binding === this.binding && this.keys?.length < keys.length &&
            this.keys.every((v, i) => keys[i] === v) && this.reply &&
            assistantKey(history[this.keys.length]) === this.reply;
        if (!reuse) {
            try {
                const r = await this.rpc.call('thread/start', {
                    ephemeral: true,
                    cwd: this.cwd,
                    model: input.model,
                    modelProvider: 'openai',
                    approvalPolicy: 'never',
                    sandbox: 'read-only',
                    baseInstructions:
                        'You are the Godot editor assistant. Never use native tools. Only propose actions to the Godot host.'
                });
                if (!r.thread?.id || !r.thread.ephemeral || r.approvalPolicy !== 'never' ||
                    r.modelProvider !== 'openai' || r.model !== input.model || r.sandbox?.type !== 'readOnly' ||
                    r.sandbox.networkAccess !== false)
                    throw fault();
                this.thread = r.thread.id;
            } catch {
                const e = fault();
                e.beforeTurn = true;
                throw e;
            }
            this.binding = binding;
            progress('thread_started');
        }
        const items = reuse ? history.slice(this.keys.length) : input.messages;
        const text = reuse ? JSON.stringify({
            messages: items,
            tool_context: input.tool_context,
            ...(this.system !== currentSystem ? {current_host_instructions: system} : {})
        }) :
                             prompt(input);
        const rpc = this.rpc, thread = this.thread;
        let turn, resolve, reject, early = [], result = '', total = 0;
        const terminal = new Promise((ok, no) => {
            resolve = ok;
            reject = no;
        });
        terminal.catch(() => {});
        const timer = setTimeout(() => rpc.close(), 300000);
        rpc.onclose = () => reject(fault());
        function receive(p) {
            if (p.params?.threadId !== thread) return;
            if (!turn) {
                if (early.length >= 256) throw fault();
                early.push(p);
                return;
            }
            if ((p.params.turnId || p.params.turn?.id) !== turn) return;
            const item = p.params.item;
            if ((p.method === 'item/started' || p.method === 'item/completed') && !itemTypes.has(item?.type))
                throw fault();
            if (p.method === 'item/agentMessage/delta') {
                total += Buffer.byteLength(p.params.delta || '');
                if (total > 2 * 1024 * 1024) throw fault();
            }
            if (p.method === 'item/completed' && item?.type === 'agentMessage') result = item.text;
            if (p.method === 'turn/completed') {
                if (p.params.turn.status !== 'completed' || !result)
                    reject(fault());
                else
                    resolve(result);
            }
        }
        rpc.notify = receive;
        try {
            const r = await rpc.call('turn/start', {
                threadId: thread,
                input: [{type: 'text', text}],
                outputSchema: schema,
                ...(input.reasoning_effort ? {effort: input.reasoning_effort} : {})
            });
            if (!r.turn?.id) throw fault();
            turn = r.turn.id;
            progress('turn_started');
            for (const p of early) receive(p);
            early = [];
            const output = await terminal;
            this.keys = keys;
            this.system = currentSystem;
            this.reply = null;
            return {output, mode: reuse ? 'incremental' : 'bootstrap', messages: items.length};
        } finally {
            clearTimeout(timer);
            rpc.notify = null;
            rpc.onclose = null;
        }
    }
}

async function start(entry, python, env) {
    if (process.platform !== 'win32' || !path.isAbsolute(python) ||
        Object.keys(env).some(k => /^(openai_api_key|openai_base_url|codex_api_key)$/i.test(k) && env[k]))
        throw fault();
    const pre = spawnSync(
        python, ['-I', path.join(__dirname, 'subscription_profile.py')],
        {windowsHide: true, encoding: 'utf8', timeout: 3500, maxBuffer: 32768});
    const names = pre.status === 0 ? JSON.parse(pre.stdout) : null;
    if (!Array.isArray(names)) throw fault();
    const settings = [
        'approval_policy="never"', 'sandbox_mode="read-only"', 'model_provider="openai"', 'notify=[]',
        'project_doc_max_bytes=0', 'web_search="disabled"', ...disabled.map(f => 'features.' + f + '=false'),
        ...names.map(n => 'mcp_servers.' + n + '.enabled=false')
    ];
    const cwd = mkdtempSync(path.join(os.tmpdir(), 'godot-codex-session-'));
    const js = /\.m?js$/.test(entry);
    const child = spawn(
        js ? process.execPath : entry,
        [...(js ? [entry] : []), 'app-server', '--listen', 'stdio://', ...settings.flatMap(s => ['-c', s])],
        {cwd, windowsHide: true, env, stdio: ['pipe', 'pipe', 'ignore']});
    const rpc = new Channel(child);
    const session = new Subscription(rpc, cwd);
    child.on('close', () => {
        try {
            rmdirSync(cwd);
        } catch {
        }
    });
    try {
        await session.initialize();
        return session;
    } catch (e) {
        rpc.close();
        throw e;
    }
}

module.exports = {
    Channel,
    Subscription,
    start
};
