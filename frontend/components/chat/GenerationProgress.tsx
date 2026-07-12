"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Film, CheckCircle2, Loader2 } from "lucide-react";
import { BASE_URL } from "@/lib/api/client";

interface Props {
  generationId: number;
  /** Вызывается, когда генерация завершилась (done/timeout) — родитель перезагружает сообщение. */
  onComplete?: () => void;
}

/**
 * Прогресс-бар видео-генерации. Подключается к SSE
 * GET /generations/{id}/progress/ и показывает процент.
 *
 * Источник истины о завершении — polling статуса сообщения на странице чата;
 * этот компонент лишь визуализирует прогресс и ускоряет перезагрузку по onComplete.
 */
export function GenerationProgress({ generationId, onComplete }: Props) {
  const t = useTranslations("chat.generationProgress");
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string>("running");
  // держим onComplete в ref, чтобы не пересоздавать EventSource на каждый рендер
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    const es = new EventSource(`${BASE_URL}/generations/${generationId}/progress/`, {
      withCredentials: true,
    });

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as { progress?: number; status?: string };
        if (typeof data.progress === "number") setProgress(data.progress);
        if (data.status) setStatus(data.status);
        if (data.status === "done" || data.status === "error" || data.status === "timeout") {
          es.close();
          if (data.status !== "error") onCompleteRef.current?.();
        }
      } catch {
        /* игнорируем некорректные кадры */
      }
    };

    es.onerror = () => {
      // транзиентная ошибка/обрыв — закрываем; статус сообщения дотянет polling страницы
      es.close();
    };

    return () => es.close();
  }, [generationId]);

  const done = status === "done";
  const pct = done ? 100 : Math.max(0, Math.min(100, progress));

  return (
    <div className="w-full max-w-sm py-1">
      <div className="mb-1.5 flex items-center gap-2">
        {done ? (
          <CheckCircle2 size={15} className="text-[#D97757]" />
        ) : (
          <Loader2 size={15} className="animate-spin text-[#D97757]" />
        )}
        <span className="flex items-center gap-1.5 text-[15px] font-medium text-[rgba(13,13,13,0.7)] dark:text-[rgba(236,236,236,0.7)]">
          <Film size={13} className="opacity-60" />
          {done ? t("done") : t("generatingVideo")}
        </span>
        <span className="ms-auto text-[14px] tabular-nums text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.45)]">
          {pct}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[rgba(13,13,13,0.08)] dark:bg-[rgba(255,255,255,0.1)]">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            done ? "bg-[#D97757]" : "bg-[#D97757]"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {!done && (
        <p className="mt-1.5 text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
          {t("hint")}
        </p>
      )}
    </div>
  );
}
