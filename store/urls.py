"""
URL configuration for storeBackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from store.views import *
from store.models import *
from store.serializers import *
from store.loyalClient import ActivateClientView, SignUpClientView, SignInClientView


urlpatterns = [
    path('ip', get_ip, name='get_ip'),
    path('products/get/all', get_all_products),
    path('products/get', get_products),
    path('product/search/get', get_searched_product),
    path('payment/handle/', handle_payment),
    path('payment/token/get', getPaymentToken),
    path('reviews/add/', add_review),
    path('reviews/get', get_reviews),
    path('orders/check', check_order),
    path('client/signup', SignUpClientView.as_view()),
    path('client/signin', SignInClientView.as_view()),
    path('client/activate/<str:activation_code>/', ActivateClientView.as_view()),
    path('send_mail/', envoyer_email)
]
