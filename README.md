# TAU News Hub

Адаптивный новостной портал на Django 5.2+: публичная часть, регистрация и вход,
категории и поиск, статьи и комментарии, редакторская панель, роли пользователей,
загрузка обложек и предпросмотр Markdown.

## Стек

- Python 3.11+ и Django 5.2+
- SQLite для быстрого локального старта; PostgreSQL 16/17 для развёртывания
- Django ORM, Pillow, Mistune и nh3
- Gunicorn и WhiteNoise в production
- Docker Compose для приложения и PostgreSQL

## 1. Локальный запуск на Windows

В PowerShell из корневой папки проекта:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Сгенерируйте секретный ключ:

```powershell
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Вставьте ключ в `.env`. Для локальной разработки оставьте `DEBUG=true` и
`ALLOWED_HOSTS=127.0.0.1,localhost`. Затем выполните:

```powershell
py manage.py migrate
py manage.py createsuperuser
py manage.py setup_roles
py manage.py seed_demo
py manage.py check
py manage.py test
py manage.py runserver
```

Откройте http://127.0.0.1:8000/. Вход в Django Admin — `/admin/`, редакторская
панель — `/dashboard/`. Проверка готовности приложения и соединения с БД — `/healthz/`.

> Начальная миграция `news/0001_initial.py` уже включена в проект. После
> дальнейших изменений моделей создавайте новые миграции командой
> `py manage.py makemigrations news` и добавляйте их в систему контроля версий.

## 2. Запуск PostgreSQL и Django через Docker Compose

Нужны Docker Engine и Docker Compose v2. В комплект включён Caddy: он принимает
публичный HTTP/HTTPS-трафик, получает и обновляет TLS-сертификат и проксирует
запросы к Django. До запуска направьте DNS A/AAAA домена на сервер и разрешите
входящие TCP 80/443 (а также UDP 443 для HTTP/3). Создайте `.env` из шаблона и задайте
уникальные секреты. Для пароля БД используйте случайную hex-строку, чтобы не
возникало проблем с URL-кодированием символов в `DATABASE_URL`:

```powershell
Copy-Item .env.example .env
py -c "import secrets; print(secrets.token_hex(32))"
```

Сгенерируйте отдельный `SECRET_KEY`, установите `DEBUG=false`, заполните
`POSTGRES_PASSWORD`, а также реальные домены в `SITE_DOMAIN`, `ALLOWED_HOSTS` и
`CSRF_TRUSTED_ORIGINS`, например:

```dotenv
SECRET_KEY=<уникальный Django secret key>
DEBUG=false
ALLOWED_HOSTS=news.example.kz,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://news.example.kz
SITE_DOMAIN=news.example.kz
POSTGRES_DB=tau_news
POSTGRES_USER=tau_news_app
POSTGRES_PASSWORD=<случайная hex-строка>
```

Не добавляйте `.env` в Git. Наружу публикуются только порты Caddy 80/443;
Django и PostgreSQL доступны только во внутренней сети Compose. Caddy раздаёт
загруженные обложки из read-only mount тома `media_data`; static-файлы обслуживает WhiteNoise.

Соберите образы и поднимите БД:

```powershell
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py setup_roles
docker compose run --rm web python manage.py check --deploy
docker compose up -d
```

Демонстрационные материалы при необходимости добавляются отдельно:

```powershell
docker compose run --rm web python manage.py seed_demo
```

Проверить состояние контейнеров и readiness:

```powershell
docker compose ps
docker compose logs -f web
docker compose exec web python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/healthz/').read().decode())"
```

`/healthz/` выполняет `SELECT 1` и возвращает HTTP 503, если БД недоступна.

## 3. Развёртывание на сервере

В Compose уже включён Caddy как reverse proxy с автоматическим TLS. Если вместо
него используется Nginx или другой reverse proxy, адаптируйте конфигурацию
и соблюдайте следующие требования:

1. Направьте домен на сервер. Caddy автоматически получает и продлевает TLS-сертификат.
2. Caddy проксирует HTTPS-запросы на внутренний сервис `web:8000`.
3. Reverse proxy должен перезаписывать `X-Forwarded-Proto: https`, а не принимать
   это значение от клиента. Caddy делает это автоматически; в Compose
   `TRUST_PROXY_SSL_HEADER=true` уже задан;
   не используйте этот флаг, если proxy не доверенный или не очищает заголовок.
4. Укажите точный домен в `ALLOWED_HOSTS` и HTTPS origin в
   `CSRF_TRUSTED_ORIGINS`.
5. Откройте наружу только 80/443 (и SSH для администрирования). Не публикуйте
   PostgreSQL и внутренний порт приложения.
6. Настройте регулярные резервные копии БД, медиа и томов Caddy и проверьте
   восстановление на отдельной тестовой среде.

Не включайте HSTS до того, как HTTPS полностью работает на всех нужных доменах.
`SECURE_HSTS_INCLUDE_SUBDOMAINS` оставляйте `false`, пока не проверены все
поддомены. Не включайте preload без отдельного решения.

### Обновление версии

Перед обновлением сделайте резервную копию. После получения новой версии:

```bash
git pull --ff-only
docker compose build web
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py check --deploy
docker compose up -d
docker compose logs --tail=100 web
```

Если исходники доставляются архивом, распакуйте новую версию в рабочую директорию
после резервного копирования и повторите команды начиная с `docker compose build`.

## 4. Резервное копирование и восстановление PostgreSQL

Создать дамп (из каталога с `compose.yaml`):

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > tau_news_$(date +%F).sql
```

