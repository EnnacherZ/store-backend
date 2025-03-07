from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path("user/register", CreateUserView.as_view()),
    path('token', TokenObtainPairView.as_view()),
    path('token/refresh', TokenRefreshView.as_view()),
    path('api-auth', include('rest_framework.urls')),
]