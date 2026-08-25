"use client";

import { useState } from "react";

export function LandingFaq({ items }: { items: { q: string; a: string }[] }) {
  const [open, setOpen] = useState(0);

  return (
    <div className="faq">
      {items.map((item, i) => (
        <div key={i} className={`q${open === i ? " open" : ""}`}>
          <button className="q-head" onClick={() => setOpen(open === i ? -1 : i)}>
            {item.q}
            <span className="q-mark">+</span>
          </button>
          <div className="q-body">
            <p>{item.a}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
