#!/bin/bash
cd /root/ai
git pull origin main
if [ $? -ne 0 ]; then
    echo "ОШИБКА: git pull не удался (см. вывод выше) — деплой остановлен, код на сервере НЕ обновлён." >&2
    exit 1
fi
bash deploy_fast.sh
