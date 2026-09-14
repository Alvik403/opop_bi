# Дашборд ОПиОП

**v1.2** — HTTPS, CSRF, isolated XLSX validation, backup/restore, hardening.

FastAPI BI-дашборд для построения витрин по Excel-файлам с листом `Калькуляция`.
Приложение поддерживает историю загруженных `.xlsx`, выбор активного файла в текущей сессии, кеширование данных по `mtime/size`, debug-раздел, health/readiness и автотесты.

## Быстрый старт (production)

1. Скопировать конфиг и задать секреты:

```bash
cp .env.example .env
```

В `.env` обязательно заменить `SESSION_SECRET`, `AUTH_USERNAME`, `AUTH_PASSWORD`.

2. Указать `SERVER_NAME`, `ALLOWED_HOSTS` и сеть мониторинга `MONITORING_CIDR`.

3. Положить TLS-сертификат и ключ в `nginx/certs/fullchain.pem` и
   `nginx/certs/privkey.pem`. Для локальной проверки можно создать временный
   самоподписанный сертификат:

```bash
openssl req -x509 -newkey rsa:3072 -sha256 -days 30 -nodes \
  -keyout nginx/certs/privkey.pem -out nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

4. Положить валидный `data/data.xlsx` в папку `data/`. На Linux выдать
   контейнерному UID только необходимые права:

```bash
sudo chown -R 10001:10001 data uploads runtime logs
chmod 750 data uploads runtime logs
```

5. Запустить:

```bash
docker compose up --build -d
```

Открыть `https://<SERVER_NAME>/` — потребуется Basic Auth из `.env`.
Порт FastAPI наружу не публикуется: доступ возможен только через nginx.

## Быстрый старт (локальная разработка)

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

Dev-порт привязан только к `127.0.0.1`. Этот compose задаёт
`ALLOW_INSECURE_DEBUG=true` и **открывает контур без auth** — его
запрещено использовать на сервере. Имена контейнеров разные:
`opop_bi_web` (prod) и `opop_bi_web_dev` (dev).

## Конфигурация

Настройки читаются из переменных окружения или `.env` (пример в `.env.example`):

- `DEBUG` — включает `/debug` и OpenAPI. **Не** отключает auth.
- `ALLOW_INSECURE_DEBUG` — единственный способ открыть контур без пароля;
  требует `DEBUG=true`. Только для `docker-compose.dev.yml`.
- `SESSION_SECRET` — ключ signed-cookie сессий (мин. 32 символа при `DEBUG=false`).
- `AUTH_USERNAME`, `AUTH_PASSWORD` — общая Basic Auth (временная модель до SSO:
  нет ролей, отзыва сессии и персональных учёток). Обязательны без
  `ALLOW_INSECURE_DEBUG`.
- `AUTH_LOCKOUT_ATTEMPTS`, `AUTH_LOCKOUT_WINDOW_SECONDS` — блокировка IP после
  неудачного перебора пароля.
- `MAX_UPLOAD_BYTES` — лимит размера `.xlsx` (по умолчанию 50 МБ).
- `UPLOAD_RATE_LIMIT_PER_MINUTE` — лимит загрузок с одного IP в минуту
  (ключ — `X-Real-IP` от nginx, не клиентский `X-Forwarded-For`).
- `MAX_UPLOAD_STORAGE_BYTES`, `MAX_UPLOAD_FILES` — общая квота и число версий.
- `XLSX_*` — лимиты ZIP/XLSX и время изолированной проверки.
- `TRUSTED_PROXY_IPS` — список доверенных proxy для `ProxyHeadersMiddleware`.
  Production compose **не** задаёт `*`: backend в internal-сети, IP клиента
  берётся из `X-Real-IP`.
- `ALLOWED_HOSTS`, `SERVER_NAME` — разрешённые Host и имя HTTPS-сервера.
- `MONITORING_CIDR` — сеть, которой доступны `/health` и `/ready` через nginx.
- `APP_HOST`, `APP_PORT` — параметры запуска uvicorn.
- `DATA_DIR` — папка исходного `data.xlsx`.
- `UPLOADS_DIR` — папка загруженных Excel-файлов.
- `DATABASE_PATH` — SQLite metadata.
- `LOGS_DIR` — JSON-логи приложения и ошибок.
- `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT` — ротация и срок хранения файлов логов.
- `ACTIVE_DEFAULT_FILE` — имя файла по умолчанию в `DATA_DIR`.

## Безопасность

- **Basic Auth** защищает все маршруты, кроме `/health` и `/ready`, и в
  production принимается только через HTTPS. Это **временная модель до SSO**:
  один логин на всех, без ролей и отзыва сессии. `DEBUG=true` auth не выключает.
- **OpenAPI/Swagger** доступен только при `DEBUG=true` (и только после auth,
  если заданы `AUTH_*`).
- **CSRF**: POST требует сессионный токен **и** Origin/Referer из `ALLOWED_HOSTS`.
- **Upload**: лимиты размера/квоты, ZIP-сигнатуры, коэффициента сжатия,
  листов/строк, isolated worker с timeout и stripped env (это не песочница),
  rate limiting по `X-Real-IP`. Стартовый `data.xlsx` проходит ту же проверку.
