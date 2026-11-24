from django import template
from django.utils.safestring import mark_safe

from news.markdown_utils import render_markdown

register = template.Library()


@register.filter
def render_article_markdown(value):
    """Выводит только HTML, очищенный серверным allowlist-санитайзером."""
    return mark_safe(render_markdown(value))
