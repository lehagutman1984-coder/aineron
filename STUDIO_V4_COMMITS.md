# Studio V4 — Коммит-план реализации

## Как читать этот документ

Это пошаговая инструкция для Claude Sonnet 4.6. Каждая **Сессия** = один рабочий контекст Sonnet (1 коммит, максимум 3 тесно связанных). Сессии независимы: каждая либо аддитивна, либо спрятана за фича-флагом `STUDIO_V4_*` (по умолчанию выключен), поэтому деплой любой сессии не ломает прод.

Правила, которым Sonnet обязан следовать:

1. **Все новые флаги — выключены по умолчанию.** Паттерн в `src/config/settings.py`:
   ```python
   STUDIO_V4_TOKEN_BILLING = os.getenv('STUDIO_V4_TOKEN_BILLING', '0') == '1'
   ```
   Флаг добавляется в той же сессии, где его читают, — чтобы сессия была самодостаточной.
2. **Любое изменение модели Django = новая миграция.** После правки `src/studio/models.py` ОБЯЗАТЕЛЬНО:
   ```bash
   cd src && python manage.py makemigrations studio
   ```
   и закоммитить файл миграции вместе с кодом. Это явно указано в каждой такой сессии — не пропускать.
3. **Не ломать существующее поведение.** Если флаг выключен — код должен исполняться ровно как до коммита. Старый путь оставляем нетронутым в `else`-ветке.
4. **Промпты на двух языках.** Везде, где правишь системный промпт агента, есть пара `*_RU` / `*_EN` и выбор через `pick_prompt(ru, en)`. Правь ОБА варианта.
5. **Перед коммитом — прогон тестов:** `cd src && python manage.py test studio`.

> **О количестве сессий.** План насчитывает **18 сессий / 28 коммитов**. Это выше ориентира «14-16 сессий» из ТЗ — сознательный компромисс: правило «frontend и backend в разных сессиях» вынуждает держать отдельно три сессии со сквозным механизмом (0.5, 3.5 и фронт-стриминг 1.3), что добавляет сессии, тогда как тесно-связанные изменения в одном файле уже объединены (0.1 = токены+биллинг, 0.4 = весь autofix, 2.1 = четыре RU-scaffold в одном файле, 3.2 = TMA-scaffold). Опускать ниже 18 пришлось бы либо смешав FE/BE в одной сессии, либо склеив несвязанные изменения — оба нарушают правила группировки.

### Важные расхождения исходного плана с реальным кодом (читать до начала)

Исходный план STUDIO_V4_PLAN.md местами описывает код неточно. Ниже — реальность на момент старта V4. Везде в инструкциях ниже опираемся на реальность, а не на план:

- **`coder_iteration(self, project_id, step_index)` НЕ принимает `fix_plan` аргументом.** FixPlan передаётся через `state.fix_plan` (JSONField), который читается внутри задачи (`tasks.py:513`). `ConsoleErrorView` уже пишет `state.fix_plan` и вызывает `coder_iteration.delay(project_id, step_index)` — autofix частично реализован.
- **Функции `run_build_check` НЕ существует.** «Проверка сборки» в текущем коде = `sandbox.wait_for_ready(container_id, timeout=60)` после записи файлов (`tasks.py:582-583`), плюс Guardian получает build-логи параметром `build_logs`. В V4 мы НЕ изобретаем новую функцию сборки — мы переиспользуем существующий вызов Guardian (`guardian_review.delay`), который уже стоит в конце `coder_iteration` (`tasks.py:584`).
- **`StudioPipelineState` НЕ имеет полей** `seen_error_hashes`, `autofix_count`. Их надо добавить миграцией.
- **`StudioProject` НЕ имеет** `deploy_target`, а в `STACK_CHOICES`/`target_stack` НЕТ значения `tma`. Добавить миграцией.
- **`run_prompt_with_continuation` НЕ накапливает токены** между раундами: каждый раунд перезаписывает `last_completion_tokens`. Это надо чинить (см. Сессию 0.1), иначе реальный биллинг будет занижать именно длинные генерации.
- **Frontend: нет единого SSE-хаба.** `AgentLog.tsx`, `PreviewPanel.tsx`, `StudioLayout.tsx` каждый открывает СВОЙ `EventSource` на `${NEXT_PUBLIC_API_URL}/studio/projects/${id}/events/`. `CodeViewer.tsx` SSE НЕ слушает (чисто props-driven, без вкладок — показывает один файл из props `content`). `PreviewPanel` уже реагирует на `step_completed`/`coder_done` (бампит `key` iframe). `target_stack` в `PreviewPanel` НЕ прокинут — надо добавить в props и прокинуть из `StudioLayout`.
- **`base.py` использует единственный кешированный `_client`** через `get_client()`. `run_prompt` собирает только `chunk.usage.completion_tokens`.

---

# ФАЗА 0 — Надёжность и стоимость

Цель фазы: закрыть утечку маржи на невидимых input-токенах, добавить fallback-провайдера, навести порядок в autofix-цикле.

---

## Сессия 0.1 — Учёт токенов + реальный биллинг (одна сессия — части бессмысленны порознь)

**Цель:** Сделать видимыми `prompt_tokens`/`total_tokens`, накапливать их по раундам дозапроса, и списывать звёзды по факту токенов. Учёт токенов без биллинга и биллинг без учёта токенов бессмысленны порознь — это одна сессия (как указано в задаче).
**Флаги:** `STUDIO_V4_TOKEN_BILLING` (default off). Учёт токенов (Коммит 0.1.1) аддитивен и флага не требует; флаг гейтит только списание.
**Файлы:** `src/studio/agents/base.py`, `src/config/settings.py`, `src/studio/billing.py`, `src/studio/tasks.py`

### Коммит 0.1.1 — last_prompt_tokens / last_total_tokens + накопление в continuation

**Файл:** `src/studio/agents/base.py`

**Что делать точно:**
- В классе `BaseAgent` рядом с `last_completion_tokens: int = 0` (строка 38) добавить два атрибута класса:
  ```python
  last_prompt_tokens: int = 0
  last_total_tokens: int = 0
  ```
- В методе `run_prompt`, в блоке сброса в начале (строки 68-69, где сейчас `self.last_finish_reason = None` и `self.last_completion_tokens = 0`), добавить сброс новых полей:
  ```python
  self.last_prompt_tokens = 0
  self.last_total_tokens = 0
  ```
- В цикле по `stream`, в ветке `if getattr(chunk, 'usage', None):` (строки 91-92), читать все три поля из одного места:
  ```python
  if getattr(chunk, 'usage', None):
      self.last_completion_tokens = chunk.usage.completion_tokens or 0
      self.last_prompt_tokens = chunk.usage.prompt_tokens or 0
      self.last_total_tokens = chunk.usage.total_tokens or 0
  ```
- **КРИТИЧНО — `run_prompt_with_continuation` (строки 120-157):** сейчас он в цикле вызывает `run_prompt`, который ПЕРЕЗАПИСЫВАЕТ счётчики каждый раунд. Надо накапливать. Реализация:
  - Перед циклом `for attempt in range(max_rounds + 1):` завести локальные аккумуляторы:
    ```python
    acc_prompt = 0
    acc_completion = 0
    acc_total = 0
    ```
  - Сразу после строки `full += part` (внутри цикла) добавить:
    ```python
    acc_prompt += self.last_prompt_tokens
    acc_completion += self.last_completion_tokens
    acc_total += self.last_total_tokens
    ```
  - **ВАЖНО:** проверка `capped` (строки 141-145) опирается на `self.last_completion_tokens` ТЕКУЩЕГО раунда — её НЕ трогаем (она про один раунд, это правильно). Аккумуляторы используем только для финального присвоения.
  - В самом конце метода, ПЕРЕД `return full`, перезаписать счётчики агрегатами, чтобы вызывающий код (биллинг) видел суммарный расход:
    ```python
    self.last_prompt_tokens = acc_prompt
    self.last_completion_tokens = acc_completion
    self.last_total_tokens = acc_total
    return full
    ```
- **Что НЕ делать:** не менять сигнатуры методов; не трогать `run_json`, `run_vision`; не трогать логику `capped`.

**Проверка коммита:** Накопление: юнит-тест на `run_prompt_with_continuation` с мок-стримом в 2 раунда — `last_prompt_tokens` равен сумме обоих раундов, а не последнего.

### Коммит 0.1.2 — флаг + биллинг по реальным токенам

**Файлы:** `src/config/settings.py`, `src/studio/billing.py`, `src/studio/tasks.py`

**Что делать точно:**

1. В `src/config/settings.py` рядом с `STUDIO_V3` (строка 314) добавить:
   ```python
   STUDIO_V4_TOKEN_BILLING = os.getenv('STUDIO_V4_TOKEN_BILLING', '0') == '1'
   ```

2. В `src/studio/billing.py` добавить функцию расчёта стоимости по токенам (после `coder_tier_for_model`, ~строка 54):
   ```python
   def stars_for_tokens(prompt_tokens: int, completion_tokens: int, tier: str) -> int:
       """Реальная стоимость одного вызова агента по факту токенов.
       STAR_RATE задан за 1000 токенов. Считаем суммарные (prompt+completion)."""
       total = (prompt_tokens or 0) + (completion_tokens or 0)
       rate = STAR_RATE.get(tier, STAR_RATE['fast'])
       return max(1, int((total / 1000.0) * rate))
   ```

3. В `src/studio/tasks.py`, функция `_billing_charge` (строки 29-53). Сейчас стоимость = `AGENT_BUDGET`-константа. Добавить ВЕТКУ по реальным токенам, не ломая старую. Сигнатуру расширить опциональными параметрами:
   ```python
   def _billing_charge(project, agent_name, step_index, tier_override=None,
                       prompt_tokens=None, completion_tokens=None):
   ```
   В начале расчёта стоимости (перед текущим `if tier_override:` на строке 31) вставить:
   ```python
   from django.conf import settings as _s
   if (_s.STUDIO_V4_TOKEN_BILLING and prompt_tokens is not None
           and completion_tokens is not None):
       from .billing import stars_for_tokens
       tier = tier_override or AGENT_BUDGET.get(agent_name, ('fast', 0))[0]
       cost = stars_for_tokens(prompt_tokens, completion_tokens, tier)
   elif tier_override:
       ...  # существующий код без изменений
   else:
       ...  # существующий код без изменений
   ```
   Остальное тело функции (cap-проверка, `charge_from_reserve`, SSE-событие, billing_log) НЕ меняем.

4. В `src/studio/tasks.py`, `coder_iteration`, место вызова `_billing_charge(project, 'coder', step_index, tier_override=coder_tier)` (строка 585). Прокинуть токены агента:
   ```python
   _billing_charge(
       project, 'coder', step_index, tier_override=coder_tier,
       prompt_tokens=agent.last_prompt_tokens,
       completion_tokens=agent.last_completion_tokens,
   )
   ```
   (`agent` — это `CoderAgent`, унаследовал поля от `BaseAgent`; после `agent.run(...)` они содержат накопленные значения благодаря Сессии 0.1.)

**Что НЕ делать:** `reserve()` / `estimate_stars()` ОСТАВЛЯЕМ на `AGENT_BUDGET` (это предоплата-резерв, она должна быть консервативной/завышенной). Менять только фактическое списание. Не трогать вызовы `_billing_charge` для других агентов (architect/guardian) в этом коммите, если токены туда не прокинуты — они уйдут в старую ветку.

### Коммит 0.1.3 — динамическая estimate_stars по длине плана

**Файл:** `src/studio/billing.py`

