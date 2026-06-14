import type {
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
  CreatePaymentResponse,
  PageSaleSettings,
  PaymentHistory,
  ApplyPromoResponse,
  ReferralData,
  FilesResponse,
} from "./types";

const BASE_URL =
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

async function request<T>(
  path: string,
  init: RequestInit & { apiKey?: string } = {}
): Promise<T> {
  const { apiKey, ...fetchInit } = init;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
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

export const authRegister = (email: string, password: string): Promise<AuthUser> =>
  request<AuthUser>("/auth/register/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
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

export const listChats = (): Promise<ChatListItem[]> =>
  request<ChatListItem[]>("/chats/");

export const createChat = (body: {
  network_slug: string;
  message: string;
  files?: unknown[];
  settings?: Record<string, unknown>;
}): Promise<CreateChatResponse> =>
  request<CreateChatResponse>("/chats/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getChat = (id: number): Promise<ChatDetail> =>
  request<ChatDetail>(`/chats/${id}/`);

export const deleteChat = (id: number): Promise<void> =>
  request<void>(`/chats/${id}/`, { method: "DELETE" });

export const sendMessage = (
  chatId: number,
  body: {
    message: string;
    files?: unknown[];
    settings?: Record<string, unknown>;
  }
): Promise<SendMessageResponse> =>
  request<SendMessageResponse>(`/chats/${chatId}/messages/`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getMessageStatus = (messageId: number): Promise<WebMessage> =>
  request<WebMessage>(`/messages/${messageId}/status/`);

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

export const payTariff = (tariffId: number): Promise<CreatePaymentResponse> =>
  request<CreatePaymentResponse>(`/billing/tariffs/${tariffId}/pay/`, {
    method: "POST",
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

// ============ Referral ============

export const getReferral = (): Promise<ReferralData> =>
  request<ReferralData>("/referral/");

export const requestReferralWithdrawal = (body: {
  amount: number;
  card_number: string;
}): Promise<{ ok: boolean }> =>
  request<{ ok: boolean }>("/referral/withdraw/", {
    method: "POST",
    body: JSON.stringify(body),
  });

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
