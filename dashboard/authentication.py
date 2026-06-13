from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

# Roles that are allowed to access dashboard/admin endpoints
DASHBOARD_ROLES = frozenset({'admin', 'manager', 'delivery'})


class CookieJWTAuthentication(JWTAuthentication):
    """
    Generic cookie-based JWT authenticator.
    Used by client-facing endpoints (store/client_profile.py).
    Reads `access_token` from httpOnly cookies — no role filtering.
    """
    def authenticate(self, request):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None
        try:                                         # ← wrap this
            validated_token = self.get_validated_token(access_token)
            return self.get_user(validated_token), validated_token
        except Exception:
            return None 


class DashboardCookieJWTAuthentication(CookieJWTAuthentication):
    """
    Dashboard-only cookie authenticator.
    Extends the base class and hard-rejects any token whose role is
    not in DASHBOARD_ROLES — so a client cookie can never authenticate
    against a dashboard view, even if a permission class is missing.
    """
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if getattr(user, 'role', None) not in DASHBOARD_ROLES:
            raise AuthenticationFailed(
                'Accès refusé : rôle insuffisant pour le tableau de bord.'
            )
        return user, token