**Что делать точно:**
- В `estimate_stars(project, planned_steps=5)` (строка 30) перед расчётом добавить вычисление реального числа шагов из плана, оставив `planned_steps` как fallback:
  ```python
  def estimate_stars(project, planned_steps: int = 5) -> int:
      idata = getattr(project, 'interview_data', {}) or {}
      plan = idata.get('plan')
      if isinstance(plan, list) and plan:
          planned_steps = len(plan)
      elif idata.get('planned_steps'):
          planned_steps = idata['planned_steps']
      # дальше — существующий расчёт без изменений
  ```
- `plan` пишется ArchitectAgent с V3 (`architect.py:171`, ключ `plan`), `planned_steps` — там же (`result['planned_steps']`). Оба могут отсутствовать у старых проектов — поэтому fallback на аргумент обязателен.

**Что НЕ делать:** не убирать параметр `planned_steps` из сигнатуры — его передают из `views/pipeline.py` (`EstimateView`, `PipelineResumeView`).

**Проверка сессии:** `STUDIO_V4_TOKEN_BILLING=0` → списания идентичны прежним (тесты `studio` зелёные). `STUDIO_V4_TOKEN_BILLING=1` → в SSE billing-событии (`-N зв.`) сумма теперь зависит от размера сгенерированного файла. `EstimateView` для проекта с заполненным `interview_data['plan']` возвращает `planned_steps == len(plan)`.

---

## Сессия 0.2 — Кэш контекста COMMITS.md в coder

**Цель:** Перестать слать весь `commits_md_content` в каждый промпт coder — слать текст текущего шага + краткое резюме остальных.
**Флаги:** `STUDIO_V4_COMMITS_CACHE` (default off).
**Файлы:** `src/config/settings.py`, `src/studio/agents/coder.py`

### Коммит 0.2.1 — commits_summary вместо полного COMMITS.md

**Файлы:** `src/config/settings.py`, `src/studio/agents/coder.py`

**Что делать точно:**

1. `settings.py`: добавить `STUDIO_V4_COMMITS_CACHE = os.getenv('STUDIO_V4_COMMITS_CACHE', '0') == '1'`.

2. `coder.py`: добавить хелпер-метод в `CoderAgent` (рядом с `_design_excerpt`, ~строка 285):
   ```python
   def _commits_summary(self) -> str:
       """3-строчное резюме всех шагов плана: '## Шаг N: title' лайны.
       Используется вместо полного COMMITS.md когда STUDIO_V4_COMMITS_CACHE=1."""
       import re as _re
       md = getattr(self.project, 'commits_md_content', '') or ''
       titles = _re.findall(r'^##\s+(?:Step|Шаг)\s+\d+[^\n]*', md, _re.MULTILINE)
       return '\n'.join(titles)
   ```

3. В `_get_manifest` (строки 172-196) и в `_generate_one_file` (строки 200-274) сейчас собирается:
   ```python
   commits_md = getattr(self.project, 'commits_md_content', '') or ''
   commits_block = f"\n\nFull implementation plan (COMMITS.md):\n{commits_md}" if commits_md else ''
   ```
   Заменить ОБА вхождения на флаг-чувствительную сборку:
   ```python
   if settings.STUDIO_V4_COMMITS_CACHE:
       summary = self._commits_summary()
       commits_block = f"\n\nПлан (заголовки шагов):\n{summary}" if summary else ''
   else:
       commits_md = getattr(self.project, 'commits_md_content', '') or ''
       commits_block = f"\n\nFull implementation plan (COMMITS.md):\n{commits_md}" if commits_md else ''
   ```
   `settings` уже импортирован в `coder.py` (строка 4: `from django.conf import settings`).
   Текст текущего шага (`step_text`) уже передаётся отдельно в обоих местах — его НЕ трогаем, он остаётся полным.

**Что НЕ делать:** не менять `step_text`; не трогать legacy-путь `_run_legacy` (он и так не вкладывает COMMITS.md).

**Проверка сессии:** `STUDIO_V4_COMMITS_CACHE=1` → в логах при `_get_manifest` промпт короче; сгенерированный проект на 6-8 шагов всё ещё собирается. Сравнить `prompt_tokens` (виден после Сессии 0.1) на одинаковом проекте с флагом и без — с флагом меньше. Тесты зелёные.

---

## Сессия 0.3 — Fallback-провайдер в base.py

**Цель:** При 5xx/timeout от основного провайдера один раз ретраить на запасном.
**Флаги:** `STUDIO_V4_PROVIDER_FALLBACK` (default off).
**Файлы:** `src/config/settings.py`, `src/studio/agents/base.py`

### Коммит 0.3.1 — get_fallback_client + retry в run_prompt

**Файлы:** `src/config/settings.py`, `src/studio/agents/base.py`

**Что делать точно:**

1. `settings.py`:
   ```python
   STUDIO_V4_PROVIDER_FALLBACK = os.getenv('STUDIO_V4_PROVIDER_FALLBACK', '0') == '1'
   LAOZHANG_API_URL_FALLBACK = os.getenv('LAOZHANG_API_URL_FALLBACK', '')
   ```

2. `base.py`, рядом с `_client` и `get_client()` (строки 20-31), добавить второй кешированный клиент:
   ```python
   _fallback_client = None

   def get_fallback_client():
       global _fallback_client
       url = getattr(settings, 'LAOZHANG_API_URL_FALLBACK', '')
       if not url:
           return None
       if _fallback_client is None:
           _fallback_client = OpenAI(
               api_key=settings.LAOZHANG_API_KEY,
               base_url=url,
               timeout=360.0,
           )
       return _fallback_client
   ```

3. В `run_prompt`, вызов `self.client.chat.completions.create(...)` (строки 82-89). Обернуть в функцию-локаль и try/except:
   ```python
   import openai  # вверху файла к существующим импортам

   def _open_stream(client):
       return client.chat.completions.create(
           model=model_id, messages=messages, stream=True,
           max_tokens=max_tokens, temperature=temperature,
           stream_options={'include_usage': True},
       )

   try:
       stream = _open_stream(self.client)
   except (openai.APIStatusError, openai.APITimeoutError) as exc:
       fb = None
       if getattr(settings, 'STUDIO_V4_PROVIDER_FALLBACK', False):
           status = getattr(exc, 'status_code', None)
           is_5xx = status is None or status >= 500  # timeout => status None
           if is_5xx:
               fb = get_fallback_client()
       if fb is None:
           raise
       logger.warning('agent %s: provider_failover model=%s err=%s',
                      self.name, model_id, exc)
       stream = _open_stream(fb)
   ```
   `import openai` добавить к импортам в начале файла (рядом с `from openai import OpenAI`).

**Что НЕ делать:** Ретраить только ОДИН раз (на fallback). НЕ ретраить при 4xx (auth/bad request). НЕ оборачивать сам цикл `for chunk in stream` — если поток оборвётся в середине, это не покрываем (слишком рискованно). Только установку соединения. Если флаг выключен — поведение прежнее (исключение пробрасывается как сейчас).

**Проверка сессии:** `STUDIO_V4_PROVIDER_FALLBACK=0` → исключения пробрасываются как раньше. С флагом и валидным `LAOZHANG_API_URL_FALLBACK`: временно подменить основной `base_url` на нерабочий → в логах `provider_failover`, генерация проходит на fallback. Тесты зелёные.

---

## Сессия 0.4 — Autofix: поля состояния, дедуп, лимит и сброс (одна сессия — весь backend autofix)

**Цель:** Защитить autofix-цикл целиком: миграция полей, дедуп по хэшу ошибки, лимит, сброс счётчиков при resume/skip и очистка при успехе. Все три коммита — backend, последовательны и зависят друг от друга (max-3 коммита на сессию допустимо правилами).
**Флаги:** `STUDIO_V4_AUTOFIX`, `STUDIO_MAX_AUTOFIX` (число, default 3).
**Файлы:** `src/config/settings.py`, `src/studio/models.py`, миграция, `src/studio/views/pipeline.py`, `src/studio/tasks.py`

### Коммит 0.4.1 — поля seen_error_hashes / autofix_count + миграция

**Файлы:** `src/config/settings.py`, `src/studio/models.py`, новая миграция

**Что делать точно:**

1. `settings.py`:
   ```python
   STUDIO_V4_AUTOFIX = os.getenv('STUDIO_V4_AUTOFIX', '0') == '1'
   STUDIO_MAX_AUTOFIX = int(os.getenv('STUDIO_MAX_AUTOFIX', '3'))
   ```

2. `src/studio/models.py`, класс `StudioPipelineState` (строка 80). После поля `error_repeat_count` (строка 106) добавить:
   ```python
   seen_error_hashes = models.JSONField(default=list, blank=True)
   autofix_count = models.IntegerField(default=0)
   ```

3. **ОБЯЗАТЕЛЬНО создать миграцию:**
   ```bash
   cd src && python manage.py makemigrations studio
   ```
   Закоммитить сгенерированный файл `src/studio/migrations/00XX_*.py` вместе с изменением модели.

**Что НЕ делать:** не менять `STATUS_CHOICES`; не добавлять другие поля в этом коммите.

### Коммит 0.4.2 — дедуп в ConsoleErrorView + лимит autofix

**Файл:** `src/studio/views/pipeline.py`

**Что делать точно:**
- `ConsoleErrorView.post` (строки 290-317). Сейчас при `request.data.get('autofix')` он безусловно ставит `state.fix_plan` и зовёт `coder_iteration.delay`. Обернуть autofix-ветку (строки 305-316) в логику дедупа/лимита, активную только при `STUDIO_V4_AUTOFIX`:
  ```python
  if request.data.get('autofix'):
      state = project.pipeline
      from django.conf import settings as _s
      if _s.STUDIO_V4_AUTOFIX:
          import hashlib
          sig = hashlib.sha256(
              f"{err['message']}|{err['file']}".encode()
          ).hexdigest()[:16]
          seen = state.seen_error_hashes or []
          if sig in seen:
              return Response(
                  {'error': 'duplicate_error', 'stored': True}, status=409
              )
          if (state.autofix_count or 0) >= _s.STUDIO_MAX_AUTOFIX:
              state.status = 'paused_on_loop'
              state.pause_reason = (
                  f'Достигнут лимит автоисправлений ({_s.STUDIO_MAX_AUTOFIX}). '
                  'Опишите проблему вручную.'
              )
              project.status = 'paused'
              project.save(update_fields=['status'])
              state.save(update_fields=['status', 'pause_reason'])
              from ..events import publish_event
              publish_event(str(project.id), {
                  'agent': 'system', 'level': 'warning', 'type': 'paused',
                  'reason': state.pause_reason,
              })
              return Response({'paused': True, 'reason': 'autofix_limit'}, status=409)
          seen.append(sig)
          state.seen_error_hashes = seen[-50:]
          state.autofix_count = (state.autofix_count or 0) + 1
      # --- общая часть (и для флага, и без) ---
      hint = f"Ошибка в превью: {err['message']} ({err['file']}:{err['line']})\n{err['stack']}"
      state.fix_plan = {
          'instructions': hint,
          'target_files': [err['file']] if err['file'] else [],
      }
      state.status = 'running'
      state.pause_requested = False
      save_fields = ['fix_plan', 'status', 'pause_requested']
      if _s.STUDIO_V4_AUTOFIX:
          save_fields += ['seen_error_hashes', 'autofix_count']
      state.save(update_fields=save_fields)
      from ..tasks import coder_iteration
      coder_iteration.delay(str(project.id), state.step_index)
  ```
- **ВАЖНО:** при выключенном флаге (`STUDIO_V4_AUTOFIX=0`) поведение идентично текущему: ни дедупа, ни лимита, обычный fix. Поля `seen_error_hashes`/`autofix_count` в save попадают только при включённом флаге.

