# Использование моделей Claude в Aineron API

Этот документ описывает, как вызывать модели Claude через OpenAI-совместимый API вашего проекта.

## Поддерживаемая модель
- claude-3-5-sonnet-20241022 — рекомендуем для кода и сложных задач.

## База API и аутентификация
- База: https://aineron.ru/api/v1 (уточнить в Swagger: https://aineron.ru/api/v1/docs/)
- Эндпоинт: /chat/completions
- Ключ: получите в Личный кабинет → API-ключи. Лимит: 120 запросов/мин на ключ.

Переменные окружения:
- AINERON_API_KEY — ваш API-ключ
- AINERON_BASE_URL — https://aineron.ru/api/v1

## Быстрый старт

### curl
```bash
curl -X POST "$AINERON_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $AINERON_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role":"system","content":"Ты — полезный помощник."},
      {"role":"user","content":"Суммируй преимущества Claude для кода."}
    ],
    "temperature": 0.3
  }'
```

### Python (openai>=1.0, совместимый клиент)
```python
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("AINERON_BASE_URL", "https://aineron.ru/api/v1"),
    api_key=os.getenv("AINERON_API_KEY"),
)

resp = client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[
        {"role": "system", "content": "Ты — полезный помощник."},
        {"role": "user", "content": "Сгенерируй пример кода на Python: функция fib(n)."},
    ],
    temperature=0.2,
)
print(resp.choices[0].message.content)
```

### Python: стриминг ответа
```python
import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("AINERON_BASE_URL", "https://aineron.ru/api/v1"),
    api_key=os.getenv("AINERON_API_KEY"),
)

stream = client.chat.completions.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": "Напиши краткий план рефакторинга Python-проекта."}],
    stream=True,
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta and delta.content:
        print(delta.content, end="", flush=True)
```

## Интеграция с IDE (Continue/Cursor)
Сервис совместим с OpenAI API — можно подключить к Cursor, VS Code, Continue.

Пример для Continue (config.json):
```json
{
  "models": [
    {
      "title": "Claude Sonnet (Aineron)",
      "provider": "openai",
      "model": "claude-3-5-sonnet-20241022",
      "apiBase": "https://aineron.ru/api/v1",
      "apiKey": "${AINERON_API_KEY}"
    }
  ]
}
```
- После сохранения выберите модель в нижнем правом углу Continue.
- Для автодополнения Continue/Cursor используют /chat/completions. Для снижения задержки используйте быструю модель (например, gpt-4o-mini) для автокомплита, а Claude — для сложных задач.

## Советы по использованию
- Выбор модели: для большинства задач по коду подойдут claude-3-5-sonnet-20241022 или gpt-4o.
- Ошибка 429 (rate limit): превышен лимит 120 RPM на ключ. Подождите несколько секунд; при постоянной нагрузке используйте отдельные ключи на разные инструменты.
- Баланс: списание идет в “звёздах”. Баланс виден в Личном кабинете.
- Переключение моделей: в IDE (Continue) можно быстро переключаться между Claude и GPT без правки конфигурации.

## Безопасность
- Храните API-ключ в переменных окружения/секретах.
- Не коммитьте ключ в репозиторий.
- Ограничьте распространение ключа между инструментами (при необходимости создавайте отдельные ключи).

## Диагностика
- Проверить доступность и схемы запросов/ответов: Swagger UI — https://aineron.ru/api/v1/docs/
- В логах клиента включите вывод тела ошибки. Убедитесь, что:
  - правильный base_url,
  - корректный заголовок Authorization: Bearer <KEY>,
  - существует модель claude-3-5-sonnet-20241022,
  - формат messages соответствует OpenAI Chat API.
