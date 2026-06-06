from django.test import TestCase


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
import json
import logging

from store.models import Order

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def youcanpay_webhook(request):
    try:
        payload = json.loads(request.body)

        logger.info("🔥 Webhook received: %s", payload)

        event_name = payload.get("event_name")
        data = payload.get("payload", {})

        transaction = data.get("transaction", {})
        transaction_id = transaction.get("id")
        order_id = transaction.get("order_id")
        status = transaction.get("status")

        # 🔥 TEST LOGIC ONLY (NO DB Y
        the_order = Order.objects.get(order_id = order_id)
        if the_order.payment_mode and the_order.is_paid=='pending' :
            the_order.transaction_id = transaction_id
            if event_name == "transaction.paid" and status == 1:
                the_order.is_paid = 'confirmed'
            else: 
                the_order.is_paid = 'failed'
            the_order.save()

        return JsonResponse({"received": True}, status=200)

    except Exception as e:
        logger.error("Webhook error: %s", str(e))
        return JsonResponse({"received": False, "error": str(e)}, status=200)
    

"""
Add these two views to your existing views.py.
Also add to urls.py:
  path('api/client/me/',      MeClientView.as_view()),
  path('api/client/signout/', SignOutClientView.as_view()),
"""

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import ClientProfile


class ClientJWTAuthentication:
    """
    Minimal cookie-based JWT authenticator.
    Reads `client_access_token_alfirdaousstore` from request cookies,
    validates it, and returns the matching LoyalClient.

    Usage — call from any view:
        client, err_response = ClientJWTAuthentication.authenticate(request)
        if err_response:
            return err_response
    """
    COOKIE = "client_access_token_alfirdaousstore"

    @staticmethod
    def authenticate(request):
        token_str = request.COOKIES.get(ClientJWTAuthentication.COOKIE)
        if not token_str:
            return None, Response(
                {"error": "Non authentifié"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token   = AccessToken(token_str)
            user_id = token["user_id"]
            client  = ClientProfile.objects.get(pk=user_id)
            return client, None
        except (TokenError, ClientProfile.DoesNotExist, KeyError):
            return None, Response(
                {"error": "Session expirée, veuillez vous reconnecter."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class MeClientView(APIView):
    """
    GET /api/client/me/
    Returns the profile of the currently authenticated client.
    The React context calls this on mount to restore the session.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client, err = ClientJWTAuthentication.authenticate(request)
        if err:
            return err

        return Response({
            "email":      client.email,
            "first_name": client.first_name,
            "last_name":  client.last_name,
            "phone":      client.phone,
            "address":    client.address,
        }, status=status.HTTP_200_OK)


class SignOutClientView(APIView):
    """
    POST /api/client/signout/
    Clears the httpOnly cookies — the only way to invalidate them from the server.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({"message": "Déconnexion réussie."}, status=status.HTTP_200_OK)
        response.delete_cookie(
            "client_access_token_alfirdaousstore",
            path="/",
            samesite="None",
        )
        response.delete_cookie(
            "client_refresh_token_alfirdaousstore",
            path="/",
            samesite="None",
        )
        return response