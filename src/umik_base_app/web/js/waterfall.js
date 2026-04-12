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
    history: [],
    maxHistory: 600,
    viewFreqMin: 20,
    viewFreqMax: 22000,
    frozen: false,
    selectionRect: null,
    isSelecting: false,
    selStartX: 0,
    selStartY: 0,
    selEndX: 0,
    selEndY: 0,
    exportButtons: [],

    init(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('dblclick', (e) => this.onDblClick(e));
    },

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.width = rect.width;
        this.height = rect.height;
        this.ctx.fillStyle = '#0d0d1a';
        this.ctx.fillRect(0, 0, this.width, this.height);
        if (this.history.length > 0) this.redrawFromHistory();
    },

    viridis(t) {
        t = Math.max(0, Math.min(1, t));
        const r = Math.round(255 * Math.min(1, Math.max(0, -0.27 + 4.15 * t - 5.1 * t * t + 2.6 * t * t * t)));
        const g = Math.round(255 * Math.min(1, Math.max(0, -0.005 + 0.48 * t + 2.35 * t * t - 2.9 * t * t * t)));
        const b = Math.round(255 * Math.min(1, Math.max(0, 0.33 + 1.4 * t - 4.8 * t * t + 5.3 * t * t * t)));
        return `rgb(${r},${g},${b})`;
    },

    buildFreqMap(freqs, fMin, fMax) {
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const logMin = Math.log10(fMin);
        const logMax = Math.log10(fMax);
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

        if (!this.frozen) {
            this.history.push({ data: data.slice(), freqs: freqs });
            while (this.history.length > this.maxHistory) this.history.shift();
        }

        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const plotH = this.height - p.top - p.bottom;
        if (plotW <= 0 || plotH <= 0) return;

        const fMin = this.viewFreqMin;
        const fMax = this.viewFreqMax;
        const freqMap = this.buildFreqMap(freqs, fMin, fMax);

        const ctx = this.ctx;
        ctx.fillStyle = '#0d0d1a';
        ctx.fillRect(0, 0, this.width, this.height);

        const startIdx = Math.max(0, this.history.length - plotH);
        const rows = this.history.slice(startIdx);
        for (let row = 0; row < rows.length; row++) {
            const y = p.top + plotH - rows.length + row;
            for (let px = 0; px < plotW; px++) {
                const db = rows[row].data[freqMap[px]] || this.dbMin;
                const t = (db - this.dbMin) / (this.dbMax - this.dbMin);
                ctx.fillStyle = this.viridis(t);
                ctx.fillRect(p.left + px, y, 1, 1);
            }
        }

        this.drawAxes(fMin, fMax);

        if (this.selectionRect) {
            this.drawSelectionOverlay();
        }
    },

    drawAxes(fMin, fMax) {
        const ctx = this.ctx;
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const plotH = this.height - p.top - p.bottom;

        ctx.fillStyle = '#0d0d1a';
        ctx.fillRect(0, this.height - p.bottom, this.width, p.bottom);
        ctx.fillRect(0, 0, p.left, this.height);

        const logMin = Math.log10(fMin);
        const logMax = Math.log10(fMax);
        const allTicks = [20, 30, 50, 100, 200, 300, 500, 1000, 2000, 3000, 5000, 10000, 20000];
        const ticks = allTicks.filter(f => f >= fMin && f <= fMax);
        ctx.fillStyle = '#666';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        for (const f of ticks) {
            const logF = Math.log10(f);
            const x = p.left + plotW * (logF - logMin) / (logMax - logMin);
            if (x >= p.left && x <= this.width - p.right) {
                const label = f >= 1000 ? (f / 1000) + 'k' : f.toString();
                ctx.fillText(label, x, this.height - p.bottom + 14);
            }
        }
    },

    redrawFromHistory() {
        if (this.history.length === 0) return;
        const sample = this.history[this.history.length - 1];
        this.draw(sample.data, sample.freqs);
    },

    onWheel(e) {
        e.preventDefault();
        const p = this.padding;
        const plotW = this.width - p.left - p.right;
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const plotX = mouseX - p.left;
        if (plotX < 0 || plotX > plotW) return;

        const logMin = Math.log10(this.viewFreqMin);
        const logMax = Math.log10(this.viewFreqMax);
        const logRange = logMax - logMin;
        const logCenter = logMin + (plotX / plotW) * logRange;
        const factor = e.deltaY > 0 ? 1.3 : 0.77;
        const newLogRange = logRange * factor;
        const minRange = 0.15;
        const maxRange = Math.log10(22000) - Math.log10(20);
        if (newLogRange < minRange || newLogRange > maxRange) return;

        const ratio = (logCenter - logMin) / logRange;
        const newLogMin = logCenter - newLogRange * ratio;
        const newLogMax = logCenter + newLogRange * (1 - ratio);

        this.viewFreqMin = Math.max(10, Math.pow(10, newLogMin));
        this.viewFreqMax = Math.min(24000, Math.pow(10, newLogMax));
        this.redrawFromHistory();
    },

    onMouseDown(e) {
        if (e.button !== 0) return;
        const rect = this.canvas.getBoundingClientRect();
        this.isSelecting = true;
        this.selStartX = e.clientX - rect.left;
        this.selStartY = e.clientY - rect.top;
        this.selEndX = this.selStartX;
        this.selEndY = this.selStartY;
        this.selectionRect = null;
        this.removeExportButtons();
    },

    onMouseMove(e) {
        if (!this.isSelecting) return;
        const rect = this.canvas.getBoundingClientRect();
        this.selEndX = e.clientX - rect.left;
        this.selEndY = e.clientY - rect.top;
        this.drawSelectionPreview();
    },

    onMouseUp(e) {
        if (!this.isSelecting) return;
        this.isSelecting = false;
        const rect = this.canvas.getBoundingClientRect();
        this.selEndX = e.clientX - rect.left;
        this.selEndY = e.clientY - rect.top;

        const p = this.padding;
        const plotLeft = p.left;
        const plotRight = this.width - p.right;
        const plotTop = p.top;
        const plotBottom = this.height - p.bottom;

        const x1 = Math.max(plotLeft, Math.min(this.selStartX, this.selEndX));
        const x2 = Math.min(plotRight, Math.max(this.selStartX, this.selEndX));
        const y1 = Math.max(plotTop, Math.min(this.selStartY, this.selEndY));
        const y2 = Math.min(plotBottom, Math.max(this.selStartY, this.selEndY));

        if (x2 - x1 < 10 || y2 - y1 < 5) {
            this.selectionRect = null;
            this.redrawFromHistory();
            return;
        }

        this.selectionRect = { x1, y1, x2, y2 };
        this.frozen = true;
        this.redrawFromHistory();
        this.showExportButtons();
    },

    onDblClick(e) {
        this.frozen = false;
        this.selectionRect = null;
        this.viewFreqMin = 20;
        this.viewFreqMax = 22000;
        this.removeExportButtons();
        this.redrawFromHistory();
    },

    drawSelectionPreview() {
        this.redrawFromHistory();
        const ctx = this.ctx;
        const x1 = Math.min(this.selStartX, this.selEndX);
        const y1 = Math.min(this.selStartY, this.selEndY);
        const w = Math.abs(this.selEndX - this.selStartX);
        const h = Math.abs(this.selEndY - this.selStartY);
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(x1, y1, w, h);
        ctx.setLineDash([]);
    },

    drawSelectionOverlay() {
        if (!this.selectionRect) return;
        const ctx = this.ctx;
        const { x1, y1, x2, y2 } = this.selectionRect;

        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
        ctx.strokeStyle = '#00ffcc';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    },

    showExportButtons() {
        this.removeExportButtons();
        if (!this.selectionRect) return;

        const { x2, y1 } = this.selectionRect;
        const container = this.canvas.parentElement;

        const btnCsv = document.createElement('button');
        btnCsv.textContent = 'Export CSV';
        btnCsv.className = 'wf-export-btn';
        btnCsv.style.left = (x2 + 8) + 'px';
        btnCsv.style.top = y1 + 'px';
        btnCsv.onclick = () => this.exportSelectionCSV();
        container.appendChild(btnCsv);
        this.exportButtons.push(btnCsv);

        const btnPng = document.createElement('button');
        btnPng.textContent = 'Export PNG';
        btnPng.className = 'wf-export-btn';
        btnPng.style.left = (x2 + 8) + 'px';
        btnPng.style.top = (y1 + 26) + 'px';
        btnPng.onclick = () => this.exportSelectionPNG();
        container.appendChild(btnPng);
        this.exportButtons.push(btnPng);
    },

    removeExportButtons() {
        for (const btn of this.exportButtons) btn.remove();
        this.exportButtons = [];
    },

    getSelectedRows() {
        if (!this.selectionRect) return null;
        const p = this.padding;
        const plotH = this.height - p.top - p.bottom;
        const { y1, y2 } = this.selectionRect;

        const rowBottom = Math.max(0, Math.round(plotH - (y2 - p.top)));
        const rowTop = Math.min(this.history.length - 1, Math.round(plotH - (y1 - p.top)));
        const startIdx = Math.max(0, this.history.length - plotH);

        const from = startIdx + rowBottom;
        const to = startIdx + rowTop;
        return this.history.slice(Math.max(0, from), Math.min(this.history.length, to + 1));
    },

    exportSelectionCSV() {
        const rows = this.getSelectedRows();
        if (!rows || rows.length === 0) return;

        const freqs = rows[0].freqs;
        const n = freqs.length;
        const avg = new Float64Array(n);
        const min = new Float64Array(n).fill(Infinity);
        const max = new Float64Array(n).fill(-Infinity);

        for (const row of rows) {
            for (let i = 0; i < n; i++) {
                avg[i] += row.data[i];
                if (row.data[i] < min[i]) min[i] = row.data[i];
                if (row.data[i] > max[i]) max[i] = row.data[i];
            }
        }
        for (let i = 0; i < n; i++) avg[i] /= rows.length;

        let csv = 'frequency_hz,avg_db,min_db,max_db\n';
        for (let i = 0; i < n; i++) {
            csv += freqs[i].toFixed(1) + ',' + avg[i].toFixed(2) + ',' + min[i].toFixed(2) + ',' + max[i].toFixed(2) + '\n';
        }

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'waterfall_selection_' + Date.now() + '.csv';
        a.click();
        URL.revokeObjectURL(url);
    },

    exportSelectionPNG() {
        if (!this.selectionRect) return;
        const { x1, y1, x2, y2 } = this.selectionRect;
        const w = Math.round(x2 - x1);
        const h = Math.round(y2 - y1);
        if (w <= 0 || h <= 0) return;

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = w;
        tempCanvas.height = h;
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.drawImage(this.canvas, x1, y1, w, h, 0, 0, w, h);

        tempCanvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'waterfall_selection_' + Date.now() + '.png';
            a.click();
            URL.revokeObjectURL(url);
        });
    }
};
