import json
import logging
import re

from openai import OpenAI
from django.conf import settings

logger = logging.getLogger('studio.agents')

MODEL_FAST = 'deepseek-v3'
MODEL_SMART = 'claude-opus-4-8'

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.LAOZHANG_API_KEY,
            base_url=getattr(settings, 'LAOZHANG_API_URL', 'https://api.laozhang.ai/v1'),
            timeout=90.0,
        )
    return _client


class BaseAgent:
    name = 'base'
    model = MODEL_SMART

    def __init__(self, project):
        self.project = project
        self.client = get_client()

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
        return resp.choices[0].message.content

    def run_json(self, system: str, user: str, model: str = None, max_tokens: int = 8192) -> dict:
        raw = self.run_prompt(system, user, model=model, max_tokens=max_tokens, temperature=0.2)
        raw = raw.strip()
        m = re.search(r'```(?:json)?\s*(.*?)```', raw, re.DOTALL)
        if m:
            raw = m.group(1).strip()
        return json.loads(raw)

    def log(self, text: str, level: str = 'info'):
        from ..events import publish_event
        publish_event(str(self.project.id), {'agent': self.name, 'level': level, 'text': text})
