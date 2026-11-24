"""Безопасная проверка и нормализация загружаемых изображений."""

from io import BytesIO
import warnings

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_WIDTH = 6000
MAX_IMAGE_HEIGHT = 6000
MAX_IMAGE_PIXELS = 25_000_000

ALLOWED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


class InvalidImageError(ValueError):
    """Возникает, если файл не проходит ограничения загрузки."""


def normalize_uploaded_image(uploaded_file):
    """Проверяет изображение и пересохраняет его без исходных метаданных.

    Пересохранение помогает убрать EXIF/GPS-метаданные и не позволяет
    полагаться только на расширение или MIME-тип, присланные браузером.
    """
    if uploaded_file.size > MAX_IMAGE_SIZE:
        raise InvalidImageError("Размер обложки не должен превышать 5 МБ.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as source:
                image_format = source.format
                width, height = source.size
                if image_format not in ALLOWED_FORMATS:
                    raise InvalidImageError("Допустимые форматы обложки: JPEG, PNG и WebP.")
                if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
                    raise InvalidImageError("Размеры обложки не должны превышать 6000×6000 пикселей.")
                if width * height > MAX_IMAGE_PIXELS:
                    raise InvalidImageError("Изображение содержит слишком много пикселей.")
                source.verify()

            # verify() проверяет структуру, поэтому для чтения пикселей файл
            # открывается повторно. EXIF-поворот применяется до сохранения.
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as source:
                image = ImageOps.exif_transpose(source)
                if image_format == "JPEG":
                    image = image.convert("RGB")
                elif image_format in {"PNG", "WEBP"}:
                    has_alpha = "A" in image.getbands() or "transparency" in image.info
                    image = image.convert("RGBA" if has_alpha else "RGB")

                output = BytesIO()
                save_options = {"optimize": True}
                if image_format in {"JPEG", "WEBP"}:
                    save_options["quality"] = 88
                image.save(output, format=image_format, **save_options)

        content = output.getvalue()
        if len(content) > MAX_IMAGE_SIZE:
            raise InvalidImageError(
                "После обработки изображение всё ещё превышает допустимый размер 5 МБ."
            )

        extension = ALLOWED_FORMATS[image_format]
        return ContentFile(content, name=f"cover.{extension}")
    except InvalidImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise InvalidImageError("Не удалось прочитать изображение. Загрузите корректный файл.") from error
    finally:
        uploaded_file.seek(0)
