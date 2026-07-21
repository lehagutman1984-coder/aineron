import type {
  StarsUsage,
  ChatCompletionRequest,
  ChatCompletionResponse,
  AnthropicRequest,
  AnthropicResponse,
  ImageGenerationRequest,
  ImageGenerationResponse,
  ModelListResponse,
  APIKey,
  APIKeyCreateRequest,
  APIKeyCreateResponse,
  User,
  Category,
  NetworkListItem,
  NetworkDetail,
  WebMessage,
  ChatListItem,
  ChatDetail,
  AttachmentItem,
  CreateChatResponse,
  SendMessageResponse,
  AuthUser,
  Organization,
  OrgMember,
  OrgInvite,
  Invoice,
  UsageStats,
  BlogCategory,
  BlogPost,
  BlogPostDetail,
  TariffsResponse,
  AutoRenewResponse,
  CreatePaymentResponse,
  PageSaleSettings,
  PaymentHistory,
  ApplyPromoResponse,
  ReferralData,
  FilesResponse,
  RerunGenerationResponse,
  UpscaleGenerationResponse,
  VariationsResponse,
  ShareGenerationResponse,
  GalleryResponse,
  PublicGeneration,
  CompareResponse,
  ImageCompareResponse,
  EnhancePromptResponse,
  PromptTemplate,
  Project,
  ProjectFile,
  ProjectConnector,
  ProjectCollaborator,
  RepoTreeItem,
  ProjectCommit,
  CommitFile,
  PublicSpace,
  DeployStatusResponse,
  ArenaEntry,
  ArenaVoteResult,
  ProjectGraph,
} from "./types";

