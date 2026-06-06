# client/views.py
import traceback, os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import ClientProfile, Client, Order
from dashboard.authentication import CookieJWTAuthentication  # reuse existing ✓

load_dotenv()

User = get_user_model()  # → AuthUser


frontend_url = os.environ.get('REQUEST_ALLOWED_ORIGINS')

def get_activation_url(code):
    base = frontend_url
    return f"{base}account/activate/{code}/"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Exactly the same cookie flags as CustomTokenObtainPairView in dashboard."""
    common = dict(httponly=True, secure=True, samesite='None', path='/')
    response.set_cookie(key='access_token',   value=access_token,   max_age=3600 * 24, **common)
    response.set_cookie(key='refresh_token',  value=refresh_token,  max_age=3600 * 24, **common)


def clear_auth_cookies(response: Response):
    response.delete_cookie('access_token',  samesite='None', path='/')
    response.delete_cookie('refresh_token', samesite='None', path='/')


# ── Guard: only allow role=client through client endpoints ───────────────────
class IsClient(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'client'
        )


# ════════════════════════════════════════════════════════════════════════════
# SIGN UP — creates AuthUser(role=client) + ClientProfile
# ════════════════════════════════════════════════════════════════════════════
class SignUpClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        try:
            # Validate required fields
            required = ['email', 'password', 'first_name', 'last_name']
            missing = [f for f in required if not data.get(f)]
            if missing:
                return Response(
                    {"error": f"Champs manquants : {', '.join(missing)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            email = data['email'].strip().lower()

            if User.objects.filter(username=email).exists():
                return Response(
                    {"error": "Un compte avec cet email existe déjà."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # AuthUser — username = email (unique identifier for clients)
            user = User.objects.create_user(
                username   = email,
                password   = data['password'],
                email      = email,
                first_name = data['first_name'],
                last_name  = data['last_name'],
                role       = 'client',
                is_active  = False,   # not active until email confirmed
            )

            # ClientProfile — extra fields
            profile = ClientProfile.objects.create(
                user    = user,
                phone   = data.get('phone', ''),
                address = data.get('address', ''),
            )

            # Send activation email
            activation_url = get_activation_url(profile.activation_code)
            send_mail(
                'Activez votre compte Al-Firdaous Store',
                (
                    f"Bonjour {user.first_name},\n\n"
                    f"Cliquez sur ce lien pour activer votre compte :\n{activation_url}\n\n"
                    f"À bientôt sur Al-Firdaous Store !"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            return Response(
                {"message": "Compte créé. Vérifiez votre boîte mail pour activer votre compte."},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ════════════════════════════════════════════════════════════════════════════
# ACTIVATE — called from the link in the email
# ════════════════════════════════════════════════════════════════════════════
class ActivateClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, activation_code):
        try:
            profile = ClientProfile.objects.select_related('user').get(
                activation_code=activation_code
            )
        except ClientProfile.DoesNotExist:
            return Response(
                {"error": "Lien d'activation invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.user.is_active:
            return Response({"message": "Compte déjà activé."}, status=status.HTTP_200_OK)

        profile.user.is_active  = True
        profile.user.save(update_fields=['is_active'])
        profile.activation_date = datetime.now()
        profile.save(update_fields=['activation_date'])

        return Response({"message": "Compte activé avec succès !"}, status=status.HTTP_200_OK)


# ════════════════════════════════════════════════════════════════════════════
# SIGN IN — reuses your existing CustomTokenObtainPairView cookie logic
# but restricted to role=client
# ════════════════════════════════════════════════════════════════════════════
class SignInClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email        = request.data.get('email', '').strip().lower()
        mot_de_passe = request.data.get('mot_de_passe', '')

        try:
            user = User.objects.get(username=email, role='client')
        except User.DoesNotExist:
            return Response(
                {"error": "Identifiants invalides."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(mot_de_passe):
            return Response(
                {"error": "Identifiants invalides."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {"error": "Compte non activé. Vérifiez votre boîte mail."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Build tokens exactly like CustomTokenObtainPairSerializer.get_token()
        refresh = RefreshToken.for_user(user)
        refresh['role']       = user.role
        refresh['username']   = user.username
        refresh['first_name'] = user.first_name
        refresh['last_name']  = user.last_name

        response = Response({"message": "Connexion réussie."}, status=status.HTTP_200_OK)
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


# ════════════════════════════════════════════════════════════════════════════
# ME — reuses CookieJWTAuthentication (same as dashboard CheckAuthView)
# ════════════════════════════════════════════════════════════════════════════
class MeClientView(APIView):
    authentication_classes = [CookieJWTAuthentication]   # existing ✓
    permission_classes     = [IsAuthenticated, IsClient]  # blocks non-clients

    def get(self, request):
        user = request.user
        try:
            profile = user.client_profile  # OneToOne reverse accessor
        except ClientProfile.DoesNotExist:
            profile = None

        return Response({
            "email":      user.email,
            "first_name": user.first_name,
            "last_name":  user.last_name,
            "phone":      profile.phone    if profile else None,
            "address":    profile.address  if profile else None,
        }, status=status.HTTP_200_OK)


# ════════════════════════════════════════════════════════════════════════════
# REFRESH — reuses your existing RefreshTokenCookieVieww logic
# ════════════════════════════════════════════════════════════════════════════
class RefreshClientTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_str = request.COOKIES.get('refresh_token')
        if not refresh_str:
            return Response({"error": "Non authentifié."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            token        = RefreshToken(refresh_str)
            access_token = str(token.access_token)
        except TokenError:
            return Response(
                {"error": "Session expirée. Veuillez vous reconnecter."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"message": "Token rafraîchi."}, status=status.HTTP_200_OK)
        response.set_cookie(
            key='access_token', value=access_token,
            httponly=True, secure=True, samesite='None',
            max_age=3600 * 24, path='/',
        )
        return response


# ════════════════════════════════════════════════════════════════════════════
# SIGN OUT — clears both cookies
# ════════════════════════════════════════════════════════════════════════════
class SignOutClientView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response({"message": "Déconnexion réussie."}, status=status.HTTP_200_OK)
        clear_auth_cookies(response)
        return response
    



class ClientOrdersView(APIView):
    """
    GET /api/client/orders/
    Returns all orders whose Client.email matches the logged-in user's email.
    Orders are matched by email because Client is a form-filled model (no FK to AuthUser).
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes     = [IsAuthenticated, IsClient]
 
    def get(self, request):
        user  = request.user
        email = user.email
 
        # Match all Client rows with this email
        clients = Client.objects.filter(email=email)
 
        if not clients.exists():
            return Response([], status=status.HTTP_200_OK)
 
        orders = (
            Order.objects
            .filter(client__in=clients)
            .prefetch_related('ordered_products')
            .order_by('-date')
        )
 
        data = []
        for order in orders:
            products = [
                {
                    "name":         op.name,
                    "product_type": op.product_type,
                    "category":     op.category,
                    "ref":          op.ref,
                    "size":         op.size,
                    "quantity":     op.quantity,
                    "price":        op.price,
                    "available":    op.available,
                    "product_id":   op.product_id,
                }
                for op in order.ordered_products.all()
            ]
            data.append({
                "order_id":       str(order.order_id),
                "date":           order.date.isoformat() if order.date else None,
                "amount":         order.amount,
                "currency":       order.currency,
                "is_paid":        order.is_paid,
                "status":         order.status,
                "delivered":      order.delivered,
                "payment_mode":   "online" if order.payment_mode else "cod",
                "transaction_id": order.transaction_id,
                "products":       products,
            })
 
        return Response(data, status=status.HTTP_200_OK)
 