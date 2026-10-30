"""
Корневая маршрутизация проекта DiLS.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # ---------- Аутентификация ----------
    # Явные пути /login/ и /logout/ (используются в LOGIN_URL в settings.py
    # и в navbar.html через {% url 'logout' %}).
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="auth/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # ---------- Приложение ----------
    path("", include("core.urls")),
]

# В режиме DEBUG раздаём медиа и статику через Django
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)