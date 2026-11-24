from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article, Category
from news.permissions import AUTHOR_GROUP, EDITOR_GROUP, ensure_editor_group_permissions


CATEGORIES = [
    ("Новости университета", "news"),
    ("Наука и технологии", "science"),
    ("Студенческая жизнь", "student-life"),
    ("Образование", "education"),
    ("Мероприятия", "events"),
]

ARTICLES = [
    {
        "slug": "tau-student-innovation-week",
        "title": "В TAU прошла неделя студенческих инноваций",
        "category": "Мероприятия",
        "excerpt": "Студенты представили проекты в области цифровых технологий, инженерии и устойчивого развития.",
        "body": """Университетское пространство на несколько дней превратилось в площадку для обмена идеями и практического эксперимента. Команды студентов представили прототипы сервисов, инженерные решения и исследовательские инициативы.\n\nВ программе были проектные презентации, открытые консультации с преподавателями и обсуждения с приглашёнными экспертами. Участники получили обратную связь и наметили следующие шаги для развития своих проектов.\n\nОрганизаторы отмечают, что цель инициативы — помочь студентам пройти путь от идеи до работающего прототипа и найти единомышленников внутри университета.""",
        "featured": True,
    },
    {
        "slug": "research-lab-open-day",
        "title": "Научные лаборатории TAU открыли двери для студентов",
        "category": "Наука и технологии",
        "excerpt": "Участники познакомились с исследовательским оборудованием и узнали, как присоединиться к научным командам.",
        "body": """День открытых лабораторий объединил студентов, преподавателей и молодых исследователей. Гости узнали о текущих проектах, методах работы и возможностях участия в исследованиях.\n\nВстречи проходили в формате коротких экскурсий и вопросов-ответов. Такой формат помогает студентам раньше познакомиться с научной средой и выбрать направление для дальнейшей работы.""",
    },
    {
        "slug": "career-skills-workshop",
        "title": "Для студентов провели практикум по карьерным навыкам",
        "category": "Образование",
        "excerpt": "Участники разобрали структуру резюме, подготовку к собеседованию и способы презентации собственных проектов.",
        "body": """Практический семинар был посвящён навыкам, которые помогают увереннее переходить от учёбы к профессиональной деятельности.\n\nУчастники работали с примерами резюме, тренировались формулировать достижения и обсуждали типичные вопросы на собеседованиях. Отдельный блок был посвящён портфолио учебных и командных проектов.""",
    },
    {
        "slug": "campus-volunteer-community",
        "title": "Студенческое волонтёрское сообщество запустило новый сезон",
        "category": "Студенческая жизнь",
        "excerpt": "Новый сезон объединит экологические, образовательные и социальные инициативы.",
        "body": """Волонтёрское сообщество объявило о старте нового сезона. В планах — экологические акции, помощь в организации университетских событий и образовательные встречи.\n\nПрисоединиться могут студенты разных курсов. Для новых участников подготовят вводную встречу, на которой расскажут о направлениях работы и ближайших мероприятиях.""",
    },
    {
        "slug": "tau-academic-calendar-highlights",
        "title": "Главные академические даты семестра: что важно не пропустить",
        "category": "Новости университета",
        "excerpt": "Собрали ключевые этапы семестра, чтобы студентам было проще планировать учебную нагрузку.",
        "body": """В течение семестра студентам важно следить за сроками текущего контроля, регистрацией на дисциплины и итоговой аттестацией.\n\nРекомендуем сверять даты с официальными объявлениями университета: расписание и отдельные сроки могут корректироваться. Сохраните эту публикацию как напоминание и проверяйте обновления на официальных ресурсах TAU.""",
    },
    {
        "slug": "student-media-club",
        "title": "Медиа-клуб приглашает студентов создавать истории о кампусе",
        "category": "Студенческая жизнь",
        "excerpt": "Команда ищет авторов, фотографов и начинающих видеографов для университетского медиапроекта.",
        "body": """Медиа-клуб приглашает студентов попробовать себя в создании материалов о жизни кампуса. Участники смогут работать над интервью, репортажами, фотоподборками и короткими видео.\n\nОпыт необязателен: команда планирует вводные занятия и совместную работу над первыми публикациями. Главное — интерес к историям людей и событий университета.""",
    },
]


class Command(BaseCommand):
    help = "Создаёт демонстрационные категории и публикации TAU News Hub (без дублирования)."

    def handle(self, *args, **options):
        user_model = get_user_model()
        # Демоматериалы принадлежат суперпользователю/редактору, если он есть.
        # Иначе создаётся технический автор без возможности входа.
        Group.objects.get_or_create(name=AUTHOR_GROUP)
        editor_group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
        ensure_editor_group_permissions(editor_group)
        author = user_model.objects.filter(is_superuser=True).order_by("id").first()
        if author is None:
            author = user_model.objects.filter(
                groups__name=EDITOR_GROUP
            ).order_by("id").first()
        if author is None:
            author, created = user_model.objects.get_or_create(
                username="tau_demo_author",
                defaults={"email": "demo-author@localhost"},
            )
            if created:
                author.set_unusable_password()
                author.save(update_fields=["password"])
                self.stdout.write(self.style.WARNING(
                    "Создан технический автор tau_demo_author без пароля для входа."
                ))
            author.groups.add(Group.objects.get(name=AUTHOR_GROUP))

        category_map = {}
        for name, category_slug in CATEGORIES:
            category, created = Category.objects.get_or_create(
                slug=category_slug,
                defaults={"name": name},
            )
            category_map[name] = category
            self.stdout.write(f"{'Создана' if created else 'Есть'} категория: {name}")

        created_count = 0
        for item in ARTICLES:
            category = category_map[item["category"]]
            article, created = Article.objects.get_or_create(
                slug=item["slug"],
                defaults={
                    "title": item["title"],
                    "excerpt": item["excerpt"],
                    "body": item["body"],
                    "category": category,
                    "author": author,
                    "status": Article.Status.PUBLISHED,
                    "is_featured": item.get("featured", False),
                    "published_at": timezone.now(),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Добавлена статья: {article.title}"))
            else:
                self.stdout.write(f"Пропущена (уже существует): {article.title}")

        self.stdout.write(self.style.SUCCESS(
            f"Готово: {len(CATEGORIES)} категорий, создано новых статей: {created_count}."
        ))
        self.stdout.write("Повторный запуск безопасен: существующие публикации не перезаписываются.")
