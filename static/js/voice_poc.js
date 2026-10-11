(() => {
    const page = document.getElementById('voice-poc');
    const mic = document.getElementById('voice-poc-mic');
    const cancel = document.getElementById('voice-poc-cancel');
    const status = document.getElementById('voice-poc-status');
    const transcript = document.getElementById('voice-poc-transcript');
    const response = document.getElementById('voice-poc-response');
    const events = document.getElementById('voice-poc-events');
    const context = JSON.parse(document.getElementById('voice-poc-context').textContent);
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    let current = null, sending = false, messages = [];
    const record = name => { events.textContent += new Date().toLocaleTimeString() + ' ' + name + '\n'; };
    function reset() {
        mic.disabled = sending;
        mic.querySelector('span').textContent = 'Start recording';
        mic.setAttribute('aria-label', 'Start recording');
        cancel.hidden = true;
        page.classList.remove('voice-poc-listening');
    }
    function release(session) {
        clearInterval(session.monitor);
        clearTimeout(session.timer);
        session.stream?.getTracks().forEach(track => track.stop());
        session.source?.disconnect();
        session.audio?.close().catch(() => {});
    }
    function discard(message) {
        if (!current) return;
        const session = current;
        session.cancelled = true;
        if (session.recorder?.state === 'recording') session.recorder.stop();
        release(session);
        current = null;
        sending = false;
        reset(); status.textContent = message;
    }
    function stop(session) {
        if (current !== session || session.stopping) return;
        if (!session.recorder || session.recorder.state !== 'recording') return;
        session.stopping = true;
        sending = true;
        clearInterval(session.monitor);
        clearTimeout(session.timer);
        mic.disabled = true;
        status.textContent = 'Finishing recording…';
        record('stop requested');
        session.timer = setTimeout(() => {
            if (current === session) { sending = false; discard('Recording did not finish. Nothing was submitted. Try again.'); }
        }, 5000);
        session.recorder.stop();
    }
    async function transcribe(session) {
        if (current !== session || session.cancelled) return;
        release(session); current = null;
        sending = true; reset();
        status.textContent = 'Transcribing…';
        try {
            const blob = new Blob(session.chunks, { type: session.recorder.mimeType });
            if (!blob.size || blob.size > 6 * 1024 * 1024) throw new Error('Recording is empty or too large.');
            const result = await fetch(page.dataset.transcribeUrl, {
                method: 'POST', headers: { 'Content-Type': blob.type }, body: blob,
                signal: AbortSignal.timeout(75000),
            });
            if (!result.ok) throw new Error('Transcription failed. Nothing was sent to chat.');
            const data = await result.json();
            session.final = (data.transcript || '').trim();
            transcript.textContent = session.final || 'No speech detected.';
            record('transcription received');
            if (session.final) await submit(session);
            else status.textContent = 'No speech detected. Nothing was submitted. Try again.';
        } catch (error) {
            status.textContent = error.message + ' Nothing was submitted to chat.';
            record('transcription error');
        } finally { sending = false; reset(); }
    }
    async function submit(session) {
        if (session.submitted || session.cancelled || !session.final.trim()) return;
        session.submitted = true;
        sending = true;
        reset();
        status.textContent = 'Sending automatically…';
        record('submit');
        const outgoing = [...messages, { role: 'user', content: session.final.trim() }].slice(-20);
        try {
            const result = await fetch(page.dataset.chatUrl, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: outgoing, context }),
            });
            const data = await result.json();
            if (!result.ok) throw new Error(data.error || 'Chat request failed.');
            response.textContent = data.message || 'Done.';
            messages = [...outgoing, { role: 'assistant', content: data.message || 'Done.' }].slice(-20);
            if (context.mode === 'workout_set' && data.tool_calls?.some(tool => tool.name === 'log_set')) {
                context.set_number += 1;
            }
            status.textContent = 'Submitted. Tap the microphone for another command.';
            record('response received');
        } catch (error) {
            response.textContent = error.message;
            status.textContent = 'Submission failed. Check the workout before repeating a command; it may have been saved.';
            record('submission error');
        } finally {
            sending = false;
            reset();
        }
    }
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !AudioContext) {
        mic.disabled = true;
        status.textContent = 'Microphone recording requires Safari over HTTPS.';
        return;
    }
    status.textContent = 'Ready. Tap the microphone and allow access.';
    mic.addEventListener('click', async () => {
        if (sending) return;
        if (current) { stop(current); return; }
        const session = { chunks: [], final: '', cancelled: false, submitted: false };
        current = session;
        mic.disabled = true; cancel.hidden = false;
        status.textContent = 'Opening microphone…';
        try {
            // Create/resume during the tap so Safari grants Web Audio activation.
            session.audio = new AudioContext();
            const resumed = session.audio.resume();
            session.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
            await resumed;
            if (current !== session || session.cancelled) { release(session); return; }
            const mime = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm'].find(type => window.MediaRecorder.isTypeSupported(type));
            session.recorder = new window.MediaRecorder(session.stream, mime ? { mimeType: mime } : undefined);
            session.recorder.ondataavailable = event => { if (event.data.size) session.chunks.push(event.data); };
            session.recorder.onstop = () => transcribe(session);
            session.recorder.onerror = () => { if (current === session) { sending = false; discard('Recording failed. Nothing was submitted.'); } };
            session.source = session.audio.createMediaStreamSource(session.stream);
            const analyser = session.audio.createAnalyser();
            analyser.fftSize = 2048;
            session.source.connect(analyser);
            const samples = new Float32Array(analyser.fftSize);
            const started = Date.now();
            let voiceMs = 0, lastVoice = started, previous = started;
            session.monitor = setInterval(() => {
                if (current !== session || session.stopping) return;
                analyser.getFloatTimeDomainData(samples);
                const now = Date.now();
                const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
                if (rms > 0.018) { voiceMs += Math.min(now - previous, 150); lastVoice = now; }
                previous = now;
                if (voiceMs >= 250 && now - lastVoice >= 1800) { record('silence detected'); stop(session); }
                else if (!voiceMs && now - started > 10000) discard('No speech detected. Nothing was submitted. Try again.');
            }, 100);
            session.timer = setTimeout(() => { if (current === session) stop(session); }, 45000);
            session.recorder.start();
            record('recording started');
            mic.disabled = false;
            mic.querySelector('span').textContent = 'Finish recording';
            mic.setAttribute('aria-label', 'Finish recording');
            page.classList.add('voice-poc-listening');
            status.textContent = 'Recording. Pause for about two seconds to submit.';
            transcript.textContent = 'Recording audio…';
        } catch (error) {
            record('microphone error: ' + error.name);
            if (current === session) discard('Could not record. Check Safari microphone permission and try again.');
            else release(session);
        }
    });
    cancel.addEventListener('click', () => discard('Cancelled. Nothing was submitted.'));
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && current && !current.stopping) discard('Recording cancelled when the page became hidden.');
    });
})();
