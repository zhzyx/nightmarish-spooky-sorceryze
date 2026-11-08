'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { randomUUID, createHash } = require('node:crypto');
const { spawn } = require('node:child_process');
const { Readable, Writable } = require('node:stream');
const { createTerminals, hostActionName, hostActionRequest, READ_ONLY_HOST_ACTIONS } = require('./godot_terminal');

function workspacePaths(input, fallback) {
    const resolve = value => {
        if (!value || !path.isAbsolute(value) || !fs.statSync(value).isDirectory()) throw new Error('INVALID_REQUEST');
        return fs.realpathSync(value);
    };
    const workspace = { project_root: resolve(input.project_root || fallback), engine_root: resolve(input.engine_root || path.resolve(__dirname, '../..')) };
    if (input.workspace_root) workspace.workspace_root = resolve(input.workspace_root);
    if (input.command_profile) workspace.command_profile = input.command_profile;
    if (input.provenance_guard_required === true) workspace.provenance_guard_required = true;
    return workspace;
}

function promptBlocks(input, initial, imageSupported = true) {
    // General system instructions already reach the CLI via --system-prompt.
    // Keep host restore notices in recovered history so a new session learns
    // that the undone edits are no longer applied, without replaying the turn.
    const records = input.messages.filter(message => message.role !== 'system' || message.godot_snapshot_restore === true);
    const last = records.at(-1);
    const resuming = initial && last?.role === 'tool' && typeof last.content === 'string';
    const calls = resuming ? records.filter(message => message.role === 'assistant').at(-1)?.tool_calls || [] : [];
    const awaited = calls.find(call => call.id === last?.tool_call_id);
    if (!last || typeof last.content !== 'string' || last.role !== 'user' && !(resuming && ['build_engine', 'restart_engine', 'rollback_engine'].includes(awaited?.function?.name))) throw new Error('INVALID_REQUEST');
    const images = message => (message.images || []).map(image => ({ type: 'image', data: image.data, mimeType: image.mime_type }));
    const blocks = resuming ? [{ type: 'text', text: 'Continue the interrupted conversation from the completed Godot host action. Read its result and verify the intended behavior. Do not repeat the user task or rebuild the same change.' }] : last.content ? [{ type: 'text', text: last.content }] : [];
    if (resuming) blocks.push({ type: 'resource', resource: { uri: 'godot://host/action-result', mimeType: 'application/json', text: JSON.stringify(last) } });
    if (initial && records.length > 1) {
        const history = records.slice(0, -1).map(message => ({ ...message, ...(message.images ? { images: message.images.map(({ data, ...metadata }) => metadata) } : {}) }));
        blocks.push({ type: 'resource', resource: { uri: 'godot://conversation/recovery', mimeType: 'application/json', text: JSON.stringify(history) } });
        for (let i = 0; i < records.length - 1; i++) {
            const attachments = images(records[i]);
            if (attachments.length) blocks.push({ type: 'text', text: 'Recovered attachments for history message ' + (i + 1) + ':' }, ...attachments);
        }
        if ((last.images || []).length) blocks.push({ type: 'text', text: 'Attachments for the current user message:' });
    }
    blocks.push(...images(last));
    if (blocks.some(block => block.type === 'image') && !imageSupported) throw Object.assign(new Error('IMAGE_UNSUPPORTED'), { bridgeCode: 'IMAGE_UNSUPPORTED' });
    blocks.push({ type: 'resource', resource: { uri: 'godot://host/state', mimeType: 'application/json', text: JSON.stringify(input.tool_context) } });
    if (input.workspace) blocks.push({ type: 'resource', resource: { uri: 'godot://host/workspace', mimeType: 'application/json', text: JSON.stringify(input.workspace) } });
    return blocks;
}

function fileArguments(params, writing) {
    if (!params || typeof params.path !== 'string' || !path.isAbsolute(params.path)) throw new Error('INVALID_ACTION');
    if (writing) {
        if (typeof params.content !== 'string' || Buffer.byteLength(params.content) > 256 * 1024) throw new Error('INVALID_ACTION');
        return { path: params.path, content: params.content };
    }
    const args = { path: params.path };
    if (params.line != null || params.limit != null) {
        const offset = params.line ?? 1;
        const limit = params.limit ?? 200;
        if (!Number.isSafeInteger(offset) || offset < 1 || offset > 2147483647 || !Number.isSafeInteger(limit) || limit < 1 || limit > 500) throw new Error('INVALID_ACTION');
        args.offset = offset;
        args.limit = limit;
    }
    return args;
}

// Older Godot serializers left ESC and other controls unescaped and emitted
// the non-JSON escape \v. Repair only these encodings inside string literals;
// preserve the exact decoded text and keep all other JSON validation strict.
function parseHostJson(text) {
    try { return JSON.parse(text); } catch (_) { /* Try legacy string encoding. */ }
    let quoted = false;
    let escaped = false;
    let normalized = '';
    for (const c of text) {
        if (escaped) {
            normalized += c === 'v' ? 'u000b' : c;
            escaped = false;
        } else if (quoted && c === '\\') {
            normalized += c;
            escaped = true;
        } else if (c === '"') {
            normalized += c;
            quoted = !quoted;
        } else if (quoted && c.charCodeAt(0) < 0x20) {
            normalized += '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0');
        } else {
            normalized += c;
        }
    }
    try { return JSON.parse(normalized); }
    catch (_) { throw Object.assign(new Error('Invalid Godot request JSON'), { bridgeCode: 'INVALID_REQUEST' }); }
}

function readResponse(text, args) {
    if (!Object.hasOwn(args, 'offset')) return { content: text };
    const range = parseHostJson(text);
    if (!range || typeof range.content !== 'string' || range.context_excerpted || range.offset !== args.offset) throw new Error('INVALID_RESPONSE');
    return { content: range.content };
}

function fileTextFormat(text) {
    const crlf = (text.match(/\r\n/g) || []).length;
    const rest = text.replace(/\r\n/g, '');
    const lf = (rest.match(/\n/g) || []).length;
    const cr = (rest.match(/\r/g) || []).length;
    return { newline: cr ? 'mixed' : crlf && lf ? 'mixed' : crlf ? 'crlf' : lf ? 'lf' : 'none', bom: text.startsWith('\uFEFF'), crlf_count: crlf, lf_count: lf, cr_count: cr };
}

