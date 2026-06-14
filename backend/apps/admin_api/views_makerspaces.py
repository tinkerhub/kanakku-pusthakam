from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_makerspaces import (
    MakerspaceSerializer,
    ReturnPolicySerializer,
    TenantFrontendSerializer,
)
from apps.audit import services as audit
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, TenantFrontend


@extend_schema(tags=["Admin makerspaces"], summary="List or create makerspaces")
class MakerspaceListCreateView(generics.ListCreateAPIView):
    serializer_class = MakerspaceSerializer
    permission_classes = [IsActiveStaff]
    pagination_class = None

    def get_queryset(self):
        return rbac.scope_by_action(self.request.user, rbac.Action.VIEW_INVENTORY, Makerspace.objects.all(), field="id").order_by("name")

    def perform_create(self, serializer):
        if not (self.request.user.is_superuser or self.request.user.role == User.Role.SUPERADMIN):
            raise PermissionDenied()
        instance = serializer.save(created_by=self.request.user)
        audit.record(
            self.request.user,
            "makerspace.created",
            makerspace=instance,
            target=instance,
        )


@extend_schema(tags=["Admin makerspaces"], summary="Retrieve or update a makerspace")
class MakerspaceDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MakerspaceSerializer
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        action = (
            rbac.Action.MANAGE_MAKERSPACE
            if self.request.method == "PATCH"
            else rbac.Action.VIEW_INVENTORY
        )
        return rbac.scope_by_action(self.request.user, action, Makerspace.objects.all(), field="id")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit.record(
            self.request.user,
            "makerspace.updated",
            makerspace=instance,
            target=instance,
        )


@extend_schema(tags=["Admin makerspaces"], summary="Retrieve or update return policy")
class ReturnPolicyView(generics.RetrieveUpdateAPIView):
    serializer_class = ReturnPolicySerializer
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        makerspace_id = self.kwargs["makerspace_id"]
        require_action(self.request.user, rbac.Action.ACCEPT_REQUEST, makerspace_id)
        return get_object_or_404(Makerspace, pk=makerspace_id)

    def perform_update(self, serializer):
        instance = serializer.save()
        audit.record(
            self.request.user,
            "makerspace.return_policy_updated",
            makerspace=instance,
            target=instance,
            meta={"default_loan_days": instance.default_loan_days},
        )


@extend_schema(tags=["Tenant bootstrap"], summary="List or create registered tenant frontends")
class TenantFrontendListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantFrontendSerializer
    permission_classes = [IsActiveStaff]

    def get_queryset(self):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        return TenantFrontend.objects.filter(makerspace_id=makerspace_id).order_by("frontend_type", "hostname")

    def perform_create(self, serializer):
        makerspace_id = self.kwargs["makerspace_id"]
        require_module(makerspace_id, "staff_admin")
        require_action(self.request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        frontend = serializer.save(makerspace_id=makerspace_id, created_by=self.request.user)
        audit.record(
            self.request.user,
            "tenant_frontend.created",
            makerspace=frontend.makerspace,
            target=frontend,
        )


@extend_schema(tags=["Tenant bootstrap"], summary="Retrieve or update registered tenant frontend")
class TenantFrontendDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TenantFrontendSerializer
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return rbac.scope_by_action(
            self.request.user,
            rbac.Action.MANAGE_MAKERSPACE,
            TenantFrontend.objects.select_related("makerspace"),
        )

    def perform_update(self, serializer):
        frontend = serializer.save()
        audit.record(
            self.request.user,
            "tenant_frontend.updated",
            makerspace=frontend.makerspace,
            target=frontend,
        )
