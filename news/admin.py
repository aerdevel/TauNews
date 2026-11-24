from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group

from .forms import SecureImageFormMixin
from .models import Article, Category, Comment
from .permissions import is_editor

User = get_user_model()


class ArticleAdminForm(SecureImageFormMixin, forms.ModelForm):
    class Meta:
        model = Article
        fields = "__all__"


class EditorOnlyAdminMixin:
    """Не позволяет обходить роли портала через стандартную Django Admin."""

    def has_module_permission(self, request):
        return is_editor(request.user) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return is_editor(request.user) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return is_editor(request.user) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return is_editor(request.user) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return is_editor(request.user) and super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if is_editor(request.user) else queryset.none()


class SuperuserOnlyAdminMixin:
    """Учётными записями и группами управляет только суперпользователь."""

    def has_module_permission(self, request):
        return request.user.is_superuser and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.none()


@admin.register(Category)
class CategoryAdmin(EditorOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(EditorOnlyAdminMixin, admin.ModelAdmin):
    form = ArticleAdminForm
    list_display = ("title", "category", "author", "status", "is_featured", "published_at", "views")
    list_filter = ("status", "category", "is_featured")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("views", "created_at", "updated_at")


@admin.register(Comment)
class CommentAdmin(EditorOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("article", "author", "created_at", "is_approved")
    list_filter = ("is_approved",)
    actions = ("approve_comments",)

    @admin.action(description="Одобрить выбранные комментарии")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)


# Встроенные UserAdmin и GroupAdmin по умолчанию доступны staff-пользователям
# с соответствующими permissions. В TAU News Hub назначение ролей и управление
# учётными записями оставлены только суперпользователям.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(SuperuserOnlyAdminMixin, DjangoUserAdmin):
    pass


@admin.register(Group)
class GroupAdmin(SuperuserOnlyAdminMixin, DjangoGroupAdmin):
    pass
