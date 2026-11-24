from .models import Category
from .permissions import get_user_role_label, is_author, is_editor


def site_categories(request):
    """Общие данные навигации и флаг доступа к панели редактора."""
    user = request.user
    return {
        "nav_categories": Category.objects.all(),
        "can_access_dashboard": is_author(user),
        "can_moderate": is_editor(user),
        "role_label": get_user_role_label(user) if user.is_authenticated else "",
    }
