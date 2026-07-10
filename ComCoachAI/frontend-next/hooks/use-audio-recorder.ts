"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadRecording, saveRecording } from "@/lib/audio-store";

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac", "audio/wav"];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionFor(type: string) {
  if (type.includes("mp4")) return "m4a";
  if (type.includes("aac")) return "aac";
  if (type.includes("wav")) return "wav";
  return "webm";
}

export function useAudioRecorder() {
  const [status, setStatus] = useState<"idle" | "requesting" | "recording" | "stopped" | "error">("idle");
  const [recording, setRecording] = useState<{ blob: Blob; url: string; filename: string } | null>(null);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  const support = useMemo(() => {
    const secure = typeof window === "undefined" || window.isSecureContext || window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    const media = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
    const recorder = typeof MediaRecorder !== "undefined";
    return { secure, media, recorder, supported: secure && media && recorder };
  }, []);

  useEffect(() => {
    loadRecording().then((saved) => {
      if (saved?.blob) {
        setRecording({
          blob: saved.blob,
          filename: saved.filename,
          url: URL.createObjectURL(saved.blob),
        });
        setStatus("stopped");
      }
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (recording?.url) URL.revokeObjectURL(recording.url);
    };
  }, [recording?.url]);

  const start = useCallback(async () => {
    setError("");
    if (!support.secure) {
      setStatus("error");
      setError("Microphone access requires HTTPS, localhost, or 127.0.0.1.");
      return;
    }
    if (!support.media || !support.recorder) {
      setStatus("error");
      setError("This browser does not support native audio recording.");
      return;
    }

    try {
      setStatus("requesting");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];
      streamRef.current = stream;
      recorderRef.current = recorder;
      setSeconds(0);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        const filename = `recording.${extensionFor(type)}`;
        const url = URL.createObjectURL(blob);
        await saveRecording(blob, filename);
        setRecording((previous) => {
          if (previous?.url) URL.revokeObjectURL(previous.url);
          return { blob, filename, url };
        });
        setStatus("stopped");
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start(1_000);
      setStatus("recording");
      timerRef.current = window.setInterval(() => setSeconds((value) => value + 1), 1_000);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Could not start microphone recording.");
      streamRef.current?.getTracks().forEach((track) => track.stop());
    }
  }, [support]);

  const stop = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  const setUploadedFile = useCallback(async (file: File) => {
    const url = URL.createObjectURL(file);
    await saveRecording(file, file.name);
    setRecording((previous) => {
      if (previous?.url) URL.revokeObjectURL(previous.url);
      return { blob: file, filename: file.name, url };
    });
    setStatus("stopped");
  }, []);

  return {
    status,
    recording,
    error,
    seconds,
    support,
    start,
    stop,
    setUploadedFile,
  };
}
