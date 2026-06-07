"""
store/client_profile.py
Client-facing auth endpoints:
  POST  /api/client/signup/
  GET   /api/client/activate/<uuid>/
  POST  /api/client/signin/
  GET   /api/client/me/
  POST  /api/client/refresh/
  POST  /api/client/signout/
  GET   /api/client/orders/
"""
import os, traceback, uuid
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from dotenv import load_dotenv

from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import ClientProfile, Client, Order
from dashboard.authentication import CookieJWTAuthentication

load_dotenv()
User = get_user_model()

_frontend_url = os.environ.get('REQUEST_ALLOWED_ORIGINS', '')


def _activation_url(code: uuid.UUID) -> str:
    return f"{_frontend_url}account/activate/{code}/"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    common = dict(httponly=True, secure=True, samesite='None', path='/')
    response.set_cookie(key='access_token',  value=access,  max_age=3600 * 8,  **common)
    response.set_cookie(key='refresh_token', value=refresh, max_age=3600 * 24, **common)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie('access_token',  samesite='None', path='/')
    response.delete_cookie('refresh_token', samesite='None', path='/')


class IsClient(permissions.BasePermission):
    """Allows only authenticated users whose role is 'client'."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'client'
        )


# ─── Sign Up ──────────────────────────────────────────────────────────────────

class SignUpClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        try:
            required = ['email', 'password', 'first_name', 'last_name']
            missing  = [f for f in required if not data.get(f)]
            if missing:
                return Response(
                    {'error': f"Champs manquants : {', '.join(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = data['email'].strip().lower()

            if User.objects.filter(username=email).exists():
                return Response(
                    {'error': 'Un compte avec cet email existe déjà.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_user(
                username   = email,
                email      = email,
                password   = data['password'],
                first_name = data['first_name'],
                last_name  = data['last_name'],
                role       = 'client',
                is_active  = False,
            )

            profile = ClientProfile.objects.create(
                user    = user,
                phone   = data.get('phone', ''),
                address = data.get('address', ''),
            )

            send_mail(
                'Activez votre compte Al-Firdaous Store',
                (
                    f"Bonjour {user.first_name},\n\n"
                    f"Cliquez sur ce lien pour activer votre compte :\n"
                    f"{_activation_url(profile.activation_code)}\n\n"
                    f"À bientôt sur Al-Firdaous Store !"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            return Response(
                {'message': 'Compte créé. Vérifiez votre boîte mail pour activer votre compte.'},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            traceback.print_exc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ─── Activate ─────────────────────────────────────────────────────────────────

class ActivateClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, activation_code):
        try:
            profile = ClientProfile.objects.select_related('user').get(
                activation_code=activation_code
            )
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': "Lien d'activation invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.user.is_active:
            return Response({'message': 'Compte déjà activé.'}, status=status.HTTP_200_OK)

        profile.user.is_active  = True
        profile.user.save(update_fields=['is_active'])
        profile.activation_date = datetime.now()
        profile.save(update_fields=['activation_date'])

        return Response({'message': 'Compte activé avec succès !'}, status=status.HTTP_200_OK)


# ─── Sign In ──────────────────────────────────────────────────────────────────

class SignInClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email    = request.data.get('email', '').strip().lower()
        password = request.data.get('mot_de_passe', '')

        try:
            user = User.objects.get(username=email, role='client')
        except User.DoesNotExist:
            return Response(
                {'error': 'Identifiants invalides.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(password):
            return Response(
                {'error': 'Identifiants invalides.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {'error': 'Compte non activé. Vérifiez votre boîte mail.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        refresh['role']       = user.role
        refresh['username']   = user.username
        refresh['first_name'] = user.first_name
        refresh['last_name']  = user.last_name

        response = Response(
            {
                'message': 'Connexion réussie.',
                'user': {
                    'email':      user.email,
                    'first_name': user.first_name,
                    'last_name':  user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )
        _set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


# ─── Me ───────────────────────────────────────────────────────────────────────

class MeClientView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated, IsClient]

    def get(self, request):
        user    = request.user
        profile = getattr(user, 'client_profile', None)

        return Response({
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'phone':      profile.phone    if profile else None,
            'address':    profile.address  if profile else None,
            'image'  :    user.image.url       if user.image.url else ''  
        }, status=status.HTTP_200_OK)


# ─── Refresh ──────────────────────────────────────────────────────────────────

class RefreshClientTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_str = request.COOKIES.get('refresh_token')
        if not refresh_str:
            return Response({'error': 'Non authentifié.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            token        = RefreshToken(refresh_str)
            access_token = str(token.access_token)
        except TokenError:
            return Response(
                {'error': 'Session expirée. Veuillez vous reconnecter.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({'message': 'Token rafraîchi.'}, status=status.HTTP_200_OK)
        response.set_cookie(
            key='access_token', value=access_token,
            httponly=True, secure=True, samesite='None',
            max_age=3600 * 8, path='/',
        )
        return response


# ─── Sign Out ─────────────────────────────────────────────────────────────────

class SignOutClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({'message': 'Déconnexion réussie.'}, status=status.HTTP_200_OK)
        _clear_auth_cookies(response)
        return response


# ─── Client orders ────────────────────────────────────────────────────────────

class ClientOrdersView(APIView):
    """
    GET /api/client/orders/
    Returns all orders for the logged-in client, matched by email.
    Orders are linked via Client.email because Client is a checkout form
    model that may have been filled as a guest (no direct FK to AuthUser).
    Registered-client orders are also linked via Client.profile, but email
    matching covers both cases uniformly.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated, IsClient]

    def get(self, request):
        email   = request.user.email
        clients = Client.objects.filter(email=email)

        if not clients.exists():
            return Response([], status=status.HTTP_200_OK)

        orders = (
            Order.objects
            .filter(client__in=clients)
            .prefetch_related('ordered_products')
            .select_related('client')
            .order_by('-date')
        )

        data = [
            {
                'order_id':       str(o.order_id),
                'date':           o.date.isoformat() if o.date else None,
                'amount':         o.amount,
                'currency':       o.currency,
                'is_paid':        o.is_paid,
                'status':         o.status,
                'delivered':      o.delivered,
                'payment_mode':   'online' if o.payment_mode else 'cod',
                'transaction_id': o.transaction_id,
                'products': [
                    {
                        'name':         op.name,
                        'product_type': op.product_type,
                        'category':     op.category,
                        'ref':          op.ref,
                        'size':         op.size,
                        'quantity':     op.quantity,
                        'price':        op.price,
                        'available':    op.available,
                        'product_id':   op.product_id,
                    }
                    for op in o.ordered_products.all()
                ],
            }
            for o in orders
        ]

        return Response(data, status=status.HTTP_200_OK)
    

