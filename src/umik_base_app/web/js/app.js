const App = {
    ws: null,
    reconnectDelay: 1000,

    init() {
        FFTPlot.init('fft-canvas');
        Waterfall.init('waterfall-canvas');
        TimeGraph.init('time-canvas');
        this.connect();
        this.bindControls();
        setInterval(() => TimeGraph.draw(), 50);
    },

    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/ws`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('stat-mic').textContent = 'Mic: connected';
            this.send({ type: 'list_devices' });
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'fft') {
                FFTPlot.draw(msg.data, msg.freqs, msg.noise_floor);
                Waterfall.draw(msg.data, msg.freqs);
                TimeGraph.push(msg.db_spl, msg.snr_avg);
                this.updateStatus(msg);
            } else if (msg.type === 'recording_stopped') {
                document.getElementById('btn-record').classList.remove('active');
                document.getElementById('btn-record').textContent = '\u25CF REC';
                alert('Recording saved: ' + msg.path);
            } else if (msg.type === 'calibration_loaded') {
                const el = document.getElementById('cal-status');
                el.textContent = 'Calibrated \u2713';
                el.className = 'ok';
            } else if (msg.type === 'device_list') {
                this.populateDevices(msg.devices);
            } else if (msg.type === 'device_changed') {
                if (msg.success) {
                    const sel = document.getElementById('device-select');
                    const opt = sel.querySelector(`option[value="${msg.device_id}"]`);
                    document.getElementById('stat-mic').textContent = opt ? opt.textContent : 'Mic: connected';
                }
            }
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed, reconnecting...');
            document.getElementById('stat-mic').textContent = 'Mic: disconnected';
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error', err);
            this.ws.close();
        };
    },

    updateStatus(msg) {
        document.getElementById('stat-spl').textContent = `dBSPL: ${msg.db_spl.toFixed(1)}`;
        document.getElementById('stat-snr').textContent = `SNR: ${msg.snr_avg.toFixed(1)} dB`;

        const micEl = document.getElementById('stat-mic');
        const status = msg.snr_status;
        micEl.textContent = `Mic: ${status}`;
        micEl.className = '';
        if (status === 'OK') micEl.classList.add('snr-ok');
        else if (status === 'LOW') micEl.classList.add('snr-low');
        else if (status === 'NOISE') micEl.classList.add('snr-noise');

        if (msg.capturing) {
            document.getElementById('btn-quiet-room').textContent = 'Capturing...';
            document.getElementById('btn-quiet-room').disabled = true;
        } else {
            document.getElementById('btn-quiet-room').textContent = 'Capture Quiet Room';
            document.getElementById('btn-quiet-room').disabled = false;
        }
    },

    send(msg) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(msg));
        }
    },

    bindControls() {
        document.getElementById('btn-quiet-room').addEventListener('click', () => {
            this.send({ type: 'capture_quiet_room' });
        });

        const btnRec = document.getElementById('btn-record');
        btnRec.addEventListener('click', () => {
            if (btnRec.classList.contains('active')) {
                this.send({ type: 'stop_recording' });
                btnRec.classList.remove('active');
                btnRec.textContent = '\u25CF REC';
            } else {
                this.send({ type: 'start_recording' });
                btnRec.classList.add('active');
                btnRec.textContent = '\u25A0 STOP';
            }
        });

        document.getElementById('btn-export').addEventListener('click', () => {
            this.send({ type: 'export_csv' });
        });

        document.getElementById('btn-load-cal').addEventListener('click', () => {
            const fileInput = document.getElementById('cal-file');
            const file = fileInput.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                this.send({ type: 'load_calibration', content: e.target.result });
            };
            reader.readAsText(file);
        });

        document.getElementById('device-select').addEventListener('change', (e) => {
            const deviceId = parseInt(e.target.value);
            if (!isNaN(deviceId)) {
                this.send({ type: 'change_device', device_id: deviceId });
            }
        });
    },

    populateDevices(devices) {
        const sel = document.getElementById('device-select');
        sel.innerHTML = '';
        for (const d of devices) {
            const opt = document.createElement('option');
            opt.value = d.id;
            const shortName = d.name.length > 35 ? d.name.substring(0, 32) + '...' : d.name;
            opt.textContent = `[${d.id}] ${shortName}`;
            sel.appendChild(opt);
        }
    }
};

window.addEventListener('DOMContentLoaded', () => App.init());
