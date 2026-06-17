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
        """Per-agent override first, then project-level ai_model, then default."""
        agent_models = getattr(self.project, 'agent_models', {}) or {}
        override = agent_models.get(self.name)
        if override and override in MODEL_TIER:
            return override
        model = getattr(self.project, 'ai_model', None)
        return model if model in MODEL_TIER else DEFAULT_STUDIO_MODEL

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
        brace = raw.find('{')
        bracket = raw.find('[')
        if brace == -1 and bracket == -1:
            logger.warning('agent %s: no JSON found in response (len=%d): %.200s', self.name, len(raw), raw)
            raise ValueError(f'No JSON in model response: {raw[:200]}')
        elif brace == -1:
            start = bracket
        elif bracket == -1:
            start = brace
        else:
            start = min(brace, bracket)
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw, start)
            return obj
        except json.JSONDecodeError as exc:
            logger.warning('agent %s: JSON parse failed (%s), raw len=%d: %.300s',
                           self.name, exc, len(raw), raw[max(0, start - 20):start + 200])
            raise

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
