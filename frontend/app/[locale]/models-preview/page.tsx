import type { Metadata } from "next";
import { PricingPreviewClient } from "./PricingPreviewClient";

export const metadata: Metadata = {
  title: "Каталог моделей и цены (превью)",
  robots: { index: false, follow: false },
};

/**
 * Отдельная витрина-превью каталога — не связана с NeuralNetwork/биллингом
 * и не заменяет /models/. Данные статичные, см. lib/data/pricingPreviewModels.ts
 * и PRICING_SIMPLIFICATION_PLAN.md. Заменит текущий каталог позже, целиком.
 */
export default function ModelsPreviewPage() {
  return <PricingPreviewClient />;
}
