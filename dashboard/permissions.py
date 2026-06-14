from rest_framework.permissions import BasePermission
from dotenv import load_dotenv
import os

load_dotenv()

allowed_origins = os.environ.get('REQUEST_ALLOWED_ORIGINS')
ALLOWED_ORIGINS = [allowed_origins]



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
        referer = request.META.get("HTTP_REFERER", "")
        return referer in ALLOWED_ORIGINS