import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Локальный .env предназначен только для разработки. В production значения
# должны поступать из переменных окружения платформы/секрет-хранилища.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes"}
allowed_hosts_default = "127.0.0.1,localhost" if DEBUG else ""
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", allowed_hosts_default).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if not SECRET_KEY or SECRET_KEY.startswith("replace-"):
    raise RuntimeError(
        "Задайте уникальный SECRET_KEY в .env или переменных окружения. "
        "Не используйте ключ из .env.example."
    )
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("В production необходимо явно задать ALLOWED_HOSTS.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "news",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "news.context_processors.site_categories",
        ],
    },
}]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# SQLite остаётся вариантом по умолчанию для простого локального запуска.
# Для PostgreSQL достаточно передать DATABASE_URL; парсер проверяет схему URL.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
            conn_health_checks=True,
            ssl_require=os.getenv("DB_SSL_REQUIRE", "false").lower() in {"1", "true", "yes"},
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Asia/Almaty"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 5.2 STORAGES: в production WhiteNoise отдаёт сжатые static-файлы
# с хешированными именами; загружаемые пользователями media остаются на диске.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_REDIRECT_URL = "news:home"
LOGOUT_REDIRECT_URL = "news:home"
LOGIN_URL = "accounts:login"

# Безопасные cookie и заголовки применяются также в режиме разработки.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # Readiness probe вызывается внутренним HTTP healthcheck контейнера.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = (
        os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").strip().lower()
        in {"1", "true", "yes"}
    )
    SECURE_HSTS_PRELOAD = False

# Включать только если приложение действительно находится за доверенным
# reverse proxy, который сам перезаписывает X-Forwarded-Proto.
if os.getenv("TRUST_PROXY_SSL_HEADER", "false").strip().lower() in {"1", "true", "yes"}:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Поддерживает multipart-запрос с обложкой до 5 МБ и полями формы.
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024


# В production вывод направляется в stdout/stderr и может собираться платформой.
# События изменения ролей помечаются отдельным security-логгером.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
        },
        "news.security": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
