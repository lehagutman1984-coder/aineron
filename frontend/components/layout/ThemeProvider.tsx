"use client";

import { useEffect } from "react";
import { useUIStore, type Theme } from "@/lib/stores/ui";

function applyTheme(theme: Theme) {
  const isDark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
}

export function ThemeProvider() {
  const { theme, setTheme } = useUIStore();

  // Load saved theme from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("aineron-theme") as Theme | null;
      if (saved === "light" || saved === "dark" || saved === "system") {
        setTheme(saved);
      }
    } catch {
      // ignore (SSR / private browsing)
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync theme → html[data-theme] and localStorage
  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem("aineron-theme", theme);
    } catch {
      // ignore
    }

    // When theme=system, react to OS preference changes live
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  return null;
}
