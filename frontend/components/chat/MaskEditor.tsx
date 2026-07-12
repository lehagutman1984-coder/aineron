"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Eraser, Check, Loader2, Brush, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { uploadFile } from "@/lib/api/client";

// Конвенция маски: БЕЛОЕ = область редактирования, ЧЁРНОЕ = сохранить.
// На экспорте белые штрихи накладываются на чёрный фон → бинарная PNG-маска.

type BrushKey = "small" | "medium" | "large";
type DrawMode = "draw" | "erase";

const BRUSH_RATIO: Record<BrushKey, number> = {
  small: 0.03,
  medium: 0.06,
  large: 0.1,
};

interface Props {
  imageUrl: string;
  chatId: number;
  applying: boolean;
  onApply: (maskUrl: string) => void;
}

export function MaskEditor({ imageUrl, chatId, applying, onApply }: Props) {
  const t = useTranslations("chat.maskEditor");
  const BRUSH_LABEL: Record<BrushKey, string> = {
    small: t("brushSizeSmall"),
    medium: t("brushSizeMedium"),
    large: t("brushSizeLarge"),
  };

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const drawingRef = useRef(false);
  const lastRef = useRef<{ x: number; y: number } | null>(null);
  const historyRef = useRef<ImageData[]>([]);

  const [brush, setBrush] = useState<BrushKey>("medium");
  const [mode, setMode] = useState<DrawMode>("draw");
  const [ready, setReady] = useState(false);
  const [hasStrokes, setHasStrokes] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Превью курсора: позиция в px относительно контейнера + диаметр в display-px
  const [cursor, setCursor] = useState<{ x: number; y: number; d: number } | null>(null);

  const syncCanvasSize = useCallback(() => {
    const img = imgRef.current;
    const canvas = canvasRef.current;
    if (!img || !canvas) return;
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    if (w && h && (canvas.width !== w || canvas.height !== h)) {
      canvas.width = w;
      canvas.height = h;
    }
    setReady(Boolean(w && h));
  }, []);

  useEffect(() => {
    setReady(false);
    setHasStrokes(false);
    setError(null);
    historyRef.current = [];
    setCursor(null);
  }, [imageUrl]);

  const saveSnapshot = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    historyRef.current = [
      ...historyRef.current.slice(-19),
      ctx.getImageData(0, 0, canvas.width, canvas.height),
    ];
  }, []);

  const handleUndo = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || historyRef.current.length === 0) return;
    const prev = historyRef.current[historyRef.current.length - 1];
    historyRef.current = historyRef.current.slice(0, -1);
    ctx.putImageData(prev, 0, 0);
    setHasStrokes(historyRef.current.length > 0);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        handleUndo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleUndo]);

  const brushPx = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return 20;
    const base = Math.max(canvas.width, canvas.height);
    return Math.max(4, Math.round(base * BRUSH_RATIO[brush]));
  }, [brush]);

  // Координаты в системе canvas (натуральный размер)
  const toCanvasCoords = useCallback((e: React.PointerEvent) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / rect.width;
    const sy = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * sx,
      y: (e.clientY - rect.top) * sy,
    };
  }, []);

  // Обновить позицию курсора-превью (display-координаты относительно canvas)
  const updateCursor = useCallback(
    (e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const scale = rect.width / canvas.width;
      const d = Math.max(4, brushPx() * scale);
      setCursor({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        d,
      });
    },
    [brushPx]
  );

  const drawDot = useCallback(
    (x: number, y: number) => {
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) return;
      const r = brushPx() / 2;
      ctx.globalCompositeOperation = mode === "erase" ? "destination-out" : "source-over";
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalCompositeOperation = "source-over";
    },
    [brushPx, mode]
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!ready) return;
      e.preventDefault();
      saveSnapshot();
      (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
      drawingRef.current = true;
      const p = toCanvasCoords(e);
      lastRef.current = p;
      drawDot(p.x, p.y);
      setHasStrokes(true);
    },
    [ready, toCanvasCoords, drawDot, saveSnapshot]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      updateCursor(e);
      if (!drawingRef.current) return;
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) return;
      const p = toCanvasCoords(e);
      const last = lastRef.current ?? p;
      ctx.globalCompositeOperation = mode === "erase" ? "destination-out" : "source-over";
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = brushPx();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.globalCompositeOperation = "source-over";
      lastRef.current = p;
    },
    [updateCursor, toCanvasCoords, brushPx, mode]
  );

  const handlePointerUp = useCallback(() => {
    drawingRef.current = false;
    lastRef.current = null;
  }, []);

  const handlePointerLeave = useCallback(() => {
    drawingRef.current = false;
    lastRef.current = null;
    setCursor(null);
  }, []);

  const handleClear = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    historyRef.current = [];
    setHasStrokes(false);
  }, []);

  // Экспорт: белые штрихи на чёрном фоне → бинарная PNG-маска
  const handleApply = useCallback(async () => {
    const canvas = canvasRef.current;
    if (!canvas || !hasStrokes) return;
    setError(null);

    const out = document.createElement("canvas");
    out.width = canvas.width;
    out.height = canvas.height;
    const octx = out.getContext("2d");
    if (!octx) return;
    octx.fillStyle = "#000000";
    octx.fillRect(0, 0, out.width, out.height);
    octx.drawImage(canvas, 0, 0);

    const blob: Blob | null = await new Promise((resolve) =>
      out.toBlob((b) => resolve(b), "image/png")
    );
    if (!blob) {
      setError(t("errorMaskFailed"));
      return;
    }

    setUploading(true);
    try {
      const file = new File([blob], "mask.png", { type: "image/png" });
      const res = await uploadFile(chatId, file);
      onApply(res.url);
    } catch {
      setError(t("errorUploadFailed"));
    } finally {
      setUploading(false);
    }
  }, [hasStrokes, chatId, onApply, t]);

  return (
    <div className="space-y-3">
      {/* Контейнер: изображение + canvas-маска + курсор-превью */}
      <div
        ref={containerRef}
        className="relative mx-auto w-fit overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.04)]"
      >
        {/* Исходное изображение — видно через полупрозрачный оверлей */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={imageUrl}
          alt={t("imageAlt")}
          onLoad={syncCanvasSize}
          className="block max-h-[55vh] w-auto max-w-full select-none"
          draggable={false}
        />

        {/* Canvas маски: полупрозрачный тёмный фон, белые штрихи = выделение */}
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerLeave}
          className="absolute inset-0 h-full w-full touch-none"
          style={{
            background: "rgba(0,0,0,0.38)",
            cursor: "none",
          }}
        />

        {/* Курсор-превью: кольцо нужного размера следует за указателем */}
        {cursor && ready && (
          <div
            className="pointer-events-none absolute rounded-full border-2"
            style={{
              left: cursor.x,
              top: cursor.y,
              width: cursor.d,
              height: cursor.d,
              transform: "translate(-50%, -50%)",
              borderColor: mode === "erase" ? "#ff4444" : "white",
              boxShadow: mode === "erase"
                ? "0 0 0 1px rgba(0,0,0,0.5), inset 0 0 0 1px rgba(255,68,68,0.3)"
                : "0 0 0 1px rgba(0,0,0,0.6)",
              opacity: 0.9,
            }}
          />
        )}

        {!ready && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 size={20} className="animate-spin text-white" />
          </div>
        )}
      </div>

      <div className="space-y-0.5">
        <p className="text-[14px] text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
          {mode === "draw" ? (
            <>
              <span className="font-medium text-[#1A1A1A] dark:text-white">{t("brushLabel")}</span>
              {" "}{t("brushHint")}
            </>
          ) : (
            <>
              <span className="font-medium text-[#e74c3c]">{t("eraseLabel")}</span>
              {" "}{t("eraseHint")}
            </>
          )}
        </p>
        <p className="text-[13px] text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)]">
          {t("modelHint")}
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Кисть / Ластик */}
        <div className="flex items-center gap-1 rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.03)] p-1">
          <button
            type="button"
            onClick={() => setMode("draw")}
            title={t("drawTooltip")}
            className={`rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors flex items-center gap-1 ${
              mode === "draw"
                ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-white"
                : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.5)] dark:hover:text-white"
            }`}
          >
            <Brush size={12} />
            {t("drawButton")}
          </button>
          <button
            type="button"
            onClick={() => setMode("erase")}
            title={t("eraseTooltip")}
            className={`rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors flex items-center gap-1 ${
              mode === "erase"
                ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-white"
                : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.5)] dark:hover:text-white"
            }`}
          >
            <Eraser size={12} />
            {t("eraseButton")}
          </button>
        </div>

        {/* Размер кисти */}
        <div className="flex items-center gap-1 rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.03)] p-1">
          <Brush size={13} className="ms-1 text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]" />
          {(Object.keys(BRUSH_RATIO) as BrushKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setBrush(k)}
              className={`rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors ${
                brush === k
                  ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-white"
                  : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.5)] dark:hover:text-white"
              }`}
            >
              {BRUSH_LABEL[k]}
            </button>
          ))}
        </div>

        {/* Отменить */}
        <button
          type="button"
          onClick={handleUndo}
          disabled={historyRef.current.length === 0}
          title={t("undoTooltip")}
          className="flex h-9 items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-40 dark:border-[rgba(236,236,236,0.12)] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(236,236,236,0.06)]"
        >
          <RotateCcw size={14} />
          {t("undoButton")}
        </button>

        {/* Очистить */}
        <button
          type="button"
          onClick={handleClear}
          disabled={!hasStrokes}
          className="flex h-9 items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-40 dark:border-[rgba(236,236,236,0.12)] dark:text-[rgba(236,236,236,0.65)] dark:hover:bg-[rgba(236,236,236,0.06)]"
        >
          <Eraser size={14} />
          {t("clearButton")}
        </button>

        {/* Применить */}
        <button
          type="button"
          onClick={handleApply}
          disabled={!hasStrokes || uploading || applying}
          className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 text-[14px] font-medium text-white transition-colors hover:bg-[#C4623E] disabled:opacity-40"
        >
          {uploading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          {t("applyButton")}
        </button>
      </div>

      {error && <p className="text-[14px] text-[#e74c3c]">{error}</p>}
    </div>
  );
}
