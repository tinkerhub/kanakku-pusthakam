from apps.hardware_requests.workflow_errors import (
    BoxUnavailable,
    BoxValidationError,
    InvalidTransition,
    RequestValidationError,
    RequesterBlocked,
)
from apps.inventory.availability import InsufficientStock

WORKFLOW_EXCEPTIONS = (
    InvalidTransition,
    RequestValidationError,
    RequesterBlocked,
    BoxUnavailable,
    BoxValidationError,
    InsufficientStock,
)
