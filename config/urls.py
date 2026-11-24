from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import urls as auth_urls
from django.urls import include, path

from config.health import health_check

urlpatterns = [
    path("healthz/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("", include("news.urls")),
    # Явное пространство имён согласовано с LOGIN_URL и шаблонами.
    path("accounts/", include((auth_urls.urlpatterns, "accounts"), namespace="accounts")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
