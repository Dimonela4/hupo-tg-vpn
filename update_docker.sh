#!/bin/bash

echo "Копируем обнову с гита"
git pull

CONTAINER_NAME="vpn_stars_bot"
LOCAL_PATH="."
CONTAINER_PATH="/app"

echo "📦 Копируем файлы..."
docker cp "$LOCAL_PATH/." "$CONTAINER_NAME:$CONTAINER_PATH"

echo "🔄 Перезапускаем контейнер..."
docker restart "$CONTAINER_NAME"

echo "✅ Готово"