export const BASE_URL =
  (process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1").replace(/\/$/, "");

export class APIError extends Error {
  status: number;
  code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

export async function request<T>(
  path: string,
  init: RequestInit & { apiKey?: string } = {}
): Promise<T> {
  const { apiKey, ...fetchInit } = init;

  // Don't set Content-Type for FormData — browser sets it with correct boundary
  const isFormData = fetchInit.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(fetchInit.headers as Record<string, string> | undefined),
  };

  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...fetchInit,
    headers,
    credentials: "include", // send Django session cookie for web-auth routes
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg =
      (body as { error?: { message?: string } })?.error?.message ??
      `HTTP ${res.status}`;
    const code =
      (body as { error?: { code?: string } })?.error?.code ?? null;
    throw new APIError(res.status, msg, code);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ============ Models ============

export const listModels = (apiKey: string) =>
  request<ModelListResponse>("/models", { apiKey });

// ============ Chat ============

export const createChatCompletion = (
  body: ChatCompletionRequest,
  apiKey: string
) =>
  request<ChatCompletionResponse>("/chat/completions", {
    method: "POST",
    body: JSON.stringify(body),
    apiKey,
  });

export const createAnthropicMessage = (
  body: AnthropicRequest,
  apiKey: string
) =>
  request<AnthropicResponse>("/messages", {
    method: "POST",
    body: JSON.stringify(body),
    apiKey,
  });

// ============ Images ============

export const generateImage = (
  body: ImageGenerationRequest,
  apiKey: string
) =>
  request<ImageGenerationResponse>("/images/generations", {
    method: "POST",
    body: JSON.stringify(body),
    apiKey,
  });

// ============ API Keys ============

export const listAPIKeys = () =>
  request<APIKey[]>("/keys/", { method: "GET" });

export const createAPIKey = (body: APIKeyCreateRequest) =>
  request<APIKeyCreateResponse>("/keys/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const deleteAPIKey = (id: number) =>
  request<void>(`/keys/${id}/`, { method: "DELETE" });

// ============ Auth (DRF session endpoints) ============

export const getMe = (): Promise<AuthUser> =>
  request<AuthUser>("/auth/me/");

export const authLogin = (email: string, password: string): Promise<AuthUser> =>
  request<AuthUser>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const authLogout = (): Promise<{ ok: boolean }> =>
  request<{ ok: boolean }>("/auth/logout/", { method: "POST" });

export const authRegister = (email: string, password: string, lang?: string): Promise<AuthUser> =>
  request<AuthUser>("/auth/register/", {
    method: "POST",
    body: JSON.stringify({ email, password, ...(lang && { lang }) }),
  });

export const authVerifyEmail = (code: string): Promise<{ ok: boolean }> =>
  request<{ ok: boolean }>("/auth/verify-email/", {
    method: "POST",
    body: JSON.stringify({ code }),
  });

export const authResendVerification = (): Promise<{ ok: boolean }> =>
  request<{ ok: boolean }>("/auth/resend-verification/", { method: "POST" });

// ============ Catalog ============

export const listCategories = (): Promise<Category[]> =>
  request<Category[]>("/catalog/categories/");

export const listNetworks = (params?: {
  category?: string;
  is_popular?: boolean;
  provider?: string;
}): Promise<NetworkListItem[]> => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.is_popular) qs.set("is_popular", "1");
  if (params?.provider) qs.set("provider", params.provider);
  const query = qs.toString();
  return request<NetworkListItem[]>(`/catalog/networks/${query ? "?" + query : ""}`);
};

export const getNetwork = (slug: string): Promise<NetworkDetail> =>
  request<NetworkDetail>(`/catalog/networks/${slug}/`);

// ============ Web Chats ============

export const listChats = (params?: { project_id?: number | "none" }): Promise<ChatListItem[]> => {
  const qs = params?.project_id !== undefined ? `?project_id=${params.project_id}` : "";
  return request<ChatListItem[]>(`/chats/${qs}`);
};

export const createChat = (body: {
  network_slug: string;
  message: string;
  files?: unknown[];
  settings?: Record<string, unknown>;
  web_search?: boolean;
  project_id?: number;
}): Promise<CreateChatResponse> =>
  request<CreateChatResponse>("/chats/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getChat = (id: number): Promise<ChatDetail> =>
  request<ChatDetail>(`/chats/${id}/`);

export const deleteChat = (id: number): Promise<void> =>
  request<void>(`/chats/${id}/`, { method: "DELETE" });

export const renameChat = (id: number, title: string): Promise<{ id: number; title: string }> =>
  request<{ id: number; title: string }>(`/chats/${id}/`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const searchChats = (q: string, page = 1): Promise<import("./types").ChatSearchResponse> =>
  request<import("./types").ChatSearchResponse>(`/chats/search/?q=${encodeURIComponent(q)}&page=${page}`);

export const exportChat = (id: number, format: "md" | "html" = "md"): string =>
  `${BASE_URL}/chats/${id}/export/?format=${format}`;

export const regenerateChat = (chatId: number): Promise<{ assistant_message_id: number; new_balance: number; new_balance_kopecks: number }> =>
  request<{ assistant_message_id: number; new_balance: number; new_balance_kopecks: number }>(`/chats/${chatId}/regenerate/`, {
    method: "POST",
  });

export const sendMessage = (
  chatId: number,
  body: {
    message: string;
    files?: unknown[];
    settings?: Record<string, unknown>;
    attachment_ids?: string[];
    web_search?: boolean;
  }
): Promise<SendMessageResponse> =>
  request<SendMessageResponse>(`/chats/${chatId}/messages/`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const uploadFile = (chatId: number, file: File): Promise<AttachmentItem> => {
  const formData = new FormData();
  formData.append("file", file);
  return fetch(`${BASE_URL}/chats/${chatId}/upload/`, {
    method: "POST",
    body: formData,
    credentials: "include",
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: { message?: string; code?: string } };
      throw new APIError(res.status, body?.error?.message ?? `HTTP ${res.status}`, body?.error?.code ?? null);
    }
    return res.json() as Promise<AttachmentItem>;
  });
};

// Загрузка референсного фото ДО создания чата (img2img со стартового экрана модели)
export const uploadReferenceImage = (file: File): Promise<AttachmentItem> => {
  const formData = new FormData();
  formData.append("file", file);
  return fetch(`${BASE_URL}/uploads/reference-image/`, {
    method: "POST",
    body: formData,
    credentials: "include",
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: { message?: string; code?: string } };
      throw new APIError(res.status, body?.error?.message ?? `HTTP ${res.status}`, body?.error?.code ?? null);
    }
    return res.json() as Promise<AttachmentItem>;
  });
};

export const getMessageStatus = (messageId: number): Promise<WebMessage> =>
  request<WebMessage>(`/messages/${messageId}/status/`);

// ============ SSE Streaming ============

