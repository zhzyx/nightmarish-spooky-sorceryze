// File notifications only invalidate the board. Python verifies every receipt against GitHub.
import {watch} from 'node:fs';
import {normalize, sep} from 'node:path';

const directory = process.argv[2];
const sourceEvents = process.argv.includes("--source-events");
const pending = new Set();
let flush;
const watcher = watch(directory, {recursive: true}, (_event, filename) => {
    if (!filename) return;
    const parts = normalize(filename).split(sep);
    const [area, group, name] = parts;
    if (area === 'daqian-direct' && /^daqian-direct-[0-9a-f]{20}$/.test(group)
        && /^(route-[0-9a-f]{64}|start|state)\.json$/.test(name)) {
        // Old editors expect a bare key. New editors can reread only the affected source.
        pending.add(sourceEvents && (name === "start.json" || name === "state.json") ? "source:" + group : group);
    }
    if (area === 'codex-dispatch' && group === 'sources') {
        const match = /^([0-9a-f]{64})-[0-9a-f]{64}\.(worker|terminal)\.json$/.exec(name);
        if (match) pending.add(match[1]);
    }
    if (!pending.size || flush) return;
    flush = setTimeout(() => {
        for (const key of pending) process.stdout.write(key + '\n');
        pending.clear();
        flush = null;
    }, 120);
});
process.stdout.write('ready\n');
process.stdin.resume();
process.stdin.on('end', () => watcher.close());
