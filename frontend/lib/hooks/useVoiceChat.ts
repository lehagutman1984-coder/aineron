"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type VoiceState = "idle" | "recording" | "processing" | "playing" | "error";

interface VoiceMessage {
  type: "transcript" | "reply" | "error";
  text: string;
}

const WS_BASE = typeof window !== "undefined"
  ? (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host
  : "";

/**
 * Half-duplex voice chat hook.
 * Connects to VoiceConsumer, handles MediaRecorder → WS → audio playback.
 *
 * Usage:
 *   const { state, start, stop, messages } = useVoiceChat({ chatId: 42 });
 */
export function useVoiceChat({ chatId }: { chatId: number }) {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/voice/${chatId}/`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        const msg = JSON.parse(event.data) as { transcript?: string; reply?: string; error?: string };
        if (msg.transcript) {
          setMessages((prev) => [...prev, { type: "transcript", text: msg.transcript! }]);
        }
        if (msg.reply) {
          setMessages((prev) => [...prev, { type: "reply", text: msg.reply! }]);
        }
        if (msg.error) {
          setMessages((prev) => [...prev, { type: "error", text: msg.error! }]);
          setVoiceState("error");
        }
      } else if (event.data instanceof ArrayBuffer) {
        // Play received audio
        await playAudio(event.data);
        setVoiceState("idle");
      }
    };

    ws.onclose = () => setVoiceState("idle");

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [chatId]);

  async function playAudio(data: ArrayBuffer) {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
    }
    const ctx = audioCtxRef.current;
    const buffer = await ctx.decodeAudioData(data);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start();
    setVoiceState("playing");
    source.onended = () => setVoiceState("idle");
  }

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        blob.arrayBuffer().then((buf) => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(buf);
            setVoiceState("processing");
          }
        });
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start();
      setVoiceState("recording");
    } catch {
      setVoiceState("error");
    }
  }, []);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
  }, []);

  return { voiceState, messages, start, stop };
}
