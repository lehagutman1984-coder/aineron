/**
 * Оверлей витринной цены (опт × K) поверх реального каталога /models.
 *
 * Реальная цена (cost_kopecks) приходит из БД через serverListNetworks —
 * её не трогаем, i18n/тарифы/project_id/SEO у /models остаются как есть.
 * Этот файл добавляет ВТОРОЕ число на карточку — честную цену по
 * опту×курсу из pricingPreviewModels.ts (для сравнения с конкурентами),
 * без риска для остальной логики каталога.
 *
 * SLUG_ALIASES — там, где витринный id (человекочитаемый, для /models-preview)
 * отличается от реального слага NeuralNetwork в БД. Список сверен вручную
 * 2026-09-02 (см. комментарий в pricingPreviewModels.ts).
 */
import { PREVIEW_MODELS, type PreviewModel } from "./pricingPreviewModels";

const SLUG_ALIASES: Record<string, string> = {
  "nano-banana-2": "gemini-3-1-flash-image",
  "nano-banana-pro": "gemini-3-pro-image",
  "qwen-image-3": "qwen-image-3-0",
  "qwen-image-3-pro": "qwen-image-3-0-pro",
  "sora-2": "sora-character",
  "sora-2-pro": "sora-2-character",
  "veo-3-1-quality": "veo-3-1",
  "kling-v2-6": "kling-v26",
  "kling-3-turbo": "kling-3-0-turbo",
  "minimax-hailuo-2-3": "hailuo-2-3",
  "minimax-hailuo-2-3-fast": "hailuo-2-3-fast",
};

export const REFERENCE_PRICING: Record<string, PreviewModel> = (() => {
  const map: Record<string, PreviewModel> = {};
  for (const m of PREVIEW_MODELS) {
    if (m.isFree) continue;
    const slug = SLUG_ALIASES[m.id] ?? m.id;
    map[slug] = m;
  }
  return map;
})();
