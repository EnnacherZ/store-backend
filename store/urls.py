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


urlpatterns = [
    # path('events/shoes/', sse_shoes, name='sse_shoes'),
    # path('events/sandals/', sse_sandals, name='sse_sandals'),
    # path('events/shirts/', sse_shirts, name='sse_shirts'),
    # path('events/pants/', sse_pants, name='sse_pants'),
    # path('events/shoes_sizes/', sse_sizes_shoes, name='sse_shoes_sizes'),
    # path('events/sandals_sizes/', sse_sizes_sandals, name='sse_sandals_sizes'),
    # path('events/shirts_sizes/', sse_sizes_shirts, name='sse_shirts_sizes'),
    # path('events/pants_sizes/', sse_sizes_pants, name='sse_pants_sizes'),
    # path('api/getShoesNew/', sse_shoes_new),
    # path('api/getSandalsNew/', sse_sandals_new),
    # path('api/getShirtsNew/', sse_shirts_new),
    path('api/getProducts', get_products),
    path('api/handlepay/', handlePayment),
    path('api/ip', get_ip, name='get_ip'),
    path('api/getPaymentToken', getPaymentToken),
    path('api/getAllProducts', get_newest_products),
    path('api/getNewestShoe', get_newest_shoes),
    path('api/getNewestSandal', get_newest_sandals),
    path('api/getNewestShirt', get_newest_shirts),
    path('api/getNewestPant', get_newest_pants),
    path('api/getSearchedProd', get_searched_product),
    path('api/addReview', add_review),
    path('api/getReviews', get_reviews),
]
