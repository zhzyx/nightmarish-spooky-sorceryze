import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import test from "node:test";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("../../customizations/components/godot-host/daqian/watch_progress.mjs", import.meta.url));
for (const tagged of [true, false]) {
    test(`watcher source notification negotiation (${tagged ? "tagged" : "legacy"})`, { timeout: 8000 }, async (t) => {
        const dir = await mkdtemp(join(tmpdir(), "daqian-watch-"));
        const keys = ["a", "b", "c"].map(letter => "daqian-direct-" + letter.repeat(20));
        for (const key of keys) await mkdir(join(dir, "daqian-direct", key), { recursive: true });
        const watcher = spawn(process.execPath, [script, dir, ...(tagged ? ["--source-events"] : [])],
            { stdio: ["pipe", "pipe", "inherit"], windowsHide: true });
        const lines = createInterface({ input: watcher.stdout })[Symbol.asyncIterator]();
        const stopped = new Promise(resolve => watcher.once("close", resolve));
        t.after(async () => {
            watcher.kill();
            await stopped;
            await rm(dir, { recursive: true, force: true });
        });
        assert.equal((await lines.next()).value, "ready");
        for (const [i, name] of [`route-${"a".repeat(64)}.json`, "start.json", "state.json"].entries()) {
            await writeFile(join(dir, "daqian-direct", keys[i], name), "{}");
            assert.equal((await lines.next()).value, (tagged && i > 0 ? "source:" : "") + keys[i]);
        }
    });
}
