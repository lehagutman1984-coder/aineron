"use client";

import { useEffect, useRef } from "react";

export function LandingVideo({ src, tag }: { src: string; tag: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = ref.current;
    if (!video || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) video.play().catch(() => {});
          else video.pause();
        }
      },
      { threshold: 0.35 }
    );
    io.observe(video);
    return () => io.disconnect();
  }, []);

  return (
    <div className="media-video">
      <span className="media-tag">{tag}</span>
      <video ref={ref} src={src} controls muted loop playsInline preload="metadata" />
    </div>
  );
}