"""
api/client/views.py  (relevant section)

PATCH /api/client/me/update/

Accepts: { first_name, last_name, phone, address }
Updates AuthUser.first_name / last_name and ClientProfile.phone / address
in a single atomic transaction so the two models are never half-updated.

Auth: ClientCookieJWTAuthentication + IsAuthenticated + IsClientUser
      (same pattern used by the rest of your client API views)
"""

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import ClientProfile                      # adjust import path


# ── Serializer ────────────────────────────────────────────────────────────────

class UpdateProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name  = serializers.CharField(max_length=150, required=False)
    phone      = serializers.CharField(max_length=20,  required=False, allow_blank=True)
    address    = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("No fields provided.")
        return attrs


# ── View ──────────────────────────────────────────────────────────────────────

class UpdateClientProfileView(APIView):
    """
    PATCH /api/client/me/update/

    Partial update: only the fields present in the request body are changed.
    Atomically writes to both AuthUser and ClientProfile.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated, IsClient]

    def patch(self, request):
        serializer = UpdateProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            with transaction.atomic():
                user = request.user

                # ── AuthUser fields ───────────────────────────────────────
                user_dirty = False
                if "first_name" in data:
                    user.first_name = data["first_name"]
                    user_dirty = True
                if "last_name" in data:
                    user.last_name = data["last_name"]
                    user_dirty = True
                if user_dirty:
                    user.save(update_fields=["first_name", "last_name"])

                # ── ClientProfile fields ──────────────────────────────────
                # get_or_create guards against a missing profile row
                profile, _ = ClientProfile.objects.get_or_create(user=user)
                profile_dirty = False
                if "phone" in data:
                    profile.phone = data["phone"]
                    profile_dirty = True
                if "address" in data:
                    profile.address = data["address"]
                    profile_dirty = True
                if profile_dirty:
                    profile.save(update_fields=["phone", "address"])

        except Exception as exc:
            return Response(
                {"detail": f"Update failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Return the refreshed user data so the frontend can update its cache
        return Response({
            "first_name": user.first_name,
            "last_name":  user.last_name,
            "email":      user.email,
            "phone":      profile.phone,
            "address":    profile.address,
        }, status=status.HTTP_200_OK)