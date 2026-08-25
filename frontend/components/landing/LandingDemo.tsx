"use client";

import { useState } from "react";
import { formatMoney } from "@/lib/money";

type ModelKey = "gpt" | "claude" | "flux";
type PromptKey = "coffee" | "lease" | "cover";

const MODELS: { key: ModelKey; label: string }[] = [
  { key: "gpt", label: "GPT-5" },
  { key: "claude", label: "Claude Sonnet 5" },
  { key: "flux", label: "Flux 2 Pro" },
];

export function LandingDemo({
  prompts,
  chipLabels,
  sendLabel,
  answers,
  coverImageUrl,
}: {
  prompts: Record<PromptKey, { text: string; kind: "text" | "image" }>;
  chipLabels: Record<PromptKey, string>;
  sendLabel: string;
  answers: Record<
    string,
    { label: string; costKopecks?: number; lines?: string[]; note: string; switchNote?: boolean }
  >;
  coverImageUrl: string;
}) {
  const [model, setModel] = useState<ModelKey>("gpt");
  const [prompt, setPrompt] = useState<PromptKey>("coffee");

  function pickPrompt(p: PromptKey) {
    setPrompt(p);
    const kind = prompts[p].kind;
    if (kind === "image" && model !== "flux") setModel("flux");
    if (kind === "text" && model === "flux") setModel("gpt");
  }

  const key = `${model}|${prompt}`;
  const answer = answers[key];
  const showCoverImage = key === "flux|cover";

  return (
    <div className="wrap">
      <div className="demo">
        <div className="demo-top">
          <div className="dots">
            <i />
            <i />
            <i />
          </div>
          <div className="tabs">
            {MODELS.map((m) => (
              <button
                key={m.key}
                className={`tab${model === m.key ? " on" : ""}`}
                onClick={() => setModel(m.key)}
              >
                <i />
                {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="demo-body">
          <div className="prompt-row">
            <div className="prompt-box">
              <span className="c">›</span>
              <span>{prompts[prompt].text}</span>
            </div>
            <a href="/register" className="btn btn-primary">
              {sendLabel} →
            </a>
          </div>
          <div className="chips">
            {(Object.keys(chipLabels) as PromptKey[]).map((p) => (
              <button
                key={p}
                className={`chip${prompt === p ? " on" : ""}`}
                onClick={() => pickPrompt(p)}
              >
                {chipLabels[p]}
              </button>
            ))}
          </div>
          <div className="answer">
            {answer && (
              <>
                <div className="answer-label">
                  {answer.label}
                  {answer.costKopecks ? ` · ${formatMoney(answer.costKopecks)}` : ""}
                </div>
                {showCoverImage && (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <div className="gen-img">
                    <img src={coverImageUrl} alt="" />
                  </div>
                )}
                {answer.lines && (
                  <ol>
                    {answer.lines.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ol>
                )}
                <p
                  dangerouslySetInnerHTML={{
                    __html: answer.note.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"),
                  }}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
