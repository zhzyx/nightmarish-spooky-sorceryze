'use strict';
class ContentPreview {
    constructor() { this.prefix = ''; this.text = ''; this.escape = ''; this.started = false; this.done = false; this.high = ''; this.last = 0; }
    feed(chunk) {
        if (this.done) return '';
        for (const c of chunk) {
            if (!this.started) {
                this.prefix += c;
                if (/^\s*\{\s*"content"\s*:\s*"$/.test(this.prefix)) this.started = true;
                else if (this.prefix.length > 256) { this.done = true; break; }
            } else if (this.escape) {
                this.escape += c;
                if (this.escape.length === 2 && c !== 'u' || this.escape.length === 6) {
                    let decoded;
                    try { decoded = JSON.parse('"' + this.escape + '"'); } catch { this.done = true; this.text = ''; break; }
                    this.add(decoded); this.escape = '';
                }
            } else if (c === '"') { this.done = true; break; }
            else if (c === '\\') this.escape = c;
            else if (c.charCodeAt(0) < 32) { this.done = true; break; }
            else this.add(c);
            if (this.text.length >= 2048) { this.done = true; break; }
        }
        const now = Date.now();
        if (this.text && (!this.last || now - this.last >= 100 || this.done)) { this.last = now; return this.text; }
        return '';
    }
    add(c) {
        if (c.length === 1 && /[\uD800-\uDBFF]/.test(c)) { this.high = c; return; }
        this.text += this.high + c; this.high = '';
        this.text = this.text.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '');
    }
}
function contentPreview(raw) { return new ContentPreview().feed(raw); }
module.exports = { ContentPreview, contentPreview };
