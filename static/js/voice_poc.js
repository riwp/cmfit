(() => {
    const page = document.getElementById('voice-poc');
    const mic = document.getElementById('voice-poc-mic');
    const cancel = document.getElementById('voice-poc-cancel');
    const status = document.getElementById('voice-poc-status');
    const transcript = document.getElementById('voice-poc-transcript');
    const response = document.getElementById('voice-poc-response');
    const events = document.getElementById('voice-poc-events');
    const context = JSON.parse(document.getElementById('voice-poc-context').textContent);
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let current = null;
    let sending = false;
    let messages = [];
    const record = name => { events.textContent += `${new Date().toLocaleTimeString()} ${name}\n`; };
    function reset() {
        mic.disabled = sending;
        mic.querySelector('span').textContent = 'Start recording';
        mic.setAttribute('aria-label', 'Start recording');
        cancel.hidden = true;
        page.classList.remove('voice-poc-listening');
    }
    function discard(message) {
        if (!current) return;
        const session = current;
        session.cancelled = true;
        clearTimeout(session.timer);
        current = null;
        session.recognition.abort();
        reset();
        status.textContent = message;
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
    if (!Recognition || !window.isSecureContext) {
        mic.disabled = true;
        status.textContent = !window.isSecureContext ? 'Open this page over HTTPS to use the microphone.'
            : 'Speech recognition is unavailable. Check Siri/Dictation settings and open in Safari.';
        return;
    }
    status.textContent = 'Ready. Tap the microphone and allow permissions if asked.';
    mic.addEventListener('click', () => {
        if (sending) return;
        if (current) { current.recognition.stop(); record('manual stop'); return; }
        const recognition = new Recognition();
        const session = { recognition, final: '', submitted: false, cancelled: false, timer: null };
        current = session;
        recognition.lang = 'en-US';
        recognition.continuous = false;
        recognition.interimResults = true;
        transcript.textContent = 'Listening…';
        response.textContent = 'Waiting for this command.';
        cancel.hidden = false;
        mic.querySelector('span').textContent = 'Finish recording';
        mic.setAttribute('aria-label', 'Finish recording');
        status.textContent = 'Starting microphone…';
        recognition.onstart = () => {
            if (current !== session) return;
            record('start'); page.classList.add('voice-poc-listening');
            status.textContent = 'Listening. Finish speaking to submit automatically.';
        };
        recognition.onresult = event => {
            if (current !== session || session.cancelled) return;
            let final = '', interim = '';
            for (let i = 0; i < event.results.length; i++) {
                if (event.results[i].isFinal) final += event.results[i][0].transcript + ' ';
                else interim += event.results[i][0].transcript + ' ';
            }
            session.final = final.trim();
            transcript.textContent = (final + interim).trim();
            record(final ? 'final transcript' : 'interim transcript');
            if (session.final) recognition.stop();
        };
        recognition.onspeechend = () => { if (current === session) { record('speech ended'); recognition.stop(); } };
        recognition.onerror = event => {
            if (current !== session) return;
            record(`error: ${event.error}`);
            discard(`Recognition failed (${event.error}). Nothing was submitted. Check permissions, Siri/Dictation and your connection.`);
        };
        recognition.onend = () => {
            record('end');
            if (current !== session) return;
            clearTimeout(session.timer); current = null; reset();
            if (session.final) submit(session);
            else status.textContent = 'No final transcript received. Nothing was submitted. Tap to try again.';
        };
        session.timer = setTimeout(() => {
            if (current === session) discard('Recognition timed out. Nothing was submitted. Try again or reload Safari.');
        }, 45000);
        try { recognition.start(); record('start requested'); }
        catch (error) { record(error.name); discard('Could not start recognition. Check Safari microphone permissions.'); }
    });
    cancel.addEventListener('click', () => { record('cancel'); discard('Cancelled. Nothing was submitted.'); });
    document.addEventListener('visibilitychange', () => { if (document.hidden) discard('Recording cancelled when the page became hidden.'); });
})();
