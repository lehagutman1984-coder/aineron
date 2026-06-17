import json
import logging
import re

from openai import OpenAI
from django.conf import settings
from ..models_catalog import ESCALATION_MAP, MODEL_TIER, DEFAULT_STUDIO_MODEL

logger = logging.getLogger('studio.agents')

# Backward-compat aliases
MODEL_FAST = 'deepseek-v3.2'
MODEL_SMART = 'claude-opus-4-8'


def pick_prompt(ru: str, en: str) -> str:
    """Return EN prompt by default; switch to RU via STUDIO_PROMPT_LANG=ru env var."""
    return en if getattr(settings, 'STUDIO_PROMPT_LANG', 'en') == 'en' else ru

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.LAOZHANG_API_KEY,
            base_url=getattr(settings, 'LAOZHANG_API_URL', 'https://api.laozhang.ai/v1'),
            timeout=360.0,
        )
    return _client


class BaseAgent:
    name = 'base'
    model = DEFAULT_STUDIO_MODEL
    last_finish_reason: str | None = None

    def __init__(self, project):
        self.project = project
        self.client = get_client()

    def resolve_model(self) -> str:
        """Per-agent override → per-agent default → project ai_model → global default."""
        agent_models = getattr(self.project, 'agent_models', {}) or {}
        override = agent_models.get(self.name)
        if override and override in MODEL_TIER:
            return override
        from ..models_catalog import DEFAULT_AGENT_MODELS
        per_agent = DEFAULT_AGENT_MODELS.get(self.name)
        if per_agent and per_agent in MODEL_TIER:
            return per_agent
        model = getattr(self.project, 'ai_model', None)
        if model and model in MODEL_TIER:
            return model
        return DEFAULT_STUDIO_MODEL

    def run_prompt(self, system: str, user: str, model: str = None,
                   max_tokens: int = 8192, temperature: float = 0.7) -> str:
        """
        Call model using streaming so the HTTP connection never idles out,
        even for large outputs (16K+ tokens). Accumulates all chunks and returns
        the full text. Sets self.last_finish_reason for callers to inspect.
        """
        self.last_finish_reason = None
        model_id = model or self.model
        chunks = []

        stream = self.client.chat.completions.create(
            model=model_id,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta and choice.delta.content:
                chunks.append(choice.delta.content)
            if choice.finish_reason:
                self.last_finish_reason = choice.finish_reason

        content = ''.join(chunks)
        if not content:
            logger.warning(
                'agent %s: model %s returned empty content (finish_reason=%s)',
                self.name, model_id, self.last_finish_reason,
            )
            return ''
        if self.last_finish_reason == 'length':
            logger.warning(
                'agent %s: model %s HIT TOKEN LIMIT max_tokens=%d — output TRUNCATED',
                self.name, model_id, max_tokens,
            )
        else:
            logger.debug(
                'agent %s: model %s finished OK (finish_reason=%s, tokens=%d)',
                self.name, model_id, self.last_finish_reason, len(content),
            )
        return content

    def run_json(self, system: str, user: str, model: str = None, max_tokens: int = 8192) -> dict:
        raw = self.run_prompt(system, user, model=model, max_tokens=max_tokens, temperature=0.2)
        if not raw or not raw.strip():
            logger.warning('agent %s: empty response from model %s', self.name, model)
            raise ValueError('Empty response from model')

        # If the model hit the token limit the JSON is incomplete — fail fast so
        # the caller can retry rather than silently returning partial data.
        if self.last_finish_reason == 'length':
            raise ValueError(
                f'Model hit token limit ({max_tokens} tokens) — JSON response is incomplete. '
                'Retry with fewer files or higher max_tokens.'
            )

        raw = raw.strip()
        # Strip markdown code fences
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw, re.DOTALL)
        if m:
            raw = m.group(1).strip()

        # Collect ALL parseable JSON candidates (object or array).
        # Track their size so we can prefer larger / more relevant ones.
        decoder = json.JSONDecoder()
        candidates: list[tuple[int, object]] = []  # (token_length, parsed)
        for marker in ('{', '['):
            pos = 0
            while True:
                idx = raw.find(marker, pos)
                if idx == -1:
                    break
                try:
                    obj, end = decoder.raw_decode(raw, idx)
                    candidates.append((end - idx, obj))
                except json.JSONDecodeError:
                    pass
                pos = idx + 1

        if not candidates:
            logger.warning(
                'agent %s: no valid JSON in response (len=%d): %.300s',
                self.name, len(raw), raw[:300],
            )
            raise ValueError(f'No JSON in model response: {raw[:200]}')

        # Prefer the dict that contains a 'files' key (coder output).
        # Among those, prefer the largest (most complete).
        # Fall back to the largest candidate overall.
        by_size = sorted(candidates, key=lambda x: -x[0])
        for _, obj in by_size:
            if isinstance(obj, dict) and 'files' in obj:
                return obj
        return by_size[0][1]

    def run_vision(self, system: str, image_b64: str, model: str = None, max_tokens: int = 1500) -> str:
        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{image_b64}'}},
                ]},
            ],
            stream=False,
            max_tokens=max_tokens,
            temperature=0.5,
        )
        return resp.choices[0].message.content or ''

    def log(self, text: str, level: str = 'info'):
        from ..events import publish_event
        publish_event(str(self.project.id), {'agent': self.name, 'level': level, 'text': text})
