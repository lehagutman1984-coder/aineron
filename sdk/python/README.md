# aineron — Sandboxes SDK

Изолированные microVM для исполнения кода AI-агентов и пользователей.
Из России, оплата в рублях, один API-ключ.

```bash
pip install aineron
export AINERON_API_KEY=ak_...   # ключ со скоупом «sandboxes»: aineron.ru/account/keys/
```

## Быстрый старт

```python
from aineron import Sandbox

with Sandbox(template="python") as sbx:
    result = sbx.exec(code="print(2 + 2)")
    print(result.stdout)          # 4
```

Контекст-менеджер гарантирует остановку песочницы (и биллинга) при выходе из блока.

## Файлы и команды

```python
with Sandbox(template="python", timeout=600) as sbx:
    sbx.write_file("data.csv", open("local.csv", "rb").read())
    sbx.write_file("job.py", "import csv; print(sum(1 for _ in open('data.csv')))")
    result = sbx.exec(command="python3 job.py", timeout=120)
    if result.ok:
        print(result.stdout)
    output = sbx.read_file("data.csv")
```

## Веб-сервер с публичным URL

```python
with Sandbox(template="nodejs", timeout=900) as sbx:
    sbx.write_file("server.js", "require('http').createServer((q,s)=>s.end('hi')).listen(3000)")
    sbx.exec(command="node server.js", background=True)
    print(sbx.url(3000))          # https://3000-<id>.… — открывается из браузера
```

## AI-агент, который пишет и выполняет код

```python
from openai import OpenAI
from aineron import Sandbox

llm = OpenAI(base_url="https://aineron.ru/api/v1", api_key="ak_...")

task = "Посчитай сумму чисел от 1 до 1000 на Python"
code = llm.chat.completions.create(
    model="deepseek-v3",
    messages=[{"role": "user", "content": f"Верни только код без пояснений: {task}"}],
).choices[0].message.content

with Sandbox(template="python") as sbx:
    print(sbx.exec(code=code).stdout)
```

## Тарифы

| Размер | Ресурсы | Цена |
|---|---|---|
| `small` | 1 vCPU / 1 GiB | 0,50 ₽/мин |
| `standard` | 2 vCPU / 2 GiB | 1 ₽/мин |

Округление до минуты вверх; при ошибке запуска средства не списываются.
Документация: https://aineron.ru/api-docs/
