// Shared voice for the form and the chat. Nothing listens or speaks unless the user asks.
// Default: the browser's own speech recognition and voices (free). If the server has VOICE_ENGINE=openai,
// a "natural voice" option (OpenAI text to speech) and OpenAI transcription for browsers without recognition.
window.pfaVoice = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  let engine = 'browser', audio = null, active = null;
  const ready = fetch('/api/voice/config').then(r => r.json()).then(c => { engine = c.engine; }).catch(() => {});

  const canListen = () => !!SR || (engine === 'openai' && !!window.MediaRecorder && !!navigator.mediaDevices);
  const canSpeak = () => !!window.speechSynthesis || engine === 'openai';
  const natural = { get: () => engine === 'openai' && store.get('pfa-natural-voice') === '1',
                    set: v => store.set('pfa-natural-voice', v ? '1' : '0') };

  function plain(text) {
    return String(text).replace(/<[^>]+>/g, ' ').replace(/\*\*/g, '').replace(/^[-•]\s+/gm, '')
      .replace(/^Live data:.*$/m, '').replace(/₹\s?/g, 'rupees ').replace(/\s+/g, ' ').trim();
  }

  function stopSpeaking() {
    if (window.speechSynthesis) speechSynthesis.cancel();
    if (audio) { audio.pause(); audio = null; }
  }

  // Resolves when the voice has finished (so the form can listen right after a question).
  async function speak(text) {
    stopSpeaking();
    const words = plain(text);
    if (!words) return;
    if (natural.get()) {
      try {
        const r = await fetch('/api/voice/speak', { method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-PFA': '1' }, body: JSON.stringify({ text }) });
        if (r.ok) {
          audio = new Audio(URL.createObjectURL(await r.blob()));
          await new Promise(res => { audio.onended = res; audio.onerror = res; audio.play().catch(res); });
          return;
        }
      } catch (e) { /* fall back to the browser voice */ }
    }
    if (!window.speechSynthesis) return;
    await new Promise(res => {
      const u = new SpeechSynthesisUtterance(words);
      const voices = speechSynthesis.getVoices();
      u.voice = voices.find(v => v.lang === 'en-IN') || voices.find(v => v.lang && v.lang.startsWith('en')) || null;
      u.lang = u.voice ? u.voice.lang : 'en-IN'; u.rate = 1.02;
      u.onend = res; u.onerror = res;
      speechSynthesis.speak(u);
    });
  }

  // Why the browser's speech recognition stopped (v1.6.2: every error is explained, not only a blocked mic).
  const ERRORS = {
    'not-allowed': 'Microphone access is blocked for this site.',
    'service-not-allowed': "This browser doesn't allow speech recognition here (Brave and some privacy browsers turn it off).",
    'network': "The browser's speech service couldn't be reached (Brave and some browsers block it, or you may be offline).",
    'no-speech': "I didn't hear anything - check the right microphone is selected and not muted.",
    'audio-capture': "No microphone was found - check your computer's sound input settings.",
    'language-not-supported': "Speech recognition for English (India) isn't available in this browser.",
  };
  let lastError = '';

  // Resolves with what was said ('' if nothing). onInterim shows words as they come (browser engine).
  // continuous: keep listening through pauses until stopped or maxMs (for dictating a paragraph).
  function listen({ onInterim, maxMs = 8000, continuous = false } = {}) {
    stopSpeaking();
    lastError = ''; lastAlert = '';
    if (SR) {
      return new Promise(res => {
        const rec = new SR();
        rec.lang = 'en-IN'; rec.interimResults = true; rec.maxAlternatives = 1; rec.continuous = continuous;
        let finalText = '';
        rec.onresult = e => {
          let interim = '';
          finalText = '';
          for (const r of e.results) { if (r.isFinal) finalText += r[0].transcript + ' '; else interim += r[0].transcript; }
          if (onInterim) onInterim((finalText + interim).trim());
        };
        rec.onerror = e => {
          if (e.error === 'aborted') return;
          lastError = e.error;
          alertOnce(ERRORS[e.error] || `Voice input stopped (${e.error}).`);
        };
        rec.onend = () => { active = null; res(finalText.trim().replace(/\s+/g, ' ')); };
        active = { stop: () => rec.stop() };
        rec.start();
        setTimeout(() => { try { rec.stop(); } catch (e) { /* ended */ } }, maxMs);
      });
    }
    return recordAndTranscribe(maxMs);
  }

  async function recordAndTranscribe(maxMs) {
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { alertOnce('Microphone access is blocked for this site.'); return ''; }
    const rec = new MediaRecorder(stream); const chunks = []; const t0 = Date.now();
    rec.ondataavailable = e => chunks.push(e.data);
    const done = new Promise(res => { rec.onstop = res; });
    active = { stop: () => { if (rec.state === 'recording') rec.stop(); } };
    rec.start();
    setTimeout(() => active && active.stop(), maxMs);
    await done;
    stream.getTracks().forEach(t => t.stop()); active = null;
    const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
    const r = await fetch('/api/voice/transcribe', { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': blob.type, 'X-PFA': '1', 'X-Audio-Seconds': String((Date.now() - t0) / 1000) }, body: blob });
    const j = await r.json().catch(() => ({}));
    if (j.error) alertOnce(j.error);
    return (j.text || '').trim();
  }

  function stopListening() { if (active) active.stop(); }
  const isListening = () => !!active;

  let lastAlert = '';
  function alertOnce(msg) {
    if (msg === lastAlert) return;
    lastAlert = msg;
    document.dispatchEvent(new CustomEvent('pfa-voice-note', { detail: msg }));
  }

  return { ready, canListen, canSpeak, speak, stopSpeaking, listen, stopListening, isListening, natural,
           get engine() { return engine; }, get lastError() { return lastError; } };
})();