function createFileTextView(limit = 256) {
    const formats = new Map();
    const key = file => process.platform === 'win32' ? path.normalize(file).toLowerCase() : path.normalize(file);
    return {
        read(text, args) {
            const response = readResponse(text, args);
            const format = fileTextFormat(response.content);
            if (!Object.hasOwn(args, 'offset')) {
                const file = key(args.path);
                if (!formats.has(file) && formats.size >= limit) formats.delete(formats.keys().next().value);
                formats.set(file, format);
            }
            if (format.newline !== 'mixed') response.content = response.content.replace(/\r\n/g, '\n');
            if (!Object.hasOwn(args, 'offset') || args.offset === 1) response.content = response.content.replace(/^\uFEFF/, '');
            return response;
        },
        write(args) {
            const format = formats.get(key(args.path));
            if (!format) return args;
            let content = args.content;
            if (format.newline === 'crlf' || format.newline === 'lf') {
                content = content.replace(/\r\n/g, '\n');
                if (format.newline === 'crlf') content = content.replace(/\n/g, '\r\n');
            }
            if (format.bom && !content.startsWith('\uFEFF')) content = '\uFEFF' + content;
            if (Buffer.byteLength(content) > 256 * 1024) throw new Error('INVALID_ACTION');
            return { ...args, content };
        },
        saved(args) {
            const file = key(args.path);
            if (!formats.has(file) && formats.size >= limit) formats.delete(formats.keys().next().value);
            formats.set(file, fileTextFormat(args.content));
        },
        clear() { formats.clear(); },
    };
}

function toolFailure(update) {
    if (update?.sessionUpdate !== 'tool_call_update' || update.status !== 'failed') return null;
    const texts = Array.isArray(update.content) ? update.content.filter(block => block?.type === 'content' && block.content?.type === 'text' && typeof block.content.text === 'string').map(block => block.content.text) : [];
    const text = texts.join('\n').replace(/\r\n/g, '\n');
    const prefix = 'Edit error: ';
    const suffix = '\n\nNo edits were applied.';
    const cause = text === prefix + 'The provided `old_string` is empty.' + suffix ? 'empty_old_string' : text.startsWith(prefix + 'The provided `old_string` does not appear in the file: "') && text.endsWith('".' + suffix) ? 'old_string_not_found' : 'unknown';
    return { failure_cause: cause, tool_text_bytes: Buffer.byteLength(text), tool_content_blocks: texts.length };
}

function createWaitBudget(now = () => performance.now(), idleMs = 300000, hardMs = 1800000) {
    let spent = 0;
    let resumed;
    let last;
    return {
        resume() { resumed = last = now(); },
        touch() { if (resumed !== undefined) last = now(); },
        pause() { if (resumed !== undefined) spent += now() - resumed; resumed = undefined; },
        snapshot() {
            const elapsed = spent + (resumed === undefined ? 0 : now() - resumed);
            const idle = resumed === undefined ? 0 : now() - last;
            return { elapsed_ms: Math.floor(elapsed), idle_ms: Math.floor(idle), remaining_ms: Math.max(0, Math.min(idleMs - idle, hardMs - elapsed)), expired: elapsed >= hardMs ? 'hard' : idle >= idleMs ? 'idle' : '' };
        },
    };
}

function progressUpdate(update) {
    if (update.sessionUpdate === 'agent_message_chunk' && update.content?.type === 'text') return { activity: 'responding', content_delta: update.content.text };
    if (update.sessionUpdate === 'agent_thought_chunk' || update.sessionUpdate === 'plan') return { activity: 'analyzing', content_delta: '' };
    if (update.sessionUpdate === 'tool_call' || update.sessionUpdate === 'tool_call_update') return { activity: update.kind === 'search' || ['Glob', 'Grep'].includes(update.title) ? 'searching' : 'tool_pending', content_delta: '' };
    return null;
}

function createToolKindState(limit = 256) {
    const kinds = new Map();
    let sessionId;
    const validId = id => typeof id === 'string' && id.length > 0 && id.length <= 256;
    return {
        begin(session) { sessionId = session; kinds.clear(); },
        clear() { kinds.clear(); },
        update(notification) {
            const update = notification?.update;
            if (notification?.sessionId !== sessionId || !update || !['tool_call', 'tool_call_update'].includes(update.sessionUpdate) || !validId(update.toolCallId)) return;
            const id = update.toolCallId;
            if (update.sessionUpdate === 'tool_call' || ['completed', 'failed'].includes(update.status)) kinds.delete(id);
            if (['completed', 'failed'].includes(update.status)) return;
            if (update.kind != null && typeof update.kind === 'string' && (kinds.has(id) || kinds.size < limit)) kinds.set(id, update.kind);
        },
        resolve(session, call) {
            if (session !== sessionId || !call || !validId(call.toolCallId)) return { kind: 'missing', kind_source: 'missing' };
            if (call.kind != null) return { kind: typeof call.kind === 'string' ? call.kind : 'other', kind_source: 'permission' };
            if (kinds.has(call.toolCallId)) return { kind: kinds.get(call.toolCallId), kind_source: 'notification' };
            return { kind: 'missing', kind_source: 'missing' };
        },
    };
}

