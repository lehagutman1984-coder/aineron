"use client";

import { useEffect, useState } from "react";

const PHRASES = [
  "GPT-4o пишет код за секунды",
  "Claude объясняет сложное просто",
  "Gemini анализирует документы",
  "Midjourney рисует по запросу",
  "DeepSeek решает задачи по математике",
  "Perplexity ищет актуальную информацию",
];

export function HeroTypewriter() {
  const [idx, setIdx] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const phrase = PHRASES[idx];
    let timeout: ReturnType<typeof setTimeout>;

    if (!deleting && displayed.length < phrase.length) {
      timeout = setTimeout(() => setDisplayed(phrase.slice(0, displayed.length + 1)), 38);
    } else if (!deleting && displayed.length === phrase.length) {
      timeout = setTimeout(() => setDeleting(true), 2200);
    } else if (deleting && displayed.length > 0) {
      timeout = setTimeout(() => setDisplayed(displayed.slice(0, -1)), 18);
    } else if (deleting && displayed.length === 0) {
      setDeleting(false);
      setIdx((i) => (i + 1) % PHRASES.length);
    }

    return () => clearTimeout(timeout);
  }, [displayed, deleting, idx]);

  return (
    <span className="inline-block min-h-[1.2em] text-[#f0a38a]">
      {displayed}
      <span className="animate-pulse">|</span>
    </span>
  );
}
