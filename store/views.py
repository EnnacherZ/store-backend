import os, json, datetime
from .models import *
from rest_framework.decorators import api_view, permission_classes

from dashboard.permissions import OriginPermission
from django.http import HttpResponseForbidden, JsonResponse
from rest_framework import status
from .serializers import *
from dotenv import load_dotenv
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import traceback

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication




from django.template.loader import render_to_string


@csrf_exempt


# ── Settings contract ──────────────────────────────────────────────────────────
#
# Add these to your settings.py (or settings/prod.py):
#
#   EMAIL_HOST_USER     = "you@gmail.com"
#   EMAIL_HOST_PASSWORD = "your-app-password"
#
#   COMPANY_NAME        = "Al Firdaous Store"
#   COMPANY_TAGLINE     = "Premium Footwear"
#   COMPANY_LOGO_URL    = "https://yourdomain.com/static/logo.png"  # absolute URL
#   COMPANY_ADDRESS     = "123 Rue Mohammed V, Casablanca, Maroc"
#   COMPANY_WEBSITE     = "https://yourdomain.com"
#
#   SOCIAL_FACEBOOK     = "https://facebook.com/yourpage"
#   SOCIAL_INSTAGRAM    = "https://instagram.com/yourpage"
#   SOCIAL_TIKTOK       = "https://tiktok.com/@yourpage"
#   SOCIAL_TWITTER      = "https://x.com/yourhandle"
#   SOCIAL_LINKEDIN     = "https://linkedin.com/company/yourpage"
#   SOCIAL_YOUTUBE      = "https://youtube.com/@yourchannel"
#
#   UNSUBSCRIBE_URL     = "https://yourdomain.com/unsubscribe/"
#
# Any setting left undefined silently defaults to "" (icon not rendered).
# ──────────────────────────────────────────────────────────────────────────────


def _company_context(request) -> dict:
    """
    Build the branding + social block from settings.
    Called once per email send — centralises all setting reads.
    """
    def s(key, default=""):
        return getattr(settings, key, default)

    return {
        # Branding
        "company_name":     s("COMPANY_NAME",    "Your Company"),
        "company_tagline":  s("COMPANY_TAGLINE", ""),
        "company_logo_url": s("COMPANY_LOGO_URL", ""),
        "company_address":  s("COMPANY_ADDRESS",  ""),
        "company_website":  s("COMPANY_WEBSITE",  ""),

        # Social — only rendered in the template when non-empty
        "social_facebook":  s("SOCIAL_FACEBOOK"),
        "social_instagram": s("SOCIAL_INSTAGRAM"),
        "social_tiktok":    s("SOCIAL_TIKTOK"),
        "social_twitter":   s("SOCIAL_TWITTER"),
        "social_linkedin":  s("SOCIAL_LINKEDIN"),
        "social_youtube":   s("SOCIAL_YOUTUBE"),

        # Footer
        "unsubscribe_url":  s("UNSUBSCRIBE_URL"),
    }


