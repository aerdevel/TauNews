from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from .image_utils import InvalidImageError, normalize_uploaded_image
from .models import Article, Comment
from .permissions import (
    AUTHOR_GROUP,
    EDITOR_GROUP,
    MANAGED_ROLE_GROUPS,
    ROLE_AUTHOR,
    ROLE_EDITOR,
    ROLE_READER,
    ensure_editor_group_permissions,
    get_user_role,
)

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Электронная почта")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class SecureImageFormMixin:
    """Применяет одинаковые правила обработки обложек в редакторе и админке."""

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image
        try:
            return normalize_uploaded_image(image)
        except InvalidImageError as error:
            raise forms.ValidationError(str(error)) from error


class ArticleForm(SecureImageFormMixin, forms.ModelForm):
    def __init__(self, *args, can_publish=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Права не определяются данными POST: представление передаёт флаг
        # только после серверной проверки роли пользователя.
        if not can_publish:
            self.fields.pop("status", None)
            self.fields.pop("is_featured", None)

    class Meta:
        model = Article
        fields = ("title", "excerpt", "body", "image", "category", "status", "is_featured")
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "body": forms.Textarea(attrs={
                "rows": 16,
                "class": "markdown-source",
                "spellcheck": "true",
            }),
        }
        help_texts = {
            "body": (
                "Поддерживается Markdown: **жирный**, *курсив*, заголовки, "
                "списки, ссылки и блоки кода."
            ),
            "image": "JPEG, PNG или WebP; до 5 МБ и 6000×6000 пикселей.",
        }


class RoleAssignmentForm(forms.Form):
    """Форма назначения только трёх управляемых ролей без выдачи superuser."""

    ROLE_CHOICES = (
        (ROLE_READER, "Читатель"),
        (ROLE_AUTHOR, "Автор"),
        (ROLE_EDITOR, "Редактор"),
    )

    role = forms.ChoiceField(
        label="Роль",
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "role-select"}),
    )
    can_access_admin = forms.BooleanField(
        label="Доступ к Django Admin",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "admin-access-checkbox"}),
    )

    def __init__(self, *args, target_user, **kwargs):
        self.target_user = target_user
        if not args and "data" not in kwargs and "initial" not in kwargs:
            kwargs["initial"] = {
                "role": get_user_role(target_user),
                "can_access_admin": target_user.is_staff,
            }
        super().__init__(*args, **kwargs)

    def save(self):
        if not self.is_valid():
            raise ValueError("Нельзя сохранить невалидную форму назначения роли.")
        if self.target_user.is_superuser:
            raise ValidationError("Роль суперпользователя нельзя изменить здесь.")

        selected_role = self.cleaned_data["role"]
        with transaction.atomic():
            managed_groups = list(Group.objects.filter(name__in=MANAGED_ROLE_GROUPS))
            if managed_groups:
                self.target_user.groups.remove(*managed_groups)

            group_name = {
                ROLE_READER: None,
                ROLE_AUTHOR: AUTHOR_GROUP,
                ROLE_EDITOR: EDITOR_GROUP,
            }[selected_role]
            if group_name:
                group, _ = Group.objects.get_or_create(name=group_name)
                self.target_user.groups.add(group)
                if group_name == EDITOR_GROUP:
                    ensure_editor_group_permissions(group)

            # is_staff — отдельный доступ к стандартной Django Admin.
            # Он не следует автоматически из роли редактора портала.
            self.target_user.is_staff = self.cleaned_data["can_access_admin"]
            self.target_user.save(update_fields=["is_staff"])

        return self.target_user


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("text",)
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "placeholder": "Поделитесь мнением..."})}
