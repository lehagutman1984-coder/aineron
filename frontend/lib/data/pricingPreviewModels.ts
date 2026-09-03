/**
 * Данные для нового каталога моделей и цен — витрина цен в стиле RouterAI
 * (₽/1М токенов для текста, ₽/генерацию для изображений, ₽/сек для видео)
 * + реальная цена, которая спишется в чате прямо сейчас.
 *
 * Источник цен: PRICING_SIMPLIFICATION_PLAN.md §1.1/§2.1 — опт снят живьём с
 * openrouter.ai/models и apimart.ai/ru/pricing (2026-09-02), розничная
 * витринная цена = опт_$ × K, K = 105 ₽/$ (подтверждено пользователем
 * 2026-09-02: не выше конкурента и заметно дешевле, было 110).
 *
 * ДВЕ ЦЕНЫ НА КАЖДОЙ КАРТОЧКЕ: опт×K — честная цена по токенам/генерации для
 * сравнения с конкурентами, и priceRealKopecks — реальная цена, которая
 * спишется в чате. РЕАЛЬНЫЙ БИЛЛИНГ ПЕРЕПИСАН НА ЭТИ ЦИФРЫ (2026-09-03):
 * cost_kopecks для всех 65 платных моделей пересчитан из ₽/1М по стандартному
 * профилю токенов (6000 вход/1500 выход для текста, генерация напрямую для
 * картинок, ₽/сек × реальная длительность по умолчанию из config_json для
 * видео) — по правилу "новая цена = min(старая, расчётная)": цена никогда не
 * растёт, только падает или остаётся прежней. У ~12 моделей (в основном
 * видео, где расчёт по секундам вышел бы дороже старой плоской цены за
 * генерацию) priceRealKopecks поэтому равен старой цене, а не строго
 * выведен из ₽/1М — это осознанно, не баг. Бэкап цен до пересчёта:
 * /tmp/reprice_rollback_2026-09-03.json на сервере.
 *
 * СПИСОК МОДЕЛЕЙ СИНХРОНИЗИРОВАН С ПРОДОМ (2026-09-02): каждая модель здесь —
 * это реальная, активная запись NeuralNetwork. Всё, что не попало в этот
 * список, деактивировано в проде тем же днём (is_active=False, не удалено).
 * 4 модели заведены как новые записи NeuralNetwork в этом же заходе — их
 * раньше не существовало в базе, только на бумаге/в тестах: claude-fable-5-1,
 * grok-4-6, qwen3-8-max, gemini-3-7-flash (все живьём проверены через
 * get_laozhang_client → laozhang.ai/apimart.ai fallback, реальная цена
 * выставлена по тиру соседней версии).
 *
 * TEXT_MODELS (21 из 21): "Qwen 3.8 Flash", "GLM 5.3", "GLM 5.3 Flash" —
 * реальные модели на OpenRouter, но у обоих наших провайдеров (laozhang,
 * apimart) возвращают model_not_found — не добавлены. Старые версии (Grok
 * 4.5, Qwen 3.6 Max, Gemini 3.6 Flash, Claude Fable 5) оставлены рядом с
 * новыми — обе версии реально работают в проде, решение пользователя не
 * заменять старое новым, а добавлять. Первые три сняты с публичного прайса
 * OpenRouter (только новая версия осталась в листинге) — их ₽/1М цена
 * ориентирована на тир соседней новой версии. Gemini 3.6 Flash — исключение,
 * ещё живьём на OpenRouter, цена подтверждена напрямую ($0.75/$3.75 за 1М).
 * Остальные ~50 текстовых моделей (GPT-5, GPT-4o, o1/o3, Grok 4, Kimi K2,
 * DeepSeek R1/V3, Qwen3 5.x/6.x-flash/plus и т.д.) деактивированы в проде —
 * это осознанное сужение каталога до текущей витрины, не баг.
 *
 * IMAGE_MODELS (20 из 20): "Midjourney" и фиктивные "Seedream 5.0 Pro/Lite"
 * убраны — в проде НЕТ соответствующих записей NeuralNetwork вообще (не
 * деактивированы, никогда не заводились). Реальные Seedream-модели —
 * "Seedream 5.0" и "Seedream 4.5" (следующая по актуальности после 5.0).
 * Добавлена "Flux Kontext Max" — реальная активная модель, была пропущена в
 * прошлой ревизии. Деактивированы как замещённые новым поколением:
 * gemini-2-5-flash-image (старая Nano Banana, есть 2/Pro), qwen-image-2-0
 * (есть 3.0/3.0 Pro), seedream-4-0 (есть 4.5/5.0).
 *
 * КАРТИНКИ: РЕАЛЬНАЯ ЦЕНА ПОДНЯТА ДО "КОНКУРЕНТ × 0,95" (2026-09-03, тот же
 * запрос пользователя, что и по видео). 12 из 20 моделей — там, где нашлось
 * ОДНО чистое число у конкурента (не широкий диапазон, не гадание по
 * валюте/токенам): gpt-image-2, gpt-image-1-5, dall-e-3, flux-kontext-pro,
 * flux-kontext-max, nano-banana-2, seedream-4-5, flux-2-pro/max/flex,
 * z-image-turbo, qwen-image-3 — цена = конкурент_₽ × 0.95 (источники:
 * gptrf.ru, gen-api.ru/pricing, routerai.ru, сверено живьём). Оставшиеся 8
 * (gpt-image-1, gpt-image-1-mini, nano-banana-pro, seedream-5-0,
 * qwen-image-3-pro, wan-2-7-image, grok-imagine-image(-quality)) НЕ тронуты —
 * у конкурентов либо нет данных вообще, либо только широкий/ненадёжный
 * диапазон (10-30x разброс, оценка по валюте курса, подписочный тариф) —
 * недостаточно уверенности, чтобы менять реальную цену.
 *
 * VIDEO_MODELS (24 из 24): 1:1 совпадение с активными видео-моделями в
 * проде, деактивировать нечего. id в этом файле — витринные, отличаются от
 * реальных слагов NeuralNetwork у 6 моделей (sora-2→sora-character,
 * sora-2-pro→sora-2-character, veo-3-1-quality→veo-3-1,
 * kling-v2-6→kling-v26, kling-3-turbo→kling-3-0-turbo,
 * minimax-hailuo-2-3(-fast)→hailuo-2-3(-fast)) — сверено, реальная цена
 * проставлена по факту.
 *
 * ВИДЕО: РЕАЛЬНАЯ ЦЕНА ПОДНЯТА ДО "ROUTERAI × 0,95" (2026-09-03, по прямому
 * запросу пользователя). RouterAI ₽/сек сверены живьём на routerai.ru/ai-video
 * для 16 из 24 моделей, где есть прямое соответствие; цена = (routerai_₽/сек
 * × 0.95) × наша реальная длительность ролика по умолчанию (config_json).
 * Раньше у этих 16 цена была НИЖЕ этого порога (после пересчёта 2026-09-03
 * под K=105) — теперь подняты до уровня "на 5% дешевле конкурента", как
 * попросил пользователь, а не оставлены заниженными. Оставшиеся 8 моделей
 * (базовая Sora 2, Vidu, Pixverse, Kling Motion Control/3.0 Turbo и т.д.) у
 * RouterAI не продаются вообще — цена не менялась, сравнивать не с чем.
 *
 * FREE_MODELS (14 из 14) — синхронизировано 1:1 с активными бесплатными
 * моделями в проде (NeuralNetwork, is_free=True, is_active=True). Три
 * провайдера: openrouter_free (6), zai_free (3, Z.ai/Zhipu — GLM-*-Flash),
 * cloudflare_free (5, Cloudflare Workers AI, общий дневной пул 10 000
 * "neurons"). Ранее активны были ещё free-nemotron-nano-9b/
 * free-nemotron-3-nano-30b/free-nemotron-nano-12b-vl — деактивированы
 * 2026-09-02 (живой вызов вернул 404 model_not_found). free-glm-5-2 и
 * free-gemma-4-31b проверены в тот же день — вернули 429 rate-limit (не
 * 404), оставлены активными.
 */

