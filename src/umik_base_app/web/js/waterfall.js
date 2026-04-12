const Waterfall = {
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    maxRows: 500,
    freqMin: 20,
    freqMax: 22000,
    dbMin: -100,
    dbMax: 0,
    padding: { top: 10, right: 10, bottom: 30, left: 50 },
    imageData: null,

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
        this.imageData = this.ctx.createImageData(this.width, this.height);
    },

    viridis(t) {
        t = Math.max(0, Math.min(1, t));
        const r = Math.round(255 * Math.min(1, Math.max(0, -0.27 + 4.15 * t - 5.1 * t * t + 2.6 * t * t * t)));
        const g = Math.round(255 * Math.min(1, Math.max(0, -0.005 + 0.48 * t + 2.35 * t * t - 2.9 * t * t * t)));
        const b = Math.round(255 * Math.min(1, Math.max(0, 0.33 + 1.4 * t - 4.8 * t * t + 5.3 * t * t * t)));
        return [r, g, b];
    },

    draw(data, freqs) {
        if (!data || !freqs || !this.imageData) return;

        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const plotH = this.height - p.top - p.bottom;

        this.ctx.drawImage(this.canvas, 0, 0, this.width, this.height - 1, 0, 0, this.width, this.height);

        const rowY = p.top;
        const logMin = Math.log10(this.freqMin);
        const logMax = Math.log10(this.freqMax);

        for (let px = 0; px < plotW; px++) {
            const logFreq = logMin + (px / plotW) * (logMax - logMin);
            const targetFreq = Math.pow(10, logFreq);

            let idx = 0;
            for (let i = 1; i < freqs.length; i++) {
                if (freqs[i] >= targetFreq) { idx = i; break; }
                idx = i;
            }

            const db = data[idx] || this.dbMin;
            const t = (db - this.dbMin) / (this.dbMax - this.dbMin);
            const [r, g, b] = this.viridis(t);

            const x = p.left + px;
            const imgIdx = (rowY * this.width + x) * 4;
            if (imgIdx >= 0 && imgIdx < this.imageData.data.length - 3) {
                this.imageData.data[imgIdx] = r;
                this.imageData.data[imgIdx + 1] = g;
                this.imageData.data[imgIdx + 2] = b;
                this.imageData.data[imgIdx + 3] = 255;
            }
        }

        this.ctx.putImageData(this.imageData, 0, 0, p.left, rowY, plotW, 1);

        this.ctx.fillStyle = '#0d0d1a';
        this.ctx.fillRect(0, this.height - p.bottom, this.width, p.bottom);
        this.ctx.fillRect(0, 0, p.left, this.height);

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