@api_view(["POST"])
@permission_classes([OriginPermission])
def envoyer_email(request):
    """
    POST /api/envoyer-email/

    Required POST fields:
        subject         str   — Email subject line
        body            str   — Plain-text / main message body
        to              str   — Recipient(s), comma-separated
        customer_name   str   — Recipient display name shown in greeting

    Optional POST fields:
        cc              str   — CC addresses, comma-separated
        bcc             str   — BCC addresses, comma-separated
        file            file  — Attachment (multipart/form-data)

        reference_number str  — Order / invoice / ticket ref shown in info card
        cta_url          str  — Call-to-action button URL
        cta_label        str  — CTA button label (default: "View Details →")

    Branding and social links are never accepted from the request —
    they are always read from Django settings (see _company_context above).
    """
    try:
        # ── Required fields ────────────────────────────────────────────────
        subject       = request.POST.get("subject", "").strip()
        body          = request.POST.get("body", "").strip()
        to            = request.POST.get("to", "").strip()
        #customer_name = request.POST.get("customer_name", "").strip()

        if not subject or not body or not to :
            return JsonResponse(
                {"error": "Missing required fields: subject, body, to, customer_name"},
                status=400,
            )

        # ── Optional per-email fields ──────────────────────────────────────
        cc   = request.POST.get("cc", "")
        bcc  = request.POST.get("bcc", "")
        file = request.FILES.get("file")

        reference_number = request.POST.get("reference_number", "")
        cta_url          = request.POST.get("cta_url", "")
        cta_label        = request.POST.get("cta_label", "View Details →")

        # ── Recipient lists ────────────────────────────────────────────────
        to_list  = [e.strip() for e in to.split(",")  if e.strip()]
        cc_list  = [e.strip() for e in cc.split(",")  if e.strip()]
        bcc_list = [e.strip() for e in bcc.split(",") if e.strip()]
        all_recipients = to_list + cc_list + bcc_list

        # ── Build template context ─────────────────────────────────────────
        context = {
            # Per-email fields (from request)
            "subject":          subject,
            "body":             body,
           # "customer_name":    customer_name,
            "reference_number": reference_number,
            "cta_url":          cta_url,
            "cta_label":        cta_label,
            "current_year":     datetime.datetime.now().year,

            # Global branding + socials (always from settings, never from request)
            **_company_context(request),
        }

        html_content = render_to_string("email_template.html", context)

        # ── Build MIME message ─────────────────────────────────────────────
        sender_email = settings.EMAIL_HOST_USER
        password     = settings.EMAIL_HOST_PASSWORD

        msg = MIMEMultipart("alternative")
        msg["From"]    = sender_email
        msg["To"]      = ", ".join(to_list)
        msg["Cc"]      = ", ".join(cc_list)
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if file:
            attachment = MIMEApplication(file.read(), Name=file.name)
            attachment["Content-Disposition"] = f'attachment; filename="{file.name}"'
            msg.attach(attachment)

        # ── Send via Gmail SMTP ────────────────────────────────────────────
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, all_recipients, msg.as_string())

        return JsonResponse({"message": "Email sent successfully ✅"})

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)



load_dotenv()
key1 = os.environ.get('payment_second_key')
key2 = os.environ.get('payment_first_key')
allowed_origins = os.environ.get('REQUEST_ALLOWED_ORIGINS')
is_sandbox = os.environ.get('IS_SANDBOX_MODE') == 'True'
forbbiden_message = 'Forbidden-Acces denied'
ALLOWED_ORIGINS = [allowed_origins]


# ─── Helpers ──────────────────────────────────────────────────────────────────
 
