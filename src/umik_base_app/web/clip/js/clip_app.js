/**
 * ClipApp — WebSocket client and UI controller for audio-tools-clip.
 */
class ClipApp {
  constructor(port) {
    this._port         = port;
    this._ws           = null;
    this._duration     = 0;
    this._currentPath  = null;
    this._previewAudio = null;
    this._allFiles      = [];
    this._regionBlobUrl = null;
    this._playheadRaf   = null;

    this._waveform = new WaveformView(
      document.getElementById('waveform-canvas'),
      document.getElementById('axis-canvas'),
      (start, end) => this._onHandleChange(start, end),
      (start, end) => this._updateAudioPlayer(start, end),
    );

    this._els = {
      pathInput:    document.getElementById('path-input'),
      btnOpen:      document.getElementById('btn-open'),
      // Left panel
      leftPanel:    document.getElementById('left-panel'),
      leftDir:      document.getElementById('left-dir'),
      leftCount:    document.getElementById('left-count'),
      leftFilter:   document.getElementById('left-filter'),
      leftItems:    document.getElementById('left-items'),
      // Right panel
      fileInfoBar:       document.getElementById('file-info-bar'),
      fileInfoText:      document.getElementById('file-info-text'),
      playerRow:         document.getElementById('player-row'),
      btnPlayPause:      document.getElementById('btn-play-pause'),
      audioTime:         document.getElementById('audio-time'),
      audioScrubberWrap: document.getElementById('audio-scrubber-wrap'),
      audioProgress:     document.getElementById('audio-progress'),
      audioPlayer:       document.getElementById('audio-player'),
      hint:         document.getElementById('hint'),
      // Controls
      startInput:   document.getElementById('start-input'),
      endInput:     document.getElementById('end-input'),
      srInput:      document.getElementById('sr-input'),
      duration:     document.getElementById('duration-display'),
      outputInput:  document.getElementById('output-input'),
      btnPreview:   document.getElementById('btn-preview'),
      btnClip:      document.getElementById('btn-clip'),
      // Status
      wsDot:        document.getElementById('ws-dot'),
      statusText:   document.getElementById('status-text'),
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
      try { this._onMessage(JSON.parse(e.data)); } catch (_) {}
    };
  }

  _send(obj) {
    if (this._ws && this._ws.readyState === WebSocket.OPEN)
      this._ws.send(JSON.stringify(obj));
  }

  // ── Message handling ───────────────────────────────────────────────────────

  _onMessage(msg) {
    switch (msg.type) {
      case 'file_loaded': this._onFileLoaded(msg); break;
      case 'file_list':   this._onFileList(msg);   break;
      case 'clip_done':   this._onClipDone(msg);   break;
      case 'error':       this._onError(msg);      break;
    }
  }

  _onFileList(msg) {
    this._allFiles = msg.files;

    // Show left panel with directory info
    const name = msg.dir.split('/').filter(Boolean).pop() || msg.dir;
    this._els.leftDir.textContent = name;
    this._els.leftDir.title = msg.dir;
    this._els.leftFilter.value = '';
    this._renderFileList(msg.files);
    this._els.leftPanel.classList.add('open');

    this._setStatus(`${msg.files.length} file(s) — type to filter`, 'info');
  }

  _onFileLoaded(msg) {
    this._duration    = msg.duration;
    this._currentPath = msg.path || msg.filename;

    // Update toolbar path
    this._els.pathInput.value = this._currentPath;

    // Show file info
    this._els.fileInfoText.textContent =
      `${msg.filename}  ·  ${msg.duration.toFixed(2)}s  ·  ${msg.sr} Hz  ·  ` +
      `${msg.channels === 1 ? 'mono' : msg.channels + 'ch'}  ·  ${msg.subtype}`;
    this._els.fileInfoBar.style.display = 'block';

    // Show audio player
    this._els.playerRow.style.display = 'flex';

    // Hide hint, load waveform
    this._els.hint.style.display = 'none';
    this._waveform.load(msg.waveform, msg.duration);

    // Stop any running playhead loop
    if (this._playheadRaf) { cancelAnimationFrame(this._playheadRaf); this._playheadRaf = null; }

    // Reset selection to full range
    this._els.startInput.value = '0.00';
    this._els.endInput.value   = msg.duration.toFixed(2);
    this._updateDuration(0, msg.duration);

    // Enable buttons
    this._els.btnPlayPause.disabled = false;
    this._els.btnPlayPause.textContent = '▶';
    this._els.btnPreview.disabled = false;
    this._els.btnClip.disabled    = false;

    // Default output dir: sibling clips/ folder
    const parent = this._currentPath.substring(0, this._currentPath.lastIndexOf('/'));
    this._els.outputInput.value = parent + '/clips';

    // Prime audio player with full selection
    this._updateAudioPlayer(0, msg.duration);

    // Highlight active file in left panel
    this._markActive(this._currentPath);

    this._setStatus(`Loaded: ${msg.filename}`, 'ok');
  }

