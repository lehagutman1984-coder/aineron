"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Eraser, Check, Loader2, Brush } from "lucide-react";
import { uploadFile } from "@/lib/api/client";

// Конвенция маски: БЕЛОЕ = область редактирования (что менять / дорисовать),
// ЧЁРНОЕ = сохранить. Совпадает с _prepare_outpaint_canvas на бэкенде.
// Кисть рисуется непрозрачным белым в полном разрешении исходника; на экране
// полотно затемнено через CSS (display-only), а на экспорте белые штрихи
// накладываются на сплошной чёрный фон → бинарная маска PNG.

type BrushKey = "small" | "medium" | "large";

const BRUSH_RATIO: Record<BrushKey, number> = {
  small: 0.03,
  medium: 0.06,
  large: 0.1,
};

const BRUSH_LABEL: Record<BrushKey, string> = {
  small: "Маленькая",
  medium: "Средняя",
  large: "Большая",
};

interface Props {
  imageUrl: string;
  chatId: number;
  applying: boolean;
  onApply: (maskUrl: string) => void;
}

export function MaskEditor({ imageUrl, chatId, applying, onApply }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const drawingRef = useRef(false);
  const lastRef = useRef<{ x: number; y: number } | null>(null);

  const [brush, setBrush] = useState<BrushKey>("medium");
  const [ready, setReady] = useState(false);
  const [hasStrokes, setHasStrokes] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Синхронизируем разрешение полотна с натуральным размером изображения
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
  }, [imageUrl]);

  const brushPx = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return 20;
    const base = Math.max(canvas.width, canvas.height);
    return Math.max(4, Math.round(base * BRUSH_RATIO[brush]));
  }, [brush]);

  // Переводим координаты указателя в систему координат полотна (натуральный размер)
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

  const drawDot = useCallback(
    (x: number, y: number) => {
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) return;
      const r = brushPx() / 2;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    },
    [brushPx]
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (!ready) return;
      e.preventDefault();
      (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
      drawingRef.current = true;
      const p = toCanvasCoords(e);
      lastRef.current = p;
      drawDot(p.x, p.y);
      setHasStrokes(true);
    },
    [ready, toCanvasCoords, drawDot]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!drawingRef.current) return;
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) return;
      const p = toCanvasCoords(e);
      const last = lastRef.current ?? p;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = brushPx();
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      lastRef.current = p;
    },
    [toCanvasCoords, brushPx]
  );

  const handlePointerUp = useCallback(() => {
    drawingRef.current = false;
    lastRef.current = null;
  }, []);

  const handleClear = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasStrokes(false);
  }, []);

  // Экспорт: белые штрихи поверх сплошного чёрного фона → бинарная PNG-маска
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
      setError("Не удалось сформировать маску");
      return;
    }

    setUploading(true);
    try {
      const file = new File([blob], "mask.png", { type: "image/png" });
      const res = await uploadFile(chatId, file);
      onApply(res.url);
    } catch {
      setError("Ошибка загрузки маски");
    } finally {
      setUploading(false);
    }
  }, [hasStrokes, chatId, onApply]);

  return (
    <div className="space-y-3">
      {/* Canvas overlay поверх изображения.
          Контейнер ужимается до отрисованного размера картинки (w-fit + max-w-full),
          а холст с inset-0 точно совпадает с ним — иначе для не-квадратных изображений
          object-contain создаёт поля и штрихи смещаются. */}
      <div className="relative mx-auto w-fit overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.04)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={imageUrl}
          alt="Изображение для маски"
          onLoad={syncCanvasSize}
          className="block max-h-[55vh] w-auto max-w-full select-none"
          draggable={false}
        />
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          className="absolute inset-0 h-full w-full cursor-crosshair touch-none"
          style={{ background: "rgba(0,0,0,0.45)" }}
        />
        {!ready && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 size={20} className="animate-spin text-white" />
          </div>
        )}
      </div>

      <p className="text-[12px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.5)]">
        Закрасьте белым области, которые нужно изменить
      </p>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.03)] p-1">
          <Brush size={13} className="ml-1 text-[rgba(13,13,13,0.45)]" />
          {(Object.keys(BRUSH_RATIO) as BrushKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setBrush(k)}
              className={`rounded-[6px] px-2.5 py-1 text-[12px] font-medium transition-colors ${
                brush === k
                  ? "bg-white text-[#0d0d0d] shadow-sm"
                  : "text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d]"
              }`}
            >
              {BRUSH_LABEL[k]}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={handleClear}
          disabled={!hasStrokes}
          className="flex h-9 items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 text-[12px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-40"
        >
          <Eraser size={14} />
          Очистить
        </button>

        <button
          type="button"
          onClick={handleApply}
          disabled={!hasStrokes || uploading || applying}
          className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#0a7cff] px-4 text-[12px] font-medium text-white transition-colors hover:bg-[#0066cc] disabled:opacity-40"
        >
          {uploading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          Применить маску
        </button>
      </div>

      {error && <p className="text-[12px] text-[#e74c3c]">{error}</p>}
    </div>
  );
}
