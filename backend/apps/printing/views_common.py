from drf_spectacular.utils import OpenApiResponse
from rest_framework.exceptions import ValidationError

from apps.printing.serializers import ErrorSerializer


ERROR_RESPONSES = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid request."),
    401: OpenApiResponse(description="Authentication credentials were not provided."),
    403: OpenApiResponse(description="Permission denied."),
    404: OpenApiResponse(description="Not found."),
}
ACTION_RESPONSES = {
    **ERROR_RESPONSES,
    409: OpenApiResponse(ErrorSerializer, description="Invalid status transition."),
}


def _int_query_param(request, name, *, required=False):
    value = request.query_params.get(name)
    if value in (None, ""):
        if required:
            raise ValidationError({name: "This query parameter is required."})
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Must be an integer."}) from exc
