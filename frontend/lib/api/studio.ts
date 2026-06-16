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
  coder_model: 'fast' | 'smart';
  max_iterations: number;
  max_stars_budget: number;
  auto_deploy: boolean;
  project_md_content: string;
  commits_md_content: string;
  interview_data: Record<string, unknown>;
  repo_url: string;
  vercel_deployment_url: string;
  github_repo_url: string;
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
  review_report: Record<string, unknown>;
  test_report: Record<string, unknown>;
  fix_plan: Record<string, unknown>;
  last_error: string;
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

export interface TimelineStep {
  step_index: number;
  name: string;
  planned: string;
  changed_files: string[];
  version_id: number | null;
  git_sha: string;
}

export interface DeviationReport {
  matched: string[];
  deviations: { planned: string; actual: string; severity: 'low' | 'medium' | 'high' }[];
}

export interface SandboxStatus {
  alive: boolean;
  port: number | null;
  uptime_s: number;
}

export interface StudioFileDiff {
  path: string;
  old: string;
  new: string;
}

export interface FileSearchResult {
  file_id: number;
  path: string;
  line: number;
  snippet: string;
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

  fileDiff: (id: string, fileId: number, ref: string) =>
    request<StudioFileDiff>(`/studio/projects/${id}/files/${fileId}/diff/?ref=${encodeURIComponent(ref)}`),

  updateFile: (id: string, fileId: number, content: string) =>
    request<StudioFileDetail>(`/studio/projects/${id}/files/${fileId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),

  searchFiles: (id: string, q: string) =>
    request<FileSearchResult[]>(`/studio/projects/${id}/search/?q=${encodeURIComponent(q)}`),

  updateSettings: (id: string, data: Partial<{ coder_model: string; max_iterations: number; max_stars_budget: number; auto_deploy: boolean; mode: string }>) =>
    request<Record<string, unknown>>(`/studio/projects/${id}/settings/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  restartPreview: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/preview/restart/`, { method: 'POST' }),

  createFile: (id: string, path: string, content = '') =>
    request<StudioFileDetail>(`/studio/projects/${id}/files/`, {
      method: 'POST',
      body: JSON.stringify({ path, content, language: '' }),
    }),

  deleteFile: (id: string, fileId: number) =>
    request<void>(`/studio/projects/${id}/files/${fileId}/`, { method: 'DELETE' }),

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

  sandbox: (id: string) =>
    request<SandboxStatus>(`/studio/projects/${id}/sandbox/`),

  contextChat: (id: string, message: string) =>
    request<{ answer: string }>(`/studio/projects/${id}/chat/`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  approve: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/approve/`, { method: 'POST' }),

  deploy: (id: string) =>
    request<{ status: string }>(`/studio/projects/${id}/deploy/`, { method: 'POST' }),

  deviation: (id: string, n: number) =>
    request<DeviationReport>(`/studio/projects/${id}/steps/${n}/deviation/`),

  exportGithub: (id: string, repoName: string, isPrivate: boolean) =>
    request<{ status: string }>(`/studio/projects/${id}/export/github/`, {
      method: 'POST',
      body: JSON.stringify({ repo_name: repoName, private: isPrivate }),
    }),

  uploadScreenshot: (id: string, file: File): Promise<{ description: string }> => {
    const fd = new FormData();
    fd.append('image', file);
    return fetch(`${process.env.NEXT_PUBLIC_API_URL}/studio/projects/${id}/screenshot/`, {
      method: 'POST',
      body: fd,
      credentials: 'include',
    }).then((r) => r.json() as Promise<{ description: string }>);
  },

  reportConsoleError: (
    id: string,
    data: { message: string; stack?: string; file?: string; line?: number; autofix?: boolean },
  ) =>
    request<{ stored: boolean; count: number }>(`/studio/projects/${id}/console-error/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  explain: (id: string, code: string, path?: string) =>
    request<{ explanation: string }>(`/studio/projects/${id}/explain/`, {
      method: 'POST',
      body: JSON.stringify({ code, path }),
    }),

  timeline: (id: string) =>
    request<TimelineStep[]>(`/studio/projects/${id}/timeline/`),

  branchFrom: (id: string, versionId: number) =>
    request<{ id: string }>(`/studio/projects/${id}/branch/${versionId}/`, { method: 'POST' }),

  exportUrl: (id: string) =>
    `${process.env.NEXT_PUBLIC_API_URL}/studio/projects/${id}/export/`,

  templates: () =>
    request<StudioTemplate[]>('/studio/templates/'),
};
