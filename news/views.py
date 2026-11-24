import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .forms import ArticleForm, CommentForm, RegisterForm, RoleAssignmentForm
from .markdown_utils import render_markdown
from .models import Article, Category, Comment
from .permissions import (
    ROLE_LABELS,
    author_required,
    editor_required,
    get_user_role,
    get_user_role_label,
    is_editor,
    superuser_required,
)

User = get_user_model()
security_logger = logging.getLogger("news.security")
MAX_SEARCH_LENGTH = 100


def published_articles():
    """Единая выборка опубликованных материалов для публичной части."""
    return Article.objects.filter(
        status=Article.Status.PUBLISHED,
        published_at__lte=timezone.now(),
    ).select_related("category", "author")


def home(request):
    articles = published_articles()
    featured = articles.filter(is_featured=True).first() or articles.first()
    latest = articles.exclude(pk=featured.pk) if featured else articles
    return render(request, "news/home.html", {
        "featured": featured,
        "page_obj": Paginator(latest, 9).get_page(request.GET.get("page")),
    })


def article_detail(request, slug):
    article = get_object_or_404(published_articles(), slug=slug)
    Article.objects.filter(pk=article.pk).update(views=F("views") + 1)
    article.refresh_from_db()
    comments = article.comments.filter(is_approved=True).select_related("author")
    form = CommentForm()
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.author = request.user
            comment.save()
            messages.success(request, "Комментарий отправлен на модерацию.")
            return redirect(article.get_absolute_url())
    related = published_articles().filter(category=article.category).exclude(pk=article.pk)[:3]
    return render(request, "news/article_detail.html", {
        "article": article, "comments": comments, "form": form, "related": related
    })


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    page_obj = Paginator(
        published_articles().filter(category=category), 9
    ).get_page(request.GET.get("page"))
    return render(request, "news/listing.html", {
        "page_obj": page_obj, "heading": category.name
    })


