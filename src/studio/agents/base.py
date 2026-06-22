# ... (остальной код)
# В точке, где вызывается _billing_charge, прокидываем usage с prompt_tokens, если есть
def run_prompt_with_continuation(self, *args, **kwargs):
    # ... (остальной код)
    # После выполнения запроса к LLM
    # usage = chunk.usage or {}
    # tokens = usage.get('completion_tokens', 0) + usage.get('prompt_tokens', 0)
    # И далее передаём usage в _billing_charge
    # _billing_charge(project, agent, step_index, usage=usage)
    pass  # (оставить как напоминание внедрить при необходимости)
# ... (остальной код)
