from django.urls import path

from apps.hardware_requests import views

app_name = "hardware_requests"

urlpatterns = [
    path(
        "public/<slug:makerspace_slug>/checkin/verify",
        views.CheckinVerifyView.as_view(),
        name="checkin-verify",
    ),
    path(
        "public/<slug:makerspace_slug>/requests",
        views.RequestSubmitView.as_view(),
        name="request-submit",
    ),
    path(
        "public/requests/<uuid:public_token>/status",
        views.RequestStatusView.as_view(),
        name="request-status",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/pending-requests",
        views.PendingRequestsView.as_view(),
        name="pending-requests",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/accepted-requests",
        views.AcceptedRequestsView.as_view(),
        name="accepted-requests",
    ),
    path(
        "admin/makerspace/<int:makerspace_id>/active-loans",
        views.ActiveLoansView.as_view(),
        name="active-loans",
    ),
    path(
        "admin/requests/<int:pk>/accept",
        views.AcceptRequestView.as_view(),
        name="request-accept",
    ),
    path(
        "admin/requests/<int:pk>/reject",
        views.RejectRequestView.as_view(),
        name="request-reject",
    ),
    path(
        "admin/requests/<int:pk>/assign-box",
        views.AssignBoxView.as_view(),
        name="request-assign-box",
    ),
    path(
        "admin/requests/<int:pk>/issue",
        views.IssueRequestView.as_view(),
        name="request-issue",
    ),
    path(
        "admin/requests/<int:pk>/return",
        views.ReturnRequestView.as_view(),
        name="request-return",
    ),
]