  _onClipDone(msg) {
    this._setStatus(`✂ Saved ${msg.duration.toFixed(2)}s → ${msg.output}`, 'ok');
  }

  _onError(msg) {
    this._setStatus(`Error: ${msg.message}`, 'err');
  }

  // ── Left panel ─────────────────────────────────────────────────────────────

  _renderFileList(files) {
    const items = this._els.leftItems;
    items.innerHTML = '';
    this._els.leftCount.textContent = `${files.length} file(s)`;

    if (files.length === 0) {
      const d = document.createElement('div');
      d.className = 'file-list-empty';
      d.textContent = 'No matching files.';
      items.appendChild(d);
      return;
    }

    const frag = document.createDocumentFragment();
    for (const f of files) {
      const d = document.createElement('div');
      d.className = 'file-item';
      d.textContent = f.name;
      d.title = f.path;
      d.dataset.path = f.path;
      d.addEventListener('click', () => {
        this._els.pathInput.value = f.path;
        this._waveform.clear();
        this._els.btnPreview.disabled = true;
        this._els.btnClip.disabled    = true;
        this._setStatus(`Opening ${f.name}…`, 'info');
        this._send({ type: 'load_file', path: f.path });
      });
      frag.appendChild(d);
    }
    items.appendChild(frag);

    // Re-apply active highlight if a file is already selected
    if (this._currentPath) this._markActive(this._currentPath);
  }

  _markActive(path) {
    for (const el of this._els.leftItems.querySelectorAll('.file-item')) {
      el.classList.toggle('active', el.dataset.path === path);
    }
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
    this._updateAudioPlayer(start, end);
  }

  _updateDuration(start, end) {
    this._els.duration.textContent = `${Math.max(0, end - start).toFixed(2)}s`;
  }

  // ── Audio player ───────────────────────────────────────────────────────────

  _fmtTime(s) {
    if (!isFinite(s) || s < 0) return '0:00';
    const m = Math.floor(s / 60);
    return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  }

  _updateTimeDisplay() {
    const player = this._els.audioPlayer;
    const cur = player.currentTime || 0;
    const dur = player.duration;
    this._els.audioTime.textContent =
      `${this._fmtTime(cur)} / ${this._fmtTime(isFinite(dur) ? dur : 0)}`;
    this._els.audioProgress.style.width =
      (isFinite(dur) && dur > 0) ? `${(cur / dur) * 100}%` : '0%';
  }

