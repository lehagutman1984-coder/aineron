"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function isIOS() {
  if (typeof navigator === "undefined") return false;
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function isStandalone() {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    ("standalone" in window.navigator && (window.navigator as { standalone?: boolean }).standalone === true)
  );
}

export function PWAProvider() {
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    // Register service worker
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }

    // Already installed as PWA
    if (isStandalone()) return;

    // Already dismissed
    if (localStorage.getItem("pwa-dismissed")) return;

    const iosDevice = isIOS();
    setIos(iosDevice);

    if (iosDevice) {
      // iOS: show manual install tip after 30s
      const t = setTimeout(() => setShowBanner(true), 30_000);
      return () => clearTimeout(t);
    }

    // Android/Chrome: listen for native prompt
    const handler = (e: Event) => {
      e.preventDefault();
      setPrompt(e as BeforeInstallPromptEvent);
      setShowBanner(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!prompt) return;
    await prompt.prompt();
    const { outcome } = await prompt.userChoice;
    if (outcome === "dismissed") {
      localStorage.setItem("pwa-dismissed", "1");
    }
    setPrompt(null);
    setShowBanner(false);
  };

  const dismiss = () => {
    localStorage.setItem("pwa-dismissed", "1");
    setShowBanner(false);
  };

  if (!showBanner) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 mx-auto flex max-w-sm items-start gap-3 rounded-[14px] border border-[rgba(10,124,255,0.20)] bg-white p-4 shadow-[0_4px_24px_rgba(0,0,0,0.12)]">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-[#0a7cff] text-white">
        <Download size={18} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-semibold text-[#0d0d0d]">
          Установить приложение
        </p>
        {ios ? (
          <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.55)] leading-relaxed">
            Нажмите{" "}
            <span className="font-medium text-[#0d0d0d]">«Поделиться»</span> в
            Safari, затем{" "}
            <span className="font-medium text-[#0d0d0d]">
              «На экран Домой»
            </span>
          </p>
        ) : (
          <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.55)]">
            Работает без браузера, быстрее загружается
          </p>
        )}
        {!ios && (
          <button
            onClick={install}
            className="mt-2 rounded-[7px] bg-[#0a7cff] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-[#0066cc] transition-colors"
          >
            Установить
          </button>
        )}
      </div>
      <button
        onClick={dismiss}
        className="shrink-0 text-[rgba(13,13,13,0.35)] hover:text-[rgba(13,13,13,0.7)] transition-colors"
        aria-label="Закрыть"
      >
        <X size={16} />
      </button>
    </div>
  );
}
