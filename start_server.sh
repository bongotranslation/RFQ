#!/bin/bash
# Скрипт для запуска FastAPI сервера
# Переменные окружения автоматически загружаются из .env файла

echo "🚀 Запуск FastAPI сервера..."
echo "📁 Переменные окружения загружаются из .env файла"
echo "🌐 Сервер будет доступен на http://127.0.0.1:8082"
echo "📚 API документация: http://127.0.0.1:8082/docs"
echo ""

python -m uvicorn app.main:app --host 127.0.0.1 --port 8082 --reload
docker-compose up -d