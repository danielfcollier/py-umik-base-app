const TimeGraph = {
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    buffer: [],
    maxEntries: 600,
    defaultWindowSeconds: 30,
    padding: { top: 8, right: 50, bottom: 20, left: 50 },
    calibrated: false,
    splMin: -100,
    splMax: 0,
    snrMin: 0,
    snrMax: 60,

    init(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
    },

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.width = rect.width;
        this.height = rect.height;
    },

    push(dbSpl, snrAvg, calibrated) {
        if (calibrated !== this.calibrated) {
            this.calibrated = calibrated;
            this.splMin = calibrated ? 20 : -100;
            this.splMax = calibrated ? 120 : 0;
            this.buffer = [];
        }
        const now = performance.now() / 1000;
        this.buffer.push({ t: now, spl: dbSpl, snr: snrAvg });
        while (this.buffer.length > this.maxEntries) this.buffer.shift();
    },

    splToY(db) {
        const p = this.padding;
        const plotH = this.height - p.top - p.bottom;
        return p.top + plotH * (1.0 - (db - this.splMin) / (this.splMax - this.splMin));
    },

    snrToY(snr) {
        const p = this.padding;
        const plotH = this.height - p.top - p.bottom;
        return p.top + plotH * (1.0 - (snr - this.snrMin) / (this.snrMax - this.snrMin));
    },

    timeToX(t, tMin, tMax) {
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        if (tMax <= tMin) return p.left;
        return p.left + plotW * (t - tMin) / (tMax - tMin);
    },

    draw() {
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const p = this.padding;

        ctx.fillStyle = '#0d0d1a';
        ctx.fillRect(0, 0, w, h);

        const plotW = w - p.left - p.right;
        const plotH = h - p.top - p.bottom;
        if (plotW <= 0 || plotH <= 0) return;

        ctx.strokeStyle = '#222';
        ctx.lineWidth = 0.5;
        for (let db = this.splMin; db <= this.splMax; db += 20) {
            const y = this.splToY(db);
            ctx.beginPath();
            ctx.moveTo(p.left, y);
            ctx.lineTo(w - p.right, y);
            ctx.stroke();
        }

        ctx.fillStyle = '#2ecc71';
        ctx.font = '9px monospace';
        ctx.textAlign = 'right';
        for (let db = this.splMin; db <= this.splMax; db += 40) {
            ctx.fillText(db.toString(), p.left - 4, this.splToY(db) + 3);
        }

        ctx.fillStyle = '#f1c40f';
        ctx.textAlign = 'left';
        for (let s = this.snrMin; s <= this.snrMax; s += 20) {
            ctx.fillText(s.toString(), w - p.right + 4, this.snrToY(s) + 3);
        }

        if (this.buffer.length < 2) return;

        const tMax = this.buffer[this.buffer.length - 1].t;
        const zoom = (typeof Waterfall !== 'undefined' && Waterfall.timeZoom) ? Waterfall.timeZoom : 1.0;
        const windowSeconds = this.defaultWindowSeconds / zoom;
        const tMin = tMax - windowSeconds;

        ctx.strokeStyle = '#2ecc71';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        let started = false;
        for (const pt of this.buffer) {
            if (pt.t < tMin) continue;
            const x = this.timeToX(pt.t, tMin, tMax);
            const y = this.splToY(pt.spl);
            if (!started) { ctx.moveTo(x, y); started = true; }
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        ctx.strokeStyle = '#f1c40f';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        started = false;
        for (const pt of this.buffer) {
            if (pt.t < tMin) continue;
            const x = this.timeToX(pt.t, tMin, tMax);
            const y = this.snrToY(pt.snr);
            if (!started) { ctx.moveTo(x, y); started = true; }
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        const secAgo = [0, 10, 20, 30];
        ctx.fillStyle = '#555';
        ctx.textAlign = 'center';
        ctx.font = '8px monospace';
        for (const s of secAgo) {
            const t = tMax - s;
            const x = this.timeToX(t, tMin, tMax);
            if (x >= p.left && x <= w - p.right) {
                ctx.fillText(s === 0 ? 'now' : '-' + s + 's', x, h - p.bottom + 14);
            }
        }
        
        if (zoom > 1.05) {
            ctx.fillStyle = '#444';
            ctx.font = '8px monospace';
            ctx.textAlign = 'left';
            ctx.fillText(zoom.toFixed(1) + 'x', w - p.right + 4, p.top + 10);
        }
    }
};
