"""Преобразование Markdown в HTML с обязательной очисткой результата."""

import mistune
import nh3

# Рендерер экранирует произвольный HTML из исходного текста. nh3 дополнительно
# применяет allowlist к тегам, атрибутам и URL-протоколам.
MARKDOWN = mistune.create_markdown(
    escape=True,
    plugins=["table", "strikethrough"],
)

ALLOWED_TAGS = {
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4",
    "hr", "li", "ol", "p", "pre", "strong", "table", "tbody", "td",
    "th", "thead", "tr", "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "code": {"class"},
}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def render_markdown(source):
    """Рендерит Markdown и удаляет небезопасные HTML-теги и атрибуты."""
    rendered = MARKDOWN(source or "")
    return nh3.clean(
        rendered,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )
