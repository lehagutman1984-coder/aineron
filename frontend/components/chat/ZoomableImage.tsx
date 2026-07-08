"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { ZoomIn, ZoomOut, RotateCcw, X, Maximize2, Download } from "lucide-react";

interface Props {
  src: string;
  alt?: string;
  className?: string;
  maxZoom?: number;
}

function FullscreenOverlay({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  const t = useTranslations("chat.zoomableImage");
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    setScale((prev) => {
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const next = Math.min(8, Math.max(1, prev * delta));
      if (next === 1) setOffset({ x: 0, y: 0 });
      return next;
    });
  }, []);

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
    setOffset({ x: dragStart.current.ox + e.clientX - dragStart.current.x, y: dragStart.current.oy + e.clientY - dragStart.current.y });
  };
  const stopDrag = () => { setDragging(false); dragStart.current = null; };
  const reset = () => { setScale(1); setOffset({ x: 0, y: 0 }); };

  const handleDownload = () => {
    const a = document.createElement("a");
    a.href = src;
    a.download = "aineron-image.png";
    a.target = "_blank";
    a.rel = "noopener";
    a.click();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={containerRef}
        className="relative flex h-full w-full select-none items-center justify-center overflow-hidden"
        style={{ cursor: scale > 1 ? (dragging ? "grabbing" : "grab") : "default", touchAction: "none" }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
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
            maxWidth: "90vw",
            maxHeight: "90vh",
            objectFit: "contain",
          }}
        />
      </div>

      {/* Controls */}
      <div className="pointer-events-none absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-[10px] bg-black/60 p-1.5 backdrop-blur-md">
        {[
          { icon: ZoomOut, onClick: () => setScale((s) => { const n = Math.max(0.4, +(s / 1.3).toFixed(2)); if (n <= 1) setOffset({ x: 0, y: 0 }); return n; }), title: t("zoomOut"), cls: "pointer-events-auto" },
          { icon: ZoomIn, onClick: () => setScale((s) => Math.min(8, +(s * 1.3).toFixed(2))), title: t("zoomIn"), cls: "pointer-events-auto" },
          { icon: RotateCcw, onClick: reset, title: t("reset"), cls: `pointer-events-auto transition-opacity ${scale > 1.05 ? "opacity-100" : "opacity-30"}` },
          { icon: Download, onClick: handleDownload, title: t("download"), cls: "pointer-events-auto" },
        ].map(({ icon: Icon, onClick, title, cls }) => (
          <button
            key={title}
            type="button"
            onClick={(e) => { e.stopPropagation(); onClick(); }}
            title={title}
            className={`flex h-8 w-8 items-center justify-center rounded-[7px] text-white hover:bg-white/15 transition-colors ${cls}`}
          >
            <Icon size={15} />
          </button>
        ))}
      </div>

      {/* Close */}
      <button
        type="button"
        onClick={onClose}
        className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
        title={t("closeEsc")}
      >
        <X size={17} />
      </button>
    </div>,
    document.body
  );
}

export function ZoomableImage({ src, alt = "", className = "", maxZoom = 4 }: Props) {
  const t = useTranslations("chat.zoomableImage");
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const dragStart = useRef<{ x: number; y: number; ox: number; oy: number; moved: boolean } | null>(null);
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
    e.preventDefault();
    setDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y, moved: false };
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !dragStart.current) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragStart.current.moved = true;
    if (scale > 1) setOffset({ x: dragStart.current.ox + dx, y: dragStart.current.oy + dy });
  };

  const stopDrag = (e: React.MouseEvent) => {
    // Capture ref before clearing — state (dragging) can lag behind mouseUp in React
    const ds = dragStart.current;
    setDragging(false);
    dragStart.current = null;
    if (ds && !ds.moved && scale <= 1) {
      setFullscreen(true);
    }
  };

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  return (
    <>
      <div
        ref={containerRef}
        className={`group relative overflow-hidden select-none ${className}`}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={() => { setDragging(false); dragStart.current = null; }}
        style={{ cursor: scale > 1 ? (dragging ? "grabbing" : "grab") : "zoom-in", touchAction: "none" }}
        title={t("clickToView")}
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

        <div className="absolute bottom-2 right-2 flex gap-1">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setFullscreen(true); }}
            className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
            title={t("openFullscreen")}
          >
            <Maximize2 size={12} />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setScale((s) => Math.min(maxZoom, +(s * 1.3).toFixed(2))); }}
            className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
            title={t("zoomIn")}
          >
            <ZoomIn size={13} />
          </button>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setScale((s) => { const n = Math.max(0.4, +(s / 1.3).toFixed(2)); if (n <= 1) setOffset({ x: 0, y: 0 }); return n; }); }}
            className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
            title={t("zoomOut")}
          >
            <ZoomOut size={13} />
          </button>
          {scale !== 1 && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); reset(); }}
              className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-black/55 text-white backdrop-blur-sm hover:bg-black/75 transition-colors"
              title={t("resetZoom")}
            >
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      </div>

      {fullscreen && <FullscreenOverlay src={src} alt={alt} onClose={() => setFullscreen(false)} />}
    </>
  );
}