type SSEEvent =
  | { type: "init"; user_message_id: number; assistant_message_id: number; new_balance: number; new_balance_kopecks: number }
  | { type: "search_done"; preview: string }
  | { type: "token"; text: string }
  | { type: "done"; content: string; plain_text: string; search_context?: string; sources?: import("./types").KBSource[]; variants?: import("./types").MessageVariant[]; commit_proposed?: { id: number; commit_message: string; files_count: number; project_id: number } | null; used_memory?: boolean }
  | { type: "error"; message: string };

export interface CommitProposed {
  id: number;
  commit_message: string;
  files_count: number;
  project_id: number;
}

export async function streamMessage(
  chatId: number,
  body: { message: string; files?: unknown[]; settings?: Record<string, unknown>; attachment_ids?: string[]; web_search?: boolean; variants_mode?: boolean },
  callbacks: {
    onInit: (data: { user_message_id: number; assistant_message_id: number; new_balance: number; new_balance_kopecks: number }) => void;
    onSearchDone?: (preview: string) => void;
    onToken: (text: string) => void;
    onDone: (data: { content: string; plain_text: string; search_context?: string; sources?: import("./types").KBSource[]; variants?: import("./types").MessageVariant[]; commit_proposed?: CommitProposed | null; used_memory?: boolean }) => void;
    onError: (message: string) => void;
  }
): Promise<void> {
  const res = await fetch(`${BASE_URL}/chats/${chatId}/messages/stream/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({})) as { error?: { message?: string; code?: string } };
    throw new APIError(
      res.status,
      errBody?.error?.message ?? `HTTP ${res.status}`,
      errBody?.error?.code ?? null
    );
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6)) as SSEEvent;
        if (event.type === "init") callbacks.onInit(event);
        else if (event.type === "search_done") callbacks.onSearchDone?.(event.preview);
        else if (event.type === "token") callbacks.onToken(event.text);
        else if (event.type === "done") callbacks.onDone(event);
        else if (event.type === "error") callbacks.onError(event.message);
      } catch {
        // ignore malformed SSE line
      }
    }
  }
}

// ============ Organizations ============

export const listOrgs = (): Promise<Organization[]> =>
  request<Organization[]>("/orgs/");

export const createOrg = (body: {
  name: string;
  inn?: string;
  kpp?: string;
  legal_address?: string;
}): Promise<Organization> =>
  request<Organization>("/orgs/", { method: "POST", body: JSON.stringify(body) });

export const getOrg = (id: number): Promise<Organization> =>
  request<Organization>(`/orgs/${id}/`);

export const updateOrg = (
  id: number,
  body: Partial<{ name: string; inn: string; kpp: string; legal_address: string }>
): Promise<Organization> =>
  request<Organization>(`/orgs/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const listOrgMembers = (orgId: number): Promise<OrgMember[]> =>
  request<OrgMember[]>(`/orgs/${orgId}/members/`);

export const removeOrgMember = (orgId: number, userId: number): Promise<void> =>
  request<void>(`/orgs/${orgId}/members/${userId}/`, { method: "DELETE" });

export const listOrgInvites = (orgId: number): Promise<OrgInvite[]> =>
  request<OrgInvite[]>(`/orgs/${orgId}/invites/`);

export const createOrgInvite = (
  orgId: number,
  email: string
): Promise<OrgInvite> =>
  request<OrgInvite>(`/orgs/${orgId}/invites/`, {
    method: "POST",
    body: JSON.stringify({ email }),
  });

export const acceptInvite = (
  token: string
): Promise<{ ok: boolean; organization: Organization }> =>
  request(`/orgs/invites/${token}/accept/`, { method: "POST" });

export const listInvoices = (orgId: number): Promise<Invoice[]> =>
  request<Invoice[]>(`/orgs/${orgId}/invoices/`);

export const createInvoice = (
  orgId: number,
  body: { amount_rub: number; description?: string }
): Promise<Invoice> =>
  request<Invoice>(`/orgs/${orgId}/invoices/`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const generateOrgTgToken = (orgId: number): Promise<{ token: string }> =>
  request<{ token: string }>(`/orgs/${orgId}/tg-token/`, { method: "POST" });

export const listOrgTgGroups = (orgId: number): Promise<Array<{ id: number; group_id: number; group_title: string; enabled: boolean; created_at: string }>> =>
  request(`/orgs/${orgId}/tg-groups/`);

export const unregisterOrgTgGroup = (orgId: number, groupId: number): Promise<void> =>
  request<void>(`/orgs/${orgId}/tg-groups/?group_id=${groupId}`, { method: "DELETE" });

// ============ Usage statistics ============

export const getUsageStats = (params?: {
  days?: number;
  org_id?: number;
}): Promise<UsageStats> => {
  const qs = new URLSearchParams();
  if (params?.days) qs.set("days", String(params.days));
  if (params?.org_id) qs.set("org_id", String(params.org_id));
  const query = qs.toString();
  return request<UsageStats>(`/usage/${query ? "?" + query : ""}`);
};

// ============ Blog ============

export const listBlogCategories = (): Promise<BlogCategory[]> =>
  request<BlogCategory[]>("/blog/categories/");

export const listBlogPosts = (params?: {
  category?: string;
  show_on_main?: boolean;
}): Promise<BlogPost[]> => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.show_on_main) qs.set("show_on_main", "1");
  const query = qs.toString();
  return request<BlogPost[]>(`/blog/posts/${query ? "?" + query : ""}`);
};

export const getBlogPost = (slug: string): Promise<BlogPostDetail> =>
  request<BlogPostDetail>(`/blog/posts/${slug}/`);

// ============ Billing ============

export const getTariffs = (): Promise<TariffsResponse> =>
  request<TariffsResponse>("/billing/tariffs/");

export const payTariff = (
  tariffId: number,
  promoCode?: string,
): Promise<CreatePaymentResponse> =>
  request<CreatePaymentResponse>(`/billing/tariffs/${tariffId}/pay/`, {
    method: "POST",
    body: JSON.stringify(promoCode ? { promo_code: promoCode } : {}),
  });

export interface PromoCheckResponse {
  ok: boolean;
  code: string;
  type: "discount" | "balance";
  discount_percent: number;
  kopecks: number;
  price?: string;
  discounted_price?: string;
}

export const checkPromoCode = (
  code: string,
  tariffId?: number,
): Promise<PromoCheckResponse> =>
  request<PromoCheckResponse>("/billing/promo/check/", {
    method: "POST",
    body: JSON.stringify({ code, tariff_id: tariffId }),
  });

export const updateAutoRenew = (autoRenew: boolean): Promise<AutoRenewResponse> =>
  request<AutoRenewResponse>("/billing/subscription/", {
    method: "PATCH",
    body: JSON.stringify({ auto_renew: autoRenew }),
  });

export const getPageSaleSettings = (): Promise<PageSaleSettings> =>
  request<PageSaleSettings>("/billing/pages/");

export const buyPages = (pages: number): Promise<CreatePaymentResponse> =>
  request<CreatePaymentResponse>("/billing/pages/buy/", {
    method: "POST",
    body: JSON.stringify({ pages }),
  });

export const getPaymentHistory = (): Promise<PaymentHistory[]> =>
  request<PaymentHistory[]>("/billing/history/");

// ── Crypto Pay (оплата криптовалютой) ──────────────────────────────────────

export interface CryptoConfig {
  enabled: boolean;
  assets: string[];
  mode: "rub" | "usd";
  min_amount: number;
  max_amount: number;
  kopecks_per_usd?: number;
}

export interface CryptoTopupResponse {
  payment_id: number;
  invoice_id: number;
  amount: string;
  currency: "RUB" | "USD";
  credits: number;
  pay_url: string;
  web_url: string | null;
  expires_in: number;
}

export interface CryptoStatusResponse {
  payment_id: number;
  status: "pending" | "success" | "failed" | "refunded";
  balance_kopecks: number;
}

export const getCryptoConfig = (): Promise<CryptoConfig> =>
  request<CryptoConfig>("/billing/crypto/");

export const createCryptoTopup = (
  body: { amount?: number; amount_usd?: number },
): Promise<CryptoTopupResponse> =>
  request<CryptoTopupResponse>("/billing/crypto/topup/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getCryptoTopupStatus = (paymentId: number): Promise<CryptoStatusResponse> =>
  request<CryptoStatusResponse>(`/billing/crypto/status/${paymentId}/`);

export const getStarsUsage = (days?: number): Promise<StarsUsage> =>
  request<StarsUsage>(`/billing/stars-usage/${days ? `?days=${days}` : ""}`);

export const applyPromoCode = (code: string): Promise<ApplyPromoResponse> =>
  request<ApplyPromoResponse>("/billing/promo/", {
    method: "POST",
    body: JSON.stringify({ code }),
  });

// ============ Files ============

export const getUserFiles = (params: {
  page?: number;
  per_page?: number;
  category?: "all" | "images" | "videos";
}): Promise<FilesResponse> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.per_page) q.set("per_page", String(params.per_page));
  if (params.category) q.set("category", params.category);
  return request<FilesResponse>(`/files/?${q}`);
};

