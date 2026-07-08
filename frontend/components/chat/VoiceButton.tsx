"use client";

import { useState, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Mic, MicOff, Loader } from "lucide-react";
import { transcribeAudio } from "@/lib/api/client";

type RecordState = "idle" | "recording" | "transcribing";

function getSupportedMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  if (typeof MediaRecorder === "undefined") return "";
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
}

export function VoiceButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("chat.voiceButton");
  const [state, setState] = useState<RecordState>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const isSupported =
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia;

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const startRecording = useCallback(async () => {
    setError(null);
    const mimeType = getSupportedMimeType();
    if (!mimeType) {
      setError(t("recordingNotSupported"));
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const name = (err as Error).name;
      setError(
        name === "NotAllowedError"
          ? t("micAccessDenied")
          : name === "NotFoundError"
          ? t("micNotFound")
          : t("micError")
      );
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const recorder = new MediaRecorder(stream, { mimeType });
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      stopStream();
      const blob = new Blob(chunksRef.current, { type: mimeType });
      chunksRef.current = [];

      if (blob.size < 500) {
        setState("idle");
        return;
      }

      setState("transcribing");
      try {
        const text = await transcribeAudio(blob);
        if (text.trim()) onTranscript(text.trim());
        else setError(t("nothingRecognized"));
      } catch {
        setError(t("recognitionFailed"));
      } finally {
        setState("idle");
      }
    };

    recorder.start();
    setState("recording");
  }, [onTranscript, t]);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
  }, []);

  const handleClick = () => {
    if (!isSupported || disabled || state === "transcribing") return;
    setError(null);
    if (state === "recording") stopRecording();
    else startRecording();
  };

  if (!isSupported) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || state === "transcribing"}
        title={
          state === "recording"
            ? t("titleStopRecording")
            : state === "transcribing"
            ? t("titleTranscribing")
            : t("titleVoiceInput")
        }
        className={[
          "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-medium transition-all",
          state === "recording"
            ? "bg-[rgba(231,76,60,0.12)] text-[#e74c3c]"
            : state === "transcribing"
            ? "text-[#D97757]"
            : "text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#EDE8E3]",
          disabled || state === "transcribing" ? "cursor-not-allowed opacity-40" : "",
        ].join(" ")}
      >
        {state === "transcribing" ? (
          <Loader size={12} className="animate-spin" />
        ) : state === "recording" ? (
          <>
            <MicOff size={12} />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#e74c3c]" />
          </>
        ) : (
          <Mic size={12} />
        )}
        {state === "recording"
          ? t("stop")
          : state === "transcribing"
          ? t("transcribing")
          : t("voice")}
      </button>

      {error && (
        <div
          className="absolute bottom-full left-0 mb-2 whitespace-nowrap rounded-[7px] px-2.5 py-1.5 text-[13px] text-white"
          style={{ background: "var(--surface-inverse)", boxShadow: "0 4px 12px rgba(0,0,0,0.18)" }}
        >
          {error}
          <div
            className="absolute left-3 top-full h-0 w-0"
            style={{ borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: "5px solid var(--surface-inverse)" }}
          />
        </div>
      )}
    </div>
  );
}
