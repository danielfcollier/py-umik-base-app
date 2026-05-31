/**
 * WaveformView — Canvas-based waveform renderer with draggable start/end handles.
 *
 * Renders a min/max amplitude envelope and lets the user drag two vertical
 * handles to select a time region. Emits an onChange(start, end) callback
 * whenever either handle moves.
 */
class WaveformView {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {HTMLCanvasElement} axisCanvas  - separate canvas for the time axis
   * @param {function(number, number): void} onChange - called with (startSec, endSec)
   */
  constructor(canvas, axisCanvas, onChange, onDragEnd = null) {
    this._canvas = canvas;
    this._axisCanvas = axisCanvas;
    this._ctx = canvas.getContext('2d');
    this._axisCtx = axisCanvas.getContext('2d');
    this._onChange  = onChange;
    this._onDragEnd = onDragEnd;

    /** @type {Array<{min: number, max: number}>} */
    this._envelope = [];
    this._duration = 0;
    this._startTime = 0;
    this._endTime = 0;
    this._playheadTime = null;

    this._dragging = null;   // 'start' | 'end' | null
    this._dragOffsetX = 0;

    this._bindEvents();
    this._observeSize();
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  get startTime() { return this._startTime; }
  get endTime()   { return this._endTime; }

  /** Load new waveform data and reset handles to the full range. */
  load(envelope, duration) {
    this._envelope = envelope;
    this._duration = duration;
    this._startTime = 0;
    this._endTime = duration;
    this._playheadTime = null;
    this._syncSize();
    this._draw();
  }

  /** Update handle positions from external inputs (text fields). */
  setRange(start, end) {
    this._startTime = Math.max(0, Math.min(start, this._duration));
    this._endTime   = Math.max(this._startTime, Math.min(end, this._duration));
    this._draw();
  }

  /** Move the playhead to time t (seconds in the full file). Pass null to hide it. */
  setPlayhead(t) {
    this._playheadTime = t;
    this._draw();
  }

  clear() {
    this._envelope = [];
    this._duration = 0;
    this._startTime = 0;
    this._endTime = 0;
    this._playheadTime = null;
    this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
    this._axisCtx.clearRect(0, 0, this._axisCanvas.width, this._axisCanvas.height);
  }

  // ── Coordinate helpers ─────────────────────────────────────────────────────

  _timeToX(t) {
    if (this._duration <= 0) return 0;
    return (t / this._duration) * this._canvas.width;
  }

  _xToTime(x) {
    if (this._canvas.width <= 0 || this._duration <= 0) return 0;
    return Math.max(0, Math.min(this._duration, (x / this._canvas.width) * this._duration));
  }

  _handleHitRadius() { return 8; }

  _nearHandle(x) {
    const sx = this._timeToX(this._startTime);
    const ex = this._timeToX(this._endTime);
    const r  = this._handleHitRadius();
    if (Math.abs(x - ex) <= r) return 'end';    // check end first (right > left priority)
    if (Math.abs(x - sx) <= r) return 'start';
    return null;
  }

  // ── Drawing ────────────────────────────────────────────────────────────────

  // ── Envelope drawing helper ────────────────────────────────────────────────

  _drawEnvelope(ctx, W, H, midY, fillColor, strokeColor) {
    const n = this._envelope.length;
    ctx.fillStyle = fillColor;
    for (let i = 0; i < n; i++) {
      const x  = (i / n) * W;
      const dx = Math.max(1, W / n);
      const { min, max } = this._envelope[i];
      ctx.fillRect(x, midY - max * midY, dx, Math.max(1, (max - min) * midY));
    }
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = (i / n) * W + (W / n) / 2;
      const y = midY - this._envelope[i].max * midY;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  _draw() {
    const { width: W, height: H } = this._canvas;
    const ctx = this._ctx;
    ctx.clearRect(0, 0, W, H);

    if (this._envelope.length === 0) return;

    const midY = H / 2;

    // Pass 1: full waveform — dim (unplayed) colour
    this._drawEnvelope(ctx, W, H, midY, '#1e5232', '#2a6a40');

    // Pass 2: played region — bright colour, clipped to [selStart → playhead]
    if (this._playheadTime !== null && this._duration > 0) {
      const sx = this._timeToX(this._startTime);
      const px = this._timeToX(this._playheadTime);
      if (px > sx) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(sx, 0, px - sx, H);
        ctx.clip();
        this._drawEnvelope(ctx, W, H, midY, '#3db866', '#5dce88');
        ctx.restore();
      }
    }

    // Selection region
    if (this._duration > 0) {
      const sx = this._timeToX(this._startTime);
      const ex = this._timeToX(this._endTime);
      ctx.fillStyle = 'rgba(100, 160, 255, 0.10)';
      ctx.fillRect(sx, 0, ex - sx, H);

      // Selection borders
      ctx.strokeStyle = 'rgba(100, 160, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(sx, 0); ctx.lineTo(sx, H);
      ctx.moveTo(ex, 0); ctx.lineTo(ex, H);
      ctx.stroke();

      // Start handle
      this._drawHandle(ctx, this._timeToX(this._startTime), H, '#3c8', 'start');
      // End handle
      this._drawHandle(ctx, this._timeToX(this._endTime), H, '#e54', 'end');
    }

    // Playhead
    if (this._playheadTime !== null && this._duration > 0) {
      const px = this._timeToX(this._playheadTime);
      ctx.save();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, H);
      ctx.stroke();
      ctx.restore();
    }

    this._drawAxis();
  }