**Что НЕ делать:** Не сбрасывать `autofix_count` здесь — сброс делается при ручном resume/skip (Коммит 0.4.3). Не возвращать 409 при выключенном флаге.

**Проверка коммита:** Применить миграцию. С `STUDIO_V4_AUTOFIX=1`: дважды POST `/api/v1/studio/projects/{id}/console-error/` с `{autofix:true, message:"X", file:"a.ts"}` → второй вернёт 409 `duplicate_error`. После 3 разных ошибок 4-я с новой сигнатурой → 409 `autofix_limit`, проект на паузе. С флагом 0 — старое поведение.

### Коммит 0.4.3 — сброс autofix_count при resume/skip; очистка при pass

**Файлы:** `src/studio/views/pipeline.py`, `src/studio/tasks.py`

**Что делать точно:**

1. `views/pipeline.py`, `PipelineResumeView.post` (строки 138-165): рядом с `state.iteration_count = 0` (строка 145) добавить сброс autofix-счётчика (безусловно — это дёшево и поля уже есть после Коммита 0.4.1):
   ```python
   state.autofix_count = 0
   state.seen_error_hashes = []
   ```
   Эти поля сохраняются вызовом `state.save()` ниже в каждой ветке — отдельный `update_fields` тут не используется (метод зовёт полный `state.save()`), так что достаточно присвоить.

2. `views/pipeline.py`, `PipelineSkipView.post` (строки 264-287): в список присвоений (строки 273-277) добавить:
   ```python
   state.autofix_count = 0
   state.seen_error_hashes = []
   ```
   и расширить `update_fields` (строки 278-281) элементами `'autofix_count', 'seen_error_hashes'`.

3. `tasks.py`, очистка хэша при успешном Guardian-вердикте. Найти задачу `guardian_review` (она вызывается в конце `coder_iteration`, строка 584). Прочитать её тело целиком (Grep `def guardian_review` в `tasks.py`). В ветке, где вердикт == `pass` (Guardian не нашёл проблем) и при `settings.STUDIO_V4_AUTOFIX`, удалить из `state.seen_error_hashes` хэши, относящиеся к этому шагу. Простейшая безопасная реализация: при успешном `pass` обнулить счётчик текущей серии:
   ```python
   from django.conf import settings as _s
   if _s.STUDIO_V4_AUTOFIX and verdict == 'pass':
       st = project.pipeline
       if st.autofix_count:
           st.autofix_count = 0
           st.seen_error_hashes = []
           st.save(update_fields=['autofix_count', 'seen_error_hashes'])
   ```
   Вставить это там, где `guardian_review` уже определил `verdict == 'pass'` и переходит к следующему шагу (НЕ дублировать переход — только добавить очистку рядом с существующей pass-логикой).

**Что НЕ делать:** Не менять логику самого Guardian-ревью и переходов между шагами. Если структура `guardian_review` отличается от ожидаемой — добавить очистку в ту точку, где гарантированно известно `verdict == 'pass'`, и не более того.

**Проверка сессии:** С `STUDIO_V4_AUTOFIX=1`: после 3 autofix → пауза; нажать «Продолжить» (resume) → `autofix_count == 0`, autofix снова доступен. После успешного шага (Guardian pass) → `seen_error_hashes` пуст. Тесты зелёные.

---

## Сессия 0.5 — Авто-захват ошибок iframe в превью

**Цель:** Хук `window.onerror` + `console.error` внутри iframe-превью → автоматический POST на console-error, без ручной кнопки.
**Флаги:** управляется бэкенд-флагом `STUDIO_V4_AUTOFIX` неявно (фронт просто шлёт; autofix решает бэк). Доп. флаг не нужен.
**Примечание по FE/BE:** эта сессия трогает и backend (`PreviewProxyView`, инъекция `<script>` в отдаваемый HTML), и frontend (`PreviewPanel.tsx`, приём postMessage). Сохранено в одной сессии намеренно: оба изменения — один сквозной механизм «захват ошибки в iframe → постинг наружу», бессмысленный половинами. Backend-часть — это инъекция строки в HTML, не Django-логика, поэтому риск-профиль низкий.
**Файлы:** `src/studio/views/pipeline.py`, `frontend/components/studio/PreviewPanel.tsx`

### Коммит 0.5.1 — инъекция error-хука в превью-iframe

**Файл:** `frontend/components/studio/PreviewPanel.tsx`

**Контекст (реальность):** `PreviewPanel` уже слушает `window` `message` (`type === 'studio-console-error'`, строки 35-45) и шлёт `studioApi.reportConsoleError`. Сейчас сам iframe-контент НЕ постит такие сообщения автоматически — это и надо добавить. iframe грузится по `src = ${base}/studio/projects/${projectId}/preview/` (строки 204-205), контент отдаёт backend `PreviewProxyView` (proxy на sandbox или static-файлы из БД).

**Что делать точно (вариант A — инъекция через backend proxy, предпочтительно):**
- Поскольку iframe — cross-document от того же origin (отдаётся через наш `/preview/`), скрипт-хук надо встроить в HTML, который возвращает `PreviewProxyView`. В `src/studio/views/pipeline.py`, `PreviewProxyView.get`, в ветке статической отдачи HTML (строки 395-403, где уже вставляется `<base href>`), добавить инъекцию `<script>` сразу после `<base>`:
  ```python
  err_hook = (
      '<script>(function(){'
      'function send(p){try{parent.postMessage('
      '{type:"studio-console-error",payload:p},"*");}catch(e){}}'
      'window.addEventListener("error",function(e){'
      'send({message:String(e.message||e.error),file:e.filename||"",'
      'line:e.lineno||0,stack:(e.error&&e.error.stack)||""});});'
      'var oce=console.error;console.error=function(){'
      'send({message:Array.prototype.join.call(arguments," "),file:"",line:0,stack:""});'
      'oce.apply(console,arguments);};'
      '})();</script>'
  )
  ```
  Вставлять вместе с `tag` (`<base ...>`) в том же месте, где сейчас `body.replace('<head>', f'<head>{tag}', 1)` → `f'<head>{tag}{err_hook}'`.
  - Для проксируемого sandbox-контента (ветка строки 365-381) инъекцию НЕ делаем (нельзя надёжно переписать произвольный upstream HTML) — там оставляем как есть. Авто-захват работает для static-режима; sandbox-режим использует HMR-консоль.

- В `PreviewPanel.tsx` обновить существующий `message`-listener (строки 35-45), чтобы он принимал НОВЫЙ формат `payload` (а не только старый `studio-console-error` без payload). Сделать обратносовместимо:
  ```ts
  const data = e.data || {};
  if (data.type !== 'studio-console-error') return;
  const p = data.payload || data;  // новый формат с payload или старый плоский
  const ce = { message: p.message || '', file: p.file || '', line: p.line || 0, stack: p.stack || '' };
  setErrors((prev) => [...prev.slice(-9), ce]);
  studioApi.reportConsoleError(projectId, { ...ce, autofix: false });
  ```
  **ВАЖНО:** `autofix: false` при авто-захвате — авто-починку НЕ запускаем автоматически (это спам и деньги); просто накапливаем ошибки и показываем кнопку «Исправить» (она уже есть, `handleAutofix`, строки 122-131, шлёт `autofix:true`). Решение чинить — за пользователем.

**Что НЕ делать:** Не запускать autofix автоматически по каждой ошибке. Не инъектить в проксируемый sandbox HTML. Не ломать существующий `studio-console-error` путь (поэтому проверяем оба формата).

**Проверка сессии:** Создать static-проект (HTML), в коде которого есть `throw new Error('boom')`. Открыть превью → в панели ошибок PreviewPanel появляется «boom» без ручных действий; кнопка «Исправить» запускает autofix (если бэк-флаг включён).

---

# ФАЗА 1 — UX-паритет с bolt.new

Цель: стриминг «смотри как пишется», Guardian видит весь проект, живой предпросмотр.

---

## Сессия 1.1 — Backend: проброс on_delta в run_prompt / continuation

**Цель:** Добавить колбэк дельт в генерацию текста.
**Флаги:** `STUDIO_V4_STREAMING` (default off).
**Файлы:** `src/config/settings.py`, `src/studio/agents/base.py`

### Коммит 1.1.1 — on_delta в run_prompt и run_prompt_with_continuation

**Файлы:** `src/config/settings.py`, `src/studio/agents/base.py`

**Что делать точно:**

1. `settings.py`: `STUDIO_V4_STREAMING = os.getenv('STUDIO_V4_STREAMING', '0') == '1'`.

2. `base.py`, `run_prompt` (строка 59): добавить параметр `on_delta=None` в сигнатуру:
   ```python
   def run_prompt(self, system, user, model=None, max_tokens=8192,
                  temperature=0.7, prior='', on_delta=None):
   ```
   В цикле, в ветке накопления контента (строки 96-97):
   ```python
   if choice.delta and choice.delta.content:
       chunks.append(choice.delta.content)
       if on_delta is not None:
           try:
               on_delta(choice.delta.content)
           except Exception:
               pass  # стриминг не должен ронять генерацию
   ```

3. **КРИТИЧНО:** `run_prompt_with_continuation` (строка 120) ТОЖЕ должен принимать и пробрасывать `on_delta`, иначе стриминг умрёт на любом дозапросе (а `_generate_one_file` зовёт именно continuation). Добавить `on_delta=None` в сигнатуру и передать в каждый вызов `self.run_prompt(...)` внутри цикла (строки 133-137):
   ```python
   part = self.run_prompt(
       system, user, model=model_id, max_tokens=max_tokens,
       temperature=temperature, prior=full, on_delta=on_delta,
   )
   ```

**Что НЕ делать:** Не вызывать `publish_event` отсюда — `base.py` не знает про троттлинг/буферизацию. Колбэк сырой; буферизацию делает вызывающий (Сессия 1.2). `on_delta=None` по умолчанию → старое поведение.

**Проверка сессии:** Юнит-тест: вызвать `run_prompt` с `on_delta=lambda c: collected.append(c)` на мок-стриме → `''.join(collected) == content`. Тесты зелёные.

---

## Сессия 1.2 — Backend: публикация file_delta из coder

**Цель:** Coder при генерации файла шлёт SSE-события `file_delta` с троттлингом.
**Зависит от:** Сессии 1.1.
**Флаги:** `STUDIO_V4_STREAMING`.
**Файлы:** `src/studio/agents/coder.py`

### Коммит 1.2.1 — on_delta-буфер в _generate_one_file

**Файл:** `src/studio/agents/coder.py`

**Что делать точно:**
- В `_generate_one_file` (строки 200-274), в V3-ветке перед вызовом `run_prompt_with_continuation` (строка 246) собрать колбэк с буферизацией по времени/размеру:
  ```python
  on_delta = None
  if settings.STUDIO_V4_STREAMING:
      import time as _time
      from ..events import publish_event
      _buf = {'text': '', 'ts': _time.monotonic()}
      pid = str(self.project.id)
      def on_delta(chunk_text, _buf=_buf, _path=path, _pid=pid):
          _buf['text'] += chunk_text
          now = _time.monotonic()
          if len(_buf['text']) >= 80 or (now - _buf['ts']) >= 0.2:
              publish_event(_pid, {
                  'type': 'file_delta', 'path': _path, 'chunk': _buf['text'],
              })
              _buf['text'] = ''
              _buf['ts'] = now
  ```
