"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

interface Props {
  src: string;
  alt?: string;
  className?: string;
  maxZoom?: number;
}

export function ZoomableImage({ src, alt = "", className = "", maxZoom = 4 }: Props) {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      setScale((prev) => {
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const next = Math.min(maxZoom, Math.max(1, prev * delta));
        if (next === 1) setOffset({ x: 0, y: 0 });
        return next;
      });
    },
    [maxZoom]
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  const onMouseDown = (e: React.MouseEvent) => {
    if (scale <= 1) return;
    e.preventDefault();
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !dragStart.current) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    setOffset({ x: dragStart.current.ox + dx, y: dragStart.current.oy + dy });
  };

  const stopDrag = () => {
    setDragging(false);
    dragStart.current = null;
  };

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden select-none ${className}`}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={stopDrag}
      onMouseLeave={stopDrag}
      style={{ cursor: scale > 1 ? (dragging ? "grabbing" : "grab") : "default", touchAction: "none" }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        draggable={false}
        style={{
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          transformOrigin: "center center",
          transition: dragging ? "none" : "transform 0.15s ease",
          width: "100%",
          height: "100%",
          objectFit: "contain",
        }}
      />

      <div className="absolute bottom-2 right-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100">
        <button
          type="button"
          onClick={() => setScale((s) => Math.min(maxZoom, +(s * 1.3).toFixed(2)))}
          className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
          title="Увеличить"
        >
          <ZoomIn size={13} />
        </button>
        <button
          type="button"
          onClick={() => setScale((s) => { const n = Math.max(1, +(s / 1.3).toFixed(2)); if (n === 1) setOffset({ x: 0, y: 0 }); return n; })}
          className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
          title="Уменьшить"
        >
          <ZoomOut size={13} />
        </button>
        {scale > 1.05 && (
          <button
            type="button"
            onClick={reset}
            className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
            title="Сбросить масштаб"
          >
            <RotateCcw size={13} />
          </button>
        )}
      </div>
    </div>
  );
}
