"""
Маршруты приложения core.
"""

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_redirect, name="home"),

    # Заявки (Менеджер)
    path("trips/", views.trip_list, name="trip_list"),
    path("trips/create/", views.trip_create, name="trip_create"),
    path("trips/<int:pk>/", views.trip_detail, name="trip_detail"),
    path("trips/<int:pk>/edit/", views.trip_edit, name="trip_edit"),
    path("trips/<int:pk>/delete/", views.trip_delete, name="trip_delete"),
    path("trips/<int:pk>/history/", views.trip_history, name="trip_history"),

    # Рейсы (Логист)
    path("requests/", views.request_list, name="request_list"),
    path("requests/<int:pk>/edit/", views.request_edit, name="request_edit"),
    path("requests/<int:pk>/mark-viewed/", views.request_mark_viewed, name="request_mark_viewed"),

    # Отчёты, Профиль, Настройки
    path("reports/", views.report_index, name="report_index"),
    path("profile/", views.profile_index, name="profile_index"),
    path("settings/", views.settings_index, name="settings_index"),
    path("settings/users/", views.settings_users, name="settings_users"),
    path("settings/users/<int:pk>/edit/", views.settings_user_edit, name="settings_user_edit"),

    # AJAX: селекты, поиск, создание
    path("ajax/selects/<str:kind>/", views.ajax_dependent_select, name="ajax_dependent_select"),
    path("ajax/search/<str:kind>/", views.ajax_search, name="ajax_search"),
    path("ajax/create/<str:kind>/", views.ajax_create_lookup, name="ajax_create_lookup"),
    path("ajax/preferences/save/", views.ajax_save_preferences, name="ajax_save_preferences"),

    # AJAX: управление справочниками
    path("ajax/lookup/<str:kind>/<int:pk>/", views.ajax_get_lookup_details, name="ajax_get_lookup_details"),
    path("ajax/lookup/<str:kind>/<int:pk>/edit/", views.ajax_edit_lookup, name="ajax_edit_lookup"),
    path("ajax/driver/<int:pk>/delete/", views.ajax_delete_driver, name="ajax_delete_driver"),
    path("ajax/vehicle/<int:pk>/delete/", views.ajax_delete_vehicle, name="ajax_delete_vehicle"),
    path("ajax/driver/<int:pk>/edit/", views.ajax_edit_driver, name="ajax_edit_driver"),
    path("ajax/vehicle/<int:pk>/edit/", views.ajax_edit_vehicle, name="ajax_edit_vehicle"),

    # AJAX: адреса заказчиков
    path("ajax/customer/<int:pk>/addresses/", views.ajax_get_customer_addresses, name="ajax_get_customer_addresses"),
    path("ajax/customer/<int:pk>/address/add/", views.ajax_add_customer_address, name="ajax_add_customer_address"),
    path("ajax/customer-address/<int:pk>/edit/", views.ajax_edit_customer_address, name="ajax_edit_customer_address"),
    path("ajax/customer-address/<int:pk>/delete/", views.ajax_delete_customer_address, name="ajax_delete_customer_address"),

    # Рейсы водителей (новая страница логиста)
    path("driver-trips/", views.driver_trips_list, name="driver_trips_list"),
]