"""
Конфигурация приложения core.

Здесь подключаются сигналы (логирование изменений Trip и т.п.).
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Логистическая система DiLS"

    def ready(self) -> None:
        # Импорт сигналов регистрирует их.
        # Важно: импорт должен быть внутри ready(), иначе модели
        # ещё не готовы на момент загрузки apps.
        from . import signals  # noqa: F401