"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { useAuthStore } from "@/lib/stores/auth";
import { LandingCtaButton } from "./LandingCtaButton";

const SECTIONS = ["models", "features", "compare", "save", "faq"] as const;

export function LandingHeader({
  labels,
  loginLabel,
  ctaLabel,
  accountLabel,
  menuLabel,
}: {
  labels: Record<(typeof SECTIONS)[number], string>;
  loginLabel: string;
  ctaLabel: string;
  accountLabel: string;
  menuLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const user = useAuthStore((s) => s.user);

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
            {!user && (
              <Link href="/login" style={{ fontSize: 15, color: "var(--muted)" }}>
                {loginLabel}
              </Link>
            )}
            <LandingCtaButton
              scrollHref="#final"
              authedLabel={accountLabel}
              anonLabel={ctaLabel}
              className="btn btn-primary btn-sm"
            />
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
          {!user && (
            <Link href="/login" className="d-login" onClick={close}>
              {loginLabel}
            </Link>
          )}
          <LandingCtaButton
            scrollHref="#final"
            authedLabel={`${accountLabel} →`}
            anonLabel={`${ctaLabel} →`}
            className="btn btn-primary"
            onClick={close}
          />
        </div>
      </div>
    </>
  );
}
