/**
 * ClipApp — WebSocket client and UI controller for audio-tools-clip.
 *
 * Coordinates the WaveformView, text inputs, Preview / Clip buttons, and
 * WebSocket connection to the Python aiohttp server.
 */
class ClipApp {
  /** @param {number} port - WebSocket server port (matches aiohttp port) */
  constructor(port) {
    this._port     = port;
    this._ws       = null;
    this._duration = 0;
    this._previewAudio = null;

    this._waveform = new WaveformView(
      document.getElementById('waveform-canvas'),
      document.getElementById('axis-canvas'),
      (start, end) => this._onHandleChange(start, end),
    );

    this._els = {
      pathInput:   document.getElementById('path-input'),
      btnOpen:     document.getElementById('btn-open'),
      btnPreview:  document.getElementById('btn-preview'),
      btnClip:     document.getElementById('btn-clip'),
      startInput:  document.getElementById('start-input'),
      endInput:    document.getElementById('end-input'),
      srInput:     document.getElementById('sr-input'),
      duration:    document.getElementById('duration-display'),
      fileInfo:    document.getElementById('file-info'),
      statusText:  document.getElementById('status-text'),
      wsDot:       document.getElementById('ws-dot'),
      hint:        document.getElementById('hint'),
    };

    this._bindUI();
    this._connect();
  }

  // ── WebSocket ──────────────────────────────────────────────────────────────

  _connect() {
    this._setStatus('Connecting…', 'info');
    this._ws = new WebSocket(`ws://localhost:${this._port}/ws`);

    this._ws.onopen = () => {
      this._els.wsDot.classList.add('connected');
      this._setStatus('Connected', 'ok');
    };

    this._ws.onclose = () => {
      this._els.wsDot.classList.remove('connected');
      this._setStatus('Disconnected — retrying…');
      setTimeout(() => this._connect(), 1500);
    };

    this._ws.onerror = () => {
      this._setStatus('Connection error', 'err');
    };

    this._ws.onmessage = (e) => {
      try {
        this._onMessage(JSON.parse(e.data));
      } catch (_) { /* ignore malformed frames */ }
    };
  }

  _send(obj) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN) {
      this._ws.send(JSON.stringify(obj));
    }
  }

  // ── Message handling ───────────────────────────────────────────────────────

  _onMessage(msg) {
    switch (msg.type) {
      case 'file_loaded':  this._onFileLoaded(msg);  break;
      case 'clip_done':    this._onClipDone(msg);    break;
      case 'error':        this._onError(msg);       break;
    }
  }

  _onFileLoaded(msg) {
    this._duration = msg.duration;

    this._els.hint.style.display = 'none';
    this._els.pathInput.value = msg.path || msg.filename;
    this._els.fileInfo.textContent =
      `${msg.filename}  ·  ${msg.duration.toFixed(2)}s  ·  ${msg.sr} Hz  ·  ${msg.channels === 1 ? 'mono' : msg.channels + 'ch'}  ·  ${msg.subtype}`;

    this._waveform.load(msg.waveform, msg.duration);

    this._els.startInput.value = '0.00';
    this._els.endInput.value   = msg.duration.toFixed(2);
    this._updateDuration(0, msg.duration);

    this._els.btnPreview.disabled = false;
    this._els.btnClip.disabled    = false;

    this._setStatus(`Loaded: ${msg.filename}`, 'ok');
  }

  _onClipDone(msg) {
    this._setStatus(`✂ Saved ${msg.duration.toFixed(2)}s → ${msg.output}`, 'ok');
  }

  _onError(msg) {
    this._setStatus(`Error: ${msg.message}`, 'err');
  }

  // ── Handle ↔ input sync ────────────────────────────────────────────────────

  _onHandleChange(start, end) {
    this._els.startInput.value = start.toFixed(3);
    this._els.endInput.value   = end.toFixed(3);
    this._updateDuration(start, end);
  }

  _onInputChange() {
    const start = parseFloat(this._els.startInput.value) || 0;
    const end   = parseFloat(this._els.endInput.value)   || this._duration;
    this._waveform.setRange(start, end);
    this._updateDuration(start, end);
  }

  _updateDuration(start, end) {
    const d = Math.max(0, end - start);
    this._els.duration.textContent = `${d.toFixed(2)}s`;
  }

  // ── Preview ────────────────────────────────────────────────────────────────

  _preview() {
    const start = parseFloat(this._els.startInput.value) || 0;
    const end   = parseFloat(this._els.endInput.value)   || this._duration;

    if (this._previewAudio) {
      this._previewAudio.pause();
      this._previewAudio = null;
    }

    this._setStatus('Loading preview…', 'info');
    fetch(`/audio/region?start=${start}&end=${end}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server returned ${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        this._previewAudio = new Audio(url);
        this._previewAudio.onended = () => this._setStatus('Preview complete', 'ok');
        this._previewAudio.play();
        this._setStatus('▶ Previewing…', 'info');
      })
      .catch((err) => this._setStatus(`Preview error: ${err.message}`, 'err'));
  }

  // ── Clip ───────────────────────────────────────────────────────────────────

  _clip() {
    const start = parseFloat(this._els.startInput.value) || 0;
    const end   = parseFloat(this._els.endInput.value)   || this._duration;
    const sr    = parseInt(this._els.srInput.value, 10) || null;

    this._setStatus('Clipping…', 'info');
    this._send({ type: 'clip', start, end, output: null, sr });
  }

  // ── UI binding ─────────────────────────────────────────────────────────────

  _bindUI() {
    this._els.btnOpen.addEventListener('click', () => this._openFile());
    this._els.pathInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this._openFile();
    });

    this._els.startInput.addEventListener('change', () => this._onInputChange());
    this._els.endInput.addEventListener('change',   () => this._onInputChange());

    this._els.btnPreview.addEventListener('click', () => this._preview());
    this._els.btnClip.addEventListener('click',    () => this._clip());

    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT') return;
      if (e.code === 'Space') { e.preventDefault(); this._preview(); }
      if (e.code === 'Enter') { e.preventDefault(); this._clip(); }
    });
  }

  _openFile() {
    const path = this._els.pathInput.value.trim();
    if (!path) return;
    this._setStatus(`Opening ${path}…`, 'info');
    this._waveform.clear();
    this._els.btnPreview.disabled = true;
    this._els.btnClip.disabled    = true;
    this._send({ type: 'load_file', path });
  }

  // ── Status ─────────────────────────────────────────────────────────────────

  _setStatus(text, cls = '') {
    const el = this._els.statusText;
    el.textContent = text;
    el.className = cls;
  }
}