export type PreviewCategory = "text" | "image" | "video";

export interface PreviewModel {
  id: string;
  name: string;
  provider: string;
  category: PreviewCategory;
  description: string;
  contextLabel?: string;
  /** ₽ за 1М токенов (только category="text") — витринная цена опт×K */
  priceInRub?: number;
  priceOutRub?: number;
  /** ₽ за одну генерацию (только category="image") — витринная цена опт×K */
  priceGenRub?: number;
  /** ₽ за единицу тарификации видео (только category="video") — витринная цена опт×K */
  priceVideoRub?: number;
  priceUnit?: "sec" | "call";
  inputBadges: string[];
  outputBadges: string[];
  /** Бесплатная модель — 0 ₽, лимит сообщений/день вместо цены. Не входит в счётчик своей category. */
  isFree?: boolean;
  /** Лимит сообщений в день на пользователя (только isFree=true) */
  dailyLimit?: number;
  /** Реальная цена за сообщение/генерацию, которая спишется в чате прямо сейчас (NeuralNetwork.cost_kopecks) */
  priceRealKopecks?: number;
}

const K = 105; // ₽ за $ опта — см. план §2.1 (подтверждено пользователем 2026-09-02: не выше конкурента, чуть дешевле)

const round = (usd: number) => Math.round(usd * K);