- Передать `on_delta=on_delta` в вызов `run_prompt_with_continuation` (строка 246-249).
- **После** генерации (после получения `content`, перед `return content` в V3-ветке) сбросить остаток буфера и послать финальное событие:
  ```python
  if settings.STUDIO_V4_STREAMING:
      from ..events import publish_event
      if _buf['text']:
          publish_event(str(self.project.id), {
              'type': 'file_delta', 'path': path, 'chunk': _buf['text'],
          })
      publish_event(str(self.project.id), {
          'type': 'file_delta_done', 'path': path,
      })
  ```
- Применять и в legacy-ветке `_generate_one_file` (строки 263-274) — там тоже передать `on_delta` в continuation, аналогично.

**Что НЕ делать:** Не отправлять `file_delta` в `_run_legacy` (single-call JSON) — там промежуточный текст не является чистым кодом файла. Только per-file путь.

**Проверка сессии:** `STUDIO_V4_STREAMING=1`, запустить проект, через `redis-cli SUBSCRIBE studio:events:{id}` видеть поток `{"type":"file_delta","path":...,"chunk":...}` и финальный `file_delta_done`. С флагом 0 — событий нет.

---

## Сессия 1.3 — Frontend: live-стриминг файла в CodeViewer

**Цель:** Показывать код по мере генерации (вкладка файла + дописывание + курсор).
**Зависит от:** Сессии 1.2 (события `file_delta`/`file_delta_done`).
**Флаги:** нет на фронте (просто слушает события; их наличие управляется бэк-флагом).
**Файлы:** `frontend/components/studio/StudioLayout.tsx`, `frontend/components/studio/CodeViewer.tsx`

### Коммит 1.3.1 — приём file_delta и проброс в CodeViewer

**Файлы:** `frontend/components/studio/StudioLayout.tsx`, `frontend/components/studio/CodeViewer.tsx`

**Контекст (реальность):** `CodeViewer` — props-driven, без SSE и без вкладок; показывает один файл из props `content`. `StudioLayout` владеет выбором файла (`selectedFileId`/`fileDetail`) и уже держит свой `EventSource` (строки 207-219, сейчас только трекает `currentAgent`). Логичнее всего перехватывать `file_delta` именно в `StudioLayout`.

**Что делать точно:**

1. `StudioLayout.tsx`, в существующем `EventSource.onmessage` (строки 209-216) добавить ветки:
   ```ts
   if (d.type === 'file_delta') {
     setStreamingPath(d.path);
     setStreamingContent((prev) =>
       d.path === streamingPathRef.current ? prev + d.chunk : d.chunk
     );
     return;
   }
   if (d.type === 'file_delta_done') {
     // финал: оставляем контент, гасим курсор
     setStreamingActive(false);
     return;
   }
   ```
   Завести state: `streamingPath` (string|null), `streamingContent` (string), `streamingActive` (bool), и `streamingPathRef = useRef<string|null>(null)` (синхронизировать в эффекте при смене `streamingPath`). При первом `file_delta` нового пути ставить `streamingActive=true` и сбрасывать накопленный контент.
   Когда приходит `file_delta` для нового `path`, автоматически выбрать этот файл во вкладке кода (вызвать тот же handler, что и `onFileSelect`, либо переключить активную панель на «Код»).

2. `CodeViewer.tsx`: добавить опциональные props в `CodeViewerProps` (строки 14-21):
   ```ts
   streaming?: boolean;       // показывать курсор
   streamContent?: string;    // если задан и streaming — рендерим его поверх content
   ```
   В компоненте: если `streaming && streamContent != null` — отображать `streamContent` (read-only) вместо `value`, с мигающим курсором в конце. Когда `streaming` становится `false` — вернуться к обычному props-driven отображению (`content`). Курсор — простой CSS-блинк (span с `animate-pulse` после кода). Редактирование во время стриминга отключить (`editable={false}` пока `streaming`).

3. В `StudioLayout` передать в `CodeViewer` (строки 469-476): `streaming={streamingActive && streamingPath === <текущий путь>}` и `streamContent={streamingContent}`.

**Что НЕ делать:** Не вводить отдельный EventSource в CodeViewer (используем существующий в StudioLayout). Не ломать props-driven режим: при отсутствии стриминга компонент работает как раньше. После `file_delta_done` итоговый файл всё равно прилетит через обычный refresh файлового дерева — не пытаться сохранять стрим-контент в БД с фронта.

**Проверка сессии:** `STUDIO_V4_STREAMING=1`. При генерации файла его вкладка открывается сама, код «печатается», в конце мигающий курсор гаснет, отображается финальный файл. Без флага — обычное поведение (вкладка обновляется по завершении шага).

---

## Сессия 1.4 — Guardian видит весь проект (symbol map)

**Цель:** Дать Guardian карту экспортов всего проекта + полный контент импортируемых файлов.
**Флаги:** `STUDIO_V4_GUARDIAN_CONTEXT` (default off).
**Файлы:** `src/config/settings.py`, `src/studio/agents/guardian.py`

### Коммит 1.4.1 — symbol map + контент импортируемых файлов в промпте Guardian

**Файлы:** `src/config/settings.py`, `src/studio/agents/guardian.py`

**Контекст (реальность):** `GuardianAgent.run(self, step_text, files, build_logs='', attempt=0)` (строка 160). `files` — словарь изменённых на шаге файлов. `user`-промпт собирается на строках 180-184. Нам нужен доступ ко ВСЕМ файлам проекта — берём через `self.project.files.all()`.

**Что делать точно:**

1. `settings.py`: `STUDIO_V4_GUARDIAN_CONTEXT = os.getenv('STUDIO_V4_GUARDIAN_CONTEXT', '0') == '1'`.

2. `guardian.py`: добавить модульные хелперы (вверху файла, после импортов):
   ```python
   _EXPORT_RE = re.compile(
       r'^export\s+(?:default\s+)?(?:const|function|class|type|interface)\s+(\w+)',
       re.MULTILINE,
   )
   _REEXPORT_RE = re.compile(r"^export\s+\*\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
   _IMPORT_RE = re.compile(r"import\s+[^'\"]*from\s+['\"]([^'\"]+)['\"]")

   def _exports_of(content: str) -> list:
       names = _EXPORT_RE.findall(content or '')
       names += [f'* from {m}' for m in _REEXPORT_RE.findall(content or '')]
       return names

   def _build_symbol_map(all_files: dict, changed_paths: set) -> str:
       lines = []
       for path, content in all_files.items():
           if path in changed_paths:
               continue
           exps = _exports_of(content)
           if exps:
               lines.append(f'{path}: {", ".join(exps[:20])}')
       return '\n'.join(lines)

   def _imported_paths(changed_files: dict) -> set:
       out = set()
       for content in changed_files.values():
           for spec in _IMPORT_RE.findall(content or ''):
               if spec.startswith('.'):
                   out.add(spec)  # относительный — резолвим грубо по совпадению хвоста пути
       return out
   ```

3. В `GuardianAgent.run`, перед сборкой `user` (строка 180), при флаге собрать дополнительные секции:
   ```python
   project_ctx = ''
   if settings.STUDIO_V4_GUARDIAN_CONTEXT:
       all_files = {f.path: f.content for f in self.project.files.all()}
       changed = set(files.keys())
       symbol_map = _build_symbol_map(all_files, changed)
       # полный контент файлов, на которые ссылаются изменённые (по хвосту пути)
       wanted = _imported_paths(files)
       imported_full = []
       for path, content in all_files.items():
           if path in changed:
               continue
           if any(path.endswith(w.lstrip('./').replace('./', '')) or
                  w.split('/')[-1] in path for w in wanted):
               imported_full.append(f'### {path}\n```\n{content[:6000]}\n```')
       parts = []
       if symbol_map:
           parts.append(f'Project exports (path → exported names):\n{symbol_map}')
       if imported_full:
           parts.append('Imported file contents:\n' + '\n'.join(imported_full[:6]))
       if parts:
           project_ctx = '\n\n' + '\n\n'.join(parts)
   ```
   И вставить `project_ctx` в `user` (строки 180-184), например после `files_content`:
   ```python
   user = (
       f'Planned step:\n{step_text}{design_section}{project_ctx}\n\n'
       f'Implemented files:{attempt_note}\n{files_content}'
       f'{build_section}'
   )
   ```

4. В системные промпты Guardian (`SYSTEM_V3_RU`/`SYSTEM_V3_EN`, и базовые `SYSTEM_RU`/`SYSTEM_EN`) добавить одну строку про учёт «Project exports» — например: «Учитывай раздел Project exports: не считай ошибкой импорт символа, который там присутствует». Править ОБА языка соответствующей пары.

**Что НЕ делать:** Не раздувать промпт без лимитов — `[:20]` имён на файл, `[:6]` полных файлов, `[:6000]` символов. Резолв импортов грубый (по совпадению хвоста пути) — это ок, цель снизить ложные срабатывания, а не точный модульный граф. При выключенном флаге `project_ctx = ''` — промпт прежний.

**Проверка сессии:** `STUDIO_V4_GUARDIAN_CONTEXT=1`. На проекте, где компонент импортирует из `src/lib/api.ts`, Guardian-промпт (залогировать `user` временно) содержит секции «Project exports» и контент `api.ts`. Guardian перестаёт ложно флагать «undefined import» для существующих экспортов. Тесты зелёные.

---

## Сессия 1.5 — Мягкий перезапуск превью по событию

**Цель:** После коммита шага слать `preview_restart`, фронт делает cache-bust iframe (без ручного refresh).
**Флаги:** `STUDIO_V4_STREAMING` переиспользуем НЕ будем; отдельный флаг не нужен — событие аддитивно.
**Файлы:** `src/studio/tasks.py` (или `views/pipeline.py`), `frontend/components/studio/PreviewPanel.tsx`

### Коммит 1.5.1 — событие preview_restart + reload iframe с дебаунсом

**Файлы:** `src/studio/tasks.py`, `frontend/components/studio/PreviewPanel.tsx`

**Контекст (реальность):** `PreviewPanel` уже реагирует на `step_completed`/`coder_done`, бампая `key` (строки 56-58). То есть базовый авто-reload УЖЕ есть. Эта сессия добавляет явное событие `preview_restart` (для случаев, когда коммит произошёл без `step_completed`, например после применения EDIT-блоков) и дебаунс.

**Что делать точно:**

1. `tasks.py`: найти место, где после коммита в Gitea/записи файлов фиксируется версия шага (Grep `StudioVersion.objects.create` и `gitea` в `tasks.py`). Сразу после успешного коммита шага добавить:
   ```python
   publish_event(project_id, {'type': 'preview_restart', 'step': step_index})
   ```
   Если такого единого места нет — добавить публикацию в конце `next_step` после перехода к следующему шагу. Не дублировать с уже существующими `step_completed`.

2. `PreviewPanel.tsx`, в SSE-`onmessage` (строки 55-58) расширить условие и добавить дебаунс:
   ```ts
   if (d.type === 'step_completed' || d.type === 'coder_done' || d.type === 'preview_restart') {
     if (reloadTimer.current) clearTimeout(reloadTimer.current);
     reloadTimer.current = setTimeout(() => setKey((k) => k + 1), 600);
   }
   ```
   Завести `const reloadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);` и очищать в cleanup. Дебаунс 600мс гарантирует «не чаще раза на шаг».

3. (Опционально, аккуратнее) Вместо remount по `key` можно делать cache-bust src: `setSrc(\`${base}/.../preview/?t=${Date.now()}\`)`. Но текущий механизм `key` (remount) проще и уже работает — оставляем `key`, только добавляем новое событие и дебаунс.

**Что НЕ делать:** Не вводить HMR. Не реагировать чаще раза в 600мс. Не ломать существующую реакцию на `step_completed`/`coder_done`.

**Проверка сессии:** `redis-cli` показывает `preview_restart` после шага; iframe перезагружается один раз (не мерцает). Старые события `step_completed` по-прежнему перезагружают превью.

