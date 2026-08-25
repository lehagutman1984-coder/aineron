"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";

const SECTIONS = ["models", "features", "compare", "save", "faq"] as const;

export function LandingHeader({
  labels,
  loginLabel,
  ctaLabel,
  menuLabel,
}: {
  labels: Record<(typeof SECTIONS)[number], string>;
  loginLabel: string;
  ctaLabel: string;
  menuLabel: string;
}) {
  const [open, setOpen] = useState(false);

  function toggle() {
    setOpen((v) => {
      const next = !v;
      document.body.style.overflow = next ? "hidden" : "";
      return next;
    });
  }

  function close() {
    setOpen(false);
    document.body.style.overflow = "";
  }

  return (
    <>
      <header>
        <div className="wrap nav">
          <Link href="/" className="logo">
            <i />
            Aineron
          </Link>
          <nav className="nav-links">
            {SECTIONS.map((s) => (
              <a key={s} href={`#${s}`}>
                {labels[s]}
              </a>
            ))}
          </nav>
          <div className="nav-right">
            <Link href="/login" style={{ fontSize: 15, color: "var(--muted)" }}>
              {loginLabel}
            </Link>
            <a href="#final" className="btn btn-primary btn-sm">
              {ctaLabel}
            </a>
            <button
              className={`burger${open ? " on" : ""}`}
              aria-label={menuLabel}
              onClick={toggle}
            >
              <span />
              <span />
              <span />
            </button>
          </div>
        </div>
      </header>

      <div className={`drawer${open ? " on" : ""}`}>
        {SECTIONS.map((s) => (
          <a key={s} href={`#${s}`} className="dl" onClick={close}>
            {labels[s]}
          </a>
        ))}
        <div className="d-actions">
          <Link href="/login" className="d-login" onClick={close}>
            {loginLabel}
          </Link>
          <a href="#final" className="btn btn-primary" onClick={close}>
            {ctaLabel} →
          </a>
        </div>
      </div>
    </>
  );
}
