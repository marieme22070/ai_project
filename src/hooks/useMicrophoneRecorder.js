import { useCallback, useEffect, useRef, useState } from "react";

function pickMimeType() {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

export function useMicrophoneRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [durationSec, setDurationSec] = useState(0);
  const [error, setError] = useState(null);
  const [level, setLevel] = useState(0);

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const durationRef = useRef(0);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const mimeTypeRef = useRef("audio/webm");

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => () => stopTracks(), [stopTracks]);

  const startLevelMeter = useCallback((stream) => {
    try {
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        setLevel(Math.min(100, Math.round((avg / 128) * 100)));
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      /* visualisation optionnelle */
    }
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    setDurationSec(0);
    setLevel(0);

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Votre navigateur ne supporte pas l'accès au microphone.");
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      startLevelMeter(stream);

      const mimeType = pickMimeType();
      mimeTypeRef.current = mimeType || "audio/webm";
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.start(250);
      setIsRecording(true);

      const started = Date.now();
      timerRef.current = setInterval(() => {
        const sec = Math.floor((Date.now() - started) / 1000);
        durationRef.current = sec;
        setDurationSec(sec);
      }, 200);

      return true;
    } catch (err) {
      if (err.name === "NotAllowedError") {
        setError("Accès au microphone refusé. Autorisez le micro dans les paramètres du navigateur.");
      } else if (err.name === "NotFoundError") {
        setError("Aucun microphone détecté sur cet appareil.");
      } else {
        setError(err.message || "Impossible d'activer le microphone.");
      }
      stopTracks();
      return false;
    }
  }, [startLevelMeter, stopTracks]);

  const stopRecording = useCallback(() => {
    return new Promise((resolve, reject) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        stopTracks();
        setIsRecording(false);
        reject(new Error("Aucun enregistrement en cours."));
        return;
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        const ext = mimeTypeRef.current.includes("mp4") ? "mp4" : "webm";
        const file = new File([blob], `recording.${ext}`, { type: blob.type });
        stopTracks();
        setIsRecording(false);
        setLevel(0);
        chunksRef.current = [];
        mediaRecorderRef.current = null;
        resolve({ file, durationSec: durationRef.current, blob });
      };

      recorder.stop();
    });
  }, [stopTracks]);

  const cancelRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      recorder.stop();
    }
    chunksRef.current = [];
    mediaRecorderRef.current = null;
    stopTracks();
    setIsRecording(false);
    setLevel(0);
    setDurationSec(0);
  }, [stopTracks]);

  return {
    isRecording,
    durationSec,
    error,
    level,
    startRecording,
    stopRecording,
    cancelRecording,
    setError,
  };
}