---

# ФАЗА 2 — Российский стек

Цель: сгенерированные приложения работают в РФ из коробки.

---

## Сессия 2.1 — Scaffold-блоки RU-интеграций (один файл scaffold.py — одна сессия)

**Цель:** Четыре детерминированных scaffold-блока: Робокасса, VK ID, Яндекс.Карты, Telegram Login. Все правят один файл `scaffold.py` в одном стиле — объединены в одну сессию (два коммита) согласно правилу «тесно связанные изменения = одна сессия».
**Флаги:** `STUDIO_V4_RU_STACK` (default off) — введём здесь, читать будут Сессии 2.x.
**Файлы:** `src/config/settings.py`, `src/studio/scaffold.py`

### Коммит 2.1.1 — scaffold_robokassa + scaffold_vk_id

**Файлы:** `src/config/settings.py`, `src/studio/scaffold.py`

**Контекст (реальность):** `scaffold.py` сейчас содержит только UI-примитивы (`scaffold_files(stack, design_md='')` возвращает `{path: content}` для react/nextjs). Стиль файла: модульные строковые константы `_BUTTON`/`_CARD`/... + функция, возвращающая `{path: content}`. Новые функции должны следовать этому стилю: возвращать `{path: content}`.

**Что делать точно:**

1. `settings.py`: `STUDIO_V4_RU_STACK = os.getenv('STUDIO_V4_RU_STACK', '0') == '1'`.

2. `scaffold.py`: добавить функции (каждая возвращает `dict[str, str]`):
   - `scaffold_robokassa(stack: str) -> dict` — для `nextjs`: `app/api/payment/create/route.ts` (server handler: генерирует подпись MD5 по схеме `MerchantLogin:OutSum:InvId:ROBOKASSA_PASS1`, строит redirect URL на `https://auth.robokassa.ru/Merchant/Index.aspx?MerchantLogin=...&OutSum=...&InvId=...&SignatureValue=...`, возвращает его клиенту), `app/api/payment/webhook/route.ts` (ResultURL-обработчик: принимает POST от Робокасса, проверяет подпись MD5 `OutSum:InvId:ROBOKASSA_PASS2`, активирует заказ), `src/lib/usePayment.ts` (клиентский хук: `usePayment()` → POST на `/api/payment/create` → `window.location.href = url`), `.env.example` дополнить `ROBOKASSA_LOGIN=`, `ROBOKASSA_PASS1=`, `ROBOKASSA_PASS2=`. Для `react`/`vite` — серверная часть в `server/payment.ts` (Express-подобный handler) + тот же хук.
   - `scaffold_vk_id(stack: str) -> dict` — компонент кнопки VK ID OAuth (`src/components/VkIdButton.tsx`), callback-роут (`app/api/auth/vk/callback/route.ts` для nextjs), `.env.example` += `VK_APP_ID=`.
   - Весь код — production-ready, с обработкой ошибок, без TODO. Комментарии можно на русском. Никаких эмодзи.
   - Для стеков, где блок неприменим (`vue`/`html`) — возвращать `{}`.

**Что НЕ делать:** Не вызывать эти функции автоматически из `scaffold_files` в этом коммите — просто определить (их подключают шаблоны/Architect в Сессии 2.2). Не хардкодить реальные ключи. Не добавлять серверные секреты в клиентский код.

**Проверка коммита:** Импортировать и вызвать `scaffold_robokassa('nextjs')` в shell → словарь с 4 ключами, валидный TS.

### Коммит 2.1.2 — scaffold_yandex_maps + scaffold_telegram_login

**Файл:** `src/studio/scaffold.py`

**Что делать точно:**
- `scaffold_yandex_maps(stack: str) -> dict`: `src/components/YandexMap.tsx` — React-компонент с динамической загрузкой JS API (`https://api-maps.yandex.ru/2.1/?apikey=...&lang=ru_RU`), монтирование карты в `useEffect`, очистка при unmount, props `{center, zoom, markers?}`. `.env.example` += `YANDEX_MAPS_KEY=`. (`NEXT_PUBLIC_YANDEX_MAPS_KEY` для nextjs клиента.)
- `scaffold_telegram_login(stack: str) -> dict`: `src/components/TelegramLogin.tsx` (Telegram Login Widget: вставка скрипта `telegram-widget.js` с data-атрибутами), серверная утилита валидации (`src/lib/verifyTelegramAuth.ts` или серверный route) — проверка хэша по алгоритму Telegram (HMAC-SHA256, secret = SHA256(bot_token)), `.env.example` += `TELEGRAM_BOT_TOKEN=`.
- Те же правила стиля: production-ready, без TODO, без эмодзи, vue/html → `{}`.

**Что НЕ делать:** Не дублировать `.env.example` целиком — каждая scaffold-функция возвращает СВОИ env-строки; склейку `.env.example` решает потребитель (Architect/шаблон), либо договоримся, что каждая функция возвращает ключ `.env.example` с фрагментом, а потребитель объединяет. В рамках коммита: вернуть `.env.example` с фрагментом этой интеграции (потребитель объединит).

**Проверка сессии:** Вызвать обе функции в shell → валидные TS-словари. Тесты зелёные.

---

## Сессия 2.2 — RU-шаблоны в seed_templates

**Цель:** 4 новых StudioTemplate, привязанных к RU-scaffold-блокам.
**Зависит от:** Сессии 2.1 (scaffold-функции существуют).
**Флаги:** `STUDIO_V4_RU_STACK` (шаблоны видны только при флаге, либо помечены).
**Файлы:** `src/studio/models.py`, миграция, `src/studio/management/commands/seed_templates.py`

### Коммит 2.2.1 — 4 RU-шаблона + поле features

**Контекст (реальность):** `StudioTemplate` НЕ имеет поля `features`. Исходный план предполагает «features list, который триггерит scaffold». Варианты: (a) добавить поле `features = JSONField(default=list)` на модель (миграция!), либо (b) кодировать features внутри `seed_prompt`. **Решение:** добавить поле `features` (чище и соответствует плану).

**Файлы:** `src/studio/models.py`, миграция, `src/studio/management/commands/seed_templates.py`

**Что делать точно:**
1. `models.py`, `StudioTemplate` (строка 146): добавить `features = models.JSONField(default=list, blank=True)`.
2. **Создать миграцию:** `cd src && python manage.py makemigrations studio`, закоммитить.
3. `seed_templates.py`: в список `TEMPLATES` добавить 4 записи (idempotent через `update_or_create` по slug — механизм уже есть):
   - `{'slug': 'marketplace-robokassa', 'name': 'Маркетплейс (Робокасса)', 'stack': 'nextjs', 'features': ['robokassa'], 'is_public': True, 'seed_prompt': '...маркетплейс с каталогом, корзиной и оплатой через Робокассу...', 'order': 5}`
   - `{'slug': 'service-vk-id', 'name': 'Сервис с VK ID', 'features': ['vk_id'], ...}`
   - `{'slug': 'maps-yandex', 'name': 'Карты и геолокация (Яндекс)', 'features': ['yandex_maps'], ...}`
   - `{'slug': 'landing-telegram', 'name': 'Лендинг с Telegram Login', 'features': ['telegram_login'], ...}`
   - Все `seed_prompt` — на русском, описывают конкретное приложение. Без эмодзи.

**Что НЕ делать:** Не удалять существующие 4 шаблона. `features` для старых шаблонов остаётся `[]`.

**Проверка сессии:** `python manage.py migrate && python manage.py seed_templates` → «Created: Маркетплейс (Робокасса)» и др., старые «Updated». Повторный запуск идемпотентен. Тесты зелёные.

---

## Сессия 2.3 — Подключение scaffold по features + GigaChat-модели

**Цель:** Architect/Coder на шаге 1 применяют scaffold-блоки по `features`; добавить GigaChat в каталог и клиент.
**Зависит от:** Сессий 2.1-2.2.
**Флаги:** `STUDIO_V4_RU_STACK`.
**Файлы:** `src/config/settings.py`, `src/studio/models_catalog.py`, `src/studio/agents/base.py`, `src/studio/scaffold.py`, `src/studio/tasks.py`

### Коммит 2.3.1 — GigaChat в models_catalog + клиент в base.py

**Файлы:** `src/config/settings.py`, `src/studio/models_catalog.py`, `src/studio/agents/base.py`

**Что делать точно:**
1. `settings.py`:
   ```python
   GIGACHAT_API_URL = os.getenv('GIGACHAT_API_URL', '')
   GIGACHAT_API_KEY = os.getenv('GIGACHAT_API_KEY', '')
   ```
2. `models_catalog.py`, в `STUDIO_MODELS` добавить две записи:
   ```python
   {'id': 'gigachat-pro',  'label': 'GigaChat Pro',  'category': 'smart', 'tier': 'smart', 'description': 'Сбер GigaChat Pro'},
   {'id': 'gigachat-lite', 'label': 'GigaChat Lite', 'category': 'fast',  'tier': 'fast',  'description': 'Быстрый GigaChat'},
   ```
   (`MODEL_TIER` пересоберётся автоматически — оно строится из `STUDIO_MODELS`.)
3. `base.py`, `get_client()` сейчас один клиент. Нужен выбор клиента по `model_id`. Поскольку `get_client()` не знает модель, добавить хелпер и использовать его в `run_prompt`:
   ```python
   _gigachat_client = None
   def get_client_for(model_id: str):
       if (getattr(settings, 'STUDIO_V4_RU_STACK', False)
               and isinstance(model_id, str) and model_id.startswith('gigachat-')
               and settings.GIGACHAT_API_URL):
           global _gigachat_client
           if _gigachat_client is None:
               _gigachat_client = OpenAI(
                   api_key=settings.GIGACHAT_API_KEY,
                   base_url=settings.GIGACHAT_API_URL, timeout=360.0,
               )
           return _gigachat_client
       return get_client()
   ```
   В `run_prompt` заменить `self.client.chat.completions.create(...)` на использование `get_client_for(model_id)`:
   ```python
   client = get_client_for(model_id)
   stream = client.chat.completions.create(...)  # или _open_stream(client) если Сессия 0.3 уже влита
   ```
   **Согласование с Сессией 0.3 (fallback):** если 0.3 уже добавила `_open_stream(self.client)`, заменить на `_open_stream(client)` где `client = get_client_for(model_id)`, и в fallback оставить `get_fallback_client()`.

**Что НЕ делать:** Не менять `__init__`/`self.client` (оставить как fallback для vision и обратной совместимости). При выключенном `STUDIO_V4_RU_STACK` или пустом `GIGACHAT_API_URL` — всегда основной клиент.

### Коммит 2.3.2 — применение scaffold-блоков по features на шаге 1

**Файл:** `src/studio/scaffold.py`, `src/studio/tasks.py`

**Что делать точно:**
- `scaffold.py`: добавить диспетчер:
  ```python
  def scaffold_for_features(stack: str, features: list) -> dict:
      out = {}
      fmap = {
          'robokassa': scaffold_robokassa, 'vk_id': scaffold_vk_id,
          'yandex_maps': scaffold_yandex_maps, 'telegram_login': scaffold_telegram_login,
      }
      for f in (features or []):
          fn = fmap.get(f)
          if fn:
              out.update(fn(stack))
      return out
  ```
- `tasks.py`: найти место применения `scaffold_files` на шаге 1 (Grep `scaffold_files` в `tasks.py`). Рядом, при `settings.STUDIO_V4_RU_STACK`, применить и feature-scaffold. Features берём из `project.interview_data.get('features', [])` (их кладёт шаблон при создании проекта):
  ```python
  if settings.STUDIO_V4_RU_STACK:
      from .scaffold import scaffold_for_features
      feats = (project.interview_data or {}).get('features', [])
      extra = scaffold_for_features(project.target_stack, feats)
      # записать extra в файлы проекта так же, как scaffold_files
  ```