export const deleteUserFile = (fileId: string): Promise<void> =>
  request<void>(`/files/${fileId}/`, { method: "DELETE" });

export const rerunGeneration = (genId: string): Promise<RerunGenerationResponse> =>
  request<RerunGenerationResponse>(`/generations/${genId}/rerun/`, {
    method: "POST",
  });

export const upscaleGeneration = (
  genId: string,
  factor: 2 | 4
): Promise<UpscaleGenerationResponse> =>
  request<UpscaleGenerationResponse>(`/generations/${genId}/upscale/`, {
    method: "POST",
    body: JSON.stringify({ factor }),
  });

export const createVariations = (
  genId: string,
  count = 4
): Promise<VariationsResponse> =>
  request<VariationsResponse>(`/generations/${genId}/variations/`, {
    method: "POST",
    body: JSON.stringify({ count }),
  });

export const describeGeneration = (
  genId: string
): Promise<{ prompt: string }> =>
  request<{ prompt: string }>(`/generations/${genId}/describe/`, {
    method: "POST",
  });

export const downloadImageUrl = (url: string, filename?: string): void => {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "aineron-image.png";
  a.target = "_blank";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

export const likeGeneration = (genId: number): Promise<{ id: number; likes: number }> =>
  request<{ id: number; likes: number }>(`/generations/${genId}/like/`, { method: "POST" });

export const favoriteGeneration = (genId: number): Promise<{ id: number; is_favorite: boolean }> =>
  request<{ id: number; is_favorite: boolean }>(`/generations/${genId}/favorite/`, { method: "POST" });

export const getFavorites = (params?: { page?: number; per_page?: number; media_type?: string }): Promise<{
  items: Array<{ id: number; image_url: string; prompt: string; model_name: string; media_type: string; is_favorite: boolean; created_at: string }>;
  has_next: boolean;
  page: number;
  total: number;
}> => {
  const q = new URLSearchParams();
  if (params?.page) q.set("page", String(params.page));
  if (params?.per_page) q.set("per_page", String(params.per_page));
  if (params?.media_type) q.set("media_type", params.media_type);
  return request(`/favorites/${q.toString() ? "?" + q.toString() : ""}`);
};

export const removeBackground = (genId: number): Promise<{ id: number; url: string }> =>
  request<{ id: number; url: string }>(`/generations/${genId}/remove-background/`, { method: "POST" });

// ============ Sprint 7: Public gallery & sharing ============

export const shareGeneration = (genId: string): Promise<ShareGenerationResponse> =>
  request<ShareGenerationResponse>(`/generations/${genId}/share/`, { method: "POST" });

export const unshareGeneration = (genId: string): Promise<ShareGenerationResponse> =>
  request<ShareGenerationResponse>(`/generations/${genId}/unshare/`, { method: "POST" });

export const getGallery = (params: {
  page?: number;
  per_page?: number;
  media_type?: "image" | "video";
  model_name?: string;
  search?: string;
}): Promise<GalleryResponse> => {
  const q = new URLSearchParams();
  if (params.page) q.set("page", String(params.page));
  if (params.per_page) q.set("per_page", String(params.per_page));
  if (params.media_type) q.set("media_type", params.media_type);
  if (params.model_name) q.set("model_name", params.model_name);
  if (params.search) q.set("search", params.search);
  return request<GalleryResponse>(`/gallery/?${q}`);
};

export const getPublicGeneration = (slug: string): Promise<PublicGeneration> =>
  request<PublicGeneration>(`/generations/${slug}/public/`);

// ============ Prompt Library ============

export const listPrompts = (category?: string, lang?: string): Promise<PromptTemplate[]> => {
  const qs = new URLSearchParams();
  if (category) qs.set("category", category);
  if (lang) qs.set("lang", lang);
  const query = qs.toString();
  return request<PromptTemplate[]>(`/prompts/${query ? `?${query}` : ""}`);
};

export const createPrompt = (body: {
  title: string;
  content: string;
  category: string;
  icon?: string;
}): Promise<PromptTemplate> =>
  request<PromptTemplate>("/prompts/", { method: "POST", body: JSON.stringify(body) });

export const deletePrompt = (id: number): Promise<void> =>
  request<void>(`/prompts/${id}/`, { method: "DELETE" });

// ============ Model Arena ============

export const compareModels = (body: {
  message: string;
  network_slugs: string[];
}): Promise<CompareResponse> =>
  request<CompareResponse>("/compare/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const compareImages = (body: {
  prompt: string;
  models: string[];
  settings?: Record<string, unknown>;
}): Promise<ImageCompareResponse> =>
  request<ImageCompareResponse>("/images/compare/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const enhanceImagePrompt = (body: {
  prompt: string;
  style?: string;
}): Promise<EnhancePromptResponse> =>
  request<EnhancePromptResponse>("/images/enhance-prompt/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getArenaLeaderboard = (): Promise<{ results: ArenaEntry[] }> =>
  request<{ results: ArenaEntry[] }>("/arena/leaderboard/");

export const voteArena = (body: {
  winner_slug: string;
  loser_slug: string;
  compare_chat_ids: number[];
}): Promise<ArenaVoteResult> =>
  request<ArenaVoteResult>("/arena/vote/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getProjectGraph = (projectId: number): Promise<ProjectGraph> =>
  request<ProjectGraph>(`/projects/${projectId}/graph/`);

// ============ Referral ============

export const getReferral = (): Promise<ReferralData> =>
  request<ReferralData>("/referral/");

export const requestReferralWithdrawal = (body: {
  amount: number;
  payout_destination: string;
}): Promise<{ ok: boolean }> =>
  request<{ ok: boolean }>("/referral/withdraw/", {
    method: "POST",
    body: JSON.stringify(body),
  });

// ============ Audio ============

export const transcribeAudio = (blob: Blob): Promise<string> => {
  const ext = blob.type.includes("mp4") ? "mp4" : blob.type.includes("ogg") ? "ogg" : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);
  return fetch(`${BASE_URL}/audio/transcriptions`, {
    method: "POST",
    body: form,
    credentials: "include",
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: { message?: string } };
      throw new APIError(res.status, body?.error?.message ?? `HTTP ${res.status}`);
    }
    const data = await res.json() as { text: string };
    return data.text ?? "";
  });
};

