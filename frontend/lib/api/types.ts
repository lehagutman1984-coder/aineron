// Hand-written types mirroring /api/v1/ OpenAPI contract.
// Regenerate schema.d.ts with: npm run gen:api

// ============ Shared ============

export interface APIError {
  error: {
    message: string;
    type: string;
    code: string | null;
  };
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// ============ Models ============

export interface Model {
  id: string;
  object: "model";
  created: number;
  owned_by: string;
}

export interface ModelListResponse {
  object: "list";
  data: Model[];
}

// ============ Chat Completions ============

export type Role = "system" | "user" | "assistant";

export interface TextContent {
  type: "text";
  text: string;
}

export interface ImageContent {
  type: "image_url";
  image_url: { url: string; detail?: "auto" | "low" | "high" };
}

export type MessageContent = string | Array<TextContent | ImageContent>;

export interface ChatMessage {
  role: Role;
  content: MessageContent;
  name?: string;
}

export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  stop?: string | string[];
}

export interface ChatCompletionChoice {
  index: number;
  message: ChatMessage;
  finish_reason: "stop" | "length" | "content_filter" | null;
}

export interface ChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage: Usage;
}

// ============ Anthropic-compatible ============

export interface AnthropicTextBlock {
  type: "text";
  text: string;
}

export interface AnthropicMessage {
  role: "user" | "assistant";
  content: string | AnthropicTextBlock[];
}

export interface AnthropicRequest {
  model: string;
  messages: AnthropicMessage[];
  system?: string;
  max_tokens: number;
  temperature?: number;
  stream?: boolean;
}

export interface AnthropicResponse {
  id: string;
  type: "message";
  role: "assistant";
  content: AnthropicTextBlock[];
  model: string;
  stop_reason: "end_turn" | "max_tokens" | null;
  usage: { input_tokens: number; output_tokens: number };
}

// ============ Images ============

export interface ImageGenerationRequest {
  model: string;
  prompt: string;
  n?: number;
  size?: string;
  response_format?: "url" | "b64_json";
}

export interface ImageData {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
}

export interface ImageGenerationResponse {
  created: number;
  data: ImageData[];
}

// ============ API Keys ============

export interface APIKey {
  id: number;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  scopes: string[];
}

export interface APIKeyCreateRequest {
  name: string;
}

export interface APIKeyCreateResponse extends APIKey {
  key: string; // plaintext, shown once only
}

// ============ User (from Django session API) ============

export interface User {
  id: number;
  email: string;
  pages_count: number;
  tariff: string;
  active_subscription: boolean;
  referral_code: string;
}

// ============ Catalog ============

export interface Category {
  id: number;
  name: string;
  slug: string;
  icon: string;
  order: number;
}

export interface NetworkListItem {
  id: number;
  name: string;
  slug: string;
  category: Category;
  avatar: string | null;
  description: string;
  cost_per_message: number;
  provider: string;
  is_popular: boolean;
  unlimited: boolean;
  messages_limit: number;
  handle_photo: boolean;
  handle_video: boolean;
  handle_archive: boolean;
  handle_text_files: boolean;
  seo_title: string;
  seo_description: string;
  model_name: string;
  order: number;
}

export interface FAQ {
  id: number;
  question: string;
  answer: string;
  order: number;
}

export interface NetworkDetail extends NetworkListItem {
  seo_keywords: string;
  config_json: Record<string, unknown> | null;
  has_prompt: boolean;
  is_direct: boolean;
  is_custom: boolean;
  max_tokens: number;
  faqs: FAQ[];
}

// ============ Web Chat ============

export interface WebMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  files: unknown[];
  status: "pending" | "completed" | "failed";
  error_message: string | null;
  created_at: string;
}

export interface NetworkMini {
  id: number;
  name: string;
  slug: string;
  avatar: string | null;
  category: Category;
}

export interface ChatListItem {
  id: number;
  title: string;
  network: NetworkMini;
  last_message: {
    role: "user" | "assistant";
    preview: string;
    status: "pending" | "completed" | "failed";
  } | null;
  created_at: string;
  updated_at: string;
}

export interface ChatDetail {
  id: number;
  title: string;
  network: NetworkMini;
  messages: WebMessage[];
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateChatResponse {
  chat_id: number;
  user_message_id: number;
  assistant_message_id: number;
  new_balance: number;
}

export interface SendMessageResponse {
  user_message_id: number;
  assistant_message_id: number;
  new_balance: number;
}

// ============ Organizations / B2B ============

export interface Organization {
  id: number;
  name: string;
  inn: string;
  kpp: string;
  legal_address: string;
  balance_rub: string;
  member_count: number;
  user_role: "owner" | "admin" | "member" | null;
  created_at: string;
}

export interface OrgMember {
  id: number;
  user_id: number;
  email: string;
  username: string;
  role: "owner" | "admin" | "member";
  created_at: string;
}

export interface OrgInvite {
  id: number;
  email: string;
  token: string;
  expires_at: string;
  is_accepted: boolean;
  created_at: string;
}

export interface Invoice {
  id: number;
  number: string;
  amount_rub: string;
  status: "pending" | "paid" | "cancelled";
  description: string;
  created_at: string;
  paid_at: string | null;
}

// ============ Usage statistics ============

export interface UsageDay {
  date: string;
  total_tokens: number;
  stars_charged: number;
  requests: number;
}

export interface UsageByModel {
  model_name: string;
  model_slug: string;
  total_tokens: number;
  stars_charged: number;
  requests: number;
}

export interface UsageStats {
  period_days: number;
  totals: {
    total_tokens: number;
    total_stars: number;
    total_requests: number;
  };
  by_day: UsageDay[];
  by_model: UsageByModel[];
}

// ============ Auth (DRF /api/v1/auth/me/) ============

export interface AuthUser {
  id: number;
  email: string;
  username: string;
  pages_count: number;
  active_subscription: boolean;
  referral_code: string;
  tariff_name: string;
  avatar: string;
}