**Что НЕ делать:** Не перезаписывать уже сгенерированные агентом файлы (scaffold идёт на шаге 1, до агента). При выключенном флаге — ничего не применять.

**Проверка сессии:** Проект из шаблона «Маркетплейс (Робокасса)» с `STUDIO_V4_RU_STACK=1` → на шаге 1 в файлах появляются `app/api/payment/create/route.ts` и др. `gigachat-pro` выбирается как модель агента и уходит на `GIGACHAT_API_URL` (проверить лог `calling model gigachat-pro`). Тесты зелёные.

---

## Сессия 2.4 — Architect: RU-локаль + деплой на российский хостинг

**Цель:** RU-правила в DESIGN.md; поле deploy_target; задачи деплоя на Timeweb/Selectel.
**Флаги:** `STUDIO_V4_RU_STACK`.
**Файлы:** `src/config/settings.py`, `src/studio/models.py`, миграция, `src/studio/agents/architect.py`, `src/studio/tasks.py`, `src/studio/views/pipeline.py`

### Коммит 2.4.1 — deploy_target + задачи деплоя + DeployView target

**Файлы:** `src/config/settings.py`, `src/studio/models.py`, миграция, `src/studio/tasks.py`, `src/studio/views/pipeline.py`

**Что делать точно:**
1. `settings.py`:
   ```python
   TIMEWEB_API_TOKEN = os.getenv('TIMEWEB_API_TOKEN', '')
   SELECTEL_ACCOUNT_ID = os.getenv('SELECTEL_ACCOUNT_ID', '')
   SELECTEL_API_KEY = os.getenv('SELECTEL_API_KEY', '')
   ```
2. `models.py`, `StudioProject` (строка 6): добавить
   ```python
   deploy_target = models.CharField(max_length=20, default='vercel')
   ```
   **Создать миграцию.**
3. `tasks.py`: добавить `deploy_to_timeweb(project_id)` и `deploy_to_selectel(project_id)` Celery-задачи по образцу `deploy_to_vercel` (строка 1052) — те же декораторы (`@shared_task(bind=True, ...)`), та же структура (взять файлы проекта, отправить в API хостинга, записать URL в `project.vercel_deployment_url` или новое поле, публиковать SSE). Если API-токены пусты — публиковать понятную ошибку, не падать.
4. `views/pipeline.py`, `DeployView.post` (строки 204-211): принять `target`:
   ```python
   target = request.data.get('target', project.deploy_target or 'vercel')
   from ..tasks import deploy_to_vercel, deploy_to_timeweb, deploy_to_selectel
   task = {'vercel': deploy_to_vercel, 'timeweb': deploy_to_timeweb,
           'selectel': deploy_to_selectel}.get(target, deploy_to_vercel)
   task.delay(str(project.id))
   ```
   `github` — если в проекте уже есть github-деплой через отдельный механизм, оставить как есть; иначе обрабатывать как vercel-default.

### Коммит 2.4.2 — Architect RU-локаль в DESIGN.md

**Файл:** `src/studio/agents/architect.py`

**Что делать точно:**
- В `ArchitectAgent.run` (строка 124), при сборке DESIGN.md (строки 138-144, ветка V3). Определить RU-рынок:
  ```python
  idata = self.project.interview_data or {}
  market = idata.get('market')
  if market is None:
      # авто-детект: кириллица в описании → ru
      if re.search(r'[А-Яа-яЁё]', description or ''):
          market = 'ru'
  is_ru = market == 'ru' or stack == 'tma'
  ```
  (`re` уже импортирован в architect.py.)
- При `_global_settings.STUDIO_V4_RU_STACK and is_ru` — подмешать в контекст DESIGN-промпта RU-правила:
  ```python
  ru_rules = (
      "\n\nRU-MARKET RULES (обязательно):\n"
      "- Даты в формате ДД.ММ.ГГГГ.\n"
      "- Телефоны в формате +7-XXX-XXX-XX-XX.\n"
      "- Валюта — рубли (₽), суммы как '1 990 ₽'.\n"
      "- Тексты интерфейса на русском.\n"
  )
  ```
  Добавить `ru_rules` к строке `context + f"\n\nPROJECT.md:\n{project_md}"` при вызове `run_prompt` для design (строка 140-143).

**Что НЕ делать:** Не менять язык PROJECT.md/COMMITS.md (они и так на русском по промпту). Не трогать `_parse_plan`. При выключенном флаге — `ru_rules` не добавляется.

**Проверка сессии:** Миграция применяется. Проект с русским описанием и `STUDIO_V4_RU_STACK=1` → DESIGN.md содержит правила формата дат/валюты. `DeployView` с `{target:'timeweb'}` запускает `deploy_to_timeweb`. Тесты зелёные.

---

# ФАЗА 3 — Студия Telegram Mini App

Цель: генерировать, превьюить и деплоить реальные TMA с российскими платежами.

---

## Сессия 3.1 — TMA target stack: модель, каталог, миграция

**Цель:** Ввести `tma` как target_stack.
**Флаги:** `STUDIO_V4_TMA` (default off).
**Файлы:** `src/config/settings.py`, `src/studio/models.py`, миграция, `src/studio/models_catalog.py`

### Коммит 3.1.1 — tma в STACK_CHOICES + STUDIO_TMA_BOT_TOKEN + миграция

**Файлы:** `src/config/settings.py`, `src/studio/models.py`, миграция

**Что делать точно:**
1. `settings.py`:
   ```python
   STUDIO_V4_TMA = os.getenv('STUDIO_V4_TMA', '0') == '1'
   STUDIO_TMA_BOT_TOKEN = os.getenv('STUDIO_TMA_BOT_TOKEN', '')
   ```
2. `models.py`, `StudioProject.STACK_CHOICES` (строки 19-21) и `target_stack` (строка 33): добавить `('tma', 'Telegram Mini App')` в `STACK_CHOICES`. Также в `StudioTemplate.STACK_CHOICES` (строки 147-149) добавить тот же вариант.
3. **Создать миграцию** (изменение `choices` требует миграции для консистентности): `cd src && python manage.py makemigrations studio`, закоммитить.

**Что НЕ делать:** Не менять `default='nextjs'`. Не добавлять TMA-логику в этом коммите — только enum.

**Проверка сессии:** Можно создать `StudioProject(target_stack='tma')` без ошибки валидации. Миграция применяется. Тесты зелёные.

---

## Сессия 3.2 — TMA scaffold: фундамент + Telegram Payments (один файл scaffold.py)

**Цель:** `scaffold_tma()` (каркас Telegram Mini App) и `scaffold_tma_payments()` (оплата). Оба правят `scaffold.py` в одном стиле, payments опирается на обёртку из фундамента — объединены в одну сессию (два коммита).
**Зависит от:** Сессии 3.1.
**Флаги:** `STUDIO_V4_TMA`.
**Файлы:** `src/studio/scaffold.py`

### Коммит 3.2.1 — scaffold_tma

**Файл:** `src/studio/scaffold.py`

**Что делать точно (каждый — production-ready, без TODO, без эмодзи):**
- `scaffold_tma() -> dict` возвращает:
  - `index.html` — с `<script src="https://telegram.org/js/telegram-web-app.js"></script>` в `<head>`, монтирование Vite-приложения.
  - `src/lib/telegram.ts` — TS-обёртка: `const tg = (window as any).Telegram?.WebApp;` и экспорты `ready()`, `expand()`, `showMainButton(text: string, cb: () => void)`, `hideMainButton()`, `showBackButton(cb: () => void)`, `hideBackButton()`, `haptic(type: 'light'|'medium'|'heavy'|'success'|'error')`, `getUser()` (читает `tg.initDataUnsafe?.user`). Каждая функция безопасна при отсутствии `tg` (no-op).
  - `src/lib/theme.ts` — функция `applyTelegramTheme()`: читает `tg.themeParams` и проставляет CSS-переменные на `document.documentElement.style`: `--tg-bg` (`bg_color`), `--tg-text` (`text_color`), `--tg-button` (`button_color`), `--tg-button-text` (`button_text_color`), с дефолтами.
  - `api/validate-init-data.ts` — серверная функция HMAC-SHA256 валидации `initData`: secret = `HMAC_SHA256("WebAppData", bot_token)`, проверка `hash` по отсортированным парам. **Обязательна**, не опциональна. Берёт токен из `process.env.TELEGRAM_BOT_TOKEN`.
  - `vite.config.ts` — с `server: { host: true, port: 3000, hmr: false }` (как остальные Vite-стеки).
  - `.env.example` — фрагмент с `TELEGRAM_BOT_TOKEN=`.

**Что НЕ делать:** Не использовать React-router для навигации (TMA-правило — через BackButton). Не вызывать функцию автоматически — её подключает шаг 1 для `target_stack == 'tma'` (Сессия 3.4/диспетчер).

**Проверка коммита:** `scaffold_tma()` в shell → словарь с указанными ключами, валидный TS/HTML.

### Коммит 3.2.2 — scaffold_tma_payments

**Файл:** `src/studio/scaffold.py`

**Что делать точно:**
- `scaffold_tma_payments() -> dict`:
  - `api/create-invoice.ts` — серверный route: вызывает Bot API `createInvoiceLink` (`https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/createInvoiceLink`) с `provider_token = process.env.TELEGRAM_PAYMENT_TOKEN` (Робокасса provider token для Telegram Payments), `currency: 'RUB'`, `prices`. Возвращает invoice URL.
  - `src/lib/useTelegramPayment.ts` — хук `useTelegramPayment(amount: number, description: string)`: POST на `/api/create-invoice` → `WebApp.openInvoice(url, callback)`. Использует обёртку из `src/lib/telegram.ts` (Сессия 3.2), не сырой `window.Telegram`.
  - `.env.example` фрагмент: `TELEGRAM_BOT_TOKEN=`, `TELEGRAM_PAYMENT_TOKEN=`.

**Что НЕ делать:** Не обращаться к `window.Telegram` напрямую — только через `src/lib/telegram.ts`. Без эмодзи, без TODO.

**Проверка сессии:** `scaffold_tma_payments()` → словарь с 3 ключами, валидный код. Тесты зелёные.

---

## Сессия 3.3 — TMA-промпты для Architect, Coder, Guardian

**Цель:** При `target_stack == 'tma'` агенты следуют правилам Telegram Mini App.
**Зависит от:** Сессий 3.1-3.2.
**Флаги:** `STUDIO_V4_TMA`.
**Файлы:** `src/studio/agents/tma_prompts.py` (новый), `src/studio/agents/architect.py`, `src/studio/agents/coder.py`, `src/studio/agents/guardian.py`

### Коммит 3.3.1 — TMA-секции в системных промптах трёх агентов

**Файлы:** `src/studio/agents/architect.py`, `src/studio/agents/coder.py`, `src/studio/agents/guardian.py`