export const synthesizeSpeech = (text: string, voice = "alloy"): Promise<Blob> =>
  fetch(`${BASE_URL}/audio/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ input: text.slice(0, 2000), model: "tts-1", voice }),
  }).then(async (res) => {
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: { message?: string } };
      throw new APIError(res.status, body?.error?.message ?? `HTTP ${res.status}`);
    }
    return res.blob();
  });

// ============ Projects ============

export const listProjects = (): Promise<Project[]> =>
  request<Project[]>("/projects/");

export const createProject = (body: {
  name: string;
  system_prompt?: string;
  color?: string;
  icon?: string;
}): Promise<Project> =>
  request<Project>("/projects/", { method: "POST", body: JSON.stringify(body) });

export const updateProject = (
  id: number,
  body: Partial<{ name: string; system_prompt: string; color: string; icon: string; status: string }>
): Promise<Project> =>
  request<Project>(`/projects/${id}/`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteProject = (id: number): Promise<void> =>
  request<void>(`/projects/${id}/`, { method: "DELETE" });

// ============ Project Files (knowledge base) ============

export const listProjectFiles = (projectId: number): Promise<ProjectFile[]> =>
  request<ProjectFile[]>(`/projects/${projectId}/files/`);

export const uploadProjectFile = (projectId: number, file: File): Promise<ProjectFile> => {
  const form = new FormData();
  form.append("file", file);
  return request<ProjectFile>(`/projects/${projectId}/files/`, { method: "POST", body: form });
};

export const toggleProjectFile = (
  projectId: number,
  fileId: number,
  enabled: boolean,
): Promise<ProjectFile> =>
  request<ProjectFile>(`/projects/${projectId}/files/${fileId}/`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });

export const deleteProjectFile = (projectId: number, fileId: number): Promise<void> =>
  request<void>(`/projects/${projectId}/files/${fileId}/`, { method: "DELETE" });

export const searchProjectFiles = (projectId: number, query: string): Promise<ProjectFile[]> =>
  request<ProjectFile[]>(`/projects/${projectId}/files/search/?q=${encodeURIComponent(query)}`);

// ============ Project Connectors (Git integration) ============

export const listConnectors = (projectId: number): Promise<ProjectConnector[]> =>
  request<ProjectConnector[]>(`/projects/${projectId}/connectors/`);

export const createConnector = (
  projectId: number,
  data: { connector_type: "github" | "gitea" | "website" | "rss"; repo_url: string; access_token: string; branch?: string }
): Promise<ProjectConnector> =>
  request<ProjectConnector>(`/projects/${projectId}/connectors/`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const deleteConnector = (projectId: number, connectorId: number): Promise<void> =>
  request<void>(`/projects/${projectId}/connectors/${connectorId}/`, { method: "DELETE" });

export const listRepoFiles = (
  projectId: number,
  connectorId: number
): Promise<{ items: RepoTreeItem[] }> =>
  request<{ items: RepoTreeItem[] }>(`/projects/${projectId}/connectors/${connectorId}/files/`);

export const getRepoFileContent = (
  projectId: number,
  connectorId: number,
  filePath: string
): Promise<{ path: string; content: string }> =>
  request<{ path: string; content: string }>(
    `/projects/${projectId}/connectors/${connectorId}/file/?path=${encodeURIComponent(filePath)}`
  );

// ============ Project Commits ============

export const listCommits = (projectId: number): Promise<ProjectCommit[]> =>
  request<ProjectCommit[]>(`/projects/${projectId}/commits/`);

export const createCommit = (
  projectId: number,
  data: { connector_id?: number; commit_message: string; files: CommitFile[] }
): Promise<ProjectCommit> =>
  request<ProjectCommit>(`/projects/${projectId}/commits/`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const confirmCommit = (
  projectId: number,
  commitId: number,
  action: "push" | "pr" | "reject"
): Promise<{ status: string; commit_id?: number; kind?: string } | ProjectCommit> =>
  request(`/projects/${projectId}/commits/${commitId}/confirm/`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });

export const deleteCommit = (projectId: number, commitId: number): Promise<void> =>
  request(`/projects/${projectId}/commits/${commitId}/`, { method: "DELETE" });

// ============ Connector Sync (Sprint 4.2) ============

export const syncConnector = (
  projectId: number,
  connectorId: number
): Promise<{ status: string; connector_id: number }> =>
  request(`/projects/${projectId}/connectors/${connectorId}/sync/`, { method: "POST" });

export const patchConnector = (
  projectId: number,
  connectorId: number,
  data: { auto_sync?: boolean; deploy_webhook_url?: string }
): Promise<ProjectConnector> =>
  request<ProjectConnector>(`/projects/${projectId}/connectors/${connectorId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// ============ Connector Deploy (Sprint 7.2) ============

export const triggerDeploy = (
  projectId: number,
  connectorId: number
): Promise<DeployStatusResponse> =>
  request<DeployStatusResponse>(
    `/projects/${projectId}/connectors/${connectorId}/deploy/`,
    { method: "POST" }
  );

export const getDeployStatus = (
  projectId: number,
  connectorId: number
): Promise<DeployStatusResponse> =>
  request<DeployStatusResponse>(
    `/projects/${projectId}/connectors/${connectorId}/deploy/`
  );

export interface FileVersion {
  id: number;
  repo_sha: string;
  created_at: string;
  content_preview: string;
  size: number;
}

export const listFileVersions = (projectId: number, fileId: number): Promise<FileVersion[]> =>
  request<FileVersion[]>(`/projects/${projectId}/files/${fileId}/versions/`);

export const restoreFileVersion = (
  projectId: number,
  fileId: number,
  versionId: number
): Promise<{ restored: boolean; version_id: number; file_id: number }> =>
  request(`/projects/${projectId}/files/${fileId}/versions/${versionId}/restore/`, { method: "POST" });

// ============ Collaborators (Sprint 5.1) ============

export const listCollaborators = (projectId: number): Promise<ProjectCollaborator[]> =>
  request<ProjectCollaborator[]>(`/projects/${projectId}/collaborators/`);

export const addCollaborator = (
  projectId: number,
  email: string,
  role: "viewer" | "editor"
): Promise<ProjectCollaborator> =>
  request<ProjectCollaborator>(`/projects/${projectId}/collaborators/`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });

export const updateCollaboratorRole = (
  projectId: number,
  collabId: number,
  role: "viewer" | "editor"
): Promise<ProjectCollaborator> =>
  request<ProjectCollaborator>(`/projects/${projectId}/collaborators/${collabId}/`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });

