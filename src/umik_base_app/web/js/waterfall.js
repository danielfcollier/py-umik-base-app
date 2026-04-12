const Waterfall = {
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    freqMin: 20,
    freqMax: 22000,
    dbMin: -100,
    dbMax: 0,
    padding: { top: 10, right: 10, bottom: 30, left: 50 },
    freqMap: null,
    lastFreqs: null,

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
        this.freqMap = null;
        this.ctx.fillStyle = '#0d0d1a';
        this.ctx.fillRect(0, 0, this.width, this.height);
    },

    viridis(t) {
        t = Math.max(0, Math.min(1, t));
        const r = Math.round(255 * Math.min(1, Math.max(0, -0.27 + 4.15 * t - 5.1 * t * t + 2.6 * t * t * t)));
        const g = Math.round(255 * Math.min(1, Math.max(0, -0.005 + 0.48 * t + 2.35 * t * t - 2.9 * t * t * t)));
        const b = Math.round(255 * Math.min(1, Math.max(0, 0.33 + 1.4 * t - 4.8 * t * t + 5.3 * t * t * t)));
        return `rgb(${r},${g},${b})`;
    },

    buildFreqMap(freqs) {
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const logMin = Math.log10(this.freqMin);
        const logMax = Math.log10(this.freqMax);
        const map = new Int32Array(plotW);
        for (let px = 0; px < plotW; px++) {
            const logFreq = logMin + (px / plotW) * (logMax - logMin);
            const targetFreq = Math.pow(10, logFreq);
            let idx = 0;
            for (let i = 1; i < freqs.length; i++) {
                if (freqs[i] >= targetFreq) { idx = i; break; }
                idx = i;
            }
            map[px] = idx;
        }
        return map;
    },

    draw(data, freqs) {
        if (!data || !freqs) return;

        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const plotH = this.height - p.top - p.bottom;
        if (plotW <= 0 || plotH <= 0) return;

        if (!this.freqMap || this.lastFreqs !== freqs.length) {
            this.freqMap = this.buildFreqMap(freqs);
            this.lastFreqs = freqs.length;
        }

        this.ctx.drawImage(this.canvas, 0, 0, this.width, this.height, 0, 1, this.width, this.height);

        for (let px = 0; px < plotW; px++) {
            const db = data[this.freqMap[px]] || this.dbMin;
            const t = (db - this.dbMin) / (this.dbMax - this.dbMin);
            this.ctx.fillStyle = this.viridis(t);
            this.ctx.fillRect(p.left + px, p.top, 1, 1);
        }

        this.ctx.fillStyle = '#0d0d1a';
        this.ctx.fillRect(0, this.height - p.bottom, this.width, p.bottom);
        this.ctx.fillRect(0, 0, p.left, this.height);

        const logMin = Math.log10(this.freqMin);
        const logMax = Math.log10(this.freqMax);
        const freqTicks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
        this.ctx.fillStyle = '#666';
        this.ctx.font = '9px monospace';
        this.ctx.textAlign = 'center';
        for (const f of freqTicks) {
            const logF = Math.log10(f);
            const x = p.left + plotW * (logF - logMin) / (logMax - logMin);
            const label = f >= 1000 ? (f / 1000) + 'k' : f.toString();
            this.ctx.fillText(label, x, this.height - p.bottom + 14);
        }
    }
};
