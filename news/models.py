import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def article_cover_upload_to(instance, filename):
    """Хранит обложки под случайными именами, не используя имя клиента."""
    extension = PurePosixPath(filename).suffix.lower().lstrip(".")
    if extension not in {"jpg", "png", "webp"}:
        extension = "jpg"
    return f"articles/{uuid.uuid4().hex}.{extension}"


class Category(models.Model):
    name = models.CharField("Название", max_length=80, unique=True)
    slug = models.SlugField("URL", max_length=90, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"

    title = models.CharField("Заголовок", max_length=220)
    slug = models.SlugField("URL", max_length=240, unique=True, blank=True)
    excerpt = models.TextField("Краткое описание", max_length=360)
    body = models.TextField("Текст статьи")
    image = models.ImageField("Обложка", upload_to=article_cover_upload_to, blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="Категория",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="Автор",
    )
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField("Главная новость", default=False)
    created_at = models.DateTimeField("Создано", default=timezone.now)
    published_at = models.DateTimeField("Дата публикации", blank=True, null=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)
    views = models.PositiveIntegerField("Просмотры", default=0)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "статья"
        verbose_name_plural = "статьи"
        indexes = [
            models.Index(fields=["status", "published_at"], name="article_status_pub_idx"),
            models.Index(fields=["category", "status", "published_at"], name="article_cat_status_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True)[:220] or "article"
            candidate, number = base, 2
            while Article.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{number}"
                number += 1
            self.slug = candidate
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:article_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField("Комментарий", max_length=1500)
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField("Одобрен", default=False)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "комментарий"
        verbose_name_plural = "комментарии"
        indexes = [
            models.Index(fields=["article", "is_approved", "created_at"], name="comment_moderation_idx"),
        ]

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"
