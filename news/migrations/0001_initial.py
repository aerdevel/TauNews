# Generated for TAU News Hub; initial schema for the news application.
import django.db.models.deletion
import django.utils.timezone
import news.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="Название")),
                ("slug", models.SlugField(blank=True, max_length=90, unique=True, verbose_name="URL")),
            ],
            options={"verbose_name": "категория", "verbose_name_plural": "категории", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220, verbose_name="Заголовок")),
                ("slug", models.SlugField(blank=True, max_length=240, unique=True, verbose_name="URL")),
                ("excerpt", models.TextField(max_length=360, verbose_name="Краткое описание")),
                ("body", models.TextField(verbose_name="Текст статьи")),
                ("image", models.ImageField(blank=True, null=True, upload_to=news.models.article_cover_upload_to, verbose_name="Обложка")),
                ("status", models.CharField(choices=[("draft", "Черновик"), ("published", "Опубликовано")], default="draft", max_length=12, verbose_name="Статус")),
                ("is_featured", models.BooleanField(default=False, verbose_name="Главная новость")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Создано")),
                ("published_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата публикации")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("views", models.PositiveIntegerField(default=0, verbose_name="Просмотры")),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="articles", to=settings.AUTH_USER_MODEL, verbose_name="Автор")),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="articles", to="news.category", verbose_name="Категория")),
            ],
            options={
                "verbose_name": "статья",
                "verbose_name_plural": "статьи",
                "ordering": ["-published_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(max_length=1500, verbose_name="Комментарий")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_approved", models.BooleanField(default=False, verbose_name="Одобрен")),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="news.article")),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "комментарий", "verbose_name_plural": "комментарии", "ordering": ["created_at"]},
        ),
    ]