def get_ip_address(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
 




# Create your views here.         
     



 
    
@api_view(['POST'])
@permission_classes([OriginPermission])
def add_review(request):
    if request.method == 'POST':
        #if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        #else:
            try:
                data = json.loads(request.body)
                id = int(data.get('product', ''))
                review = data.get('review', '')
                email = data.get('email', '')
                stars = data.get('stars', 0)
                date_str = data.get('date', None)
                name = data.get('name', None)
                date = None
                # Validation de la date (en format ISO)
                if date_str:
                    date = datetime.datetime.fromisoformat(date_str)  # Si le format est correct, il sera converti
                    if not date:
                        return JsonResponse({'message': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
                
                # Créer et enregistrer la nouvelle critique
                product = Product.objects.get(id=id)
                new_review = ProductReview(
                    product=product,
                    review=review,
                    stars=stars,
                    email=email,
                    date=date,
                    name=name
                )
                new_review.save()
                return JsonResponse({'message': 'Review added'}, status=status.HTTP_200_OK)
            except Exception as e:
                traceback.print_exc()
                return JsonResponse({'message': f'Error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([OriginPermission])
def get_reviews(request):
    #if origin_checker(request): return HttpResponseForbidden(forbbiden_message)
        
        try:
            print(request.META.get('HTTP_REFERER'))
            pid = int(request.GET.get('product_id'))
            product_type = request.GET.get('productType')
            product_reviews = ProductReview.objects.filter(product_id = pid)
            serialized_reviews = ProductReviewSerializer(product_reviews, many=True)
            products = Product.objects.filter(product_type=product_type, newest=True)
            serialized_products = ProductSerializer(products, many=True)
            print(serialized_reviews.data)
            return JsonResponse({'reviews':serialized_reviews.data, 'products':serialized_products.data}, status=status.HTTP_200_OK)
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'message': f'Error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([OriginPermission])
def get_searched_product(request):
    try:
        product_type = request.GET.get('productType')
        cat = request.GET.get('category')
        ref = request.GET.get('ref')
        pid = request.GET.get('id')

        if not pid:
            return JsonResponse(
                {'message': 'Product id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pid = int(pid)

        # 🔹 Produit principal
        searched_product = Product.objects.get(
            # category=cat,
            # ref=ref,
            id=pid
        )

        serialized = ProductSerializer(searched_product)

        # 🔹 Reviews 
        reviews_query = ProductReview.objects.filter(product=pid)

        product_reviews = reviews_query.order_by('-stars')

        serialized_reviews = ProductReviewSerializer(
            product_reviews,
            many=True
        )

        # 🔹 Produits similaires
        products = Product.objects.filter(
            category=cat,
            newest=True
        )

        serialized_products = ProductSerializer(products, many=True)

        return JsonResponse(
            {
                "product": serialized.data,
                "products": serialized_products.data,
                "reviews": serialized_reviews.data
            },
            status=status.HTTP_200_OK
        )

    except Product.DoesNotExist:
        return JsonResponse(
            {'message': 'Product not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    except ValueError:
        return JsonResponse(
            {'message': 'Invalid product id'},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        return JsonResponse(
            {'message': f'error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([OriginPermission])
def get_products(request):
    try:
        product_type = request.GET.get('productType')
        newest = request.GET.get('newest')

        filters = {}

        if product_type:
            filters['category__product_type__name'] = product_type  # ← traverse the FK

        if newest is not None:
            filters['newest'] = newest.lower() == 'true'

        products = (
            Product.objects
            .select_related('category__product_type')
            .prefetch_related('images', 'stock')
            .filter(**filters)
        )

        serialized = ProductSerializer(products, many=True)

        return JsonResponse(
            {'products': serialized.data},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {"message": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    

@api_view(['GET'])
@permission_classes([OriginPermission])
def check_order(request):
    order_id = request.GET.get('orderID', '').strip()
    if not order_id:
        return JsonResponse({'found': False, 'error': False}, status=200)

    try:
        the_order = (
            Order.objects
            .prefetch_related('ordered_products')
            .select_related('client')
            .get(order_id=order_id)
        )
        client = the_order.client
        products = [
            {
                'name':         op.name,
                'ref':          op.ref,
                'category':     op.category,
                'product_type': op.product_type,
                'size':         op.size,
                'quantity':     op.quantity,
                'price':        op.price,
            }
            for op in the_order.ordered_products.all()
        ]
        return JsonResponse({
            'found': True,
            'error': False,
            'client': {
                'first_name': client.first_name,
                'last_name':  client.last_name,
                'city':       client.city,
                'phone':      client.phone,
                'email':      client.email,
            },
            'order': {
                'order_id':       str(the_order.order_id),
                'amount':         the_order.amount,
                'currency':       the_order.currency,
                'is_paid':        the_order.is_paid,
                'payment_mode':   'online' if the_order.payment_mode else 'cash_on_delivery',
                'delivered':      the_order.delivered,
                'status':         the_order.status,
                # ← FIX: was serializing DateTimeField as object, now ISO string
                'date':           the_order.date.isoformat() if the_order.date else None,
                'transaction_id': the_order.transaction_id,
                'products':       products,
            },
        }, status=200)

    except Order.DoesNotExist:
        return JsonResponse({'found': False, 'error': False}, status=200)
    except Exception:
        import traceback; traceback.print_exc()
        return JsonResponse({'error': True, 'found': False}, status=500)








from collections import defaultdict

@api_view(['GET'])
# @authenticate_class([])
@permission_classes([OriginPermission])
def get_all_products(request):
    try:
        # 🔹 récupération des params
        newest = request.GET.get('newest')

        filters = {}

        # 🔹 filtre newest
        if newest is not None:
            filters['newest'] = newest.lower() == 'true'

        # 🔹 queryset optimisé
        products = Product.objects.filter(**filters) if filters else Product.objects.all()

        # 🔹 serialization
        serialized = ProductSerializer(products, many=True).data

        # 🔹 groupement par product_type
        grouped_products = defaultdict(list)

        for product in serialized:
            grouped_products[product["product_type"]].append(product)

        return JsonResponse(
            {"products": grouped_products},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {"message": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

