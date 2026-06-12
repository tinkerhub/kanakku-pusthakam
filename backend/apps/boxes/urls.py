from django.urls import path

from apps.boxes import api_views

urlpatterns = [
    path("qr/boxes", api_views.CreateBoxQrView.as_view(), name="qr-boxes"),
    path("qr/tools", api_views.CreateToolQrView.as_view(), name="qr-tools"),
    path("qr/scan", api_views.QrScanView.as_view(), name="qr-scan"),
    path("qr/<int:pk>/print", api_views.QrPrintView.as_view(), name="qr-print"),
    path("qr/<int:pk>/revoke", api_views.QrRevokeView.as_view(), name="qr-revoke"),
]

