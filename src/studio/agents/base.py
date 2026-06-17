import json
import logging
import re

from openai import OpenAI
from django.conf import settings
from ..models_catalog import ESCALATION_MAP, MODEL_TIER, DEFAULT_STUDIO_MODEL

logger = logging.getLogger('studio.agents')

# Backward-compat aliases; removed in commits 5-6 when agents migrate to resolve_model()
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
            timeout=180.0,
        )
    return _client


class BaseAgent:
    name = 'base'
    model = DEFAULT_STUDIO_MODEL

    def __init__(self, project):
        self.project = project
        self.client = get_client()

    def resolve_model(self) -> str:
        """Per-agent override → per-agent default → project ai_model → global default."""
        agent_models = getattr(self.project, 'agent_models', {}) or {}
        # 1. Explicit per-agent override set by user in settings
        override = agent_models.get(self.name)
        if override and override in MODEL_TIER:
            return override
        # 2. Sensible per-agent default (architect→opus, interviewer→deepseek, etc.)
        from ..models_catalog import DEFAULT_AGENT_MODELS
        per_agent = DEFAULT_AGENT_MODELS.get(self.name)
        if per_agent and per_agent in MODEL_TIER:
            return per_agent
        # 3. Project-level fallback chosen by user
        model = getattr(self.project, 'ai_model', None)
        if model and model in MODEL_TIER:
            return model
        return DEFAULT_STUDIO_MODEL

    def run_prompt(self, system: str, user: str, model: str = None,
                   max_tokens: int = 8192, temperature: float = 0.7) -> str:
        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = resp.choices[0].message.content
        if content is None:
            logger.warning('agent %s: model %s returned None content (finish_reason=%s)',
                           self.name, model, resp.choices[0].finish_reason)
            return ''
        return content

    def run_json(self, system: str, user: str, model: str = None, max_tokens: int = 8192) -> dict:
        raw = self.run_prompt(system, user, model=model, max_tokens=max_tokens, temperature=0.2)
        if not raw or not raw.strip():
            logger.warning('agent %s: empty response from model %s', self.name, model)
            raise ValueError('Empty response from model')
        raw = raw.strip()
        # Strip markdown code fences
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw, re.DOTALL)
        if m:
            raw = m.group(1).strip()
        # Find the first JSON value — object '{' or array '[', whichever comes first.
        # raw_decode stops at the end of that value and ignores any trailing text.
        # Scan every '{' then every '[' until one successfully parses as JSON.
        # This avoids false positives like '[...nextauth]' in file-tree text.
        decoder = json.JSONDecoder()
        for marker in ('{', '['):
            pos = 0
            while True:
                idx = raw.find(marker, pos)
                if idx == -1:
                    break
                try:
                    obj, _ = decoder.raw_decode(raw, idx)
                    return obj
                except json.JSONDecodeError:
                    pos = idx + 1
        logger.warning('agent %s: no valid JSON found in response (len=%d): %.300s',
                       self.name, len(raw), raw[:300])
        raise ValueError(f'No JSON in model response: {raw[:200]}')

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
        return resp.choices[0].message.content

    def log(self, text: str, level: str = 'info'):
        from ..events import publish_event
        publish_event(str(self.project.id), {'agent': self.name, 'level': level, 'text': text})
