import json, traceback

from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import F
from django.db import IntegrityError

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError


from .authentication import DashboardCookieJWTAuthentication
from .permissions import IsAdmin, IsDeliveryMan, IsDashboardUser, IsManager, OriginPermission
from .serializers import CustomTokenObtainPairSerializer, UserSerializer
from store.models import (
    Product, ProductStock, Order, OrderedProduct, QuantityExceptions,
)
from store.serializers import (
    ProductSerializer, ProductStockSerializer, OrderSerializer,
    QuantityExceptionsSerializer
)
from store.models import *


User = get_user_model()


DASHBOARD_ROLES = frozenset({'admin', 'manager', 'delivery'})

# Orders with these is_paid values are considered "active" (not pending/waiting).
# "pending" means the online payment webhook hasn't fired yet — we exclude those
# from dashboard order lists the same way the old `waiting=False` filter did.
ACTIVE_PAYMENT_STATUSES = ('confirmed', 'cod', 'failed')



# ─── Auth ─────────────────────────────────────────────────────────────────────

class RefreshTokenCookieView(APIView):
    """Rotate the access cookie using the refresh cookie."""
    permission_classes = [OriginPermission]

    def post(self, request):
        refresh_str = request.COOKIES.get('refresh_token')
        if not refresh_str:
            return Response({'detail': 'Refresh token missing.'}, status=400)
        try:
            token        = RefreshToken(refresh_str)
            access_token = str(token.access_token)
        except TokenError:
            return Response({'detail': 'Invalid or expired refresh token.'}, status=401)

        response = Response({'message': 'Token refreshed.'})
        response.set_cookie(
            key='access_token', value=access_token,
            httponly=True, secure=True, samesite='None',
            max_age=3600 * 8, path='/',
        )
        return response


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Dashboard login.
    Clients are explicitly rejected — they must use /api/client/signin/.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.user

        # ── Block client role from obtaining dashboard tokens ─────────────
        if getattr(user, 'role', None) not in DASHBOARD_ROLES:
            return Response(
                {'error': 'Accès refusé.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tokens = serializer.validated_data
        res = Response({
            'message': 'Login successful',
            'user': {
                'username':   user.username,
                'role':       user.role,
                'first_name': user.first_name,
                'last_name':  user.last_name,
                'image':      user.image.url if user.image else None,
            }
        }, status=status.HTTP_200_OK)

        cookie_opts = dict(httponly=True, secure=True, samesite='None', path='/')
        res.set_cookie('access_token',  str(tokens['access']),  max_age=3600 * 8,  **cookie_opts)
        res.set_cookie('refresh_token', str(tokens['refresh']), max_age=3600 * 24, **cookie_opts)
        return res


class LogoutView(APIView):
    permission_classes = [OriginPermission]

    def post(self, request):
        res = Response({'message': 'Logged out.'})
        res.delete_cookie('access_token',  samesite='None', path='/')
        res.delete_cookie('refresh_token', samesite='None', path='/')
        return res


class CheckAuthView(APIView):
    """
    Used by the React dashboard to restore session on mount.
    DashboardCookieJWTAuthentication already rejects client tokens.
    """
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({
            'message': 'Authenticated',
            'user': {
                'username':   u.username,
                'email':      u.email,
                'first_name': u.first_name,
                'last_name':  u.last_name,
                'role':       u.role,
                'image':      u.image.url if u.image else None,
            },
        }, status=200)


# ─── User management ──────────────────────────────────────────────────────────

class CreateUserView(generics.CreateAPIView):
    queryset           = User.objects.all()
    serializer_class   = UserSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes = [OriginPermission, IsAuthenticated, IsAdmin]


# ─── Products ─────────────────────────────────────────────────────────────────

class ProductViewSet(APIView):
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes = [OriginPermission, IsAuthenticated, IsManager]

    def post(self, request):
        data = request.data

        # --- Extract fields ---
        product_type_name = data.get("product_type", "").strip()
        category_name     = data.get("category", "").strip()
        ref               = data.get("ref", "").strip()
        name              = data.get("name", "").strip()
        price             = data.get("price")
        newest            = data.get("newest", "false").lower() == "true"
        promo             = data.get("promo", 0)
        image_primary     = request.FILES.get("image")

        # --- Validation ---
        if not all([product_type_name, category_name, ref, name, price, image_primary]):
            return Response(
                {"error": "Fields product_type, category, ref, name, price and image are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Resolve ProductType ---
        try:
            product_type = ProductType.objects.get(name=product_type_name)
        except ProductType.DoesNotExist:
            return Response(
                {"error": f"ProductType '{product_type_name}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # --- Resolve Category (scoped to the ProductType) ---
        try:
            category = Category.objects.get(product_type=product_type, name=category_name)
        except Category.DoesNotExist:
            return Response(
                {"error": f"Category '{category_name}' not found under '{product_type_name}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        # --- Create Product ---
        try:
            product = Product.objects.create(
                category=category,
                ref=ref,
                name=name,
                price=price,
                newest=newest,
                promo=promo,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # --- Primary image ---
        ProductImage.objects.create(
            product=product,
            image=image_primary,
            is_primary=True,
            order=0,
        )

        # --- Additional images (image1, image2, image3, image4) ---
        for i in range(1, 5):
            extra = request.FILES.get(f"image{i}")
            if extra:
                ProductImage.objects.create(
                    product=product,
                    image=extra,
                    is_primary=False,
                    order=i,
                )

        return Response({"id": product.id, "ref": product.ref}, status=status.HTTP_201_CREATED)


class ProductManager(generics.RetrieveUpdateDestroyAPIView):
    queryset               = Product.objects.all()
    serializer_class       = ProductSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsManager]
    parser_classes         = (MultiPartParser, FormParser)


class ProductStockViewSet(generics.ListCreateAPIView):
    queryset               = ProductStock.objects.all()
    serializer_class       = ProductStockSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [IsAuthenticated, IsManager]
    parser_classes         = (MultiPartParser, FormParser)


# ─── Orders ───────────────────────────────────────────────────────────────────

class OrderViewSet(generics.ListCreateAPIView):
    queryset               = Order.objects.all()
    serializer_class       = OrderSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsDashboardUser]
    parser_classes         = (MultiPartParser, FormParser)


class OrderManager(generics.RetrieveUpdateDestroyAPIView):
    queryset               = Order.objects.all()
    serializer_class       = OrderSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsDashboardUser]
    parser_classes         = (MultiPartParser, FormParser)


class QuantityExceptionsManager(generics.RetrieveUpdateDestroyAPIView):
    queryset               = QuantityExceptions.objects.all()
    serializer_class       = QuantityExceptionsSerializer
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsManager]
    parser_classes         = (MultiPartParser, FormParser)





class AddProductTypesView(APIView):
    """
    POST db/products/types/add
    Body: { "values": ["TypeA", "TypeB"] }
    """
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsManager]

    def post(self, request):
        values = request.data.get("values", [])

        if not values or not isinstance(values, list):
            return Response(
                {"error": "A non-empty list of 'values' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        created, skipped = [], []

        for name in values:
            name = name.strip()
            if not name:
                continue
            try:
                obj, was_created = ProductType.objects.get_or_create(name=name)
                (created if was_created else skipped).append(name)
            except IntegrityError:
                skipped.append(name)

        return Response(
            {"created": created, "skipped": skipped},
            status=status.HTTP_201_CREATED
        )


class AddProductParametersView(APIView):
    """
    POST db/products/parameters/add
    Body: { "productType": "TypeA", "param": "color", "values": ["Red", "Blue"] }

    Note: 'param' is received from the frontend but Category only has a 'name'
    field, so values are stored directly as category names under the given type.
    """
    authentication_classes = [DashboardCookieJWTAuthentication]
    permission_classes     = [OriginPermission, IsAuthenticated, IsManager]

    def post(self, request):
        product_type_name = request.data.get("productType", "").strip()
        values = request.data.get("values", [])

        if not product_type_name:
            return Response(
                {"error": "'productType' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not values or not isinstance(values, list):
            return Response(
                {"error": "A non-empty list of 'values' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product_type = ProductType.objects.get(name=product_type_name)
        except ProductType.DoesNotExist:
            return Response(
                {"error": f"ProductType '{product_type_name}' does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        created, skipped = [], []

        for name in values:
            name = name.strip()
            if not name:
                continue
            try:
                obj, was_created = Category.objects.get_or_create(
                    product_type=product_type,
                    name=name
                )
                (created if was_created else skipped).append(name)
            except IntegrityError:
                skipped.append(name)

        return Response(
            {"created": created, "skipped": skipped},
            status=status.HTTP_201_CREATED
        )



class ProductParametersView(APIView):
    permission_classes = [OriginPermission]
    
    def get(self, request):
        product_types = ProductType.objects.prefetch_related("categories").order_by("id")

        data = {
            "types": [pt.name for pt in product_types],
            "categories": {
                pt.name: [cat.name for cat in pt.categories.all()]
                for pt in product_types
            }
        }

        return Response(data)



# ─── Function-based dashboard views ───────────────────────────────────────────
#
# FIX: Every @api_view that requires dashboard cookie auth now carries
#      @authentication_classes([DashboardCookieJWTAuthentication]) so DRF
#      reads the httpOnly cookie instead of falling back to the global default.
#
# FIX: All `waiting=False` filters replaced with
#      `is_paid__in=ACTIVE_PAYMENT_STATUSES` — the Order model has no `waiting`
#      field; "pending" orders (awaiting webhook) are the ones to exclude.
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDashboardUser])
def db_get_orders(request):
    """Legacy single-list endpoint kept for backward compat (orders/remaining/get)."""

    try:
        # FIX: was filter(status=False, waiting=False) — 'waiting' doesn't exist
        qs = Order.objects.filter(
            status=False,
            is_paid__in=ACTIVE_PAYMENT_STATUSES,
        ).order_by('-exception')
        return JsonResponse({'orders': OrderSerializer(qs, many=True).data}, status=200)
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'}, status=400)


@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDashboardUser])
def get_deficiencies(request):

    try:
        qs = QuantityExceptions.objects.filter(treated=False)
        return JsonResponse({'deficiencies': QuantityExceptionsSerializer(qs, many=True).data}, status=200)
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'}, status=400)


@api_view(['POST'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsManager])
def updateProductStock(request):

    try:
        data     = request.data
        pid      = data.get('productId')
        size     = data.get('size')
        quantity = data.get('quantity')

        if not all([pid, size, quantity]):
            return Response({'message': 'Missing required fields.'}, status=400)

        pid      = int(pid)
        quantity = int(quantity)

        product = Product.objects.get(id=pid)
        stock, created = ProductStock.objects.get_or_create(
            product=product, size=size,
            defaults={'quantity': quantity},
        )
        if not created:
            stock.quantity = F('quantity') + quantity
            stock.save()

        return Response({'message': 'Stock updated.'}, status=200)

    except Product.DoesNotExist:
        return Response({'message': 'Product not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'}, status=500)


@api_view(['POST'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsManager])
def process_deficiency(request):
    try:
        data         = json.loads(request.body)
        exception_id = data.get('exceptionID')
        order_id     = data.get('orderID')

        exc     = QuantityExceptions.objects.get(exception_id=exception_id)
        op      = OrderedProduct.objects.get(exception_id=exception_id)
        order   = Order.objects.get(order_id=order_id)

        exc.treated       = True
        op.available      = True
        order.exception   = False

        exc.save()
        op.save()
        order.save()

        return JsonResponse({'message': 'ok'}, status=200)
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'}, status=400)


# ─── Product parameters (stored in parameters.json) ───────────────────────────











@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsManager])
def get_product_stock_details(request):
    try:
        pid     = request.GET.get('productId')
        product = Product.objects.get(id=pid)
        return JsonResponse({'data': ProductSerializer(product).data['stock']}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ─── Orders (dashboard) ───────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDashboardUser])
def get_orders(request):
    """
    Returns four order lists consumed by the React dashboard:
      - allOrders:             every active order
      - remainingOrders:       active, not yet confirmed for delivery (status=False)
      - waitingDeliveryOrders: confirmed for delivery but not yet delivered
      - deliveredOrders:       fully delivered

    FIX: replaced `waiting=False` (non-existent field) with
         `is_paid__in=ACTIVE_PAYMENT_STATUSES` to exclude orders still awaiting
         online payment confirmation.
    """
    try:
        base = Order.objects.filter(is_paid__in=ACTIVE_PAYMENT_STATUSES)
        return JsonResponse({
            'allOrders':             OrderSerializer(base.order_by('-exception'), many=True).data,
            'remainingOrders':       OrderSerializer(base.filter(status=False).order_by('-exception'), many=True).data,
            'waitingDeliveryOrders': OrderSerializer(base.filter(status=True, delivered=False).order_by('-exception'), many=True).data,
            'deliveredOrders':       OrderSerializer(base.filter(status=True, delivered=True).order_by('-exception'), many=True).data,
        }, status=200)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDashboardUser])
def get_searched_order(request):
    try:
        order_id = request.GET.get('orderID')
        order    = Order.objects.get(order_id=order_id)
        deficiencies = QuantityExceptions.objects.filter(order=order_id)
        return JsonResponse({
            'order':        OrderSerializer(order).data,
            'deficiencies': QuantityExceptionsSerializer(deficiencies, many=True).data,
            'found': True,
            'error': False,
        }, status=200)
    except Order.DoesNotExist:
        return JsonResponse({'found': False, 'error': False})
    except Exception:
        return JsonResponse({'error': True})


@api_view(['GET'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDeliveryMan])
def delivery_man_orders(request):
    try:
        # FIX: was filter(status=True, waiting=False, delivered=False)
        qs = Order.objects.filter(
            status=True,
            delivered=False,
            is_paid__in=ACTIVE_PAYMENT_STATUSES,
        )
        return JsonResponse({'orders': OrderSerializer(qs, many=True).data}, status=200)
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'}, status=400)


@api_view(['PATCH'])
@authentication_classes([DashboardCookieJWTAuthentication])
@permission_classes([OriginPermission, IsAuthenticated, IsDeliveryMan])
def confirm_delivery(request, pk):
    try:
        username = request.data.get('username')
        order    = Order.objects.get(pk=pk)
        order.delivery_man = username
        order.delivered    = True
        order.save()
        return JsonResponse({'message': 'Delivered!'})
    except Exception as e:
        return JsonResponse({'message': f'Error: {e}'})