  _updateAudioPlayer(start, end) {
    const player = this._els.audioPlayer;
    if (!player.paused) player.pause();

    fetch(`/audio/region?start=${start}&end=${end}`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(blob => {
        if (this._regionBlobUrl) URL.revokeObjectURL(this._regionBlobUrl);
        this._regionBlobUrl = URL.createObjectURL(blob);
        player.src = this._regionBlobUrl;
        player.load();
        this._els.audioProgress.style.width = '0%';
        this._els.audioTime.textContent = '0:00 / 0:00';
      })
      .catch(() => {});
  }

  // ── Playhead ───────────────────────────────────────────────────────────────

  _startPlayheadLoop() {
    const tick = () => {
      const player = this._els.audioPlayer;
      const start  = parseFloat(this._els.startInput.value) || 0;
      this._waveform.setPlayhead(start + player.currentTime);
      this._updateTimeDisplay();
      if (!player.paused && !player.ended) {
        this._playheadRaf = requestAnimationFrame(tick);
      } else {
        this._playheadRaf = null;
      }
    };
    if (this._playheadRaf) cancelAnimationFrame(this._playheadRaf);
    this._playheadRaf = requestAnimationFrame(tick);
  }

  // ── Preview ────────────────────────────────────────────────────────────────

  _preview() {
    const start = parseFloat(this._els.startInput.value) || 0;
    const end   = parseFloat(this._els.endInput.value)   || this._duration;

    if (this._previewAudio) { this._previewAudio.pause(); this._previewAudio = null; }
    this._els.audioPlayer.pause();

    this._setStatus('Loading preview…', 'info');
    fetch(`/audio/region?start=${start}&end=${end}`)
      .then(r => { if (!r.ok) throw new Error(`Server ${r.status}`); return r.blob(); })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        this._previewAudio = new Audio(url);
        this._previewAudio.onended = () => this._setStatus('Preview complete', 'ok');
        this._previewAudio.play();
        this._setStatus('▶ Previewing…', 'info');
      })
      .catch(err => this._setStatus(`Preview error: ${err.message}`, 'err'));
  }

  // ── Clip ───────────────────────────────────────────────────────────────────

  _clip() {
    const start     = parseFloat(this._els.startInput.value) || 0;
    const end       = parseFloat(this._els.endInput.value)   || this._duration;
    const sr        = parseInt(this._els.srInput.value, 10)  || null;
    const outputDir = this._els.outputInput.value.trim()     || null;

    this._setStatus('Clipping…', 'info');
    this._send({ type: 'clip', start, end, output: null, output_dir: outputDir, sr });
  }

  // ── UI binding ─────────────────────────────────────────────────────────────

  _bindUI() {
    // Toolbar
    this._els.btnOpen.addEventListener('click',     () => this._openFile());
    this._els.pathInput.addEventListener('keydown', e => { if (e.key === 'Enter') this._openFile(); });

    // Left panel filter
    this._els.leftFilter.addEventListener('input', () => {
      const q = this._els.leftFilter.value.toLowerCase();
      const filtered = q
        ? this._allFiles.filter(f => f.name.toLowerCase().includes(q))
        : this._allFiles;
      this._renderFileList(filtered);
    });

    // Selection inputs
    this._els.startInput.addEventListener('change', () => this._onInputChange());
    this._els.endInput.addEventListener('change',   () => this._onInputChange());

    // Buttons
    this._els.btnPreview.addEventListener('click', () => this._preview());
    this._els.btnClip.addEventListener('click',    () => this._clip());

    // Custom play/pause button
    this._els.btnPlayPause.addEventListener('click', () => {
      const player = this._els.audioPlayer;
      if (player.paused || player.ended) {
        player.play().catch(err => this._setStatus(`Play error: ${err.message}`, 'err'));
      } else {
        player.pause();
      }
    });

    // Scrubber click to seek
    this._els.audioScrubberWrap.addEventListener('click', (e) => {
      const player = this._els.audioPlayer;
      if (!player.src || !isFinite(player.duration)) return;
      const rect = this._els.audioScrubberWrap.getBoundingClientRect();
      const pct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      player.currentTime = pct * player.duration;
    });

    // Playhead + progress bar sync with audio player
    const player = this._els.audioPlayer;
    player.addEventListener('play', () => {
      this._els.btnPlayPause.textContent = '⏸';
      if (this._previewAudio) { this._previewAudio.pause(); this._previewAudio = null; }
      this._startPlayheadLoop();
    });
    player.addEventListener('pause', () => {
      this._els.btnPlayPause.textContent = '▶';
      const start = parseFloat(this._els.startInput.value) || 0;
      this._waveform.setPlayhead(start + player.currentTime);
      this._updateTimeDisplay();
    });
    player.addEventListener('ended', () => {
      this._els.btnPlayPause.textContent = '▶';
      this._waveform.setPlayhead(null);
      this._updateTimeDisplay();
    });
    player.addEventListener('seeked', () => {
      const start = parseFloat(this._els.startInput.value) || 0;
      this._waveform.setPlayhead(start + player.currentTime);
      this._updateTimeDisplay();
    });
    player.addEventListener('loadedmetadata', () => this._updateTimeDisplay());

    // Keyboard shortcuts (not when typing in an input)
    document.addEventListener('keydown', e => {
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
    this._els.statusText.textContent = text;
    this._els.statusText.className   = cls;
  }
}
