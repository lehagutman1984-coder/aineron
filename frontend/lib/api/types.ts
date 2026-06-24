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
  plain_text: string | null;
  files: unknown[];
  status: "pending" | "completed" | "failed";
  error_message: string | null;
  search_context?: string;
  created_at: string;
}

export interface UiField {
  name: string;
  type: "select" | "checkbox" | "slider" | "number" | "text" | "textarea";
  label: string;
  extra_cost?: number;
  options?: { value: string; label: string; extra_cost?: number }[];
  min?: number;
  max?: number;
  step?: number;
  max_length?: number;
}

export interface UiSection {
  title: string;
  fields: UiField[];
}

export interface ModelConfigJson {
  name?: string;
  api_defaults?: Record<string, unknown>;
  ui_settings?: { sections: UiSection[] };
  constraints?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface NetworkMini {
  id: number;
  name: string;
  slug: string;
  avatar: string | null;
  category: Category;
  provider: string;
  handle_photo: boolean;
  handle_video: boolean;
  config_json?: ModelConfigJson | null;
}

export interface Project {
  id: number;
  name: string;
  system_prompt: string;
  color: string;
  icon: string;
  status: "active" | "paused" | "done";
  chat_count: number;
  file_count: number;
  created_at: string;
  is_public: boolean;
  public_slug: string;
  public_show_files: boolean;
  public_show_chats: boolean;
  public_views: number;
  user_role: "owner" | "editor" | "viewer";
}

export interface ProjectCollaborator {
  id: number;
  email: string;
  username: string;
  role: "viewer" | "editor";
  invited_by_email: string | null;
  created_at: string;
}

export interface ProjectAuditEntry {
  id: number;
  action: string;
  action_display: string;
  target: string;
  files_used: string[];
  actor_email: string | null;
  created_at: string;
}

export interface PublicSpaceFile {
  id: number;
  filename: string;
  file_size: number;
  file_type: "pdf" | "doc" | "text" | "code" | "other";
  created_at: string;
}

export interface PublicSpaceChat {
  id: number;
  title: string;
  updated_at: string;
}

export interface PublicSpace {
  id: number;
  name: string;
  system_prompt: string;
  icon: string;
  color: string;
  created_at: string;
  public_show_files: boolean;
  public_show_chats: boolean;
  files: PublicSpaceFile[];
  chats: PublicSpaceChat[];
}

export interface ChatListItem {
  id: number;
  title: string;
  network: NetworkMini;
  project_id: number | null;
  last_message: {
    role: "user" | "assistant";
    preview: string;
    status: "pending" | "completed" | "failed";
  } | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: number;
  filename: string;
  file_url: string | null;
  file_size: number;
  file_type: "pdf" | "doc" | "text" | "code" | "other";
  status: "processing" | "ready" | "error";
  embed_status: "none" | "pending" | "done" | "error";
  source: "upload" | "repo";
  enabled: boolean;
  created_at: string;
  usage_hits: number;
  last_used_at: string | null;
}

export interface ChatProjectMini {
  id: number;
  name: string;
  system_prompt: string;
  color: string;
  icon: string;
}

export interface ChatDetail {
  id: number;
  title: string;
  network: NetworkMini;
  project_id: number | null;
  project: ChatProjectMini | null;
  messages: WebMessage[];
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ChatSearchResult {
  chat_id: number;
  chat_title: string;
  network_name: string;
  network_slug: string;
  message_id: number;
  role: "user" | "assistant";
  snippet: string;
  created_at: string;
}

export interface ChatSearchResponse {
  results: ChatSearchResult[];
  count: number;
  page: number;
  has_more: boolean;
}

export interface ProjectConnector {
  id: number;
  connector_type: "github" | "gitea";
  repo_url: string;
  owner: string;
  repo: string;
  branch: string;
  webhook_url: string;
  webhook_secret: string;
  last_synced_at: string | null;
  created_at: string;
  auto_sync: boolean;
  sync_status: "ok" | "error" | "running" | "";
  last_sync_report: { created?: number; updated?: number; deleted?: number; skipped?: number; errors?: number; error?: string; error_detail?: string } | null;
  // Sprint 7.2 — Deploy hook
  deploy_webhook_url?: string;
  deploy_status?: "pending" | "running" | "success" | "error" | "";
  last_deploy_at?: string | null;
  last_deploy_log?: string;
}

export interface DeployStatusResponse {
  deploy_status: "pending" | "running" | "success" | "error" | "";
  last_deploy_at: string | null;
  last_deploy_log: string;
}

export interface RepoTreeItem {
  path: string;
  type: "file" | "dir";
  size?: number | null;
}

export interface CommitFile {
  path: string;
  content: string;
}

export interface ProjectCommit {
  id: number;
  connector_id: number | null;
  commit_message: string;
  files: CommitFile[];
  status: "pending" | "pushed" | "rejected" | "failed";
  kind: "commit" | "pull_request";
  pr_branch: string;
  pr_url: string;
  error_message: string;
  created_at: string;
  pushed_at: string | null;
}

export interface AttachmentItem {
  id: string;
  url: string;
  filename: string;
  media_type: "image" | "video" | "audio" | "pdf" | "other";
  mime_type: string;
  file_size: number;
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

// ============ Blog ============

export interface BlogCategory {
  id: number;
  name: string;
  slug: string;
  description: string;
  seo_title: string | null;
  seo_description: string | null;
  seo_keywords: string | null;
}

export interface BlogPost {
  id: number;
  title: string;
  slug: string;
  category: BlogCategory | null;
  preview_image_url: string | null;
  preview_text: string;
  author_name: string | null;
  published_at: string;
  views_count: number;
  show_on_main: boolean;
  seo_title: string | null;
  seo_description: string | null;
  seo_keywords: string | null;
}

export interface BlogPostDetail extends BlogPost {
  content: string;
  updated_at: string;
  network_slugs: string[];
}

// ============ Billing ============

export interface Tariff {
  id: number;
  display_name: string;
  pages_count: number;
  price: string;
  is_free: boolean;
  is_trial: boolean;
  duration_days: number;
}

export interface UserSubscription {
  id: number;
  tariff: Tariff;
  started_at: string;
  expires_at: string;
  is_active: boolean;
  auto_renew: boolean;
  days_left: number;
}

export interface TariffsResponse {
  tariffs: Tariff[];
  current_subscription: UserSubscription | null;
  pages_count: number;
}

export interface RobokassaForm {
  action: string;
  method: string;
  fields: Record<string, string>;
}

export interface CreatePaymentResponse {
  payment_id: number;
  invoice_id: number;
  form: RobokassaForm;
}

export interface PageSaleSettings {
  price_per_page: string;
  min_pages_for_purchase: number;
  max_pages_for_purchase: number;
  is_active: boolean;
}

export interface PaymentHistory {
  id: number;
  payment_type: "subscription" | "pages" | "promo";
  invoice_id: string;
  amount: string;
  pages_count: number;
  status: "pending" | "success" | "failed" | "refunded";
  description: string;
  tariff_name: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface ApplyPromoResponse {
  ok: boolean;
  stars_added: number;
  new_balance: number;
  message: string;
}

// ============ Files ============

export interface GeneratedFile {
  id: string;
  url: string;
  prompt: string;
  media_type: "image" | "video";
  ext: string;
  size: string;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface FilesResponse {
  files: GeneratedFile[];
  has_next: boolean;
  page: number;
  total_pages: number;
  total: number;
}

// ============ Prompt Library ============

export interface PromptTemplate {
  id: number;
  title: string;
  content: string;
  category: "code" | "translate" | "analyze" | "email" | "study" | "creative" | "other";
  icon: string;
  is_public: boolean;
  is_own: boolean;
  created_at: string;
}

// ============ Model Arena (compare) ============

export interface CompareItem {
  chat_id: number;
  network_slug: string;
  network_name: string;
  network_avatar: string | null;
  provider: string;
  assistant_message_id: number;
  cost: number;
}

export interface CompareResponse {
  items: CompareItem[];
  total_cost: number;
  new_balance: number;
}

// ============ Model Arena Elo ============

export interface ArenaEntry {
  slug: string;
  name: string;
  elo_rating: number;
  elo_matches: number;
  avatar_url: string | null;
  description: string;
}

export interface ArenaVoteResult {
  match_id: number;
  winner: { slug: string; name: string; elo_rating: number; elo_matches: number };
  loser: { slug: string; name: string; elo_rating: number; elo_matches: number };
}

// ============ Knowledge Graph ============

export interface GraphNode {
  id: number;
  label: string;
  type: string;
}

export interface GraphEdge {
  source: number;
  target: number;
  weight: number;
}

export interface ProjectGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ============ Stars Usage Analytics ============

export interface StarsUsageDay {
  date: string;
  stars: number;
  requests: number;
}

export interface StarsUsageModel {
  name: string;
  stars: number;
  requests: number;
}

export interface StarsUsage {
  period_days: number;
  totals: {
    total_stars: number;
    total_requests: number;
    avg_per_day: number;
  };
  prev_period: {
    total_stars: number;
    total_requests: number;
  };
  by_day: StarsUsageDay[];
  by_model: StarsUsageModel[];
}

// ============ Referral ============

export interface ReferralEarning {
  id: number;
  amount_rub: number;
  amount_stars: number;
  tariff: string | null;
  description: string;
  created_at: string;
}

export interface ReferralWithdrawal {
  id: number;
  amount: number;
  card_number: string;
  status: "pending" | "completed" | "cancelled";
  created_at: string;
  processed_at: string | null;
  note: string;
}

export interface ReferralData {
  referral_link: string;
  referral_code: string;
  referral_clicks: number;
  balance: number;
  balance_type: "rub" | "stars";
  can_withdraw: boolean;
  earnings: ReferralEarning[];
  withdrawals: ReferralWithdrawal[];
}

// ============ AI Personas ============

export interface Persona {
  id: number;
  name: string;
  slug: string;
  description: string;
  system_prompt: string;
  avatar_url: string;
  network: number | null;
  network_name: string | null;
  is_public: boolean;
  is_active: boolean;
  order: number;
  is_own: boolean;
  created_at: string;
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
  email_verified: boolean;
}
