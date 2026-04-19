from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from store.views import get_products

# router = DefaultRouter()
# router.register(r'shoes', ShoeViewSet)
# router.register(r'sandals', SandalViewSet)
# router.register(r'shirts', ShirtViewSet)
# router.register(r'pants', PantViewSet)


urlpatterns = [
    path("user/register", CreateUserView.as_view()),
    path('token', CustomTokenObtainPairView.as_view()),
    path('app/token', CustomAppTokenObtainPairView.as_view()),
    path('app/token/refresh', TokenRefreshView.as_view()),
    # path('refreshcookie', RefreshTokenCookieView),
    path('logout', LogoutView.as_view()),
    path('check-auth/', CheckAuthView.as_view(), name='check-auth'),
    path('api-auth', include('rest_framework.urls')),
    path('products', ProductViewSet.as_view()),
    path('products/manager/<int:pk>/', ProductManager.as_view()),
    path('products/parameters/add', add_product_parameters),
    path('products/parameters/get',get_params),
    path('products/get', get_products),
    path('product/stock/get', get_product_stock_details),
    path('product/stock/update', updateProductStock),
    path('products/types/add',add_product_types),
    path('products/types/get',get_products_types),
    path('orders', OrderViewSet.as_view()),
    path('orders/manager/<int:pk>/', OrderManager.as_view()),
    path('orders/get', get_orders),
    path("orders/remaining/get", db_get_orders),
    path('orders/searched/get', get_searched_order),
    path('orders/confirmDelivery/<int:pk>/', confirm_delivery),
    path('deficiencies/manager/<int:pk>/', QuantityExceptionsManager.as_view()),
    path('deficiencies/get', get_deficiencies),
    path('deficiencies/process', process_deficiency),
    path('mandeliveryOrders', delivery_man_orders),
]