export const removeCollaborator = (projectId: number, collabId: number): Promise<void> =>
  request(`/projects/${projectId}/collaborators/${collabId}/`, { method: "DELETE" });

// ============ Audit Log (Sprint 5.5) ============

export const listProjectAudit = (projectId: number): Promise<{ entries: import("./types").ProjectAuditEntry[] }> =>
  request(`/projects/${projectId}/audit/`);

// ============ Public Spaces ============

export const publishProject = (
  id: number,
  body: { is_public: boolean; public_show_files?: boolean; public_show_chats?: boolean }
): Promise<Project> =>
  request<Project>(`/projects/${id}/publish/`, { method: "POST", body: JSON.stringify(body) });

export const getPublicSpace = (slug: string): Promise<PublicSpace> =>
  request<PublicSpace>(`/public/spaces/${slug}/`);

// ============ AI Personas ============

export const listPersonas = (): Promise<import("./types").Persona[]> =>
  request("/personas/");

export const createPersona = (body: {
  name: string;
  description?: string;
  system_prompt: string;
  avatar_url?: string;
  network?: number | string | null;
}): Promise<import("./types").Persona> =>
  request("/personas/", { method: "POST", body: JSON.stringify(body) });

export const deletePersona = (id: number): Promise<void> =>
  request(`/personas/${id}/`, { method: "DELETE" });

