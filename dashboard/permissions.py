from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

from dotenv import load_dotenv
import os

load_dotenv()

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("REQUEST_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]



class IsAdmin(BasePermission):
    """Only admin role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsManager(BasePermission):
    """Admin or manager role (can manage products, orders, etc.)."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('admin', 'manager')
        )


class IsDeliveryMan(BasePermission):
    """Delivery or admin role."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('delivery', 'admin')
        )


class IsDashboardUser(BasePermission):
    """Any non-client dashboard user (admin / manager / delivery)."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('admin', 'manager', 'delivery')
        )

class OriginPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "OPTIONS":
            return True
        referer = request.META.get("HTTP_REFERER", "")

        if referer not in ALLOWED_ORIGINS:
            raise PermissionDenied("Forbidden")

        return True