**Что делать точно:** Везде использовать одну общую константу TMA-правил, объявленную в каждом файле (или импортируемую из общего места — например `src/studio/agents/tma_prompts.py`, что чище). Предлагается создать `src/studio/agents/tma_prompts.py`:
```python
TMA_RULES = (
    "\n\nTELEGRAM MINI APP RULES (обязательно):\n"
    "- Навигация через Telegram BackButton, НЕ через router-хедер/браузерные кнопки.\n"
    "- Главное действие экрана — через Telegram MainButton.\n"
    "- Тема берётся из tg.themeParams (CSS-переменные --tg-*), не хардкодить цвета.\n"
    "- В точке входа App обязателен вызов tg.ready() и tg.expand().\n"
    "- Любой доступ к Telegram — ТОЛЬКО через src/lib/telegram.ts, не через window.Telegram напрямую.\n"
    "- initData ОБЯЗАТЕЛЬНО валидируется на сервере (api/validate-init-data.ts).\n"
)
TMA_LIB_SIGNATURE = (
    "Доступная обёртка src/lib/telegram.ts: ready(), expand(), "
    "showMainButton(text, cb), hideMainButton(), showBackButton(cb), "
    "hideBackButton(), haptic(type), getUser()."
)
```
- **architect.py:** в `run`, при `target_stack == 'tma'` (стек приходит параметром `stack`), добавить `TMA_RULES` к системному промпту COMMITS (`system_commits`). Прокинуть после выбора `system_commits` (строки 146-149): `if settings.STUDIO_V4_TMA and stack == 'tma': system_commits = system_commits + TMA_RULES`.
- **coder.py:** в `_generate_one_file` и `_get_manifest`, при `self.project.target_stack == 'tma'` и флаге, добавить `TMA_RULES + "\n" + TMA_LIB_SIGNATURE` к системному промпту (`system`). (Прибавлять к строке `system`, не к user.)
- **guardian.py:** в `GuardianAgent.run`, при `self.project.target_stack == 'tma'` и флаге, добавить к `system` чек-лист: «initData валидируется в серверных роутах? Навигация через BackButton/MainButton? Доступ к Telegram через src/lib/telegram.ts?».

**Что НЕ делать:** Импорт `settings` в каждом файле проверить (в architect.py это `_global_settings`, в coder.py/guardian.py — `settings`). При выключенном флаге или не-tma стеке промпты прежние.

**Проверка сессии:** Проект `target_stack='tma'`, `STUDIO_V4_TMA=1` → COMMITS.md упоминает MainButton/BackButton; coder-промпт (залогировать) содержит TMA_RULES. Тесты зелёные.

---

## Сессия 3.4 — TMA scaffold-диспетчер + деплой/публикация

**Цель:** Применять TMA-scaffold на шаге 1; задача публикации с инструкциями BotFather.
**Зависит от:** Сессий 3.1-3.3, 2.4 (deploy_to_timeweb).
**Флаги:** `STUDIO_V4_TMA`.
**Файлы:** `src/studio/tasks.py`, `src/studio/scaffold.py`, `src/studio/views/pipeline.py`

### Коммит 3.4.1 — применение scaffold_tma на шаге 1

**Файлы:** `src/studio/scaffold.py`, `src/studio/tasks.py`

**Что делать точно:**
- `scaffold.py`: расширить диспетчер `scaffold_for_features` (Сессия 2.3) или добавить отдельную ветку в применении шага 1: при `stack == 'tma'` всегда применять `scaffold_tma()`, плюс `scaffold_tma_payments()` если в `features` есть `'payments'`.
- `tasks.py`: в месте применения scaffold на шаге 1 (рядом с `scaffold_files`/`scaffold_for_features` из Сессии 2.3) добавить:
  ```python
  if settings.STUDIO_V4_TMA and project.target_stack == 'tma':
      from .scaffold import scaffold_tma, scaffold_tma_payments
      tma_files = scaffold_tma()
      if 'payments' in (project.interview_data or {}).get('features', []):
          tma_files.update(scaffold_tma_payments())
      # записать tma_files так же, как scaffold_files
  ```

### Коммит 3.4.2 — tma_publish + DeployView для tma

**Файлы:** `src/studio/tasks.py`, `src/studio/views/pipeline.py`

**Что делать точно:**
- `tasks.py`: Celery-задача `tma_publish(project_id, bot_token=None)`:
  - Сначала задеплоить (вызвать `deploy_to_timeweb(project_id)` синхронно через `.apply()` или дождаться URL; проще — `tma_publish` запускается ПОСЛЕ успешного деплоя и читает `project.vercel_deployment_url`/новое поле).
  - Сформировать текстовые BotFather-инструкции (plain text, на русском): шаги `/newapp`, указать URL приложения, `/setpayments` для подключения Робокасса provider_token (`TELEGRAM_PAYMENT_TOKEN`).
  - Если `bot_token` (или `STUDIO_TMA_BOT_TOKEN`) задан — авто-регистрация через Bot API: `setChatMenuButton` (с web_app URL) и при необходимости `setWebhook`. Ошибки логировать, не падать.
  - Опубликовать SSE-событие с результатом.
- `views/pipeline.py`, `DeployView.post`: при `project.target_stack == 'tma'` (или `target == 'tma'`):
  ```python
  if project.target_stack == 'tma':
      from ..tasks import tma_publish
      tma_publish.delay(str(project.id), request.data.get('bot_token'))
      return Response({'status': 'publishing', 'target': 'tma'}, status=202)
  ```
  Ответ должен в итоге (через SSE или последующий GET) содержать `{url, botfather_instructions, payment_instructions}`.

**Что НЕ делать:** Не блокировать HTTP-запрос на время деплоя — деплой в Celery, результат через SSE/последующий poll. При выключенном `STUDIO_V4_TMA` — поведение `DeployView` прежнее.

**Проверка сессии:** Проект tma с `STUDIO_V4_TMA=1`: шаг 1 содержит `src/lib/telegram.ts` и `api/validate-init-data.ts`. `DeployView` для tma запускает `tma_publish`; в SSE появляются инструкции BotFather. Тесты зелёные.

---

## Сессия 3.5 — TMA mock-SDK в превью

**Цель:** В превью TMA-проекта инжектить мок `window.Telegram.WebApp` + баннер-эмуляция.
**Зависит от:** Сессии 3.1 (target_stack='tma').
**Флаги:** управляется наличием `target_stack === 'tma'`; доп. фронт-флаг не нужен.
**Примечание по FE/BE:** трогает frontend (проброс props + баннер) и backend (инъекция mock-SDK в отдаваемый HTML). Объединено намеренно — backend-часть это вставка строки `<script>` в HTML (по образцу Сессии 0.5), а не Django-логика; мок и баннер бессмысленны порознь.
**Файлы:** `frontend/components/studio/PreviewPanel.tsx`, `frontend/components/studio/StudioLayout.tsx`, `src/studio/views/pipeline.py`

### Коммит 3.5.1 — проброс target_stack + mock Telegram WebApp + баннер

**Файлы:** `frontend/components/studio/StudioLayout.tsx`, `frontend/components/studio/PreviewPanel.tsx`, `src/studio/views/pipeline.py`

**Контекст (реальность):** `target_stack` НЕ прокинут в `PreviewPanel`. iframe-контент TMA отдаётся через `PreviewProxyView`. Инъекцию mock-SDK надёжнее делать на backend (в static-ветке `PreviewProxyView`, как error-hook в Сессии 0.5), потому что скрипт должен исполниться ВНУТРИ iframe-документа до кода приложения.

**Что делать точно:**

1. `StudioLayout.tsx`: прокинуть `targetStack={project.target_stack}` в `<PreviewPanel ...>` (строки 490, 516).

2. `PreviewPanel.tsx`: добавить `targetStack?: string` в `PreviewPanelProps` (строки 15-21). Когда `targetStack === 'tma'` — рендерить баннер над iframe:
   `«Превью — эмуляция Telegram. Реальная тема и оплата доступны после деплоя.»` (Lucide-иконка Info, без эмодзи).

3. `src/studio/views/pipeline.py`, `PreviewProxyView.get`, static-ветка отдачи HTML (строки 395-403): при `project.target_stack == 'tma'` инжектить mock-SDK ПЕРЕД остальными скриптами (в `<head>`, до `telegram-web-app.js` если он есть — мок должен победить, поэтому проще: вставить мок и НЕ давать грузиться реальному, либо мок ставит `window.Telegram` только если его нет). Скрипт-строка:
   ```python
   tma_mock = (
       '<script>(function(){'
       'if(window.Telegram&&window.Telegram.WebApp)return;'
       'var noop=function(){};'
       'var mb={text:"",show:noop,hide:noop,setText:function(t){this.text=t;},onClick:noop,offClick:noop};'
       'var bb={show:noop,hide:noop,onClick:noop,offClick:noop};'
       'window.Telegram={WebApp:{'
       'initData:"",initDataUnsafe:{user:{id:1,first_name:"Demo",username:"demo"}},'
       'themeParams:{bg_color:"#ffffff",text_color:"#000000",button_color:"#3390ec",button_text_color:"#ffffff"},'
       'colorScheme:"light",ready:noop,expand:noop,close:noop,'
       'MainButton:mb,BackButton:bb,'
       'HapticFeedback:{impactOccurred:noop,notificationOccurred:noop,selectionChanged:noop},'
       'openInvoice:function(url,cb){if(cb)cb("paid");}'
       '}};'
       '})();</script>'
   )
   ```
   Вставить вместе с `<base>`/error-hook в том же `<head>`-replace. Условие: только для `target_stack == 'tma'`.

**Что НЕ делать:** Не инжектить mock в не-TMA проекты. Не пытаться мокать реальную оплату всерьёз (`openInvoice` сразу зовёт callback с `"paid"` — для демо). Не ломать существующую отдачу HTML.

**Проверка сессии:** TMA-проект в превью: приложение запускается без `window.Telegram is undefined`, кнопки MainButton/BackButton не падают, виден баннер-эмуляция. Не-TMA проекты не затронуты.

---

## Рекомендуемое расписание по сессиям

| Сессия | Коммиты | Название | Примерное время | Приоритет | Блокирует |
|--------|---------|----------|-----------------|-----------|-----------|
| 0.1 | 3 | Учёт токенов + реальный биллинг + динамич. оценка | 1.5 дня | Критический | — |
| 0.2 | 1 | Кэш контекста COMMITS.md | 0.5 дня | Высокий | — |
| 0.3 | 1 | Fallback-провайдер | 1 день | Высокий | 2.3 (общий _open_stream) |
| 0.4 | 3 | Autofix: поля + дедуп + лимит + сброс (миграция) | 1.5 дня | Критический | — |
| 0.5 | 1 | Авто-захват ошибок iframe (FE+BE) | 0.5 дня | Средний | — |
| 1.1 | 1 | Backend: on_delta в run_prompt/continuation | 0.5 дня | Высокий | 1.2 |
| 1.2 | 1 | Backend: публикация file_delta из coder | 1 день | Высокий | 1.3 |
| 1.3 | 1 | Frontend: live-стриминг в CodeViewer | 1.5 дня | Высокий | — |
| 1.4 | 1 | Guardian видит весь проект (symbol map) | 1 день | Средний | — |
| 1.5 | 1 | Мягкий перезапуск превью (FE+BE) | 0.5 дня | Средний | — |
| 2.1 | 2 | RU-scaffold: Робокасса, VK ID, Карты, Telegram Login | 2.5 дня | Высокий | 2.2, 2.3 |
| 2.2 | 1 | RU-шаблоны + поле features (миграция) | 0.5 дня | Высокий | 2.3 |
| 2.3 | 2 | Подключение scaffold по features + GigaChat | 1.5 дня | Высокий | 3.4 |
| 2.4 | 2 | Architect RU-локаль + деплой РФ-хостинг (миграция) | 1.5 дня | Средний | 3.4 |
| 3.1 | 1 | TMA target stack (миграция) | 0.5 дня | Высокий | 3.2-3.5 |
| 3.2 | 2 | TMA scaffold: фундамент + Telegram Payments | 2.5 дня | Критический (TMA) | 3.3, 3.4, 3.5 |
| 3.3 | 1 | TMA-промпты (architect/coder/guardian) | 1 день | Высокий | — |
| 3.4 | 2 | TMA scaffold-диспетчер + деплой/публикация | 1.5 дня | Высокий | — |
| 3.5 | 1 | TMA mock-SDK в превью (FE+BE) | 1 день | Средний | — |