export const TEXT_MODELS: PreviewModel[] = [
  {
    id: "claude-opus-5",
    name: "Claude Opus 5",
    provider: "Anthropic",
    category: "text",
    description: "Флагманский Claude для сложных рассуждений, кода и длинных агентных цепочек.",
    contextLabel: "1M",
    priceInRub: round(5),
    priceOutRub: round(25),
    priceRealKopecks: 709,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-sonnet-5",
    name: "Claude Sonnet 5",
    provider: "Anthropic",
    category: "text",
    description: "Баланс скорости и интеллекта — самый ходовой Claude для повседневных задач.",
    contextLabel: "1M",
    priceInRub: round(2),
    priceOutRub: round(10),
    priceRealKopecks: 284,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-fable-5-1",
    name: "Claude Fable 5.1",
    provider: "Anthropic",
    category: "text",
    description: "Модель уровня выше Opus — многочасовые автономные агентные сессии, мышление всегда включено.",
    contextLabel: "1M",
    priceInRub: round(10),
    priceOutRub: round(50),
    priceRealKopecks: 1418,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-fable-5",
    name: "Claude Fable 5",
    provider: "Anthropic",
    category: "text",
    // Базовая версия снята с публичного прайса OpenRouter (остался только
    // Fable 5.1, проверено 2026-09-02) — витринная цена ориентирована на тот
    // же тир, что у 5.1, уточнить при появлении отдельных данных.
    description: "Предыдущая версия Fable — расширенное мышление, длинные автономные сессии.",
    contextLabel: "1M",
    priceInRub: round(10),
    priceOutRub: round(50),
    priceRealKopecks: 1418,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-sonnet-4-6",
    name: "Claude Sonnet 4.6",
    provider: "Anthropic",
    category: "text",
    description: "Предыдущее поколение Sonnet — итеративная разработка, полноценная работа с документами.",
    contextLabel: "1M",
    priceInRub: round(3),
    priceOutRub: round(15),
    priceRealKopecks: 425,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-opus-4-8",
    name: "Claude Opus 4.8",
    provider: "Anthropic",
    category: "text",
    description: "Предыдущий топовый Opus — глубокий анализ и долгие агентные задачи.",
    contextLabel: "1M",
    priceInRub: round(5),
    priceOutRub: round(25),
    priceRealKopecks: 709,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "claude-haiku-4-5",
    name: "Claude Haiku 4.5",
    provider: "Anthropic",
    category: "text",
    description: "Самый быстрый и дешёвый Claude — близко к Sonnet 4 по качеству на простых задачах.",
    contextLabel: "200K",
    priceInRub: round(1),
    priceOutRub: round(5),
    priceRealKopecks: 142,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "gpt-5-6-sol",
    name: "GPT-5.6 Sol",
    provider: "OpenAI",
    category: "text",
    description: "Флагман линейки 5.6 — сложные рассуждения, код, длинные агентные workflow.",
    contextLabel: "1.1M",
    priceInRub: round(2),
    priceOutRub: round(10),
    priceRealKopecks: 284,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "gpt-5-6-terra",
    name: "GPT-5.6 Terra",
    provider: "OpenAI",
    category: "text",
    description: "Средний тир линейки 5.6 — быстрее Sol, заметно дешевле.",
    contextLabel: "1.1M",
    priceInRub: round(2),
    priceOutRub: round(12),
    priceRealKopecks: 315,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "gpt-5-6-luna",
    name: "GPT-5.6 Luna",
    provider: "OpenAI",
    category: "text",
    description: "Младший тир 5.6 — короткие быстрые ответы по минимальной цене.",
    contextLabel: "1.1M",
    priceInRub: round(0.2),
    priceOutRub: round(1.2),
    priceRealKopecks: 32,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "gpt-5-5",
    name: "GPT-5.5",
    provider: "OpenAI",
    category: "text",
    description: "Универсальная модель поколения 5.5 — код, анализ, рассуждения.",
    priceInRub: round(5),
    priceOutRub: round(30),
    priceRealKopecks: 788,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "gpt-5-5-pro",
    name: "GPT-5.5 Pro",
    provider: "OpenAI",
    category: "text",
    description: "Топовый тир 5.5 — максимальная глубина рассуждений для самых сложных задач.",
    priceInRub: round(30),
    priceOutRub: round(180),
    priceRealKopecks: 1600,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "gemini-3-1-pro",
    name: "Gemini 3.1 Pro",
    provider: "Google",
    category: "text",
    description: "Флагман Gemini — мультимодальность, длинный контекст, сильный код.",
    contextLabel: "1M",
    priceInRub: round(2),
    priceOutRub: round(12),
    priceRealKopecks: 315,
    inputBadges: ["Текст", "Изображения", "Файл", "Видео"],
    outputBadges: ["Текст"],
  },
  {
    id: "gemini-3-7-flash",
    name: "Gemini 3.7 Flash",
    provider: "Google",
    category: "text",
    description: "Быстрая и дешёвая модель Gemini для массовых сценариев.",
    contextLabel: "1M",
    priceInRub: round(0.75),
    priceOutRub: round(3.75),
    priceRealKopecks: 107,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "gemini-3-6-flash",
    name: "Gemini 3.6 Flash",
    provider: "Google",
    category: "text",
    // Подтверждено живьём на OpenRouter (google/gemini-3.6-flash, 2026-09-02):
    // $0.75 / $3.75 за 1М — совпадает с 3.7 Flash.
    description: "Предыдущая версия Flash — та же цена, чуть более старая база знаний.",
    contextLabel: "1M",
    priceInRub: round(0.75),
    priceOutRub: round(3.75),
    priceRealKopecks: 107,
    inputBadges: ["Текст", "Изображения", "Файл"],
    outputBadges: ["Текст"],
  },
  {
    id: "deepseek-v4-pro",
    name: "DeepSeek V4 Pro",
    provider: "DeepSeek",
    category: "text",
    description: "Топовая модель DeepSeek смеси экспертов — сильный код по низкой цене.",
    contextLabel: "1M",
    // Оценка по середине диапазона провайдеров OpenRouter ($0.66-1.32/$1.98-3.96) — уточнить, план §8.1.
    priceInRub: round(1.0),
    priceOutRub: round(3.0),
    priceRealKopecks: 110,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "deepseek-v4-flash",
    name: "DeepSeek V4 Flash",
    provider: "DeepSeek",
    category: "text",
    description: "Облегчённая DeepSeek — для высокого объёма недорогих запросов.",
    contextLabel: "1.3M",
    // Оценка по середине диапазона провайдеров OpenRouter — уточнить, план §8.1.
    priceInRub: round(0.1),
    priceOutRub: round(0.22),
    priceRealKopecks: 10,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "grok-4-6",
    name: "Grok 4.6",
    provider: "xAI",
    category: "text",
    description: "Новейший Grok — сильные рассуждения, доступ к актуальным данным.",
    contextLabel: "500K",
    priceInRub: round(2),
    priceOutRub: round(6),
    priceRealKopecks: 221,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "grok-4-5",
    name: "Grok 4.5",
    provider: "xAI",
    category: "text",
    // Снята с публичного прайса OpenRouter (остался только 4.6, проверено
    // 2026-09-02) — витринная цена ориентирована на тот же тир, что у 4.6.
    description: "Предыдущее поколение Grok — те же рассуждения, чуть более старая база знаний.",
    contextLabel: "500K",
    priceInRub: round(2),
    priceOutRub: round(6),
    priceRealKopecks: 221,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "qwen3-8-max",
    name: "Qwen 3.8 Max",
    provider: "Alibaba",
    category: "text",
    description: "Топовая модель линейки Qwen — код, рассуждения, многоязычность.",
    contextLabel: "1M",
    priceInRub: round(2),
    priceOutRub: round(6),
    priceRealKopecks: 220,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "qwen3-6-max",
    name: "Qwen 3.6 Max",
    provider: "Alibaba",
    category: "text",
    // Снята с публичного прайса OpenRouter (остались только 3.7/3.8,
    // проверено 2026-09-02) — витринная цена ориентирована на тот же тир, что у 3.8 Max.
    description: "Предыдущая топовая модель Qwen — код, рассуждения, многоязычность.",
    contextLabel: "1M",
    priceInRub: round(2),
    priceOutRub: round(6),
    priceRealKopecks: 220,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
];

const roundImg = (usd: number) => Math.round(usd * K * 10) / 10;

export const IMAGE_MODELS: PreviewModel[] = [
  {
    id: "gpt-image-2",
    name: "GPT-Image-2",
    provider: "OpenAI",
    category: "image",
    description: "Новейшая модель генерации изображений OpenAI — точное следование промту.",
    priceGenRub: roundImg(0.0085),
    priceRealKopecks: 760,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "gpt-image-1",
    name: "GPT-Image-1",
    provider: "OpenAI",
    category: "image",
    // Токенный тариф у провайдера ($32/M за выходные токены изображения) —
    // цена пересчитана на типовое изображение (~1056 токенов), это оценка.
    description: "Предыдущее поколение GPT-Image — надёжная базовая генерация.",
    priceGenRub: 3.7,
    priceRealKopecks: 370,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "nano-banana-2",
    name: "Nano Banana 2",
    provider: "Google",
    category: "image",
    description: "Модель Gemini для генерации и редактирования изображений по тексту.",
    priceGenRub: roundImg(0.015),
    priceRealKopecks: 950,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Изображение"],
  },
  {
    id: "nano-banana-pro",
    name: "Nano Banana Pro",
    provider: "Google",
    category: "image",
    description: "Старшая версия Nano Banana — выше детализация и точность правок.",
    priceGenRub: roundImg(0.03),
    priceRealKopecks: 320,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Изображение"],
  },
  {
    id: "dall-e-3",
    name: "DALL-E 3",
    provider: "OpenAI",
    category: "image",
    description: "Классическая модель OpenAI — устойчивое качество на широком спектре промтов.",
    priceGenRub: roundImg(0.032),
    priceRealKopecks: 665,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "flux-kontext-pro",
    name: "Flux Kontext Pro",
    provider: "Black Forest Labs",
    category: "image",
    description: "Редактирование изображений по тексту с сохранением контекста сцены.",
    priceGenRub: roundImg(0.032),
    priceRealKopecks: 760,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Изображение"],
  },
  {
    id: "flux-2-pro",
    name: "Flux 2 Pro",
    provider: "Black Forest Labs",
    category: "image",
    description: "Актуальное поколение Flux — высокая детализация, до 4МП.",
    priceGenRub: roundImg(0.024),
    priceRealKopecks: 322,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "flux-2-max",
    name: "Flux 2 Max",
    provider: "Black Forest Labs",
    category: "image",
    description: "Топовый тир Flux 2 — максимальное качество и разрешение.",
    priceGenRub: roundImg(0.056),
    priceRealKopecks: 665,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "flux-2-flex",
    name: "Flux 2 Flex",
    provider: "Black Forest Labs",
    category: "image",
    description: "Гибкая модель Flux 2 с настраиваемыми параметрами генерации.",
    priceGenRub: roundImg(0.04),
    priceRealKopecks: 570,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "flux-kontext-max",
    name: "Flux Kontext Max",
    provider: "Black Forest Labs",
    category: "image",
    description: "Топовый тир редактирования Flux Kontext — максимальное качество правок.",
    priceGenRub: roundImg(0.056),
    priceRealKopecks: 1520,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Изображение"],
  },
  {
    id: "seedream-5-0",
    name: "Seedream 5.0",
    provider: "ByteDance",
    category: "image",
    description: "Топовая модель ByteDance — сильная типографика и композиция.",
    priceGenRub: roundImg(0.014625),
    priceRealKopecks: 150,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "seedream-4-5",
    name: "Seedream 4.5",
    provider: "ByteDance",
    category: "image",
    // Реальная цена скорректирована 2026-09-03: у RouterAI нашлось более
    // чистое число за штуку (4.52₽, не Gen-API 7.5₽) — цена = дешевле на 5%.
    description: "Предыдущее поколение Seedream — быстрее и дешевле для массовой генерации.",
    priceGenRub: roundImg(0.0133),
    priceRealKopecks: 429,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "z-image-turbo",
    name: "Z-Image Turbo",
    provider: "Alibaba",
    category: "image",
    description: "Сверхбыстрая и самая дешёвая модель в подборке — для больших объёмов.",
    priceGenRub: roundImg(0.01),
    priceRealKopecks: 119,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "qwen-image-3",
    name: "Qwen Image 3.0",
    provider: "Alibaba",
    category: "image",
    // Реальная цена скорректирована 2026-09-03: у RouterAI нашлось более
    // чистое число за штуку (3.39₽, не Gen-API 5₽/МП) — цена = дешевле на 5%.
    description: "Модель изображений Qwen — качественный текст на изображении, многоязычность.",
    priceGenRub: roundImg(0.0205712),
    priceRealKopecks: 322,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },

  // ── Добавлено 2026-09-02 (проверено живым вызовом apimart —
  // POST /v1/images/generations → task_id → completed с реальным URL) ──
  {
    id: "qwen-image-3-pro",
    name: "Qwen Image 3.0 Pro",
    provider: "Alibaba",
    category: "image",
    description: "Профессиональный тир Qwen Image 3.0 — поддержка 2K-разрешения.",
    priceGenRub: roundImg(0.0285712),
    priceRealKopecks: 300,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "wan-2-7-image",
    name: "Wan 2.7 Image",
    provider: "Alibaba",
    category: "image",
    // Цена у apimart расходится между документацией (¥0.20-0.50/картинку) и
    // прайс-таблицей ($0.0216/картинку) — взят ориентир из прайс-таблицы,
    // сверить перед подключением биллинга.
    description: "Генерация изображений Wan — серийная генерация нескольких картинок одной темой, интерактивный editing по областям.",
    priceGenRub: roundImg(0.0216),
    priceRealKopecks: 230,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "grok-imagine-image",
    name: "Grok Imagine",
    provider: "xAI",
    category: "image",
    description: "Модель генерации изображений xAI — быстрая генерация, разрешение 1K/2K.",
    priceGenRub: roundImg(0.02),
    priceRealKopecks: 210,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "grok-imagine-image-quality",
    name: "Grok Imagine Quality",
    provider: "xAI",
    category: "image",
    description: "Качественный тир Grok Imagine — выше детализация и точность следования промту.",
    priceGenRub: roundImg(0.045),
    priceRealKopecks: 470,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "gpt-image-1-5",
    name: "GPT-Image-1.5",
    provider: "OpenAI",
    category: "image",
    // Токенный тариф — оценка по аналогии с GPT-Image-1/2 (между ними по позиционированию).
    description: "Промежуточное поколение GPT-Image между 1 и 2 — улучшенная детализация.",
    priceGenRub: 4.5,
    priceRealKopecks: 570,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
  {
    id: "gpt-image-1-mini",
    name: "GPT-Image-1 Mini",
    provider: "OpenAI",
    category: "image",
    description: "Компактная и быстрая версия GPT-Image-1 — ниже цена за счёт меньшей детализации.",
    priceGenRub: 1.8,
    priceRealKopecks: 180,
    inputBadges: ["Текст"],
    outputBadges: ["Изображение"],
  },
];

const roundVideo = (usd: number) => Math.round(usd * K * 10) / 10;

export const VIDEO_MODELS: PreviewModel[] = [
  {
    id: "sora-2",
    name: "Sora 2",
    provider: "OpenAI",
    category: "video",
    description: "Флагманская видео-модель OpenAI — реалистичное движение и физика сцены.",
    contextLabel: "до 20 сек, 720p",
    priceVideoRub: roundVideo(0.08),
    priceUnit: "sec",
    priceRealKopecks: 2500,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "sora-2-pro",
    name: "Sora 2 Pro",
    provider: "OpenAI",
    category: "video",
    description: "Топовый тир Sora — более высокое разрешение и качество деталей.",
    contextLabel: "до 20 сек, 720-1080p",
    priceVideoRub: roundVideo(0.24),
    priceUnit: "sec",
    priceRealKopecks: 12540,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "veo-3-1-fast",
    name: "Veo 3.1 Fast",
    provider: "Google",
    category: "video",
    description: "Быстрая генерация видео Google — короткое время ожидания.",
    contextLabel: "8 сек, 720p",
    priceVideoRub: roundVideo(0.08),
    priceUnit: "sec",
    priceRealKopecks: 6840,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "veo-3-1-quality",
    name: "Veo 3.1 Quality",
    provider: "Google",
    category: "video",
    description: "Максимальное качество Veo — для финальных, а не черновых роликов.",
    contextLabel: "8 сек, до 4K",
    priceVideoRub: roundVideo(0.16),
    priceUnit: "sec",
    priceRealKopecks: 16720,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "veo-3-1-lite",
    name: "Veo 3.1 Lite",
    provider: "Google",
    category: "video",
    description: "Бюджетный вход в линейку Veo — тариф за клип, а не за секунду.",
    contextLabel: "8 сек, 720p",
    priceVideoRub: roundVideo(0.07),
    priceUnit: "call",
    priceRealKopecks: 2576,
    inputBadges: ["Текст"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-v2-6",
    name: "Kling v2.6",
    provider: "Kuaishou",
    category: "video",
    description: "Проверенная модель Kling — хороший баланс цены и качества.",
    contextLabel: "5-10 сек, 720-1080p",
    priceVideoRub: roundVideo(0.0368),
    priceUnit: "sec",
    priceRealKopecks: 4275,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-v3",
    name: "Kling V3",
    provider: "Kuaishou",
    category: "video",
    description: "Новое поколение Kling — точнее следует промту и референсам.",
    contextLabel: "5-10 сек, до 4K",
    priceVideoRub: roundVideo(0.0672),
    priceUnit: "sec",
    priceRealKopecks: 4275,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-v3-omni",
    name: "Kling V3 Omni",
    provider: "Kuaishou",
    category: "video",
    description: "Мультизадачная версия Kling V3 — несколько референсов и режимов в одной модели.",
    contextLabel: "5-10 сек, до 4K",
    priceVideoRub: roundVideo(0.0672),
    priceUnit: "sec",
    priceRealKopecks: 5700,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-video-o1",
    name: "Kling Video O1",
    provider: "Kuaishou",
    category: "video",
    description: "Модель Kling с акцентом на связность длинных сцен.",
    contextLabel: "5-10 сек",
    priceVideoRub: roundVideo(0.0672),
    priceUnit: "sec",
    priceRealKopecks: 5700,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-3-turbo",
    name: "Kling 3.0 Turbo",
    provider: "Kuaishou",
    category: "video",
    description: "Ускоренная генерация в топовом качестве Kling 3.0.",
    contextLabel: "5-10 сек, 720-1080p",
    priceVideoRub: roundVideo(0.1144),
    priceUnit: "sec",
    priceRealKopecks: 4000,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "minimax-hailuo-2-3",
    name: "MiniMax Hailuo 2.3",
    provider: "MiniMax",
    category: "video",
    description: "Актуальное поколение Hailuo — выше качество движения.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.0488),
    priceUnit: "sec",
    priceRealKopecks: 5130,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "minimax-hailuo-2-3-fast",
    name: "MiniMax Hailuo 2.3 Fast",
    provider: "MiniMax",
    category: "video",
    description: "Ускоренный режим Hailuo 2.3 — быстрее при небольшой потере качества.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.0248),
    priceUnit: "sec",
    priceRealKopecks: 1560,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "pixverse-v6",
    name: "Pixverse V6",
    provider: "Pixverse",
    category: "video",
    description: "Недорогая модель для быстрых черновых роликов.",
    contextLabel: "360p",
    priceVideoRub: roundVideo(0.016),
    priceUnit: "sec",
    priceRealKopecks: 850,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "wan-2-6",
    name: "Wan 2.6",
    provider: "Alibaba",
    category: "video",
    // Реальная цена снижена 2026-09-03: сверено с RouterAI (4,52 ₽/сек,
    // проверено вживую на routerai.ru/ai-video) — новая цена = (RouterAI ×
    // 0,95) × реальная длительность по умолчанию (5 сек), это единственная
    // видео-модель, где старая цена была выше этого ориентира.
    description: "Предыдущее поколение Wan — проверенное качество по средней цене.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.05),
    priceUnit: "sec",
    priceRealKopecks: 2147,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "seedance-1-5-pro",
    name: "Seedance 1.5 Pro",
    provider: "ByteDance",
    category: "video",
    description: "Доступная модель ByteDance — звук, фиксированная камера, 6 форматов кадра.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.0204),
    priceUnit: "sec",
    priceRealKopecks: 2784,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "seedance-2-0",
    name: "Seedance 2.0",
    provider: "ByteDance",
    category: "video",
    description: "Новое поколение Seedance — до 4K, адаптивный формат, мультиреференс.",
    contextLabel: "до 4K",
    priceVideoRub: roundVideo(0.066),
    priceUnit: "sec",
    priceRealKopecks: 8075,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "seedance-2-0-fast",
    name: "Seedance 2.0 Fast",
    provider: "ByteDance",
    category: "video",
    description: "Быстрый и доступный тир Seedance 2.0 — тот же движок, ниже цена.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.03984),
    priceUnit: "sec",
    priceRealKopecks: 4750,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "seedance-2-5",
    name: "Seedance 2.5",
    provider: "ByteDance",
    category: "video",
    description: "Новейшая версия Seedance — самые длинные ролики и мультиреференс в подборке.",
    contextLabel: "4-30 сек, 480-1080p",
    priceVideoRub: roundVideo(0.09608),
    priceUnit: "sec",
    priceRealKopecks: 12350,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "vidu-q3",
    name: "Vidu Q3",
    provider: "Vidu",
    category: "video",
    description: "Базовый тир Vidu — работает только по референсным фото, без чистого текста.",
    contextLabel: "до 1080p, только по фото",
    priceVideoRub: roundVideo(0.08),
    priceUnit: "sec",
    priceRealKopecks: 2500,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "vidu-q3-turbo",
    name: "Vidu Q3 Turbo",
    provider: "Vidu",
    category: "video",
    description: "Быстрый тир Vidu — доступная цена, звук по умолчанию.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.032),
    priceUnit: "sec",
    priceRealKopecks: 1500,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "vidu-q3-pro",
    name: "Vidu Q3 Pro",
    provider: "Vidu",
    category: "video",
    description: "Старший тир Vidu Q3 — выше качество, чем у Turbo.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.056),
    priceUnit: "sec",
    priceRealKopecks: 2950,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "grok-imagine-1-5",
    name: "Grok Imagine 1.5",
    provider: "xAI",
    category: "video",
    description: "Видео-модель xAI — ролики до 30 секунд, необычные форматы кадра.",
    contextLabel: "до 30 сек, 480-720p",
    priceVideoRub: roundVideo(0.0102),
    priceUnit: "sec",
    priceRealKopecks: 5130,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "wan-2-7",
    name: "Wan 2.7",
    provider: "Alibaba",
    category: "video",
    description: "Новое поколение Wan после 2.6 — тот же набор возможностей.",
    contextLabel: "до 1080p",
    priceVideoRub: roundVideo(0.0664),
    priceUnit: "sec",
    priceRealKopecks: 5225,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Видео"],
  },
  {
    id: "kling-v3-motion-control",
    name: "Kling V3 Motion Control",
    provider: "Kuaishou",
    category: "video",
    description: "Перенос движения камеры с видео-референса — не оживление фото.",
    contextLabel: "5-10 сек, до 4K",
    priceVideoRub: roundVideo(0.10288),
    priceUnit: "sec",
    priceRealKopecks: 5400,
    inputBadges: ["Текст", "Видео"],
    outputBadges: ["Видео"],
  },
];

// FREE_MODELS (2026-09-02) — синхронизировано с реально активными бесплатными
// моделями в проде (NeuralNetwork.objects.filter(is_free=True, is_active=True)):
// 14 из 14. Три провайдера, не только OpenRouter: openrouter_free (6),
// zai_free (3, Z.ai/Zhipu — GLM-*-Flash), cloudflare_free (5, Cloudflare
// Workers AI, общий дневной пул 10 000 "neurons"). Скрыты из общего каталога
// (category="text" не считает их) — показываются только во вкладке
// «Бесплатные», как и в проде (см. add_openrouter_free_models.py,
// add_zai_free_models.py, add_cloudflare_free_models.py). Ранее в проде были
// активны ещё free-nemotron-nano-9b/free-nemotron-3-nano-30b/
// free-nemotron-nano-12b-vl — деактивированы 2026-09-02 (живой вызов вернул
// 404 model_not_found/снята с бесплатного тарифа). free-glm-5-2 и
// free-gemma-4-31b проверены живьём в тот же день — вернули 429 "temporarily
// rate-limited upstream" (не 404), оставлены активными.
export const FREE_MODELS: PreviewModel[] = [
  {
    id: "free-nemotron-3-ultra",
    name: "Nemotron 3 Ultra",
    provider: "OpenRouter",
    category: "text",
    description: "Флагманская модель NVIDIA для сложных рассуждений и многошаговых задач, контекст 1M токенов.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-nemotron-3-super",
    name: "Nemotron 3 Super",
    provider: "OpenRouter",
    category: "text",
    description: "Структурированные ответы и сложные многошаговые рассуждения, контекст 1M токенов.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-north-mini-code",
    name: "North Mini Code",
    provider: "OpenRouter",
    category: "text",
    description: "Агентная модель Cohere для кода, terminal-задач и разработки.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-gemma-4-31b",
    name: "Gemma 4 31B",
    provider: "OpenRouter",
    category: "text",
    description: "Модель Google DeepMind с поддержкой изображений — универсальный чат и код.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-laguna-xs21",
    name: "Laguna XS 2.1",
    provider: "OpenRouter",
    category: "text",
    description: "Компактная модель Poolside для кода — быстрая и экономичная.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-glm-5-2",
    name: "GLM 5.2",
    provider: "OpenRouter",
    category: "text",
    description: "Флагманская модель Zhipu AI — рассуждения и код.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-glm-4-7-flash",
    name: "GLM-4.7 Flash",
    provider: "Z.ai",
    category: "text",
    description: "Быстрая модель Z.ai для кода, рассуждений и агентных задач.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-glm-4-5-flash",
    name: "GLM-4.5 Flash",
    provider: "Z.ai",
    category: "text",
    description: "Модель Z.ai с хорошей производительностью для рассуждений и кода.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-glm-4-6v-flash",
    name: "GLM-4.6V Flash",
    provider: "Z.ai",
    category: "text",
    description: "Модель Z.ai с пониманием изображений — низкая задержка, быстрый ответ.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-cf-llama-4-scout",
    name: "Llama 4 Scout",
    provider: "Cloudflare",
    category: "text",
    description: "Мультимодальная MoE-модель Meta — понимает текст и изображения.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-cf-gpt-oss-120b",
    name: "GPT-OSS 120B (Cloudflare)",
    provider: "Cloudflare",
    category: "text",
    description: "Открытая модель OpenAI для рассуждений — независимый резерв от основной модели.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-cf-qwen3-30b",
    name: "Qwen3 30B",
    provider: "Cloudflare",
    category: "text",
    description: "MoE-модель Qwen для рассуждений и агентных задач.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-cf-mistral-small",
    name: "Mistral Small 3.1",
    provider: "Cloudflare",
    category: "text",
    description: "Модель Mistral с пониманием изображений, контекст 128K токенов.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст", "Изображения"],
    outputBadges: ["Текст"],
  },
  {
    id: "free-cf-deepseek-r1-distill",
    name: "DeepSeek R1 Distill 32B",
    provider: "Cloudflare",
    category: "text",
    description: "Дистиллированная модель рассуждений DeepSeek R1 — сильна в логике и математике.",
    isFree: true,
    dailyLimit: 15,
    inputBadges: ["Текст"],
    outputBadges: ["Текст"],
  },
];

export const PREVIEW_MODELS: PreviewModel[] = [...TEXT_MODELS, ...IMAGE_MODELS, ...VIDEO_MODELS, ...FREE_MODELS];
