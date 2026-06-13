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
