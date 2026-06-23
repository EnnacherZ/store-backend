from django.urls import path
from store.views import *
from store.models import *
from store.serializers import *
from store.tests import youcanpay_webhook
from .client_profile import (
    SignUpClientView,
    ActivateClientView,
    SignInClientView,
    MeClientView,
    UpdateClientProfileView,
    AvatarUpdateView,
    RefreshClientTokenView,
    SignOutClientView,
    ClientOrdersView,
)
from .payment import *
from .email_service import *

urlpatterns = [
    # ── Webhook ───────────────────────────────────────────────────────────────
    path('webhook/ycp/', youcanpay_webhook),

    # ── Products ──────────────────────────────────────────────────────────────
    path('products/get/all',     get_all_products),
    path('products/get',         get_products),
    path('product/search/get',   get_searched_product),

    # ── Payment ───────────────────────────────────────────────────────────────
    path('payment/handle/',      handle_payment),
    path('payment/verify/',      handle_verify),
    path('payment/url/get',      getPaymentUrl),
    path('payment/url/retry/',   retry_payment_url),
    path('payment/cancel/',      cancel_payment),

    # ── Reviews ───────────────────────────────────────────────────────────────
    path('reviews/add/',         add_review),
    path('reviews/get',          get_reviews),

    # ── Order tracker (public) ────────────────────────────────────────────────
    path('orders/check',         check_order),

    # ── Client auth ───────────────────────────────────────────────────────────
    path('client/signup/',                          SignUpClientView.as_view()),
    path('client/activate/<uuid:activation_code>/', ActivateClientView.as_view()),
    path('client/signin/',                          SignInClientView.as_view()),
    path('client/me/',                              MeClientView.as_view()),
    path('client/me/update/',                       UpdateClientProfileView.as_view()),
    path('client/me/avatar/',                       AvatarUpdateView.as_view()),
    path('client/refresh/',                         RefreshClientTokenView.as_view()),
    path('client/signout/',                         SignOutClientView.as_view()),
    path('client/orders/',                          ClientOrdersView.as_view()),

    # ── Email ─────────────────────────────────────────────────────────────────
    path('send_mail/',           envoyer_email),
    path("newsletter/subscribe/", subscribe, name="subscribe"),
    path("newsletter/unsubscribe/", unsubscribe, name="unsubscribe"),
]