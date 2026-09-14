# 04. API и маршруты

## 4.1. Общие правила доступа

| Условие | Поведение |
|---------|-----------|
| `DEBUG=false` + заданы `AUTH_*` | Basic Auth на всех маршрутах, кроме публичных; только через HTTPS |
| Публичные (приложение) | `GET /health`, `GET /ready` |
| Публичные через nginx | `/health`, `/ready` доступны **только** из `MONITORING_CIDR` |
| CSRF | POST: `X-CSRF-Token` + Origin/Referer из `ALLOWED_HOSTS` (без Origin — отказ) |
| `DEBUG=true` | OpenAPI и `/debug`; auth **остаётся**, если заданы `AUTH_*` |
| `ALLOW_INSECURE_DEBUG=true` | Единственный открытый контур; только вместе с `DEBUG=true` |
| OpenAPI | `/api/docs`, `/api/redoc`, `/api/openapi.json` — **только при DEBUG=true** |

## 4.2. Публичные эндпоинты (мониторинг)

| Метод | Путь | Ответ |
|-------|------|-------|
| GET | `/health` | `{"status":"ok"}` — liveness |
| GET | `/ready` | 200 / 503 — булевы флаги готовности (без путей и stacktrace) |

## 4.3. JSON API (требуют auth в production)

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/files` | Список файлов, active/latest IDs, флаг новой версии |
| POST | `/api/session/active-file/{file_id}` | Выбрать активный файл для сессии (+ CSRF) |
| GET | `/api/excel/active` | Скачать активный `.xlsx` |
| POST | `/api/files/upload` | Загрузить новый Excel (multipart `file`, + CSRF) |
| POST | `/api/excel/save-version` | Сохранить версию из редактора (+ CSRF) |

**Ограничения upload:**

- только `.xlsx`;
- `MAX_UPLOAD_BYTES` (по умолчанию 50 МБ) → HTTP 413;
- квоты `MAX_UPLOAD_FILES` / `MAX_UPLOAD_STORAGE_BYTES`;
- ZIP/XLSX validation, лимиты листов/строк, worker timeout;
- `UPLOAD_RATE_LIMIT_PER_MINUTE` → HTTP 429;
- nginx: отдельный rate limit на upload-эндпоинты, `client_max_body_size 52m`.

## 4.4. HTML-страницы дашборда

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Редирект 307 → `/dashboard` |
| GET | `/dashboard` | Главная витрина (KPI, графики, таблицы) |
| GET | `/dashboard/excel` | Браузерный редактор Excel (Univer) |
| GET | `/dashboard/class/{class_name}` | Страница класса |
| GET | `/dashboard/class/{class}/service/{service}` | Страница услуги |
| GET | `/dashboard/cost/{cost_key}` | Обзор вида затрат (`direct` / `indirect` / `ineff`) |
| GET | `/dashboard/cost/{cost_key}/class/{class}` | Вид затрат × класс |
| GET | `/dashboard/class/.../service/.../cost/{cost_key}` | Детализация статьи затрат |

В path-параметрах используется конвертер `:path` — имена классов/услуг могут содержать `/`.

## 4.5. Debug-маршруты (только DEBUG=true)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/debug` | Меню debug |
| GET | `/debug/excel` | Сырые листы Excel |
| GET | `/debug/calculation-services` | Распарсенные услуги по классам |

При `DEBUG=false` → HTTP 404.

## 4.6. Статика

| Путь | Содержимое |
|------|------------|
| `/static/dist/*` | Собранные CSS/JS (Vite) |

## 4.7. Пример проверки API

```bash
# через nginx (production)
curl -sk https://<SERVER_NAME>/health          # 403 вне MONITORING_CIDR
curl -sk -u 'USER:PASS' https://<SERVER_NAME>/api/files

# CSRF: сначала GET /dashboard → meta csrf-token, затем POST с X-CSRF-Token

# upload
curl -sk -u 'USER:PASS' -H "X-CSRF-Token: <token>" \
  -F "file=@./data.xlsx" https://<SERVER_NAME>/api/files/upload
```
