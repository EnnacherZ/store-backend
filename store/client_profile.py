"""
store/client_profile.py
Client-facing auth + profile endpoints.
"""
import os, traceback, uuid
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.conf import settings

from dotenv import load_dotenv

from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import ClientProfile, Client, Order
from dashboard.authentication import CookieJWTAuthentication
from dashboard.permissions import OriginPermission

load_dotenv()
User = get_user_model()

_frontend_url = os.environ.get('ORIGIN', 'https://www.alfirdaousstore.com')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _activation_url(code: uuid.UUID) -> str:
    return f"{_frontend_url}/account/activate/{code}/"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    common = dict(httponly=True, secure=True, samesite='None', path='/')
    response.set_cookie(key='access_token',  value=access,  max_age=3600 * 24, **common)
    response.set_cookie(key='refresh_token', value=refresh, max_age=3600 * 24, **common)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie('access_token',  samesite='None', path='/')
    response.delete_cookie('refresh_token', samesite='None', path='/')


def _profile_payload(user, profile) -> dict:
    """
    Single source of truth for the /me/ response shape.
    Keeps MeClientView and UpdateClientProfileView in sync.
    """
    return {
        'email':          user.email,
        'first_name':     user.first_name,
        'last_name':      user.last_name,
        # image lives on AuthUser (Cloudinary FileField)
        'image':          user.image.url if user.image else None,
        # profile fields — safe even if profile row is None
        'phone':          profile.phone          if profile else None,
        'address':        profile.address        if profile else None,
        'city':           profile.city           if profile else None,
        'country':        profile.country        if profile else None,
        'loyalty_points': profile.loyalty_points if profile else 0,
    }


# ── Permission ────────────────────────────────────────────────────────────────

class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'client'
        )


# ════════════════════════════════════════════════════════════════════════════
# SIGN UP
# ════════════════════════════════════════════════════════════════════════════

class SignUpClientView(APIView):
    permission_classes = [OriginPermission]
 
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
                phone   = data.get('phone',   ''),
                address = data.get('address', ''),
                city    = data.get('city',    ''),
                country = data.get('country', ''),
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
 

# ════════════════════════════════════════════════════════════════════════════
# ACTIVATE
# ════════════════════════════════════════════════════════════════════════════

class ActivateClientView(APIView):
    permission_classes = [OriginPermission]

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


# ════════════════════════════════════════════════════════════════════════════
# SIGN IN
# ════════════════════════════════════════════════════════════════════════════

class SignInClientView(APIView):
    permission_classes = [OriginPermission]

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
            return Response({'error': 'Identifiants invalides.'}, status=status.HTTP_400_BAD_REQUEST)

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

        response = Response({'message': 'Connexion réussie.'}, status=status.HTTP_200_OK)
        _set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


# ════════════════════════════════════════════════════════════════════════════
# ME  — GET current profile
# ════════════════════════════════════════════════════════════════════════════

class MeClientView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsClient]

    def get(self, request):
        user    = request.user
        profile = getattr(user, 'client_profile', None)
        return Response(_profile_payload(user, profile), status=status.HTTP_200_OK)


# ════════════════════════════════════════════════════════════════════════════
# UPDATE PROFILE — PATCH /api/client/me/update/
#
# Accepts JSON body with any subset of:
#   first_name, last_name, phone, address, city, country
# Does NOT accept image here — image has its own endpoint below.
# ════════════════════════════════════════════════════════════════════════════

# Fields that live on AuthUser
_USER_FIELDS    = {'first_name', 'last_name'}
# Fields that live on ClientProfile
_PROFILE_FIELDS = {'phone', 'address', 'city', 'country'}
# All allowed fields
_ALLOWED_FIELDS = _USER_FIELDS | _PROFILE_FIELDS


class UpdateClientProfileView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsClient]
    parser_classes         = [JSONParser]

    def patch(self, request):
        # Only keep recognised keys; silently drop anything else.
        data = {k: v for k, v in request.data.items() if k in _ALLOWED_FIELDS}

        if not data:
            return Response(
                {'detail': 'No valid fields provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = request.user

                # ── AuthUser fields ──────────────────────────────────────
                user_fields_to_save = []
                for field in _USER_FIELDS:
                    if field in data:
                        setattr(user, field, data[field])
                        user_fields_to_save.append(field)
                if user_fields_to_save:
                    user.save(update_fields=user_fields_to_save)

                # ── ClientProfile fields ─────────────────────────────────
                profile, _ = ClientProfile.objects.get_or_create(user=user)
                profile_fields_to_save = []
                for field in _PROFILE_FIELDS:
                    if field in data:
                        setattr(profile, field, data[field])
                        profile_fields_to_save.append(field)
                if profile_fields_to_save:
                    profile.save(update_fields=profile_fields_to_save)

        except Exception as exc:
            return Response(
                {'detail': f'Update failed: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(_profile_payload(user, profile), status=status.HTTP_200_OK)


# ════════════════════════════════════════════════════════════════════════════
# AVATAR UPDATE — PATCH /api/client/me/avatar/
#
# Accepts multipart/form-data with a single field: image (file).
# Saves directly to AuthUser.image (Cloudinary FileField).
# ════════════════════════════════════════════════════════════════════════════

class AvatarUpdateView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsClient]
    parser_classes         = [MultiPartParser, FormParser]

    def patch(self, request):
        image_file = request.FILES.get('image')

        if not image_file:
            return Response(
                {'detail': 'No image file provided. Send a multipart field named "image".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Basic content-type guard — Cloudinary will also validate on its end
        if not image_file.content_type.startswith('image/'):
            return Response(
                {'detail': 'Uploaded file is not an image.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        # Assign the new file — Cloudinary storage handles the upload
        user.image = image_file
        user.save(update_fields=['image'])

        return Response(
            {'image': user.image.url},
            status=status.HTTP_200_OK,
        )


# ════════════════════════════════════════════════════════════════════════════
# REFRESH
# ════════════════════════════════════════════════════════════════════════════

class RefreshClientTokenView(APIView):
    permission_classes = [OriginPermission]

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
            max_age=3600 * 24, path='/',
        )
        return response


# ════════════════════════════════════════════════════════════════════════════
# SIGN OUT
# ════════════════════════════════════════════════════════════════════════════

class SignOutClientView(APIView):
    permission_classes = [OriginPermission]

    def post(self, request):
        response = Response({'message': 'Déconnexion réussie.'}, status=status.HTTP_200_OK)
        _clear_auth_cookies(response)
        return response


# ════════════════════════════════════════════════════════════════════════════
# CLIENT ORDERS
# ════════════════════════════════════════════════════════════════════════════

class ClientOrdersView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsClient]

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