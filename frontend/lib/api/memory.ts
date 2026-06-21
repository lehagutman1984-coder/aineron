import { request } from "./client";

// ============ Types ============

export type MemoryCategory =
  | "profile"
  | "preference"
  | "project"
  | "fact"
  | "skill";

export interface UserMemory {
  id: number;
  category: MemoryCategory;
  category_display: string;
  content: string;
  source: string; // "auto" | "manual" | ... — treat non-"auto" as manual
  is_active: boolean;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatSummary {
  id: number;
  chat_id: number;
  chat_title: string;
  network_name: string;
  summary_text: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface MemorySettings {
  memory_enabled: boolean;
  fact_count: number;
}

// ============ Facts ============

export const getMemoryFacts = (): Promise<UserMemory[]> =>
  request<UserMemory[]>("/memory/");

export const createMemoryFact = (body: {
  content: string;
  category: MemoryCategory;
}): Promise<UserMemory> =>
  request<UserMemory>("/memory/", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateMemoryFact = (
  id: number,
  body: Partial<{
    is_active: boolean;
    is_pinned: boolean;
    content: string;
    category: MemoryCategory;
  }>
): Promise<UserMemory> =>
  request<UserMemory>(`/memory/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteMemoryFact = (id: number): Promise<void> =>
  request<void>(`/memory/${id}/`, { method: "DELETE" });

export const clearAutoMemory = (): Promise<{ deleted: number }> =>
  request<{ deleted: number }>("/memory/clear/", { method: "POST" });

// ============ Summaries ============

export const getMemorySummaries = (): Promise<ChatSummary[]> =>
  request<ChatSummary[]>("/memory/summaries/");

// ============ Settings ============

export const getMemorySettings = (): Promise<MemorySettings> =>
  request<MemorySettings>("/memory/settings/");

export const updateMemorySettings = (body: {
  memory_enabled: boolean;
}): Promise<MemorySettings> =>
  request<MemorySettings>("/memory/settings/", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
