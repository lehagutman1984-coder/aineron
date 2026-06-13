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

// ============ User (Django session endpoint) ============
// This hits the existing Django users/api/ — not the DRF /api/v1/.
// Will be replaced with a DRF endpoint in Phase 3.

export async function getCurrentUser(): Promise<User | null> {
  try {
    const res = await fetch("/users/api/user/", {
      credentials: "include",
    });
    if (!res.ok) return null;
    return res.json() as Promise<User>;
  } catch {
    return null;
  }
}