// ============ User (legacy Django session endpoint, kept for compatibility) ============

export async function getCurrentUser(): Promise<User | null> {
  try {
    const res = await fetch("/users/api/user/", { credentials: "include" });
    if (!res.ok) return null;
    return res.json() as Promise<User>;
  } catch {
    return null;
  }
}

// ============ Sprint 3: Response Variants ============
// variants_mode is passed via streamMessage body — no separate endpoint needed

// ============ Sprint 4: Memory Quick Save + Toast ============

export const quickSaveFact = (text: string): Promise<{ id: number; content: string; created: boolean }> =>
  request("/memory/quick-save/", { method: "POST", body: JSON.stringify({ text }) });

export const getMemoryToast = (): Promise<import("./types").MemoryToastData> =>
  request("/memory/toast/");

export async function getMemoryFacts(): Promise<{ id: number; content: string; category: string; is_active: boolean }[]> {
  try {
    const res = await fetch(`${BASE_URL}/memory/`, { credentials: "include" });
    if (!res.ok) return [];
    const data = await res.json() as { results?: { id: number; content: string; category: string; is_active: boolean }[] } | { id: number; content: string; category: string; is_active: boolean }[];
    if (Array.isArray(data)) return data;
    return (data as { results?: { id: number; content: string; category: string; is_active: boolean }[] }).results ?? [];
  } catch {
    return [];
  }
}

