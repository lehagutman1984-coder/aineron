# Memory & Project Spaces: Plan for Market Leadership in Russia
**Version 1.0 — 2026-06-27**

---

## Executive Summary

Aineron already has strong infrastructure: hybrid RAG (vector + FTS + RRF), cross-encoder reranking, query expansion, rolling chat compression, persistent UserMemory with categories, and a memory management UI at `/account/memory/`. This is more technically advanced than most Russian competitors.

The gap is not in the backend — it is in **what users see and feel**:
- No citation display (user doesn't know which files answered their question)
- No Deep Research mode (multi-step autonomous research with sources)
- No multiple response variants
- No quick memory actions from the chat interface
- No knowledge base health dashboard
- A few performance bugs in the write path

**Goal:** Become the #1 AI assistant in Russia for users who care about accurate, well-sourced answers — coders, researchers, analysts, and professionals who create projects.

---

## Part 1: Current State Audit

### What works well
| Feature | Status | Notes |
|---|---|---|
| Persistent UserMemory (facts) | ✅ Production | Categories, pinning, dedup via content_key |
| Memory management UI | ✅ Production | `/account/memory/` — 736 lines, full CRUD |
| ChatSummary compression | ✅ Production | Rolling + incremental, Redis lock vs races |
| RAG: hybrid search (FTS + vector) | ✅ Production | RRF merge, pgvector |
| RAG: cross-encoder reranking | ✅ Production | Top-50 → Top-15 |
| RAG: query expansion | ✅ Production | 3 LLM variants, Redis cache 24h |
| @file / @web directives | ✅ Production | Parse, inject, web flag |
| Conversation-aware search | ✅ Production | Last 4 messages fused with query |
| Adaptive top_k | ✅ Production | Broad vs narrow query heuristic |
| Two-level retrieval | ✅ Production | File → Chunk |
| Git connector (GitHub/Gitea) | ✅ Production | Sync, commits, file versions |
| Collaboration + audit log | ✅ Production | Collaborators, audit entries |
| EDIT Blocks | ✅ Production | Patch-commit for large files |
| Knowledge graph | ✅ Production | `/projects/[id]/graph` page |

### Bugs Found (write-path audit)

**BUG-1 (performance): `existing_keys` computed but unused**
In `tasks.py:extract_memory_facts` line 1100: a set of existing `content_key` values is loaded from DB but never used to pre-filter before `update_or_create`. Result: N extra DB round trips per extracted fact even when all facts already exist. Pre-filter check before update_or_create would reduce DB hits by ~70%.

**BUG-2 (performance): Two separate queries for existing facts**
Lines 1100-1109 make two separate queries (`.values_list('content_key')` + `.values_list('content')`) that could be one query with both fields.

**BUG-3 (correctness): Past summaries limited to 3 with no date range**
`build_memory_context` loads only the 3 most recent `ChatSummary` records excluding current chat. If a user has 20 chats, the 4th-20th are silently dropped. No warning, no user control.

**BUG-4 (correctness): `build_search_query` fetches `conv_window + 1` messages**
Line 68 in `retrieval.py`: `[:conv_window + 1]` fetches one extra message to guard against the current message being already saved — but then the dedup check `if msg.strip() == user_message.strip()` is fragile (encoding differences, HTML, whitespace). Can silently include the current message twice.

**BUG-5 (UX): No memory feedback in chat**
When `extract_memory_facts` runs and saves new facts, the user sees nothing in the chat interface. ChatGPT shows "Memory updated" notifications. Users don't know the system is learning.

**BUG-6 (UX): No citation/source display**
`build_project_knowledge_context` injects up to 15 chunks into the system prompt. The final answer includes knowledge from those chunks but shows zero attribution. Users don't know which files were consulted.

---

## Part 2: Competitor Analysis

### World-Class Feature Inventory

| Feature | Claude.ai | ChatGPT | Cursor | Perplexity | Gemini |
|---|---|---|---|---|---|
| File uploads to project | ✅ | ✅ | ✅ (codebase) | ✅ | ✅ |
| Auto memory extraction | ❌ | ✅ | ❌ | ❌ | ✅ (partial) |
| Memory management UI | ❌ | ✅ | ❌ | ❌ | ✅ |
| Citation display | ❌ | ✅ | ✅ | ✅✅ (best) | ✅ |
| Deep Research mode | ❌ | ✅ | ❌ | ✅✅ (best) | ✅ |
| Multiple response variants | ❌ | ❌ | ❌ | ❌ | ❌ |
| Knowledge graph | ❌ | ❌ | ❌ | ❌ | ❌ |
| Git sync | ❌ | ❌ | ✅✅ (core) | ❌ | ❌ |
| Team collaboration | ✅ | ✅ (Teams) | ✅ (Teams) | ✅ | ✅ |
| Quick memory actions in chat | ❌ | ✅ | ❌ | ❌ | ❌ |
| Conversation branching | ❌ | ❌ | ❌ | ❌ | ❌ |
| Web search in projects | ❌ | ✅ | ✅ | ✅✅ | ✅ |

**Aineron unique strengths today:**
- Knowledge graph visualization (no one else has this)
- Git connector (only Cursor has this at scale)
- EDIT Blocks for large file patching
- Auto memory extraction from conversations (only ChatGPT has this among big players)
- Hybrid RAG + cross-encoder reranking (backend quality higher than most)

**Critical gaps vs world class:**
1. Citation display — Perplexity's core differentiator; users **expect** this
2. Deep Research mode — ChatGPT, Perplexity, Gemini all have it; users ask for it
3. Multiple response variants — no one has it; strong differentiator if well-executed
4. Memory notifications in chat — ChatGPT shows "Memory updated"; builds trust
5. Knowledge base health dashboard — Cursor shows indexing status prominently

---

## Part 3: Sprint Plan

### Sprint 1 — Citation Display & Source Cards (Priority: CRITICAL)
**Estimated: 4-5 days**
**Impact: HIGHEST — changes how users perceive every RAG response**

**What:**
- Backend: return `used_sources` in API response alongside the answer (file names, chunk IDs, confidence)
- Frontend: `SourceCard` component — collapsible list below every AI response in project chats
- Source cards show: file name, file path, excerpt (100 chars), relevance score
- "3 источника" collapsed by default, expandable with one click
- Visual: thin horizontal divider + `BookOpen` icon + file name badges

**Technical:**
- Modify `build_project_knowledge_context()` to also return `List[SourceRef]` (name, path, excerpt)
- Pass sources through the response stream as a final SSE event `{"type": "sources", "data": [...]}`
- Frontend: parse sources event, render below message bubble

**Files to change:**
- `src/aitext/tasks.py` — `build_project_knowledge_context` returns `(context_str, sources)`
- `src/aitext/views.py` (or SSE endpoint) — append sources event
- `frontend/components/chat/Message.tsx` — add SourceCards slot
- `frontend/components/chat/SourceCard.tsx` — new component

---

### Sprint 2 — Deep Research Mode (Priority: HIGH)
**Estimated: 6-8 days**
**Impact: HIGH — major competitive gap; users explicitly request**

**What:**
Deep Research = multi-step autonomous research that goes beyond a single RAG lookup:
1. User clicks "Глубокое исследование" button in project chat
2. AI plans 4-8 search queries (project KB + web)
3. Executes searches in parallel, reads top results
4. Synthesizes into a long-form structured report with citations
5. Shows progress: "Поиск 3/7: authentication patterns..."
6. Final report: headers, bullet points, numbered footnotes, sources section

**Architecture:**
```
DeepResearch task (Celery):
  → plan_queries(question)           # LLM: generates 4-8 sub-queries
  → parallel_search(queries):
      → kb_search(q) for each        # project RAG
      → web_search(q) for each       # Serper/Tavily API
  → deduplicate + score results
  → synthesize_report(all_chunks)    # long LLM call with citations
  → stream progress via SSE
```

**Frontend:**
- Toggle button "Обычный" / "Исследование" in project chat input
- **Research runs in background**: user can close tab and return to completed report (SSE notification on finish)
- Research progress sidebar: live step-by-step "Поиск 3/7: authentication patterns... (4 источника)" 
- Report renderer: `<ResearchReport>` with collapsible sections + numbered footnotes
- **Hover-to-preview citations**: tooltip on citation [1] shows source title, domain, exact excerpt — no navigation needed
- Export: Download as Markdown / PDF

**Files to change:**
- `src/aitext/tasks.py` — `deep_research_task(chat_id, message_id, question)`
- `src/aitext/views.py` — `DeepResearchView` (POST to start, GET for status)
- `frontend/components/chat/DeepResearchPanel.tsx`
- `frontend/components/chat/ResearchReport.tsx`
- `frontend/app/projects/[id]/page.tsx`

---

### Sprint 3 — Multiple Response Variants (Priority: HIGH)
**Estimated: 3-4 days**
**Impact: HIGH — unique feature, no competitor has it**

**What:**
- "Варианты ответа" toggle in chat input (only available in project chats, premium)
- Generates 3 responses in parallel with different instructions:
  - Вариант 1: "Краткий — максимум 150 слов"
  - Вариант 2: "Развёрнутый с примерами кода"
  - Вариант 3: "Пошаговое руководство"
- Horizontal tabs above the response: "Краткий · Подробный · Пошаговый"
- User picks one, the others are discarded
- Optional: user can customize variant names ("Для джуна" / "Для тимлида")

**Technical:**
- 3 parallel LLM calls with different system prompt suffixes
- Stream all 3 via separate SSE channels (or bundle into one multiplexed stream)
- Frontend: tab switcher component with lazy loading per variant
- Billing: count as 1.5× stars (3 requests for price of 1.5)

**Files to change:**
- `src/aitext/tasks.py` — `generate_response_variants(message_id, n=3)`
- `src/aitext/views.py` — `VariantsView`
- `frontend/components/chat/ResponseVariants.tsx`

---

### Sprint 4 — Memory Quick Actions in Chat (Priority: MEDIUM-HIGH)
**Estimated: 2-3 days**
**Impact: MEDIUM — trust + discoverability; ChatGPT shows this builds strong user habits**

**What:**
1. **Memory notification toast**: When `extract_memory_facts` saves new facts, push SSE event `{"type": "memory_update", "facts": ["Разработчик на Python", "Работает в стартапе"]}` — frontend shows brief toast "Запомнено: 2 факта"
2. **"Запомнить" quick action**: Hover on any user message → action menu with "Запомнить" → creates UserMemory fact from selected text, category selector popup
3. **"Забыть" from response**: Long-press or right-click on assistant message → "Удалить из памяти" — deactivates the fact that was used to generate this
4. **Memory indicator**: Small brain icon on messages that used memory facts, tooltip shows which facts were applied

**Files to change:**
- `src/aitext/tasks.py` — `extract_memory_facts` emits SSE event after save
- `frontend/components/chat/Message.tsx` — add action menu, memory indicator
- `frontend/components/chat/MemoryToast.tsx` — new animated toast
- `frontend/lib/api/memory.ts` — `quickSaveFact(text, category)`

---

### Sprint 5 — Knowledge Base Health Dashboard (Priority: MEDIUM)
**Estimated: 3-4 days**
**Impact: MEDIUM — Cursor's strongest UX pattern; users trust indexed codebases more when they can see the status**

**What:**
Inside `/projects/[id]/` — new "База знаний" tab:
- File list with status badges: Indexed / Pending / Failed / Disabled
- Chunk count per file, embedding size, last indexed at
- "Re-index" button per file + "Re-index all" batch
- Chunk preview: expandable view of what the AI sees from each file
- Coverage gauge: "X из Y файлов проиндексировано"
- Connector sync status: last sync, next sync, manual trigger
- Embedding model info: which model, dimension, total vectors

**Files to change:**
- `src/aitext/views.py` — `ProjectKBStatsView`, `ProjectFileReindexView`
- `frontend/app/projects/[id]/kb/page.tsx` — new page
- `frontend/components/project/KBFileRow.tsx`
- `frontend/components/project/KBCoverageGauge.tsx`

---

### Sprint 6 — Bug Fixes & Performance (Priority: MEDIUM)
**Estimated: 2 days**
**Impact: Backend quality — users feel it as faster, more accurate memory**

**What (from BUG-1 to BUG-4 above):**

1. **BUG-1 fix**: Use `existing_keys` set to pre-filter before `update_or_create`:
```python
# Before calling update_or_create, check if key already in set
if content_key in existing_keys:
    continue  # skip DB hit entirely
```

2. **BUG-2 fix**: Merge two queries into one with `.values('content_key', 'content')`:
```python
existing_facts = {
    f['content_key']: f['content']
    for f in UserMemory.objects.filter(user=user, is_active=True)
    .values('content_key', 'content')[:100]
}
existing_keys = set(existing_facts.keys())
existing_preview = '\n'.join(f'- {v}' for v in list(existing_facts.values())[:30])
```

3. **BUG-3 fix**: Add `days` parameter to `build_memory_context`, allow configuring past summary count via `MEMORY_PAST_SESSIONS` setting (default 5, not 3).

4. **BUG-4 fix**: In `build_search_query`, remove `+1` and use ID comparison instead of string equality.

5. Add database index on `ChatSummary.updated_at` for the past_summaries query.

---

### Sprint 7 — Conversation Branching (Priority: LOW-MEDIUM)
**Estimated: 5-6 days**
**Impact: MEDIUM — power users love this; differentiated from all competitors**

**What:**
- "Создать ветку" button on any message in project chat
- Branches from that message point, creating a new chat with same history up to that point
- Branch indicator showing parent message
- Sidebar: list of branches for a chat
- Merge best branch back to main: manually select "Сделать основной"

**Files to change:**
- `src/aitext/models.py` — `Chat.parent_chat`, `Chat.branch_from_message_id`
- `src/aitext/views.py` — `BranchChatView`
- `frontend/components/chat/BranchButton.tsx`
- `frontend/app/projects/[id]/page.tsx` — branch sidebar

---

## Part 3b: Verified UX Patterns from Competitor Research (Workflow Agents)

The following patterns were verified via live web search across all 5 competitors:

**What users universally love (ranked by trust signal per dev-hour):**

1. **Hover-to-preview citations** (Perplexity) — tooltip shows source title, domain, and exact quoted sentence without page navigation. Zero friction, maximum trust. Implement: frontend-only tooltip on citation number hover.

2. **Research runs in background** (ChatGPT, Perplexity) — user can close tab and return to a finished report. Eliminates "babysitting" long operations. Implement: Celery task + SSE notification on completion.

3. **Live progress sidebar with sub-topic breakdown** (Perplexity, Gemini) — shows "Searching for: X... Found 3 sources" live. Trust signal #1 vs. competitors, cited by users as primary reason to prefer Perplexity.

4. **One-click rollback on artifacts** (Claude Artifacts) — every AI edit creates a snapshot, revert in one click. Users describe it as "makes editing feel safe."

5. **Visible, versionable project instructions** (Cursor .cursorrules) — plain-text in sidebar or checked into git. Team-shareable, auditable, not buried in settings.

**Table stakes already covered in Aineron (confirmed):**
- ✅ Persistent per-project conversation history
- ✅ File upload + project knowledge base with RAG
- ✅ Custom instructions / system prompt per workspace
- ✅ Memory view/edit/delete at `/account/memory/`
- ✅ Project-level sharing with collaborators

**Differentiators Aineron can own uniquely:**
- Knowledge graph (no competitor has this)
- Git connector with EDIT Blocks (only Cursor has Git, but as desktop app)
- Multiple response variants (no competitor has this)
- Auto memory extraction from conversations (only ChatGPT has this)
- Hover-to-preview citations with knowledge graph link (unique combination)

---

## Part 4: Success Metrics

| Metric | Baseline | Target (90 days) |
|---|---|---|
| Project chat DAU | — | +40% after Deep Research launch |
| Memory fact retention (% users with >5 facts) | — | 60%+ |
| Citation click-through rate | N/A | 20% of responses |
| Deep Research activations / day | N/A | 100+ |
| Response variant selection | N/A | 30% of variant users pick non-default |
| KB health dashboard views / week | N/A | 200+ |

---

## Part 5: Priority Stack-Rank

| Sprint | Feature | Effort | Impact | Start |
|---|---|---|---|---|
| Sprint 1 | Citation Display | 4-5d | CRITICAL | Immediately |
| Sprint 2 | Deep Research | 6-8d | HIGH | After Sprint 1 |
| Sprint 3 | Response Variants | 3-4d | HIGH | Parallel with Sprint 2 |
| Sprint 4 | Memory Quick Actions | 2-3d | MEDIUM | After Sprint 1 |
| Sprint 5 | KB Health Dashboard | 3-4d | MEDIUM | After Sprint 2 |
| Sprint 6 | Bug Fixes | 2d | MEDIUM | Any time |
| Sprint 7 | Conversation Branching | 5-6d | LOW-MED | After Sprint 3 |

**Recommended order**: Sprint 6 (bugs, quick wins) → Sprint 1 (citations) → Sprint 3 + Sprint 4 (parallel) → Sprint 2 (Deep Research, most impact) → Sprint 5 → Sprint 7.

---

## Part 6: Why This Makes Aineron #1 in Russia

After these sprints, Aineron will be the **only** Russian AI service with:
1. **Citation display with knowledge graph** — users see exactly which file answered their question + graph showing connections
2. **Git-connected projects with KB health** — like Cursor but as a web SaaS
3. **Auto memory extraction + quick chat actions** — better UX than ChatGPT's memory (Russian-native)
4. **Deep Research** — matches Perplexity/ChatGPT for research use cases
5. **Multiple response variants** — unique feature no competitor offers
6. **Conversation branching** — power users love exploring alternative paths

The combination of **code intelligence** (Git + KB + Studio) + **research** (Deep Research + Citations) + **memory** (auto extraction + quick actions) creates a product that is genuinely better than individual competitors for Russian professional users.

---

*Plan written 2026-06-27. Update on each sprint completion.*
