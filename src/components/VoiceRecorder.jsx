import { useState } from "react";
import { normalizeName, speechToName } from "../api/client";
import { listenWithBrowserSpeech, isBrowserSpeechSupported } from "../hooks/useBrowserSpeech";
import { useMicrophoneRecorder } from "../hooks/useMicrophoneRecorder";

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function isOpenAiBillingError(message) {
  const m = (message || "").toLowerCase();
  return (
    m.includes("facturation") ||
    m.includes("billing") ||
    m.includes("quota") ||
    m.includes("429") ||
    m.includes("openai")
  );
}

export default function VoiceRecorder({ languageHint, onResult, onError, disabled }) {
  const {
    isRecording,
    durationSec,
    error: micError,
    level,
    startRecording,
    stopRecording,
    cancelRecording,
    setError,
  } = useMicrophoneRecorder();

  const [processing, setProcessing] = useState(false);
  const [mode, setMode] = useState("whisper"); // whisper | browser

  const runBrowserFallback = async () => {
    if (!isBrowserSpeechSupported()) {
      throw new Error(
        "Whisper indisponible et reconnaissance navigateur non supportée. Utilisez Chrome/Edge ou activez OpenAI."
      );
    }
    setMode("browser");
    const text = await listenWithBrowserSpeech("fr-FR");
    const data = await normalizeName(text, languageHint);
    onResult?.({
      ...data,
      transcription: text,
      input: text,
      metadata: { ...(data.metadata || {}), transcription_source: "browser" },
    });
  };

  const handleToggle = async () => {
    if (disabled || processing) return;

    if (isRecording) {
      setProcessing(true);
      onError?.(null);
      setMode("whisper");

      try {
        const { file, durationSec: dur } = await stopRecording();
        if (file.size < 500) {
          throw new Error("Enregistrement trop court. Parlez au moins 1 seconde.");
        }

        try {
          const data = await speechToName(file, languageHint);
          onResult?.({ ...data, recording_duration: dur });
        } catch (whisperErr) {
          if (isOpenAiBillingError(whisperErr.message)) {
            onError?.(
              `${whisperErr.message} — Bascule vers reconnaissance navigateur…`
            );
            await runBrowserFallback();
            onError?.(null);
          } else {
            throw whisperErr;
          }
        }
      } catch (e) {
        if (!e.message?.includes("Bascule")) {
          onError?.(e.message || "Erreur de transcription");
        }
      } finally {
        setProcessing(false);
        setMode("whisper");
      }
    } else {
      setError(null);
      onError?.(null);
      await startRecording();
    }
  };

  const handleBrowserOnly = async () => {
    if (disabled || processing) return;
    setProcessing(true);
    onError?.(null);
    try {
      await runBrowserFallback();
    } catch (e) {
      onError?.(e.message);
    } finally {
      setProcessing(false);
      setMode("whisper");
    }
  };

  const handleCancel = () => {
    cancelRecording();
    setProcessing(false);
  };

  return (
    <div className="voice-recorder">
      <div className="voice-recorder-header">
        <h3>Parler au microphone</h3>
        <p className="voice-hint">
          Enregistrez puis relâchez — envoi automatique (Whisper + correction locale).
          {isBrowserSpeechSupported() && (
            <> Si OpenAI est inactif, le navigateur transcrit en secours.</>
          )}
        </p>
      </div>

      <div className="voice-controls">
        <button
          type="button"
          className={`mic-button ${isRecording ? "recording" : ""} ${processing ? "processing" : ""}`}
          onClick={handleToggle}
          disabled={disabled || processing}
          aria-label={isRecording ? "Arrêter et envoyer" : "Démarrer l'enregistrement"}
        >
          <span className="mic-icon" aria-hidden="true">
            {processing ? "⏳" : isRecording ? "■" : "🎤"}
          </span>
        </button>

        <div className="voice-status-text">
          {processing && mode === "browser" && (
            <span className="status-processing">Écoute navigateur + normalisation…</span>
          )}
          {processing && mode === "whisper" && (
            <span className="status-processing">Whisper + dictionnaire mauritanien…</span>
          )}
          {isRecording && !processing && (
            <>
              <span className="status-recording">Enregistrement en cours</span>
              <span className="status-timer">{formatTime(durationSec)}</span>
            </>
          )}
          {!isRecording && !processing && (
            <span className="status-idle">Appuyez pour parler le nom</span>
          )}
        </div>
      </div>

      {(isRecording || processing) && (
        <div className="level-bar-wrap">
          <div className="level-bar" style={{ width: `${isRecording ? level : 30}%` }} />
        </div>
      )}

      <div className="voice-secondary-actions">
        {isRecording && (
          <button type="button" className="btn-cancel-rec" onClick={handleCancel}>
            Annuler
          </button>
        )}
        {isBrowserSpeechSupported() && !isRecording && !processing && (
          <button type="button" className="btn-browser-speech" onClick={handleBrowserOnly}>
            Mode vocal navigateur (sans OpenAI)
          </button>
        )}
      </div>

      {micError && <p className="voice-error">{micError}</p>}
    </div>
  );
}