export async function deactivateMemoryFact(id: number): Promise<void> {
  await fetch(`${BASE_URL}/memory/${id}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: false }),
    credentials: "include",
  });
}

// ============ Sprint 5: KB Health Dashboard ============

export const getProjectKBStats = (projectId: number): Promise<import("./types").ProjectKBStats> =>
  request<import("./types").ProjectKBStats>(`/projects/${projectId}/kb/stats/`);

export const reindexProjectFile = (projectId: number, fileId: number): Promise<{ ok: boolean; embed_status: string }> =>
  request(`/projects/${projectId}/files/${fileId}/reindex/`, { method: "POST" });

export const getFileChunks = (projectId: number, fileId: number): Promise<import("./types").ProjectChunk[]> =>
  request<import("./types").ProjectChunk[]>(`/projects/${projectId}/files/${fileId}/chunks/`);

// ============ Sprint 7: Conversation Branching ============

export const branchChat = (chatId: number, messageId: number): Promise<{ chat_id: number; title: string }> =>
  request(`/chats/${chatId}/branch/`, { method: "POST", body: JSON.stringify({ message_id: messageId }) });

// ============ Sprint 2: Deep Research ============

export const startDeepResearch = (
  chatId: number,
  question: string,
): Promise<import("./types").DeepResearchStartResponse> =>
  request(`/chats/${chatId}/research/`, { method: "POST", body: JSON.stringify({ question }) });

export const getResearchStatus = (researchId: number): Promise<import("./types").DeepResearchPollResponse> =>
  request(`/research/${researchId}/`);