- **Сессии**: `https_only` cookies при `DEBUG=false`.
- **HTTP-заголовки**: CSP (ослабленный `'unsafe-eval'` только на `/dashboard/excel`),
  HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`.
- **Docker**: non-root `app`, образы с digest, `pip install --require-hashes`.
- **Логи**: файлы приложения и Docker stdout/stderr ограничены ротацией.
- **Frontend**: Chart.js и стили собираются локально, без внешних CDN.

Система предназначена для внутренней калькуляции услуг и затрат **без
персональных данных** и не классифицирована как объект КИИ. Загрузка ПДн
запрещена. При изменении назначения необходима новая классификация и пересмотр
мер по 152-ФЗ/187-ФЗ до загрузки таких данных.

**Документация для службы безопасности (СБ):**

- [docs/07_Документация_для_проверки_ИБ.md](docs/07_Документация_для_проверки_ИБ.md) — полное описание мер защиты, архитектуры и regulatory scope
- [docs/08_Чек_лист_проверки_ИБ.md](docs/08_Чек_лист_проверки_ИБ.md) — чек-лист для согласования и периодического контроля

Сетевой чек-лист для инфраструктуры — в `docs/08_Чек_лист_проверки_ИБ.md`.

## Резервное копирование и восстановление

Создание согласованной копии SQLite, Excel и загруженных версий:

```bash
python scripts/ops/backup_restore.py backup
```

Восстановление выполнять только после `docker compose down`:

```bash
python scripts/ops/backup_restore.py restore backups/opop-bi-<timestamp>.zip --confirm
docker compose up -d
```

Архивы находятся в исключённом из Git каталоге `backups/`. Хранить их на
зашифрованном носителе, ограничить права доступа и регулярно проверять
восстановление. Шифрование рабочего диска обеспечивается ОС (BitLocker/LUKS).

## Работа с Excel-файлами

В правом верхнем углу дашборда есть шестерёнка:

- показывает историю файлов;
- подсвечивает последний загруженный файл;
- позволяет выбрать файл только для текущей сессии;
- загружает новый `.xlsx` после проверки структуры.

Если пользователь загружает новый валидный файл, он становится активным только у него. У остальных пользователей текущий выбор не меняется, но появляется плашка о новой версии.

Слева в дашборде есть вкладка `Просмотр Excel`. Она открывает активный `.xlsx` в браузерном редакторе на базе Univer: доступны листы книги, сетка ячеек, редактирование и сохранение результата как новой версии. Сохранение проходит ту же серверную проверку структуры, что и обычная загрузка файла. Макросы, внешние ссылки и часть сложного форматирования могут не сохраниться в open-source браузерном импорте/экспорте.

## Frontend assets

Tailwind и JS собираются локально через Vite:

```bash
npm install
npm run build
```

В Docker сборка выполняется в отдельном frontend-stage. Compose не монтирует весь проект в `/app`, чтобы не затереть собранные `static/dist`.

## Тесты

Запуск через Docker (dev-конфиг):

```bash
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml run --rm web sh -c "pip install -r requirements-dev.txt && pytest -q"
```

Проверка зависимостей:

```bash
python -m pip install pip-audit
pip-audit -r requirements.txt
npm audit --audit-level=high
```

Проверяется:

- парсинг Excel fixture;
- сборка overview/navigation;
- валидация upload;
- редирект `/` → `/dashboard`;
- debug mode;
- Basic Auth и production-настройки;
- лимит размера upload;
- маршруты с `/` внутри имени класса/услуги;
- session-scoped active file;
- страница и API Excel-редактора.

## Ручной smoke-check

1. Открыть `https://<SERVER_NAME>/` и убедиться, что HTTP перенаправляется на HTTPS.
2. Открыть шестерёнку, увидеть активный файл и latest.
3. Загрузить валидный `.xlsx`; он должен стать активным в текущей сессии.
4. Загрузить невалидный файл; должна появиться понятная ошибка, файл не должен стать доступным.
5. Выбрать прошлый файл из истории; latest не меняется глобально.
6. Открыть `/dashboard/excel`, изменить ячейку и нажать `Сохранить как новую версию`.
7. Вернуться на `/dashboard` и убедиться, что активным стал новый файл.
8. Проверить `/health` и `/ready` из сети мониторинга и запрет из других сетей.
9. При `DEBUG=true` открыть `/debug`, `/debug/excel`, `/debug/calculation-services`.
10. Убедиться, что порт `8000` production недоступен с хоста и из сети (доступ только через nginx :443).

Автоматизированная проверка: `python scripts/security_check.py`

## Версии

- **v1.2** — HTTPS nginx, CSRF fail-closed, isolated XLSX + default-file validation,
  backup/restore по env-путям, pin digest/hash-lock, CI, документация для СБ.
- **v1.1** — hardening: Basic Auth, upload limits, security headers, non-root Docker, без CDN.
- **v1.0** — первая стабильная версия: FastAPI-дашборд, загрузка Excel, браузерный редактор Univer, health/readiness, автотесты.
- Актуальный код — ветка `main`, тег `v1.2`.
