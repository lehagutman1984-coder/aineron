"use client";

import { useEffect, useRef, useState } from "react";

interface UseYjsProjectOptions {
  projectId: number | null;
  enabled?: boolean;
}

interface YjsProjectState {
  connected: boolean;
  participantCount: number;
}

const WS_BASE = typeof window !== "undefined"
  ? (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host
  : "";

/**
 * Connects to the Yjs WebSocket consumer for a project.
 * Returns connection state and a send function for raw binary updates.
 *
 * Usage:
 *   const { connected, send } = useYjsProject({ projectId: 42 });
 */
export function useYjsProject({ projectId, enabled = true }: UseYjsProjectOptions) {
  const [state, setState] = useState<YjsProjectState>({ connected: false, participantCount: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Array<(data: ArrayBuffer) => void>>([]);

  useEffect(() => {
    if (!enabled || !projectId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/yjs/${projectId}/`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setState((s) => ({ ...s, connected: true }));
    ws.onclose = () => setState({ connected: false, participantCount: 0 });
    ws.onerror = () => setState((s) => ({ ...s, connected: false }));

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        for (const fn of listenersRef.current) fn(event.data);
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [projectId, enabled]);

  function send(data: Uint8Array) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }

  function onUpdate(fn: (data: ArrayBuffer) => void) {
    listenersRef.current.push(fn);
    return () => {
      listenersRef.current = listenersRef.current.filter((f) => f !== fn);
    };
  }

  return { ...state, send, onUpdate };
}
