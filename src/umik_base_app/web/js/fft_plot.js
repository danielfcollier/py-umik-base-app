const FFTPlot = {
    canvas: null,
    ctx: null,
    width: 0,
    height: 0,
    freqs: null,
    noiseFloor: null,
    padding: { top: 10, right: 10, bottom: 30, left: 50 },
    dbMin: -100,
    dbMax: 0,
    freqMin: 20,
    freqMax: 22000,

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

    freqToX(freq) {
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const logMin = Math.log10(this.freqMin);
        const logMax = Math.log10(this.freqMax);
        const logFreq = Math.log10(Math.max(freq, this.freqMin));
        return p.left + plotW * (logFreq - logMin) / (logMax - logMin);
    },

    dbToY(db) {
        const p = this.padding;
        const plotH = this.height - p.top - p.bottom;
        return p.top + plotH * (1.0 - (db - this.dbMin) / (this.dbMax - this.dbMin));
    },

    draw(data, freqs, noiseFloor) {
        if (!data || !freqs) return;
        this.freqs = freqs;
        if (noiseFloor) this.noiseFloor = noiseFloor;

        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const p = this.padding;

        ctx.fillStyle = '#0d0d1a';
        ctx.fillRect(0, 0, w, h);

        ctx.strokeStyle = '#222';
        ctx.lineWidth = 0.5;
        for (let db = this.dbMin; db <= this.dbMax; db += 20) {
            const y = this.dbToY(db);
            ctx.beginPath();
            ctx.moveTo(p.left, y);
            ctx.lineTo(w - p.right, y);
            ctx.stroke();
        }

        const freqTicks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
        ctx.fillStyle = '#666';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        for (const f of freqTicks) {
            const x = this.freqToX(f);
            ctx.beginPath();
            ctx.moveTo(x, p.top);
            ctx.lineTo(x, h - p.bottom);
            ctx.strokeStyle = '#222';
            ctx.stroke();
            const label = f >= 1000 ? (f / 1000) + 'k' : f.toString();
            ctx.fillText(label, x, h - p.bottom + 14);
        }

        ctx.fillStyle = '#555';
        ctx.textAlign = 'right';
        for (let db = this.dbMin; db <= this.dbMax; db += 20) {
            ctx.fillText(db.toString(), p.left - 4, this.dbToY(db) + 3);
        }

        if (this.noiseFloor) {
            ctx.strokeStyle = 'rgba(231, 76, 60, 0.3)';
            ctx.fillStyle = 'rgba(231, 76, 60, 0.1)';
            ctx.beginPath();
            ctx.moveTo(p.left, h - p.bottom);
            for (let i = 0; i < freqs.length; i++) {
                ctx.lineTo(this.freqToX(freqs[i]), this.dbToY(this.noiseFloor[i]));
            }
            ctx.lineTo(w - p.right, h - p.bottom);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }

        if (this.noiseFloor) {
            ctx.strokeStyle = 'rgba(150, 150, 150, 0.5)';
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            for (let i = 0; i < freqs.length; i++) {
                const x = this.freqToX(freqs[i]);
                const y = this.dbToY(this.noiseFloor[i]);
                i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);
        }

        ctx.strokeStyle = '#00ff88';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i < data.length; i++) {
            const x = this.freqToX(freqs[i]);
            const y = this.dbToY(data[i]);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
    }
};
