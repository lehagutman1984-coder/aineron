"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

interface Props {
  beforeUrl: string;
  afterUrl: string;
  onClose: () => void;
}

export function BeforeAfterSlider({ beforeUrl, afterUrl, onClose }: Props) {
  const [pos, setPos] = useState(50); // 0-100%
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const updatePos = useCallback((clientX: number) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const pct = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
    setPos(pct);
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    updatePos(e.clientX);
  }, [updatePos]);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    dragging.current = true;
    updatePos(e.touches[0].clientX);
  }, [updatePos]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => { if (dragging.current) updatePos(e.clientX); };
    const onUp = () => { dragging.current = false; };
    const onTouchMove = (e: TouchEvent) => { if (dragging.current) updatePos(e.touches[0].clientX); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('touchend', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onUp);
    };
  }, [updatePos]);

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4" onClick={onClose}>
      <div className="relative max-h-[90vh] max-w-[90vw]" onClick={e => e.stopPropagation()}>
        {/* Close */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80"
        >
          <X size={16} />
        </button>

        {/* Labels */}
        <div className="absolute left-3 top-3 z-10 rounded-[6px] bg-black/60 px-2 py-1 text-[11px] font-medium text-white">
          До
        </div>
        <div className="absolute right-3 top-3 z-10 rounded-[6px] bg-black/60 px-2 py-1 text-[11px] font-medium text-white">
          После
        </div>

        {/* Slider container */}
        <div
          ref={containerRef}
          className="relative select-none overflow-hidden rounded-[12px] cursor-col-resize"
          onMouseDown={onMouseDown}
          onTouchStart={onTouchStart}
        >
          {/* After image (full) */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={afterUrl} alt="После" className="block max-h-[80vh] w-auto max-w-[85vw] select-none" draggable={false} />

          {/* Before image (clipped) */}
          <div
            className="absolute inset-0 overflow-hidden"
            style={{ width: `${pos}%` }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={beforeUrl}
              alt="До"
              className="block h-full select-none object-cover"
              style={{ maxWidth: 'none', width: containerRef.current?.offsetWidth ?? 'auto' }}
              draggable={false}
            />
          </div>

          {/* Divider line */}
          <div
            className="absolute inset-y-0 z-10 flex w-[2px] items-center justify-center bg-white shadow-[0_0_8px_rgba(0,0,0,0.5)]"
            style={{ left: `${pos}%`, transform: 'translateX(-50%)' }}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-lg">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M5 8l-3 0M14 8l-3 0M11 5l3 3-3 3M5 5L2 8l3 3" stroke="#333" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>
        </div>

        <p className="mt-2 text-center text-[12px] text-white/60">
          Перетащите разделитель для сравнения
        </p>
      </div>
    </div>
  );
}
