from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'shoes', ShoeViewSet)
router.register(r'sandals', SandalViewSet)
router.register(r'shirts', ShirtViewSet)
router.register(r'pants', PantViewSet)



urlpatterns = [
    path("user/register", CreateUserView.as_view()),
    path('token', TokenObtainPairView.as_view()),
    path('token/refresh', TokenRefreshView.as_view()),
    path('api-auth', include('rest_framework.urls')),
    path('shoes', ShoeViewSet.as_view()),
    path('sandals', SandalViewSet.as_view()),
    path('shirts', ShirtViewSet.as_view()),
    path('pants', PantViewSet.as_view()),
    path('orders', OrderViewSet.as_view()),
    path('shoes/manager/<int:pk>/', ShoeManager.as_view()),
    path('sandals/manager/<int:pk>/', SandalManager.as_view()),
    path('shirts/manager/<int:pk>/', ShirtManager.as_view()),
    path('pants/manager/<int:pk>/', PantManager.as_view()),
    path('shoesDetails', ShoeDetailViewSet.as_view()),
    path('orders/manager/<int:pk>/', OrderManager.as_view()),
    path('orders/getOrders', get_orders),
    path("updateShoeDetails", updateShoeDetail),
    path("updateSandalDetails", updateSandalDetail),
    path("updateShirtDetails", updateShirtDetail),
    path("updatePantDetails", updatePantDetail),
    path("remaining_orders", db_get_orders),
    path('getDeficiencies', get_deficiencies),
    path('products/parameters', add_product_parameters),
    path('productsChoices', get_products_choices),
    path('getProductDetails', get_product_details),
    path('products/getCategories',get_params),
    path('products/setTypes',add_product_types),
    path('products/getTypes',get_products_types),
]