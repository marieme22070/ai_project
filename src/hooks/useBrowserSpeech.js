/**
 * Reconnaissance vocale navigateur (fallback si Whisper / OpenAI indisponible).
 */
export function isBrowserSpeechSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function listenWithBrowserSpeech(lang = "fr-FR", timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      reject(new Error("Reconnaissance vocale du navigateur non supportée (utilisez Chrome/Edge)."));
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        recognition.stop();
        reject(new Error("Délai dépassé — parlez plus fort ou réessayez."));
      }
    }, timeoutMs);

    recognition.onresult = (event) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const text = event.results[0]?.[0]?.transcript?.trim();
      if (text) resolve(text);
      else reject(new Error("Aucune parole détectée."));
    };

    recognition.onerror = (event) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(event.error === "not-allowed" ? "Microphone refusé." : `Erreur micro: ${event.error}`));
    };

    recognition.onend = () => clearTimeout(timer);

    try {
      recognition.start();
    } catch (e) {
      clearTimeout(timer);
      reject(e);
    }
  });
}