function createTraceLog(directory, maxBytes = 8 * 1024 * 1024) {
    const started = performance.now();
    const file = path.join(directory, 'acp-' + new Date().toISOString().replace(/[:.]/g, '-') + '-' + process.pid + '-' + randomUUID().slice(0, 8) + '.jsonl');
    let bytes = 0;
    let sequence = 0;
    let enabled = true;
    const numeric = new Set(['request', 'child_pid', 'elapsed_ms', 'idle_ms', 'stdout_bytes', 'stderr_bytes', 'pending_count', 'message_count', 'image_count', 'prompt_bytes', 'text_bytes', 'content_bytes', 'read_count', 'write_count', 'permission_count', 'rpc_count', 'line', 'limit', 'protocol_version', 'exit_code', 'rpc_error_code', 'crlf_count', 'lf_count', 'cr_count', 'tool_text_bytes', 'tool_content_blocks']);
    const boolean = new Set(['active', 'yielded', 'stopped', 'session_match', 'permission_enabled', 'success', 'image_supported', 'embedded_context', 'read_enabled', 'write_enabled', 'bom']);
    const enums = {
        direction: ['incoming', 'outgoing'],
        stage: ['connecting', 'waiting', 'analyzing', 'responding', 'tool_pending', 'searching', 'executing'],
        operation: ['read_logs', 'get_parent_context', 'get_editor_state', 'editor_action', 'route_engine_message', 'read_file', 'write_file', 'run_command', 'build_engine', 'restart_engine', 'rollback_engine', 'complete_delivery'],
        decision: ['allow_once', 'reject_once', 'cancelled'],
        kind_source: ['permission', 'notification', 'missing'],
        native_tool: ['Glob', 'Grep'],
        newline: ['crlf', 'lf', 'mixed', 'none'],
        failure_cause: ['empty_old_string', 'old_string_not_found', 'unknown'],
        kind: ['read', 'edit', 'delete', 'move', 'search', 'execute', 'think', 'fetch', 'switch_mode', 'other', 'missing'],
        status: ['pending', 'in_progress', 'completed', 'failed', 'other', 'missing'],
        reason: ['invalid_session', 'permission_disabled', 'round_limit_reached', 'unavailable', 'invalid_arguments', 'budget_exhausted', 'host_rejected', 'invalid_response', 'none'],
        stop_reason: ['end_turn', 'max_tokens', 'max_turn_requests', 'refusal', 'cancelled', 'other'],
        timeout_kind: ['idle', 'hard'],
        failure_hint: ['AUTH_REQUIRED', 'NETWORK_ERROR', 'MODEL_UNAVAILABLE', 'NATIVE_COMPONENT_MISSING'],
        code: ['TIMEOUT', 'OUTPUT_LIMIT', 'PROCESS_EXIT', 'PROCESS_START', 'AUTH_REQUIRED', 'NETWORK_ERROR', 'MODEL_UNAVAILABLE', 'NATIVE_COMPONENT_MISSING', 'RESULT_FAILED', 'UNSUPPORTED_HOST_TOOL', 'REQUEST_SIZE_LIMIT', 'CONTEXT_LIMIT', 'INVALID_REQUEST', 'INVALID_RESPONSE', 'BRIDGE_ERROR', 'IMAGE_UNSUPPORTED', 'TOOL_ROUND_LIMIT_REACHED', 'TOOLS_DISABLED', 'CLI_CANCELLED', 'EDIT_MATCH_FAILED'],
    };
    try { fs.mkdirSync(directory, { recursive: true }); } catch (_) { enabled = false; }
    return {
        file,
        write(event, details = {}) {
            if (!enabled) return;
            const safe = {};
            for (const [key, value] of Object.entries(details)) {
                if (numeric.has(key) && Number.isSafeInteger(value) && value >= -32768) safe[key] = value;
                else if (boolean.has(key) && typeof value === 'boolean') safe[key] = value;
                else if (enums[key]?.includes(value)) safe[key] = value;
                else if (['kind', 'status', 'stop_reason'].includes(key) && typeof value === 'string') {
                    safe[key] = 'other';
                    safe[key + '_hash'] = createHash('sha256').update(value).digest('hex').slice(0, 16);
                }
                else if (['method', 'update'].includes(key) && typeof value === 'string') {
                    const known = key === 'method' ? ['initialize', 'session/new', 'session/prompt', 'session/cancel', 'session/set_model', 'session/set_mode', 'session/update', 'session/request_permission', 'fs/read_text_file', 'fs/write_text_file'] : ['agent_message_chunk', 'agent_thought_chunk', 'user_message_chunk', 'tool_call', 'tool_call_update', 'plan', 'available_commands_update', 'current_mode_update', 'config_option_update', 'usage_update', 'session_info_update'];
                    safe[key] = known.includes(value) ? value : 'other';
                    if (!known.includes(value)) safe[key + '_hash'] = createHash('sha256').update(value).digest('hex').slice(0, 16);
                }
                else if (['rpc_id_hash', 'call_hash'].includes(key) && /^[a-f0-9]{16}$/.test(value)) safe[key] = value;
                else if (['node_version', 'cli_version', 'sdk_version'].includes(key) && /^v?\d+\.\d+\.\d+$/.test(value)) safe[key] = value;
            }
            const record = JSON.stringify({ time: new Date().toISOString(), since_start_ms: Math.floor(performance.now() - started), sequence: ++sequence, event: /^[a-z_]{1,48}$/.test(event) ? event : 'other', ...safe }) + '\n';
            if (bytes + Buffer.byteLength(record) > maxBytes) { enabled = false; return; }
            try { fs.appendFileSync(file, record, { encoding: 'utf8', mode: 0o600 }); bytes += Buffer.byteLength(record); } catch (_) { enabled = false; }
        },
    };
}

const RPC_MESSAGE_LIMIT = 16 * 1024 * 1024;
const RPC_BUFFER_LIMIT = 32 * 1024 * 1024;
const RPC_STREAM_WATERMARK = 64 * 1024;

function rpcTrace(direction, record, { maxMessageBytes = RPC_MESSAGE_LIMIT, onBytes = () => {}, onLine = () => {}, onLimit = () => {} } = {}) {
    let fragments = [];
    let pendingBytes = 0;
    const hash = value => createHash('sha256').update(String(value)).digest('hex').slice(0, 16);
    const append = bytes => {
        if (pendingBytes + bytes.byteLength > maxMessageBytes) {
            fragments = [];
            pendingBytes = 0;
            record('rpc_line_limit', { direction });
            const error = Object.assign(new Error('ACP message exceeds the byte limit'), { bridgeCode: 'OUTPUT_LIMIT' });
            onLimit(error);
            throw error;
        }
        if (bytes.byteLength) fragments.push(Buffer.from(bytes));
        pendingBytes += bytes.byteLength;
    };
    const complete = terminated => {
        const size = pendingBytes + (terminated ? 1 : 0);
        const line = Buffer.concat(fragments, pendingBytes).toString('utf8');
        fragments = [];
        pendingBytes = 0;
        let queued = false;
        if (line.trim()) {
            try {
                const packet = JSON.parse(line);
                // The SDK only enqueues objects/arrays; malformed and blank
                // lines must not retain a slot in its pending-byte ledger.
                queued = packet !== null && typeof packet === 'object';
                record(packet?.method ? 'rpc_method' : 'rpc_result', { direction, method: packet?.method, rpc_id_hash: packet?.id == null ? undefined : hash(packet.id), rpc_error_code: packet?.error?.code, success: !packet?.error });
            } catch (_) { record('rpc_parse_error', { direction }); }
        }
        onLine(size, queued);
    };
    return new TransformStream({
        transform(chunk, controller) {
            onBytes(chunk.byteLength);
            const bytes = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
            let start = 0;
            let newline;
            while ((newline = bytes.indexOf(10, start)) >= 0) {
                append(bytes.subarray(start, newline));
                complete(true);
                start = newline + 1;
            }
            append(bytes.subarray(start));
            controller.enqueue(chunk);
        },
        flush() { if (pendingBytes) complete(false); },
    }, new ByteLengthQueuingStrategy({ highWaterMark: RPC_STREAM_WATERMARK }), new ByteLengthQueuingStrategy({ highWaterMark: RPC_STREAM_WATERMARK }));
}