def search(request):
    query = request.GET.get("q", "").strip()[:MAX_SEARCH_LENGTH]
    results = published_articles().filter(
        Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(body__icontains=query)
    ) if query else published_articles().none()
    return render(request, "news/listing.html", {
        "page_obj": Paginator(results, 9).get_page(request.GET.get("page")),
        "heading": f"Поиск: {query}" if query else "Поиск",
        "query": query,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect("news:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Регистрация всегда создаёт читателя. Повышение роли доступно
        # только суперпользователю через отдельный защищённый экран.
        login(request, user)
        messages.success(request, "Аккаунт создан. Добро пожаловать!")
        return redirect("news:home")
    return render(request, "registration/register.html", {"form": form})


@author_required
def dashboard(request):
    editor = is_editor(request.user)
    articles = Article.objects.select_related("category", "author")
    if not editor:
        articles = articles.filter(author=request.user)

    pending_comments = Comment.objects.filter(is_approved=False).select_related(
        "author", "article"
    ).order_by("created_at") if editor else Comment.objects.none()
    context = {
        "articles": articles[:20],
        "total": articles.count(),
        "published": articles.filter(status=Article.Status.PUBLISHED).count(),
        "drafts": articles.filter(status=Article.Status.DRAFT).count(),
        "pending_comments": pending_comments.count(),
        "pending_comment_list": pending_comments[:10],
        "can_moderate": editor,
        "can_manage_users": request.user.is_superuser,
        "role_label": get_user_role_label(request.user),
    }
    return render(request, "dashboard/index.html", context)


@author_required
def article_create(request):
    editor = is_editor(request.user)
    form = ArticleForm(
        request.POST or None,
        request.FILES or None,
        can_publish=editor,
    )
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        if not editor:
            # Даже поддельные поля status/is_featured из HTTP-запроса
            # не могут дать автору право опубликовать материал.
            article.status = Article.Status.DRAFT
            article.is_featured = False
        article.save()
        messages.success(request, "Статья сохранена.")
        return redirect("news:dashboard")
    return render(request, "dashboard/article_form.html", {
        "form": form,
        "heading": "Новая статья",
        "is_editor": editor,
    })


@author_required
def article_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)
    editor = is_editor(request.user)
    if not editor:
        if article.author_id != request.user.pk:
            raise PermissionDenied
        # После публикации материал редактирует только редактор: автор не
        # может незаметно изменить уже опубликованный текст.
        if article.status == Article.Status.PUBLISHED:
            raise PermissionDenied

    form = ArticleForm(
        request.POST or None,
        request.FILES or None,
        instance=article,
        can_publish=editor,
    )
    if request.method == "POST" and form.is_valid():
        updated_article = form.save(commit=False)
        if not editor:
            updated_article.status = Article.Status.DRAFT
            updated_article.is_featured = False
        updated_article.save()
        messages.success(request, "Изменения сохранены.")
        return redirect("news:dashboard")
    return render(request, "dashboard/article_form.html", {
        "form": form,
        "heading": "Редактировать статью",
        "is_editor": editor,
    })


@author_required
@xframe_options_sameorigin
def article_preview(request):
    """Показывает безопасный предпросмотр, не сохраняя материал в БД."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    return render(request, "dashboard/article_preview.html", {
        "title": request.POST.get("title", "")[:220],
        "excerpt": request.POST.get("excerpt", "")[:360],
        "preview_html": render_markdown(request.POST.get("body", "")[:200_000]),
    })


@author_required
def article_delete(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not is_editor(request.user):
        if article.author_id != request.user.pk:
            raise PermissionDenied
        if article.status == Article.Status.PUBLISHED:
            raise PermissionDenied

    if request.method == "POST":
        article.delete()
        messages.success(request, "Статья удалена.")
        return redirect("news:dashboard")
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", "POST"])
    return render(request, "dashboard/article_confirm_delete.html", {"article": article})


@editor_required
@require_POST
def comment_moderate(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    action = request.POST.get("action")
    if action == "approve":
        comment.is_approved = True
        comment.save(update_fields=["is_approved"])
        messages.success(request, "Комментарий одобрен.")
    elif action == "delete":
        comment.delete()
        messages.success(request, "Комментарий удалён.")
    else:
        messages.error(request, "Неизвестное действие модерации.")
    return redirect("news:dashboard")


@superuser_required
def user_management(request):
    """Экран назначения ролей; доступен только суперпользователям."""
    accounts = User.objects.order_by("username")
    rows = [
        {
            "account": account,
            "role_label": get_user_role_label(account),
            "form": None if account.is_superuser else RoleAssignmentForm(target_user=account),
        }
        for account in accounts
    ]
    return render(request, "dashboard/users.html", {
        "user_rows": rows,
        "role_label": get_user_role_label(request.user),
        "can_moderate": True,
    })


@superuser_required
@require_POST
def user_role_update(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.is_superuser:
        messages.error(request, "Нельзя менять роль суперпользователя через этот экран.")
        return redirect("news:user_management")

    old_role = get_user_role(target_user)
    old_staff_access = target_user.is_staff
    form = RoleAssignmentForm(request.POST, target_user=target_user)
    if not form.is_valid():
        messages.error(request, "Роль не изменена: выберите допустимое значение.")
        return redirect("news:user_management")

    form.save()
    new_role = get_user_role(target_user)
    security_logger.warning(
        "role_changed actor_id=%s target_id=%s old_role=%s new_role=%s",
        request.user.pk,
        target_user.pk,
        old_role,
        new_role,
    )
    if old_staff_access != target_user.is_staff:
        security_logger.warning(
            "django_admin_access_changed actor_id=%s target_id=%s enabled=%s",
            request.user.pk,
            target_user.pk,
            target_user.is_staff,
        )
    messages.success(
        request,
        f"Роль пользователя {target_user.username} изменена: {ROLE_LABELS[new_role].lower()}.",
    )
    return redirect("news:user_management")
