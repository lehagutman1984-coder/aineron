/**
 * Оверлей витринных данных (опт × K цена + богатые детали) поверх реального
 * каталога /models и /models/[slug].
 *
 * Реальная цена (cost_kopecks) и вся живая логика (i18n/тарифы/project_id/
 * SEO/ChatStartForm) приходят из БД через serverListNetworks/serverGetNetwork
 * — их не трогаем. Этот файл добавляет ДОПОЛНИТЕЛЬНЫЕ данные поверх: честную
 * цену по опту×курсу (для сравнения с конкурентами) и развёрнутые детали
 * (supportedParameters/bestFor/reasoningLevels/контекст) из pricingPreview*
 * файлов — без риска для остальной логики страниц.
 *
 * SLUG_ALIASES — там, где витринный id (человекочитаемый, использовался в
 * /models-preview) отличается от реального слага NeuralNetwork в БД. Список
 * сверен вручную 2026-09-02 (см. комментарий в pricingPreviewModels.ts).
 */
import { PREVIEW_MODELS, type PreviewModel } from "./pricingPreviewModels";
import { DETAILS, type ModelDetail } from "./pricingPreviewDetails";

export const SLUG_ALIASES: Record<string, string> = {
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

export const REFERENCE_DETAILS: Record<string, ModelDetail> = (() => {
  const map: Record<string, ModelDetail> = {};
  for (const [previewId, detail] of Object.entries(DETAILS)) {
    const slug = SLUG_ALIASES[previewId] ?? previewId;
    map[slug] = detail;
  }
  return map;
})();
