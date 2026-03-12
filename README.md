# Wiki Path Finder

Сервис, который ищет путь между двумя статьями русской Википедии

Реализация:
- FastAPI backend
- React + Vite frontend
- Telegram-бот на aiogram @wikipathfinder_bot

## Что есть в проекте сейчас

- Двунаправленный поиск (вперёд по ссылкам + назад по backlinks)
- Двухэтапный режим поиска: быстрый эвристический проход и fallback без ограничения ветвления
- Кеш + дедупликация запросов к Wikipedia API в клиенте
- Валидация входных названий статей в API и в боте
- Дашборд метрик (`/dashboard` во фронте) с данными из `reports/metrics.json`

## Быстрый старт (локально)

### 1) Python-часть

```bash
pip install -r requirements.txt
```

Запуск API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Проверка:

```bash
curl http://localhost:8000/health
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

По умолчанию фронт поднимается на `http://localhost:5173`.

### 3) Telegram-бот

Создай `.env` в корне проекта:

```env
BOT_TOKEN=your_telegram_token
```

Запуск:

```bash
python -m telegram_bot.main
```

Команды бота:
- `/start` - начать поиск
- `/info` - краткая справка

## Docker

Поднять API:

```bash
docker compose up --build
```

Поднять вместе с ботом (через profile):

```bash
docker compose --profile bot up --build
```

Остановить:

```bash
docker compose down
```

## API

- `GET /health` - healthcheck
- `POST /api/search` - поиск пути
- `GET /api/metrics` - отдаёт benchmark-метрики из `reports/metrics.json`

Пример запроса:

```json
{
    "start_article": "Москва",
    "end_article": "Россия"
}
```

## Benchmark

Точка входа: `python -m benchmarking`

Пример запуска:

```bash
python -m benchmarking --total-cases 240 --time-limit 40 --concurrency 8 --out-json reports/metrics.json
```

Что на выходе:
- `reports/metrics.json` - сырые и агрегированные метрики

## Переменные окружения

- `BOT_TOKEN` - токен Telegram-бота
- `CORS_ALLOW_ORIGINS` - список origins для API через запятую
- `VITE_API_BASE_URL` - URL backend для frontend (если не задано, используется `http://localhost:8000`)

## Структура

```text
api/            # FastAPI
search/         # алгоритм поиска + Wikipedia API client
telegram_bot/   # aiogram-бот
frontend/       # React/Vite UI
benchmarking/   # генерация кейсов, прогон и сбор метрик
reports/        # артефакты бенчмарка
```

---

По вопросам обращайтесь в Telegram @v1adicke14