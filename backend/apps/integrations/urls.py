from django.urls import path

from apps.integrations import views

urlpatterns = [
    path("telegram/webhook", views.TelegramWebhookView.as_view(), name="telegram-webhook"),
    path("telegram/test-alert", views.TelegramTestAlertView.as_view(), name="telegram-test-alert"),
]

