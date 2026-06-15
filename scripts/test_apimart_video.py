"""
Smoke-тест apimart.ai видео API.

Запуск (с реальным ключом в .env):
    ! python scripts/test_apimart_video.py

Проверяет:
1. Авторизацию (APIMART_API_KEY)
2. Формат ответа create — структуру task_id
3. Формат ответа poll — какие поля присутствуют
4. Имя поля с URL видео в result (url / video_url / download_url)
"""

import os
import sys
import time
import json
import http.client
import urllib.parse

# Пробуем загрузить ключ из .env
API_KEY = os.environ.get('APIMART_API_KEY', '')
if not API_KEY:
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    for line in open(env_path, encoding='utf-8'):
        line = line.strip()
        if line.startswith('APIMART_API_KEY='):
            API_KEY = line.split('=', 1)[1].strip()
            break

if not API_KEY:
    print('[ERROR] APIMART_API_KEY не задан в .env')
    sys.exit(1)

BASE_URL = 'api.apimart.ai'
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
}


def post(path, body):
    conn = http.client.HTTPSConnection(BASE_URL, timeout=30)
    conn.request('POST', path, json.dumps(body).encode(), HEADERS)
    resp = conn.getresponse()
    raw = resp.read().decode()
    return resp.status, json.loads(raw)


def get(path):
    conn = http.client.HTTPSConnection(BASE_URL, timeout=30)
    conn.request('GET', path, headers={k: v for k, v in HEADERS.items() if k != 'Content-Type'})
    resp = conn.getresponse()
    raw = resp.read().decode()
    return resp.status, json.loads(raw)


print('=== apimart.ai smoke test ===\n')

# --- Шаг 1: создать задачу с самой дешёвой моделью (kling, 5 сек) ---
print('1. POST /v1/videos/generations (kling-v2-6, 5s)...')
status, pd = post('/v1/videos/generations', {
    'model': 'kling-v2-6',
    'prompt': 'A white cat sits in the sun',
    'duration': 5,
    'aspect_ratio': '16:9',
    'mode': 'std',
})
print(f'   HTTP {status}')
print(f'   Response: {json.dumps(pd, ensure_ascii=False, indent=2)[:600]}')

if status not in (200, 201):
    print('[FAIL] Создание задачи вернуло ошибку. Проверьте ключ и model_id.')
    sys.exit(1)

# --- Парсим task_id ---
data = pd.get('data', pd)
if isinstance(data, list):
    data = data[0]
task_id = data.get('task_id') or data.get('id')
if not task_id:
    print(f'[FAIL] task_id не найден в ответе: {pd}')
    sys.exit(1)

print(f'\n   task_id: {task_id}')

# --- Шаг 2: быстрый poll (3 попытки, только смотрим структуру) ---
print('\n2. GET /v1/tasks/{task_id} — структура poll-ответа:')
for attempt in range(1, 4):
    print(f'   Попытка {attempt}/3 (через 5 сек)...')
    time.sleep(5)
    st, pd = get(f'/v1/tasks/{task_id}')
    print(f'   HTTP {st}')
    # Покажем верхние ключи и статус
    status_obj = pd.get('data') if isinstance(pd.get('data'), dict) else pd
    task_status = status_obj.get('status', '?')
    print(f'   status={task_status}')
    print(f'   top-level keys: {list(pd.keys())}')
    if isinstance(pd.get('data'), dict):
        print(f'   data keys: {list(pd["data"].keys())}')

    if task_status in ('completed', 'succeeded', 'success'):
        print('\n   [OK] Задача завершена!')
        result = status_obj.get('result') or status_obj
        print(f'   result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}')
        # Ищем URL видео
        videos = result.get('videos') or result.get('output') or []
        if isinstance(videos, list) and videos:
            v = videos[0]
            print(f'   video object keys: {list(v.keys()) if isinstance(v, dict) else v}')
            url = (v.get('url') or v.get('video_url') or v.get('download_url')) if isinstance(v, dict) else v
            print(f'   [OK] URL видео: {url}')
        break
    elif task_status in ('failed', 'error'):
        err = status_obj.get('error') or status_obj.get('message', '')
        print(f'\n   [FAIL] Генерация завершилась ошибкой: {err}')
        break
    else:
        print(f'   (ещё выполняется, продолжаем...)')

print('\n=== Smoke test завершён ===')
print('Проверьте вывод выше на соответствие ожидаемым форматам.')
print('Если task_status был submitted/processing — дождитесь и проверьте вручную.')