Итого: **18 сессий, 28 коммитов.**

**Порядок исполнения:** строго по фазам (0 → 1 → 2 → 3). Внутри фазы — по возрастанию номера, соблюдая колонку «Блокирует». Сессии без зависимостей внутри одной фазы можно вести параллельно разными контекстами Sonnet. Сессии 0.3 (fallback) и 2.3 (GigaChat-клиент) обе трогают `run_prompt`/`_open_stream` в `base.py` — если идут параллельно, мерджить аккуратно (инструкция Коммита 2.3.1 учитывает наличие 0.3).

---

# СТАТУС РЕАЛИЗАЦИИ — 100% ЗАВЕРШЕНО (2026-06-24)

Все 18 сессий / 28 коммитов реализованы в коде. Флаги по умолчанию `=0` — включаются в `.env` по мере тестирования и готовности к прод-трафику. Ниже — карта реального состояния для следующего ИИ-ассистента.

## Что реализовано и где лежит

### Агенты (`src/studio/agents/`)

**`base.py`** — фундамент всех агентов:
- Учёт токенов: `last_prompt_tokens`, `last_completion_tokens`, `last_total_tokens` — накапливаются по раундам `run_prompt_with_continuation`.
- Колбэк стриминга: `on_delta=None` в `run_prompt` и `run_prompt_with_continuation` — вызывается на каждый чанк.
- Fallback-провайдер: `get_fallback_client()` — при 5xx от основного провайдера один ретрай на `LAOZHANG_API_URL_FALLBACK`.
- GigaChat: `get_gigachat_client()` — отдельный OpenAI-совместимый клиент при `model_id.startswith('gigachat')` и `STUDIO_V4_RU_STACK=1`.
- Выбор клиента: `get_client_for(model_id)` — автоматически роутит на GigaChat или основной клиент.

**`coder.py`** — генерация файлов проекта:
- Кэш COMMITS.md: `_commits_summary()` — сжатое резюме заголовков шагов вместо полного файла при `STUDIO_V4_COMMITS_CACHE=1`.
- Стриминг: при `STUDIO_V4_STREAMING=1` в `_generate_one_file` буферизуются чанки (80 символов или 200ms) и публикуются SSE-события `file_delta` / `file_delta_done` через `publish_event`.

**`guardian.py`** — ревью шага:
- Symbol map: `_build_symbol_map(all_files)` — карта экспортов всего проекта; при `STUDIO_V4_GUARDIAN_CONTEXT=1` Guardian видит все экспорты и контент импортируемых файлов, а не только изменённые.
- TMA-чеклист: при `STUDIO_V4_TMA=1` и `target_stack='tma'` в промпт добавляется проверка initData/BackButton/MainButton/lib/telegram.ts.

**`architect.py`** — создание DESIGN.md и COMMITS.md:
- RU-локаль: при `STUDIO_V4_RU_STACK=1` и кириллице в описании добавляет правила дат/телефонов/валюты в DESIGN.md.
- TMA: при `STUDIO_V4_TMA=1` и `target_stack='tma'` добавляет `TMA_RULES` в системный промпт COMMITS.

**`tma_prompts.py`** — константы `TMA_RULES` и `TMA_LIB_SIGNATURE`, импортируются всеми тремя агентами.

### Модели (`src/studio/models.py`)

**`StudioProject`**:
- `deploy_target` — `CharField` с выбором `none/vercel/timeweb/selectel/tma`.
- `target_stack` — включает вариант `tma` (Telegram Mini App) в `STACK_CHOICES`.

**`StudioPipelineState`**:
- `seen_error_hashes` — `JSONField(default=list)`, хранит SHA256-хэши последних 50 ошибок autofix для дедупликации.
- `autofix_count` — `IntegerField(default=0)`, счётчик автоисправлений в текущей серии; сбрасывается при resume/skip/guardian-pass.

### Scaffold (`src/studio/scaffold.py`)

Детерминированные файловые блоки (возвращают `dict[str, str]`):
- `scaffold_files(stack, design_md='')` — базовый UI-каркас (react/nextjs/vite/html).
- `scaffold_robokassa()` — серверный route + ResultURL-хук + клиентский хук `usePayment`. MD5-подпись Robokassa.
- `scaffold_vk_id()` — OAuth-кнопка VK ID + callback route.
- `scaffold_yandex_maps()` — React-компонент `YandexMap` с динамической загрузкой JS API 2.1.
- `scaffold_telegram_login()` — Telegram Login Widget + серверная HMAC-SHA256 валидация.
- `scaffold_tma()` — полный каркас Telegram Mini App: `src/lib/telegram.ts` (обёртка WebApp API), `src/lib/theme.ts` (CSS-переменные из themeParams), `api/validate-init-data.ts` (HMAC-SHA256 валидация initData), `vite.config.ts`, `index.html`.
- `scaffold_tma_payments()` — Telegram Payments: `api/create-invoice.ts` (Bot API createInvoiceLink), `src/lib/useTelegramPayment.ts`.
- `scaffold_for_features(stack, features)` — диспетчер по списку ключей (`robokassa/vk_id/yandex_maps/telegram_login/tma_payments`).

### Задачи (`src/studio/tasks.py`)

- `deploy_to_timeweb(project_id)` — деплой статики на Timeweb Cloud через API.
- `deploy_to_selectel(project_id)` — деплой на Selectel Object Storage.
- `tma_publish(project_id, bot_token=None)` — деплой TMA + инструкции BotFather + авто-setChatMenuButton если задан bot_token.
- Autofix-сброс: при `guardian verdict == 'pass'` и `STUDIO_V4_AUTOFIX=1` — обнуляет `autofix_count` и `seen_error_hashes`.
- `preview_restart` событие публикуется после успешного коммита шага.

### Views (`src/studio/views/pipeline.py`)

- `ConsoleErrorView.post` — при `STUDIO_V4_AUTOFIX=1`: SHA256-дедуп ошибок, лимит (`STUDIO_MAX_AUTOFIX`, default 3), статус `paused_on_loop` при превышении.
- `DeployView.post` — роутинг по `target`: vercel / timeweb / selectel / tma → соответствующая Celery-задача.
- `PreviewProxyView.get` (static-ветка): инжектирует в `<head>` три блока: `<base href>` + `err_hook` (захват `window.onerror/console.error` → postMessage) + `tma_mock` (мок `window.Telegram.WebApp` для TMA-проектов).

### Frontend (`frontend/components/studio/`)

- `CodeViewer.tsx` — props `streaming?: boolean` и `streamContent?: string`: при `streaming=true` показывает накапливаемый текст вместо сохранённого файла, редактирование заблокировано.
- `StudioLayout.tsx` — слушает SSE `file_delta` / `file_delta_done`: накапливает `streamingContent` по `streamingPath`; передаёт в `CodeViewer`. Реагирует на `preview_restart` + дебаунс 600мс для reload iframe.
- `PreviewPanel.tsx` — при `targetStack === 'tma'` показывает баннер-эмуляция. Получает `targetStack` из `StudioLayout`.

### Флаги в `src/config/settings.py`

| Флаг | Что включает | По умолчанию |
|------|-------------|--------------|
| `STUDIO_V4_TOKEN_BILLING` | Биллинг по реальным токенам вместо фиксированного AGENT_BUDGET | 0 |
| `STUDIO_V4_COMMITS_CACHE` | Сжатое резюме COMMITS.md вместо полного текста | 0 |
| `STUDIO_V4_PROVIDER_FALLBACK` | Retry на fallback-провайдер при 5xx | 0 |
| `STUDIO_V4_AUTOFIX` | Дедуп ошибок + лимит + пауза | 0 |
| `STUDIO_V4_STREAMING` | SSE file_delta из coder, live в CodeViewer | 0 |
| `STUDIO_V4_GUARDIAN_CONTEXT` | Symbol map + импортируемые файлы в Guardian | 0 |
| `STUDIO_V4_RU_STACK` | GigaChat, RU-scaffold, RU-локаль Architect, деплой РФ | 0 |
| `STUDIO_V4_TMA` | TMA stack, scaffold, агентные правила, tma_publish | 0 |

---

## Что можно улучшать дальше (идеи для Studio V5)

Ниже — список открытых слабых мест и возможностей, выявленных при реализации V4. Следующий план должен закрыть хотя бы первые 5.

### Критические (влияют на качество генерации)

1. **Multi-file coherence.** Coder генерирует файлы последовательно, не видя уже сгенерированных на этом же шаге. Guardian проверяет постфактум. Решение: после каждого файла добавлять его в контекст следующего (скользящее окно 2-3 файла).
2. **Plan drift.** Architect создаёт план один раз; если шаг N провалился, план не пересматривается. Нужен «replanner» — лёгкий агент, который после 2 провалов шага переформулирует оставшиеся шаги.
3. **Guardian false positives.** Symbol map (Сессия 1.4) снижает ложные срабатывания, но `pass/fail` без промежуточного `warn` вызывает полный autofix на минорные проблемы (например, неиспользуемый импорт). Нужен трёхуровневый вердикт `pass / warn / fail`.
4. **Token limit на большие проекты.** При >30 файлах контекст Guardian переполняется. Нужен chunked review: Guardian проверяет изменённые файлы + только зависимые, не все.
5. **Нет тестов в пайплайне.** После генерации никто не запускает тесты. Нужен TestRunnerAgent: запустить `npm test` в sandbox → передать вывод Guardian как `build_logs`.

### Важные (UX/продукт)

6. **Нет диффа между шагами.** Пользователь видит только текущие файлы, не что изменилось на шаге. Нужен diff-вид в CodeViewer (старое / новое по шагу).
7. **Нет rollback.** Если шаг сломал проект, нельзя откатиться к предыдущей версии. `StudioVersion` модель есть, UI rollback — нет.
8. **Превью только static.** Sandbox-режим (реальный Docker, HMR) медленный и дорогой. Нужен лёгкий режим: Vite dev server в контейнере с проксированием через nginx, без полного Docker-in-Docker.
9. **Нет импорта существующего кода.** Пользователь не может загрузить свой репозиторий и попросить доработать. Нужен import flow: zip/git URL → распаковка в `StudioProjectFile` → дальше как обычный проект.
10. **Шаблоны не кастомизируются.** При выборе шаблона пользователь видит только `seed_prompt`. Нужен Interview расширенный: вопросы по `features` (какие интеграции нужны), `design` (цвета/шрифты), `deploy` (куда деплоить).

### Технический долг V4

11. **`provider='fal-ai'` — legacy DB-ключ.** В `models_cmd.py` и `images.py` бота фильтры по `provider='fal-ai'` — это устаревший ключ, реальные запросы идут через laozhang/apimart. Нужна data-migration: переименовать в `laozhang` / `apimart` по факту провайдера.
12. **Флаги V4 все `=0`.** Ни один флаг не включён на проде. После тестирования на staging включить поэтапно: сначала `STUDIO_V4_TOKEN_BILLING`, затем `STUDIO_V4_STREAMING`, затем остальные.
13. **`tma_publish` не проверен на реальном боте.** Логика есть, но `setChatMenuButton` требует прав бота и реального `STUDIO_TMA_BOT_TOKEN`. Нужен интеграционный тест.
14. **`deploy_to_timeweb/selectel` — заглушки.** API-вызовы написаны, но `TIMEWEB_API_TOKEN` и `SELECTEL_*` не заданы в проде. Нужна документация для DevOps + тест-деплой.