  _drawHandle(ctx, x, H, color, which) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();

    // Triangle grip at top
    const arrowW = 8;
    const arrowH = 12;
    ctx.fillStyle = color;
    ctx.beginPath();
    if (which === 'start') {
      ctx.moveTo(x, 0);
      ctx.lineTo(x + arrowW, arrowH);
      ctx.lineTo(x, arrowH);
    } else {
      ctx.moveTo(x, 0);
      ctx.lineTo(x - arrowW, arrowH);
      ctx.lineTo(x, arrowH);
    }
    ctx.closePath();
    ctx.fill();
  }

  _drawAxis() {
    const W = this._axisCanvas.width;
    const H = this._axisCanvas.height;
    const ctx = this._axisCtx;
    ctx.clearRect(0, 0, W, H);

    if (this._duration <= 0) return;

    ctx.fillStyle   = '#555';
    ctx.strokeStyle = '#333';
    ctx.font        = '10px Menlo, Consolas, monospace';
    ctx.lineWidth   = 1;

    const step = _niceStep(this._duration);
    let t = 0;
    while (t <= this._duration + step * 0.01) {
      const x = this._timeToX(t) * (W / this._canvas.width);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 5);
      ctx.stroke();
      const label = t % 1 === 0 ? `${t}s` : `${t.toFixed(1)}s`;
      ctx.fillText(label, x + 2, H - 2);
      t = Math.round((t + step) * 100) / 100;
    }
  }

  // ── Events ─────────────────────────────────────────────────────────────────

  _bindEvents() {
    const c = this._canvas;

    c.addEventListener('mousedown', (e) => {
      if (this._envelope.length === 0) return;
      const x = this._clientX(e);
      const hit = this._nearHandle(x);
      if (hit) {
        this._dragging = hit;
        this._canvas.style.cursor = 'ew-resize';
        e.preventDefault();
      }
    });

    window.addEventListener('mousemove', (e) => {
      if (!this._dragging) return;
      const x = this._clientX(e);
      const t = this._xToTime(x);
      if (this._dragging === 'start') {
        this._startTime = Math.min(t, this._endTime - 0.001);
      } else {
        this._endTime = Math.max(t, this._startTime + 0.001);
      }
      this._draw();
      this._onChange(this._startTime, this._endTime);
      e.preventDefault();
    });

    window.addEventListener('mouseup', () => {
      if (this._dragging) {
        this._dragging = null;
        this._canvas.style.cursor = 'crosshair';
        if (this._onDragEnd) this._onDragEnd(this._startTime, this._endTime);
      }
    });

    // Cursor hint
    c.addEventListener('mousemove', (e) => {
      if (this._dragging || this._envelope.length === 0) return;
      const hit = this._nearHandle(this._clientX(e));
      c.style.cursor = hit ? 'ew-resize' : 'crosshair';
    });
  }

  _clientX(e) {
    return e.clientX - this._canvas.getBoundingClientRect().left;
  }

  // ── Resize ─────────────────────────────────────────────────────────────────

  _syncSize() {
    this._canvas.width     = this._canvas.offsetWidth;
    this._canvas.height    = this._canvas.offsetHeight;
    this._axisCanvas.width = this._axisCanvas.offsetWidth;
    this._axisCanvas.height = this._axisCanvas.offsetHeight;
  }

  _observeSize() {
    let pending = false;
    const ro = new ResizeObserver(() => {
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        this._syncSize();
        this._draw();
      });
    });
    ro.observe(this._canvas);  // axis canvas follows; observing it separately causes double redraws
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Pick a human-friendly tick interval for a given total duration (seconds). */
function _niceStep(duration) {
  const targets = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300];
  const ideal = duration / 10;
  return targets.reduce((best, v) => Math.abs(v - ideal) < Math.abs(best - ideal) ? v : best, targets[0]);
}
