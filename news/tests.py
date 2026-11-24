from io import BytesIO

from django.contrib.auth.models import Group, Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .forms import ArticleForm
from .image_utils import MAX_IMAGE_SIZE, InvalidImageError, normalize_uploaded_image
from .markdown_utils import render_markdown
from .models import Article, Category, Comment
from .permissions import AUTHOR_GROUP, EDITOR_GROUP


class TestDataMixin:
    def create_article(self, author, title="Тестовая статья", status=Article.Status.DRAFT):
        return Article.objects.create(
            title=title,
            excerpt="Описание материала",
            body="Текст материала",
            category=self.category,
            author=author,
            status=status,
        )


class PublicPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="writer", password="test-password")
        self.category = Category.objects.create(name="Новости")
        self.article = Article.objects.create(
            title="Тестовая публикация",
            excerpt="Краткое описание тестовой публикации",
            body="**Полный текст** публикации.",
            category=self.category,
            author=self.user,
            status=Article.Status.PUBLISHED,
        )

    def test_home_shows_published_article(self):
        response = self.client.get(reverse("news:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)

    def test_article_detail_increments_views_and_renders_markdown(self):
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>Полный текст</strong>", html=True)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views, 1)

    def test_draft_is_not_public(self):
        self.article.status = Article.Status.DRAFT
        self.article.save()
        self.assertEqual(self.client.get(self.article.get_absolute_url()).status_code, 404)

    def test_seed_demo_command_is_idempotent(self):
        call_command("seed_demo", verbosity=0)
        first_count = Article.objects.count()
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Article.objects.count(), first_count)
        self.assertGreaterEqual(Category.objects.count(), 5)


class InfrastructureHealthTests(TestCase):
    def test_health_endpoint_checks_database_and_returns_ok(self):
        response = self.client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class MarkdownSecurityTests(TestCase):
    def test_markdown_formats_text(self):
        rendered = render_markdown("**Жирный текст**\n\n- Первый пункт\n- Второй пункт")
        self.assertIn("<strong>Жирный текст</strong>", rendered)
        self.assertIn("<ul>", rendered)
        self.assertIn("<li>Первый пункт</li>", rendered)

    def test_raw_html_is_escaped_and_unsafe_link_is_blocked(self):
        rendered = render_markdown(
            '<script>alert("xss")</script>\n\n[опасная ссылка](javascript:alert(1))'
        )
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertIn("&lt;script&gt;", rendered)


class ImageUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="writer", password="test-password")
        self.category = Category.objects.create(name="Технологии")

    @staticmethod
    def make_image(format_name="PNG"):
        buffer = BytesIO()
        Image.new("RGB", (24, 16), color=(210, 120, 40)).save(buffer, format=format_name)
        extension = "jpg" if format_name == "JPEG" else format_name.lower()
        return SimpleUploadedFile(
            f"client-controlled-name.{extension}",
            buffer.getvalue(),
            content_type=f"image/{extension}",
        )

    def test_valid_cover_is_normalized(self):
        form = ArticleForm(
            data={
                "title": "Материал с обложкой",
                "excerpt": "Описание материала",
                "body": "Текст материала",
                "category": self.category.pk,
            },
            files={"image": self.make_image()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        normalized = form.cleaned_data["image"]
        self.assertEqual(normalized.name, "cover.png")
        normalized.seek(0)
        with Image.open(normalized) as saved_image:
            self.assertEqual(saved_image.format, "PNG")

    def test_gif_is_rejected(self):
        upload = self.make_image("GIF")
        with self.assertRaises(InvalidImageError):
            normalize_uploaded_image(upload)

    def test_oversized_upload_is_rejected_before_decoding(self):
        upload = SimpleUploadedFile("large.png", b"x" * (MAX_IMAGE_SIZE + 1))
        with self.assertRaises(InvalidImageError):
            normalize_uploaded_image(upload)


class ArticlePreviewTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor", password="test-password")
        editor_group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
        self.editor.groups.add(editor_group)

    def test_preview_is_not_available_to_regular_reader(self):
        regular_user = User.objects.create_user(username="reader", password="test-password")
        self.client.force_login(regular_user)
        response = self.client.post(reverse("news:article_preview"), {"body": "Текст"})
        self.assertEqual(response.status_code, 403)

    def test_preview_does_not_save_article(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("news:article_preview"),
            {
                "title": "Черновик предпросмотра",
                "excerpt": "Короткое описание",
                "body": "**Проверка предпросмотра**",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertContains(response, "Проверка предпросмотра")
        self.assertContains(response, "ПРЕДПРОСМОТР")
        self.assertEqual(Article.objects.count(), 0)


class EditorialAccessTests(TestCase, TestDataMixin):
    def setUp(self):
        self.author = User.objects.create_user(username="author", password="test-password")
        self.other_author = User.objects.create_user(username="other", password="test-password")
        self.editor = User.objects.create_user(username="editor", password="test-password")
        author_group, _ = Group.objects.get_or_create(name=AUTHOR_GROUP)
        editor_group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
        self.author.groups.add(author_group)
        self.editor.groups.add(editor_group)
        self.category = Category.objects.create(name="Редакция")
        self.own_draft = self.create_article(self.author, "Мой черновик")
        self.other_draft = self.create_article(self.other_author, "Чужой черновик")
        self.published_article = self.create_article(
            self.author, "Опубликованный материал", Article.Status.PUBLISHED
        )

    def test_authenticated_reader_is_denied_dashboard(self):
        reader = User.objects.create_user(username="reader", password="test-password")
        self.client.force_login(reader)
        response = self.client.get(reverse("news:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_staff_flag_alone_does_not_grant_dashboard_access(self):
        staff = User.objects.create_user(
            username="staff-only", password="test-password", is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("news:dashboard")).status_code, 403)

    def test_author_sees_only_own_articles(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("news:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.own_draft.title)
        self.assertNotContains(response, self.other_draft.title)

    def test_author_can_edit_own_draft(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("news:article_edit", args=[self.own_draft.pk]))
        self.assertEqual(response.status_code, 200)

    def test_author_cannot_edit_another_users_article(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("news:article_edit", args=[self.other_draft.pk]))
        self.assertEqual(response.status_code, 403)

    def test_author_cannot_edit_own_published_article(self):
        self.client.force_login(self.author)
        response = self.client.get(
            reverse("news:article_edit", args=[self.published_article.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_author_cannot_delete_another_users_article(self):
        self.client.force_login(self.author)
        response = self.client.get(
            reverse("news:article_delete", args=[self.other_draft.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_author_cannot_delete_published_article(self):
        self.client.force_login(self.author)
        response = self.client.get(
            reverse("news:article_delete", args=[self.published_article.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_author_cannot_publish_by_forging_post_fields(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("news:article_create"),
            {
                "title": "Попытка публикации",
                "excerpt": "Описание",
                "body": "Текст",
                "category": self.category.pk,
                "status": Article.Status.PUBLISHED,
                "is_featured": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Article.objects.get(title="Попытка публикации")
        self.assertEqual(created.author, self.author)
        self.assertEqual(created.status, Article.Status.DRAFT)
        self.assertFalse(created.is_featured)

    def test_editor_can_edit_another_authors_article(self):
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("news:article_edit", args=[self.other_draft.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_editor_can_publish_article(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("news:article_create"),
            {
                "title": "Публикация редактора",
                "excerpt": "Описание публикации",
                "body": "Текст публикации",
                "category": self.category.pk,
                "status": Article.Status.PUBLISHED,
                "is_featured": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Article.objects.get(title="Публикация редактора")
        self.assertEqual(created.status, Article.Status.PUBLISHED)
        self.assertTrue(created.is_featured)

    def test_editor_can_approve_comments(self):
        comment = Comment.objects.create(
            article=self.published_article,
            author=self.other_author,
            text="Комментарий для одобрения",
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("news:comment_moderate", args=[comment.pk]),
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        comment.refresh_from_db()
        self.assertTrue(comment.is_approved)

    def test_author_cannot_moderate_comments(self):
        comment = Comment.objects.create(
            article=self.published_article,
            author=self.other_author,
            text="Комментарий для проверки",
        )
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("news:comment_moderate", args=[comment.pk]),
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertFalse(comment.is_approved)

    def test_comment_moderation_requires_post(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("news:comment_moderate", args=[1]))
        self.assertEqual(response.status_code, 405)


class UserRoleManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="root", email="root@example.test", password="test-password"
        )
        self.editor = User.objects.create_user(username="editor", password="test-password")
        editor_group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
        self.editor.groups.add(editor_group)
        self.target = User.objects.create_user(username="new-user", password="test-password")

    def test_only_superuser_can_open_role_management(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("news:user_management"))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_open_role_management(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("news:user_management"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователи и роли")

    def test_superuser_can_assign_editor_role(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "editor"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.target.groups.filter(name=EDITOR_GROUP).exists())

    def test_changing_role_removes_other_managed_roles(self):
        author_group, _ = Group.objects.get_or_create(name=AUTHOR_GROUP)
        self.target.groups.add(author_group)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "editor"},
        )
        self.assertFalse(self.target.groups.filter(name=AUTHOR_GROUP).exists())
        self.assertTrue(self.target.groups.filter(name=EDITOR_GROUP).exists())

    def test_reader_role_removes_editor_and_author_groups(self):
        author_group, _ = Group.objects.get_or_create(name=AUTHOR_GROUP)
        self.target.groups.add(author_group)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "reader"},
        )
        self.assertFalse(self.target.groups.filter(name__in=[AUTHOR_GROUP, EDITOR_GROUP]).exists())

    def test_role_assignment_cannot_promote_user_to_superuser(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "admin"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.target.is_superuser)
        self.assertFalse(self.target.groups.filter(name__in=[AUTHOR_GROUP, EDITOR_GROUP]).exists())

    def test_superuser_role_is_immutable_in_role_screen(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("news:user_role_update", args=[self.admin.pk]),
            {"role": "reader"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.admin.is_superuser)

    def test_django_admin_access_is_separate_from_portal_role(self):
        self.target.is_staff = True
        self.target.save(update_fields=["is_staff"])
        self.client.force_login(self.admin)
        self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "editor"},
        )
        self.target.refresh_from_db()
        self.assertTrue(self.target.groups.filter(name=EDITOR_GROUP).exists())
        self.assertFalse(self.target.is_staff)

    def test_superuser_can_explicitly_grant_django_admin_access(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("news:user_role_update", args=[self.target.pk]),
            {"role": "editor", "can_access_admin": "on"},
        )
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_staff)

    def test_setup_roles_command_is_idempotent(self):
        call_command("setup_roles", verbosity=0)
        call_command("setup_roles", verbosity=0)
        self.assertTrue(Group.objects.filter(name=AUTHOR_GROUP).exists())
        editor_group = Group.objects.get(name=EDITOR_GROUP)
        self.assertTrue(editor_group.permissions.filter(codename="change_article").exists())
        self.assertTrue(editor_group.permissions.filter(codename="change_category").exists())

    def test_staff_author_cannot_bypass_portal_role_in_django_admin(self):
        staff_author = User.objects.create_user(
            username="staff-author", password="test-password", is_staff=True
        )
        author_group, _ = Group.objects.get_or_create(name=AUTHOR_GROUP)
        staff_author.groups.add(author_group)
        view_permission = Permission.objects.get(
            content_type__app_label="news", codename="view_article"
        )
        staff_author.user_permissions.add(view_permission)
        self.client.force_login(staff_author)
        response = self.client.get("/admin/news/article/")
        self.assertEqual(response.status_code, 403)

    def test_staff_user_cannot_manage_groups_or_accounts_in_django_admin(self):
        staff_user = User.objects.create_user(
            username="staff-manager", password="test-password", is_staff=True
        )
        permissions = Permission.objects.filter(
            content_type__app_label="auth",
            codename__in=("view_group", "change_group", "view_user", "change_user"),
        )
        staff_user.user_permissions.add(*permissions)
        self.client.force_login(staff_user)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 403)
        self.assertEqual(self.client.get("/admin/auth/user/").status_code, 403)
