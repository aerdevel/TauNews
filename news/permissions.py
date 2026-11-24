"""Единые правила доступа к редакторской части сайта."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied

AUTHOR_GROUP = "Authors"
EDITOR_GROUP = "Editors"
MANAGED_ROLE_GROUPS = (AUTHOR_GROUP, EDITOR_GROUP)

ROLE_READER = "reader"
ROLE_AUTHOR = "author"
ROLE_EDITOR = "editor"
ROLE_ADMIN = "admin"

ROLE_LABELS = {
    ROLE_READER: "Читатель",
    ROLE_AUTHOR: "Автор",
    ROLE_EDITOR: "Редактор",
    ROLE_ADMIN: "Администратор",
}


def is_editor(user):
    """Редактор и суперпользователь могут управлять любыми публикациями."""
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=EDITOR_GROUP).exists()
    )


def is_author(user):
    """Автор имеет доступ к редактору своих черновиков."""
    return user.is_authenticated and (
        is_editor(user) or user.groups.filter(name=AUTHOR_GROUP).exists()
    )


def get_user_role(user):
    """Возвращает одну основную роль; права суперпользователя имеют приоритет."""
    if user.is_superuser:
        return ROLE_ADMIN
    if user.groups.filter(name=EDITOR_GROUP).exists():
        return ROLE_EDITOR
    if user.groups.filter(name=AUTHOR_GROUP).exists():
        return ROLE_AUTHOR
    return ROLE_READER


def get_user_role_label(user):
    return ROLE_LABELS[get_user_role(user)]



def ensure_editor_group_permissions(group=None):
    """Выдаёт группе Editors только права на контентные модели портала."""
    group = group or Group.objects.get(name=EDITOR_GROUP)
    codenames = [
        f"{action}_{model}"
        for model in ("article", "category", "comment")
        for action in ("add", "change", "delete", "view")
    ]
    permissions = Permission.objects.filter(
        content_type__app_label="news",
        codename__in=codenames,
    )
    group.permissions.add(*permissions)
    return group


def _role_required(check):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


editor_required = _role_required(is_editor)
author_required = _role_required(is_author)
superuser_required = _role_required(lambda user: user.is_superuser)
