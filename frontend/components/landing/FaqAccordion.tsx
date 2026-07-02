"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const FAQS = [
  {
    q: "Как работает баланс?",
    a: "Баланс aineron.ru — это рубли. Каждое сообщение к нейросети стоит несколько рублей (обычно 1–5 ₽). Средства не сгорают, баланс пополняется через Robokassa без комиссии.",
  },
  {
    q: "Нужен ли VPN для использования сервиса?",
    a: "Нет. aineron.ru — российский сервис с серверами в России. Доступ без VPN, оплата картами РФ, работает в любом браузере и приложении.",
  },
  {
    q: "Какие нейросети доступны?",
    a: "Доступны GPT-4o, GPT-4o mini, Claude 3.5 Sonnet, Gemini 1.5 Pro, DeepSeek V3, Mistral, Llama и более 200 других моделей. Для изображений: Stable Diffusion, Flux, Midjourney-совместимые модели.",
  },
  {
    q: "Есть ли API для разработчиков?",
    a: "Да. API-совместим с OpenAI SDK — просто смените base_url и API-ключ. Работает с Cursor, VS Code (Continue), GitHub Copilot-альтернативами и любым OpenAI-совместимым приложением.",
  },
  {
    q: "Как оплатить?",
    a: "Через Robokassa: карты Visa/MasterCard/Мир, ЮMoney, СБП. Доступно пополнение баланса на любую сумму и подписки со скидкой. Для юридических лиц — счёт и договор.",
  },
  {
    q: "Что если AI даст плохой ответ?",
    a: "На каждом сообщении есть кнопка «Regenerate» — AI сгенерирует новый ответ без дополнительного списания средств. Если возникла техническая ошибка — средства возвращаются автоматически.",
  },
];

export function FaqAccordion() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="flex flex-col divide-y" style={{ borderTop: "1px solid rgba(13,13,13,0.08)", borderBottom: "1px solid rgba(13,13,13,0.08)" }}>
      {FAQS.map((faq, i) => (
        <div key={i}>
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between gap-4 py-4 text-left"
          >
            <span className="text-[16px] font-medium text-[#1A1A1A]">{faq.q}</span>
            <ChevronDown
              size={16}
              className="shrink-0 text-[rgba(13,13,13,0.40)] transition-transform duration-200"
              style={{ transform: open === i ? "rotate(180deg)" : "none" }}
            />
          </button>
          {open === i && (
            <p className="pb-4 text-[16px] leading-relaxed text-[rgba(13,13,13,0.60)]">
              {faq.a}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