function boundedRpcStream(acp, output, input, record, onLimit, onBytes = () => {}, { maxMessageBytes = RPC_MESSAGE_LIMIT, maxBufferedBytes = RPC_BUFFER_LIMIT } = {}) {
    // Bound bytes still waiting in the SDK decoder/parsed-message queue, not
    // lifetime traffic. Debit each frame as it reaches the ACP dispatcher.
    let bufferedBytes = 0;
    let sizes = [];
    let head = 0;
    const limit = error => {
        sizes = [];
        head = 0;
        bufferedBytes = 0;
        onLimit(error);
    };
    const incoming = input.pipeThrough(rpcTrace('incoming', record, {
        maxMessageBytes,
        onLimit: limit,
        onBytes(size) {
            onBytes(size);
            bufferedBytes += size;
            if (bufferedBytes > maxBufferedBytes) {
                record('rpc_buffer_limit', { direction: 'incoming' });
                const error = Object.assign(new Error('Unprocessed ACP buffer exceeds the byte limit'), { bridgeCode: 'OUTPUT_LIMIT' });
                limit(error);
                throw error;
            }
        },
        onLine(size, queued) {
            if (queued) sizes.push(size);
            else bufferedBytes -= size;
        },
    }));
    const stream = acp.ndJsonStream(output, incoming, { maxMessageBytes });
    const readable = stream.readable.pipeThrough(new TransformStream({
        transform(message, controller) {
            if (head < sizes.length) {
                bufferedBytes -= sizes[head];
                sizes[head++] = undefined;
                if (head === sizes.length) { sizes = []; head = 0; }
                else if (head >= 1024 && head * 2 >= sizes.length) { sizes = sizes.slice(head); head = 0; }
            }
            controller.enqueue(message);
        },
    }));
    return { readable, writable: stream.writable, get bufferedBytes() { return bufferedBytes; } };
}

function readonlyHostRequest(command, tools) {
    if (typeof command !== 'string') return null;
    let request;
    try { request = hostActionRequest(command); } catch (_) { return null; }
    if (!request || !READ_ONLY_HOST_ACTIONS.has(request.name) || !tools.some(tool => tool.function?.name === request.name)) return null;
    if (['read_file', 'read_script', 'list_directory'].includes(request.name)) {
        const args = request.arguments;
        const fields = request.name === 'list_directory' ? ['path'] : ['path', 'offset', 'limit'];
        if (Object.keys(args).some(key => !fields.includes(key)) || typeof args.path !== 'string' || !args.path || args.path.length > 4096 || args.path.includes('\0')) return null;
        if (args.offset !== undefined && (!Number.isSafeInteger(args.offset) || args.offset < 1 || args.offset > 2147483647)) return null;
        if (args.limit !== undefined && (!Number.isSafeInteger(args.limit) || args.limit < 1 || args.limit > 500)) return null;
    }
    return request;
}