Восстановление в заранее созданную пустую БД:

```bash
cat tau_news_YYYY-MM-DD.sql | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

Для Windows PowerShell перенаправление `>` также подходит для текстового SQL-дампа;
при проблемах с кодировкой используйте `cmd /c` или выполняйте команду в WSL.

Медиафайлы хранятся отдельно от БД в Docker volume `media_data`. Для резервного
копирования остановите запись в приложение на время копирования и используйте
согласованный snapshot/backup volume средствами Docker-хоста или инфраструктуры.
Дамп БД без копии медиа не сохраняет загруженные обложки. Храните копии вне
сервера и периодически проверяйте восстановление.

## 5. Роли и редакторская панель

После создания суперпользователя войдите в `/dashboard/`. Только суперпользователь
видит `/dashboard/users/` и может назначать роли:

- **Читатель** — публичная часть сайта и комментарии после входа.
- **Автор** — создаёт и редактирует только собственные черновики.
- **Редактор** — работает со всеми статьями, публикует материалы и модерирует комментарии.
- **Администратор** — суперпользователь Django.

Роли «Автор» и «Редактор» используют группы Django `Authors` и `Editors`.
Команда `setup_roles` безопасно создаёт группы и permissions. Обычная регистрация
всегда создаёт читателя. Флаг `is_staff` отдельно управляет входом в Django Admin.

## 6. Редактор статей и обложки

В поле текста поддерживается Markdown. Предпросмотр не сохраняет статью.
Результат Markdown очищается через allowlist `nh3`. Обложки принимаются в JPEG,
PNG и WebP до 5 МБ, проходят проверку Pillow и пересохранение без исходных EXIF.

## 7. Настройки безопасности

При `DEBUG=false` Django включает HTTPS redirect, secure cookies и HSTS.
`SECURE_PROXY_SSL_HEADER` задаётся только для доверенного reverse proxy.
`SECRET_KEY` обязателен; шаблонное значение не допускается. В production
используйте секрет-хранилище или защищённые переменные окружения, а не Git.

Дополнительные настройки:

- `DB_CONN_MAX_AGE` — время повторного использования соединения PostgreSQL.
- `DB_SSL_REQUIRE=true` — требует SSL для PostgreSQL, если провайдер это поддерживает.
- `SECURE_HSTS_SECONDS` — длительность HSTS.
- `SECURE_HSTS_INCLUDE_SUBDOMAINS` — включать только после проверки поддоменов.
- `DJANGO_LOG_LEVEL` — уровень логирования Django.

## 8. Финальная проверка перед production

На целевом окружении выполните:

```bash
python manage.py check --deploy
python manage.py test
python manage.py migrate --check
python manage.py showmigrations
```

