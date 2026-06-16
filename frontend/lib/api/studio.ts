import { request } from './client';

export type StudioMode = 'auto' | 'semi' | 'manual';
export type EntryMode = 'description' | 'clone_url';
export type StudioStack = 'nextjs' | 'react' | 'vue' | 'html';

export interface StudioProject {
  id: string;
  name: string;
  description: string;
  status: string;
  mode: StudioMode;
  entry_mode: EntryMode;
  target_url: string;
  target_stack: StudioStack;
  stars_spent: number;
  sandbox_container_id: string;
  preview_port: number | null;
  project_md_content: string;
  commits_md_content: string;
  interview_data: Record<string, unknown>;
  repo_url: string;
  created_at: string;
}

export interface StudioFileNode {
  id: number;
  path: string;
  language: string;
  last_modified_by: string;
}

export interface StudioFileDetail extends StudioFileNode {
  content: string;
}

export interface PipelineState {
  status: string;
  step_index: number;
  iteration_count: number;
  pause_reason: string;
  resume_hint: string;
}

export interface InterviewQuestion {
  id: string;
  question: string;
  type: 'text' | 'choice';
  options?: string[];
}

export interface StudioTemplate {
  id: number;
  slug: string;
  name: string;
  description: string;
  stack: StudioStack;
  preview_image: string;
  seed_prompt: string;
  order: number;
}

export interface StudioVersion {
  id: number;
  step_index: number;
  step_name: string;
  git_sha: string;
  stars_spent_at_version: number;
  created_at: string;
}

export interface StudioEstimate {
  estimated_stars: number;
  planned_steps: number;
  balance: number;
  affordable: boolean;
}

export const studioApi = {
  list: () =>
    request<StudioProject[]>('/studio/projects/'),

  create: (data: {
    name: string;
    description?: string;
    mode?: StudioMode;
    entry_mode?: EntryMode;
    target_url?: string;
    target_stack?: StudioStack;
  }) =>
    request<StudioProject>('/studio/projects/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  get: (id: string) =>
    request<StudioProject>(`/studio/projects/${id}/`),

  files: (id: string) =>
    request<StudioFileNode[]>(`/studio/projects/${id}/files/`),

  fileDetail: (id: string, fileId: number) =>
    request<StudioFileDetail>(`/studio/projects/${id}/files/${fileId}/`),

  pipeline: (id: string) =>
    request<PipelineState>(`/studio/projects/${id}/pipeline/`),

  run: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/run/`, { method: 'POST' }),

  interview: (id: string) =>
    request<{ questions: InterviewQuestion[]; status: string; interview_error?: string }>(`/studio/projects/${id}/interview/`),

  submitInterview: (id: string, answers: unknown[]) =>
    request<{ status: string }>(`/studio/projects/${id}/interview/`, {
      method: 'POST',
      body: JSON.stringify({ answers }),
    }),

  pause: (id: string, reason?: string) =>
    request<{ status: string }>(`/studio/projects/${id}/pause/`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  resume: (id: string, data: { action: 'continue' | 'with_hint' | 'skip_step'; hint?: string }) =>
    request<{ status: string }>(`/studio/projects/${id}/resume/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  commits: (id: string) =>
    request<StudioVersion[]>(`/studio/projects/${id}/commits/`),

  rollback: (id: string, versionId: number) =>
    request<{ status: string }>(`/studio/projects/${id}/rollback/${versionId}/`, {
      method: 'POST',
    }),

  clone: (data: { url: string; name?: string }) =>
    request<StudioProject>('/studio/clone/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  estimate: (id: string) =>
    request<StudioEstimate>(`/studio/projects/${id}/estimate/`),

  templates: () =>
    request<StudioTemplate[]>('/studio/templates/'),
};