async function runAcpSession(entry, cwd, env, setChild, api) {
    const trace = createTraceLog(env.GODOT_ACP_LOG_DIRECTORY || path.join(__dirname, 'logs'));
    let requestNumber = 0;
    const counts = { read_count: 0, write_count: 0, permission_count: 0, rpc_count: 0 };
    const record = (event, details = {}) => trace.write(event, { request: requestNumber, ...details });
    const versionAt = file => { try { return JSON.parse(fs.readFileSync(file, 'utf8')).version; } catch (_) { return undefined; } };
    record('bridge_start', { node_version: process.version, cli_version: versionAt(path.join(path.dirname(entry), '..', 'package.json')), sdk_version: versionAt(path.join(__dirname, 'node_modules/@agentclientprotocol/sdk/package.json')) });
    const acp = await import('@agentclientprotocol/sdk');
    const fileError = message => new acp.RequestError(-32000, message);
    const toolKinds = createToolKindState();
    const fileText = createFileTextView();
    let child;
    let connection;
    let sessionId;
    let agentId;
    let currentModel;
    let capabilityBinding;
    let defaultModel;
    let imageSupported = false;
    let outputBytes = 0;
    let active;
    let timer;
    let flushTimer;
    let progressTimer;
    let stderrBytes = 0;
    let stderrTail = '';
    let stopped = false;
    let resetting = false;
    const closedChildren = new WeakSet();
    const diagnostics = () => ({ ...active?.budget.snapshot(), stdout_bytes: outputBytes, stderr_bytes: stderrBytes, stage: active?.activity || 'connecting' });
    const heartbeat = setInterval(() => {
        if (active && !stopped) record('wait_snapshot', { ...diagnostics(), ...counts, active: true, yielded: active.yielded, pending_count: pending.size, content_bytes: active.contentBytes });
    }, 15000);
    heartbeat.unref();
    const flushProgress = () => {
        clearTimeout(progressTimer);
        progressTimer = undefined;
        if (!active || active.yielded || stopped) return;
        do {
            let length = Math.min(active.delta.length, 8192);
            if (length < active.delta.length && /[\uD800-\uDBFF]/.test(active.delta[length - 1])) length--;
            const content_delta = active.delta.slice(0, length);
            active.delta = active.delta.slice(length);
            process.stdout.write(JSON.stringify({ event: 'progress', activity: active.activity, content_delta, diagnostics: api.safeDiagnostics(diagnostics()) }) + '\n');
        } while (active.delta.length);
    };
    const reportProgress = activity => {
        if (!active || active.yielded || stopped) return;
        active.activity = activity;
        active.budget.touch();
        armTimeout(false);
        if (!progressTimer) progressTimer = setTimeout(flushProgress, 200);
    };
    const pending = new Map();
    const terminalResults = [];
    const flushTerminalResults = () => {
        if (!active || stopped || active.yielded) return;
        for (const result of terminalResults.splice(0)) process.stdout.write(JSON.stringify({ event: 'command_result', result }) + '\n');
    };
    const rejectPending = () => {
        for (const item of pending.values()) item.reject(new Error('Godot session closed; operation was not completed'));
        pending.clear();
        toolKinds.clear();
    };
    const fail = error => {
        if (stopped) return;
        flushProgress();
        stopped = true;
        clearTimeout(timer);
        clearTimeout(flushTimer);
        clearTimeout(progressTimer);
        clearInterval(heartbeat);
        const code = error.bridgeCode || api.classifyDiagnostics(String(error.message) + '\n' + stderrTail);
        const failure = api.bridgeError(code);
        const hint = api.classifyDiagnostics(stderrTail);
        failure.diagnostics = { ...diagnostics(), timeout_kind: error.timeoutKind, ...(hint !== 'PROCESS_EXIT' ? { failure_hint: hint } : {}) };
        record('request_failed', { ...diagnostics(), ...counts, code, timeout_kind: error.timeoutKind, failure_hint: hint, pending_count: pending.size, content_bytes: active?.contentBytes, yielded: active?.yielded });
        process.stdout.write(JSON.stringify({ error: api.serializeError(failure) }) + '\n');
        rejectPending();
        terminals.close().catch(() => {
            record('terminal_cleanup_failed', { success: false });
            process.stdout.write(JSON.stringify({ error: api.serializeError(api.bridgeError('PROCESS_BOUNDARY_FAILED')) }) + '\n');
        });
        if (child) child.kill();
        process.exitCode = 1;
        process.stdin.destroy();
    };
    const armTimeout = (resume = true) => {
        clearTimeout(timer);
        if (terminals.running) {
            active.budget.pause();
            if (!active.yielded) {
                active.activity = 'executing';
                flushProgress();
                timer = setTimeout(() => armTimeout(false), 15000);
            }
            return;
        }
        if (resume) active.budget.resume();
        const state = active.budget.snapshot();
        if (state.expired) {
            const error = api.bridgeError('TIMEOUT');
            error.timeoutKind = state.expired;
            fail(error);
            return;
        }
        timer = setTimeout(() => armTimeout(false), state.remaining_ms);
    };
    const emit = calls => {
        flushProgress();
        clearTimeout(timer);
        active.budget.pause();
        record(calls.length ? 'host_tools_dispatched' : 'host_completion_sent', { ...diagnostics(), pending_count: pending.size, content_bytes: active.contentBytes });
        const message = { role: 'assistant', content: active.content };
        active.content = '';
        if (calls.length) message.tool_calls = calls;
        const transport = { protocol: 'acp-native-files', mode: active.initial ? 'bootstrap' : 'incremental', session_id: sessionId, agent_id: agentId, transmitted_bytes: active.transmittedBytes, message_count: active.input.messages.length };
        process.stdout.write(JSON.stringify({ choices: [{ message, finish_reason: calls.length ? 'tool_calls' : 'stop' }], transport }) + '\n');
        active.initial = false;
        active.yielded = calls.length > 0;
    };
    const flushTools = () => {
        flushTimer = undefined;
        if (stopped || !active || active.yielded || !pending.size) return;
        const calls = [...pending].filter(([, item]) => !item.sent).map(([id, item]) => {
            item.sent = true;
            return { id, type: 'function', function: { name: item.name, arguments: JSON.stringify(item.arguments) } };
        });
        if (calls.length) emit(calls);
    };
    const fileRequest = async (params, writing) => {
        const name = writing ? 'write_file' : 'read_file';
        counts[writing ? 'write_count' : 'read_count']++;
        record('file_callback_received', { operation: name, session_match: params.sessionId === sessionId, active: !!active, stopped, line: params.line, limit: params.limit, ...counts });
        const deny = (reason, message) => { record('file_callback_denied', { operation: name, reason }); return Promise.reject(fileError(message)); };
        if (!active || stopped || params.sessionId !== sessionId) return deny('invalid_session', 'Invalid or inactive Godot file session');
        if (writing && !active.input.tool_context.writes_allowed) return deny('unavailable', 'This Godot review session cannot write files');
        const reason = active.input.tool_context.unavailable_reason;
        if (reason !== 'none') {
            return deny(reason, api.bridgeError(reason === 'round_limit_reached' ? 'TOOL_ROUND_LIMIT_REACHED' : 'TOOLS_DISABLED').message);
        }
        if (!active.input.available_tools.some(tool => tool.function?.name === name) || pending.size >= 8 || [...pending.values()].some(item => ['build_engine', 'restart_engine', 'rollback_engine', 'complete_delivery', 'delegate_review'].includes(item.name))) return deny('unavailable', 'Godot file operation is not available during an editor self-update');
        let args;
        try {
            args = fileArguments(params, writing);
            if (writing) args = fileText.write(args);
        } catch (_) { return deny('invalid_arguments', 'Invalid Godot file request arguments; use an absolute path, at most 500 lines per range read and at most 256 KiB per complete write including original newline encoding'); }
        reportProgress('tool_pending');
        if (stopped) {
            return Promise.reject(fileError('Godot model waiting budget exhausted'));
        }
        return new Promise((resolve, reject) => {
            const id = 'acp_file_' + randomUUID();
            pending.set(id, { resolve, reject, name, arguments: args, sent: false });
            record('host_file_queued', { operation: name, call_hash: createHash('sha256').update(id).digest('hex').slice(0, 16), pending_count: pending.size });
            if (!flushTimer && !active.yielded) flushTimer = setTimeout(flushTools, 10);
        });
    };
    const validateTerminal = params => {
        if (!active || stopped || params.sessionId !== sessionId || active.input.tool_context.unavailable_reason !== 'none') throw fileError('Invalid, inactive or disabled Godot terminal session');
        const context = active.input.tool_context;
        if (context.consultation_only || !context.execution_allowed) {
            if (params.command !== undefined) {
                const request = readonlyHostRequest(params.command, active.input.available_tools);
                if (!request) throw fileError('This Godot review session only accepts advertised read-only host requests');
            }
        } else if (!active.input.available_tools.some(tool => tool.function?.name === 'run_command')) throw fileError('Godot command execution is unavailable');
        if (params.command !== undefined) {
            const name = hostActionName(params.command);
            if (name && !active.input.available_tools.some(tool => tool.function?.name === name)) throw fileError('Godot host action is unavailable. Nothing was executed.');
        }
    };
    const hostAction = (name, actionArgs = {}, command = '') => {
        if (!active || !active.input.available_tools.some(tool => tool.function?.name === name) || active.input.tool_context.consultation_only && !READ_ONLY_HOST_ACTIONS.has(name)) return Promise.reject(fileError('Godot host action is not permitted in this session'));
        if (pending.size || terminals.running) return Promise.reject(fileError('Godot host actions must run alone, after all other tools and terminals finish'));
        reportProgress('tool_pending');
        return new Promise((resolve, reject) => {
            const id = 'acp_host_' + randomUUID();
            pending.set(id, { resolve, reject, name, arguments: actionArgs, sent: false, hostAction: true });
            record('host_action_queued', { operation: name, pending_count: pending.size });
            if (!flushTimer && !active.yielded) flushTimer = setTimeout(flushTools, 10);
        });
    };
    const terminals = createTerminals({
        env,
        validate: validateTerminal,
        hostAction,
        approve: args => {
            if (!active?.input.tool_context.execution_allowed || active.input.tool_context.consultation_only) return Promise.reject(fileError('This Godot review session cannot execute commands'));
            if (pending.size >= 8 || [...pending.values()].some(item => ['build_engine', 'restart_engine', 'rollback_engine', 'complete_delivery', 'delegate_review'].includes(item.name))) return Promise.reject(fileError('Godot command capacity exceeded or editor self-update in progress'));
            reportProgress('tool_pending');
            return new Promise((resolve, reject) => {
                const id = 'acp_command_' + randomUUID();
                const argumentsForHost = active?.input.workspace.provenance_guard_required ? { ...args, _godot_provenance_guard: 1 } : args;
                pending.set(id, { resolve, reject, name: 'run_command', arguments: argumentsForHost, sent: false });
                record('host_command_queued', { operation: 'run_command', pending_count: pending.size });
                if (!flushTimer && !active.yielded) flushTimer = setTimeout(flushTools, 10);
            });
        },
        stateChanged: () => { if (active && !stopped && !active.yielded) armTimeout(); },
        finished: result => {
            record('terminal_completed', { exit_code: result.exit_status.exitCode, success: result.exit_status.exitCode === 0 });
            if (active && !stopped) { terminalResults.push(result); flushTerminalResults(); }
        },
    });
    const initialize = async input => {
        agentId = input.agent_id || 'default';
        const instance = spawn(process.execPath, [entry, ...api.sessionArguments(input.model, input.instructions || '', input.tool_context.permission_enabled, input.tool_context.consultation_only)], { cwd: input.workspace.workspace_root || input.workspace.project_root, env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
        child = instance;
        const belongs = () => child === instance && !resetting && !stopped;
        const failInstance = error => { if (belongs()) fail(error); };
        const scoped = callback => params => {
            if (!belongs()) throw fileError('Superseded Godot native session');
            return callback(params);
        };
        setChild(child);
        record('cli_spawned', { child_pid: child.pid });
        child.on('error', () => failInstance(api.bridgeError('PROCESS_START')));
        child.on('close', code => { closedChildren.add(instance); record('cli_closed', { exit_code: code, stopped }); if (!stopped) failInstance(api.bridgeError('PROCESS_EXIT')); });
        child.stderr.on('data', bytes => {
            if (!belongs()) return;
            stderrBytes += bytes.byteLength;
            stderrTail = (stderrTail + bytes.toString('utf8')).slice(-16384);
        });
        const observe = (event, details) => { counts.rpc_count++; record(event, details); };
        const outgoing = rpcTrace('outgoing', observe, { onLimit: failInstance });
        outgoing.readable.pipeTo(Writable.toWeb(child.stdin)).catch(error => { record('stdin_pipe_closed', { stopped }); if (!stopped) failInstance(error.bridgeCode ? error : api.bridgeError('PROCESS_EXIT')); });
        // Total protocol traffic is diagnostic only. A long task may safely
        // process far more than 16 MiB without retaining it in memory.
        const stream = boundedRpcStream(acp, outgoing.writable, Readable.toWeb(child.stdout), observe, failInstance, size => { if (child === instance) outputBytes += size; });
        connection = new acp.ClientSideConnection(() => ({
            readTextFile: scoped(params => fileRequest(params, false)),
            writeTextFile: scoped(params => fileRequest(params, true)),
            createTerminal: scoped(params => terminals.create(params, active?.input.workspace)),
            terminalOutput: scoped(params => terminals.output(params)),
            waitForTerminalExit: scoped(params => terminals.wait(params)),
            killTerminal: scoped(params => terminals.kill(params)),
            releaseTerminal: scoped(params => terminals.release(params)),
            requestPermission: async params => {
                if (!belongs()) return { outcome: { outcome: 'cancelled' } };
                const allow = params.options.find(option => option.kind === 'allow_once');
                const reject = params.options.find(option => option.kind === 'reject_once');
                const resolved = toolKinds.resolve(params.sessionId, params.toolCall);
                const readonlyRequest = active?.input.tool_context.consultation_only && readonlyHostRequest(params.toolCall?.rawInput?.command, active.input.available_tools);
                const fileKind = !!readonlyRequest || ['read', 'search'].includes(resolved.kind) || resolved.kind === 'edit' && active?.input.tool_context.writes_allowed && !active.input.tool_context.consultation_only || resolved.kind === 'execute' && active?.input.tool_context.execution_allowed && !active.input.tool_context.consultation_only && active.input.available_tools.some(tool => tool.function?.name === 'run_command');
                counts.permission_count++;
                const allowed = params.sessionId === sessionId && active && !stopped && active.input.tool_context.unavailable_reason === 'none' && fileKind && allow;
                record('permission_decided', { ...counts, ...resolved, session_match: params.sessionId === sessionId, active: !!active, yielded: active?.yielded, call_hash: typeof params.toolCall?.toolCallId === 'string' ? createHash('sha256').update(params.toolCall.toolCallId).digest('hex').slice(0, 16) : undefined, decision: allowed ? 'allow_once' : reject ? 'reject_once' : 'cancelled', permission_enabled: active?.input.tool_context.permission_enabled, reason: !active || stopped || params.sessionId !== sessionId ? 'invalid_session' : active.input.tool_context.unavailable_reason !== 'none' ? active.input.tool_context.unavailable_reason : fileKind && allow ? 'none' : 'unavailable' });
                if (allowed) return { outcome: { outcome: 'selected', optionId: allow.optionId } };
                return reject ? { outcome: { outcome: 'selected', optionId: reject.optionId } } : { outcome: { outcome: 'cancelled' } };
            },
            sessionUpdate: async notification => {
                if (!belongs()) return;
                record('session_notification', { update: notification.update?.sessionUpdate, native_tool: ['Glob', 'Grep'].includes(notification.update?.title) ? notification.update.title : undefined, kind: notification.update?.kind || 'missing', status: notification.update?.status || 'missing', call_hash: typeof notification.update?.toolCallId === 'string' ? createHash('sha256').update(notification.update.toolCallId).digest('hex').slice(0, 16) : undefined, session_match: notification.sessionId === sessionId, active: !!active, yielded: active?.yielded, stopped, text_bytes: notification.update?.content?.type === 'text' && typeof notification.update.content.text === 'string' ? Buffer.byteLength(notification.update.content.text) : 0 });
                if (notification.sessionId !== sessionId || !active || stopped) return;
                const failure = toolFailure(notification.update);
                if (failure) {
                    record('native_tool_failed', { ...failure, ...toolKinds.resolve(notification.sessionId, { toolCallId: notification.update.toolCallId }), call_hash: createHash('sha256').update(String(notification.update.toolCallId)).digest('hex').slice(0, 16) });
                    if (failure.failure_cause !== 'unknown') active.editMatchFailed = true;
                }
                toolKinds.update(notification);
                if (active.yielded) return;
                const progress = progressUpdate(notification.update);
                if (!progress) return;
                if (progress.content_delta) {
                    active.contentBytes += Buffer.byteLength(progress.content_delta);
                    if (active.contentBytes > 2 * 1024 * 1024) { fail(api.bridgeError('OUTPUT_LIMIT')); return; }
                    active.content += progress.content_delta;
                    active.delta += progress.content_delta;
                }
                reportProgress(progress.activity);
            },
        }), stream);
        record('initialize_started');
        const handshake = await connection.initialize({ protocolVersion: acp.PROTOCOL_VERSION, clientCapabilities: { fs: { readTextFile: true, writeTextFile: input.tool_context.writes_allowed }, terminal: true }, clientInfo: { name: 'godot-editor', version: '1.0.0' } });
        if (handshake.protocolVersion !== acp.PROTOCOL_VERSION || !handshake.agentCapabilities?.promptCapabilities?.embeddedContext) throw api.bridgeError('INVALID_RESPONSE');
        imageSupported = handshake.agentCapabilities?.promptCapabilities?.image === true;
        record('initialize_completed', { protocol_version: handshake.protocolVersion, image_supported: imageSupported, embedded_context: handshake.agentCapabilities?.promptCapabilities?.embeddedContext === true });
        record('session_new_started');
        const session = await connection.newSession({ cwd: input.workspace.workspace_root || input.workspace.project_root, mcpServers: [] });
        if (typeof session.sessionId !== 'string' || !session.sessionId) throw api.bridgeError('INVALID_RESPONSE');
        sessionId = session.sessionId;
        record('session_new_completed');
        defaultModel = session.models?.currentModelId;
        currentModel = input.model;
        if (input.model && defaultModel && input.model !== defaultModel) await connection.request('session/set_model', { sessionId, modelId: input.model });
    };
    const submit = async input => {
        input = api.validateInput(input);
        const capabilities = JSON.stringify([input.tool_context.consultation_only, input.tool_context.writes_allowed, input.tool_context.execution_allowed]);
        if (capabilityBinding !== undefined && capabilityBinding !== capabilities) throw api.bridgeError('INVALID_REQUEST');
        capabilityBinding = capabilities;
        input.workspace = workspacePaths(input, cwd);
        if (agentId !== undefined && (input.agent_id || 'default') !== agentId) throw api.bridgeError('INVALID_REQUEST');
        if (active) {
            if (!active.yielded || !pending.size) throw api.bridgeError('INVALID_REQUEST');
            const results = input.messages.filter(message => message.role === 'tool');
            const sent = [...pending].filter(([, item]) => item.sent);
            if (results.length !== sent.length || new Set(results.map(result => result.tool_call_id)).size !== results.length || results.some(result => !pending.get(result.tool_call_id)?.sent || typeof result.content !== 'string') || input.messages.some(message => message.role === 'user') || input.tool_context.tool_rounds !== active.input.tool_context.tool_rounds + 1) throw api.bridgeError('INVALID_REQUEST');
            active.input = input;
            active.yielded = false;
            active.transmittedBytes = 0;
            flushTerminalResults();
            armTimeout();
            for (const result of results) {
                const item = pending.get(result.tool_call_id);
                pending.delete(result.tool_call_id);
                record('host_file_result', { operation: item.name, success: result.godot_file_success === true, content_bytes: Buffer.byteLength(result.content), call_hash: createHash('sha256').update(result.tool_call_id).digest('hex').slice(0, 16), pending_count: pending.size });
                if (item.hostAction && ['read_file', 'read_script', 'list_scripts', 'list_directory'].includes(item.name)) {
                    if (item.name === 'read_file' || item.name === 'read_script') {
                        item.resolve(result.godot_file_success === true ? { ok: true, content: result.content } : { ok: false, error: 'Godot did not confirm file read success' });
                    } else {
                        try {
                            const listing = JSON.parse(result.content);
                            if (!listing || !Array.isArray(listing[item.name === 'list_scripts' ? 'paths' : 'entries'])) throw new Error('Invalid host listing');
                            item.resolve({ ok: true, result: listing });
                        } catch (_) { item.resolve({ ok: false, error: 'Godot did not confirm a valid directory listing' }); }
                    }
                    continue;
                }
                if (['read_logs', 'get_parent_context', 'get_editor_state', 'editor_action', 'route_engine_message', 'build_engine', 'restart_engine', 'rollback_engine', 'complete_delivery', 'delegate_review'].includes(item.name)) {
                    try {
                        const actionResult = JSON.parse(result.content);
                        if (!actionResult || typeof actionResult.ok !== 'boolean') throw new Error('Invalid host action result');
                        item.resolve(actionResult);
                    } catch (_) { item.reject(fileError('Godot did not confirm a valid host action result')); }
                    continue;
                }
                if (result.godot_file_success !== true) {
                    item.reject(fileError(result.godot_file_success === false ? result.content : 'Godot did not confirm file operation success'));
                    continue;
                }
                try {
                    if (item.name === 'read_file') {
                        const raw = readResponse(result.content, item.arguments);
                        record('file_text_view', { ...fileTextFormat(raw.content), operation: item.name, content_bytes: Buffer.byteLength(raw.content) });
                        item.resolve(fileText.read(result.content, item.arguments));
                    } else if (item.name === 'run_command') {
                        const approval = JSON.parse(result.content);
                        if (approval?.approved !== true) throw new Error('Command was not approved');
                        item.resolve(approval);
                    } else {
                        fileText.saved(item.arguments);
                        record('file_text_saved', { ...fileTextFormat(item.arguments.content), operation: item.name });
                        item.resolve({});
                    }
                } catch (_) { item.reject(fileError('Godot returned an incomplete or invalid file response; use a narrower read range')); }
            }
            if (pending.size) flushTimer = setTimeout(flushTools, 10);
            return;
        }
        requestNumber++;
        for (const key of Object.keys(counts)) counts[key] = 0;
        record('user_request_received', { message_count: input.messages.length, permission_enabled: input.tool_context.permission_enabled, read_enabled: input.available_tools.some(tool => tool.function?.name === 'read_file'), write_enabled: input.available_tools.some(tool => tool.function?.name === 'write_file') });
        outputBytes = stderrBytes = 0;
        stderrTail = '';
        active = { input, initial: !connection, content: '', delta: '', contentBytes: 0, activity: connection ? 'waiting' : 'connecting', budget: createWaitBudget(), yielded: false, transmittedBytes: 0 };
        armTimeout();
        flushProgress();
        if (!connection) await initialize(input);
        else if (input.model !== currentModel) {
            const modelId = input.model || defaultModel;
            if (!modelId) throw api.bridgeError('MODEL_UNAVAILABLE');
            await connection.request('session/set_model', { sessionId, modelId });
            currentModel = input.model;
        }
        let prompt;
        try { prompt = promptBlocks(input, active.initial, imageSupported); } catch (error) { throw api.bridgeError(error.bridgeCode || 'INVALID_REQUEST'); }
        active.transmittedBytes = Buffer.byteLength(JSON.stringify(prompt));
        if (stopped) return;
        toolKinds.begin(sessionId);
        reportProgress('waiting');
        record('model_prompt_sent', { prompt_bytes: active.transmittedBytes, image_count: prompt.filter(block => block.type === 'image').length, text_bytes: prompt.filter(block => block.type === 'text').reduce((sum, block) => sum + Buffer.byteLength(block.text), 0) });
        const submitted = active;
        connection.prompt({ sessionId, prompt }).then(async result => {
            if (active !== submitted || resetting) return;
            record('model_prompt_completed', { stop_reason: result.stopReason, stopped, pending_count: pending.size });
            if (stopped) return;
            if (pending.size || active.yielded) throw api.bridgeError('RESULT_FAILED');
            if (result.stopReason !== 'end_turn') {
                const reason = active.input.tool_context.unavailable_reason;
                throw api.bridgeError(reason === 'round_limit_reached' ? 'TOOL_ROUND_LIMIT_REACHED' : reason === 'permission_disabled' ? 'TOOLS_DISABLED' : active.editMatchFailed ? 'EDIT_MATCH_FAILED' : result.stopReason === 'cancelled' ? 'CLI_CANCELLED' : 'RESULT_FAILED');
            }
            await terminals.reset();
            if (stopped || active !== submitted || resetting) return;
            emit([]);
            toolKinds.clear();
            active = undefined;
        }).catch(error => { if (active === submitted && !resetting) fail(error); });
    };
    const resetSession = async () => {
        // Reset is host-owned and only valid after a tool yield or completion.
        // Close native terminals before replacing the model process; killing
        // only the bridge would leave detached command groups alive on Unix.
        if (active && !active.yielded) throw api.bridgeError('INVALID_REQUEST');
        resetting = true;
        clearTimeout(timer);
        clearTimeout(flushTimer);
        clearTimeout(progressTimer);
        flushTimer = progressTimer = undefined;
        const previousChild = child;
        const previousConnection = connection;
        const previousSession = sessionId;
        active = undefined;
        child = connection = sessionId = undefined;
        if (previousConnection && previousSession) previousConnection.cancel({ sessionId: previousSession }).catch(() => {});
        rejectPending();
        try {
            await terminals.reset();
            terminalResults.length = 0;
            fileText.clear();
            if (previousChild && !closedChildren.has(previousChild)) {
                const exited = new Promise(resolve => previousChild.once('close', resolve));
                previousChild.kill();
                const force = setTimeout(() => previousChild.kill('SIGKILL'), 2000);
                let deadline;
                const failed = new Promise((_, reject) => { deadline = setTimeout(() => reject(api.bridgeError('PROCESS_BOUNDARY_FAILED')), 4000); });
                // An exit code can become visible before pipes have closed.
                // A new session requires the old process's actual close receipt.
                try { await Promise.race([exited, failed]); } finally { clearTimeout(force); clearTimeout(deadline); }
            }
            record('session_reset_completed', { success: true });
        } catch (error) {
            if (previousChild && previousChild.exitCode === null) previousChild.kill('SIGKILL');
            throw error;
        } finally {
            resetting = false;
        }
    };
    const lines = require('node:readline').createInterface({ input: process.stdin, crlfDelay: Infinity });
    try {
        for await (const line of lines) {
            if (stopped) break;
            if (Buffer.byteLength(line) > 8192) throw api.bridgeError('INVALID_REQUEST');
            const request = JSON.parse(line);
            if (typeof request.path !== 'string' || !path.isAbsolute(request.path) || request.reset !== undefined && typeof request.reset !== 'boolean') throw api.bridgeError('INVALID_REQUEST');
            if (fs.statSync(request.path).size > 1024 * 1024) throw api.bridgeError('REQUEST_SIZE_LIMIT');
            const input = api.validateInput(parseHostJson(fs.readFileSync(request.path, 'utf8')));
            if (request.reset) {
                if (agentId !== undefined && (input.agent_id || 'default') !== agentId) throw api.bridgeError('INVALID_REQUEST');
                await resetSession();
            }
            await submit(input);
        }
    } catch (error) {
        fail(error);
    } finally {
        stopped = true;
        clearTimeout(timer);
        clearTimeout(flushTimer);
        clearTimeout(progressTimer);
        clearInterval(heartbeat);
        record('bridge_closed', { ...diagnostics(), ...counts, pending_count: pending.size });
        if (connection && sessionId) connection.cancel({ sessionId }).catch(() => {});
        rejectPending();
        await terminals.close();
        if (child) child.kill();
    }
}

module.exports = { workspacePaths, runAcpSession, promptBlocks, fileArguments, parseHostJson, readResponse, createWaitBudget, progressUpdate, createToolKindState, createFileTextView, fileTextFormat, toolFailure, createTraceLog, rpcTrace, boundedRpcStream };
