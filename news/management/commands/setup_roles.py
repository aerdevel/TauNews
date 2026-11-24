from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from news.permissions import (
    AUTHOR_GROUP,
    EDITOR_GROUP,
    ensure_editor_group_permissions,
)


class Command(BaseCommand):
    help = "Создаёт группы Authors и Editors для ролей портала."

    def handle(self, *args, **options):
        for group_name in (AUTHOR_GROUP, EDITOR_GROUP):
            group, created = Group.objects.get_or_create(name=group_name)
            state = "создана" if created else "уже существует"
            self.stdout.write(f"Группа «{group_name}»: {state}.")
            if group_name == EDITOR_GROUP:
                ensure_editor_group_permissions(group)
                self.stdout.write("  Назначены права на статьи, категории и комментарии.")
        self.stdout.write(self.style.SUCCESS(
            "Роли готовы. Назначайте их через Панель → Пользователи или Django Admin."
        ))
