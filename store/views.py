from django.utils.encoding import smart_str
import time, os, json, datetime
from .models import *
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponseForbidden, JsonResponse, StreamingHttpResponse
from rest_framework import status
from .serializers import *
from dotenv import load_dotenv
from django.db import transaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import traceback

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from youcanpay.youcan_pay import YouCanPay
from youcanpay.models.token import TokenData
from youcanpay.models.data import Customer




from django.template.loader import render_to_string


@csrf_exempt
def envoyer_email(request):
    """
    POST /api/envoyer-email/

    Required fields:
        subject         str   — Email subject line
        body            str   — Plain-text / main message body
        to              str   — Recipient(s), comma-separated
        customer_name   str   — Recipient's display name (shown in greeting)

    Optional fields:
        cc              str   — CC addresses, comma-separated
        bcc             str   — BCC addresses, comma-separated
        file            file  — Attachment (multipart/form-data)

        reference_number str  — Order / ticket / ref number shown in info card
        cta_url          str  — Call-to-action button URL
        cta_label        str  — Call-to-action button label (default: "View Details →")

        company_name     str  — Sender company name   (default: settings.COMPANY_NAME)
        company_tagline  str  — Tagline under logo     (default: settings.COMPANY_TAGLINE)
        company_logo_url str  — Absolute URL to logo   (default: settings.COMPANY_LOGO_URL)
        company_address  str  — Footer address          (default: settings.COMPANY_ADDRESS)

        unsubscribe_url  str  — Unsubscribe link in footer
        social_facebook  str  — Facebook URL
        social_twitter   str  — Twitter/X URL
        social_linkedin  str  — LinkedIn URL
        social_instagram str  — Instagram URL
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        # ── Required fields ────────────────────────────────────────────────
        subject       = request.POST.get("subject", "").strip()
        body          = request.POST.get("body", "").strip()
        to            = request.POST.get("to", "").strip()
        customer_name = request.POST.get("customer_name", "").strip()

        # if not subject or not body or not to or not customer_name:
        #     return JsonResponse(
        #         {"error": "Missing required fields: subject, body, to, customer_name"},
        #         status=400,
        #     )

        # ── Optional fields ────────────────────────────────────────────────
        cc   = request.POST.get("cc", "")
        bcc  = request.POST.get("bcc", "")
        file = request.FILES.get("file")

        reference_number = request.POST.get("reference_number", "")
        cta_url          = request.POST.get("cta_url", "")
        cta_label        = request.POST.get("cta_label", "View Details →")

        company_name     = request.POST.get("company_name",    getattr(settings, "COMPANY_NAME",    "Your Company"))
        company_tagline  = request.POST.get("company_tagline", getattr(settings, "COMPANY_TAGLINE", "Premium Experience"))
        company_logo_url = request.POST.get("company_logo_url",getattr(settings, "COMPANY_LOGO_URL",""))
        company_address  = request.POST.get("company_address", getattr(settings, "COMPANY_ADDRESS", ""))

        unsubscribe_url  = request.POST.get("unsubscribe_url", "")
        social_facebook  = request.POST.get("social_facebook", "")
        social_twitter   = request.POST.get("social_twitter",  "")
        social_linkedin  = request.POST.get("social_linkedin",  "")
        social_instagram = request.POST.get("social_instagram", "")

        # ── Recipient lists ────────────────────────────────────────────────
        to_list  = [e.strip() for e in to.split(",")  if e.strip()]
        cc_list  = [e.strip() for e in cc.split(",")  if e.strip()]
        bcc_list = [e.strip() for e in bcc.split(",") if e.strip()]
        all_recipients = to_list + cc_list + bcc_list

        # ── Render HTML template ───────────────────────────────────────────
        html_content = render_to_string(
            "email_template.html",
            {
                "subject":          subject,
                "body":             body,
                "customer_name":    customer_name,
                "reference_number": reference_number,
                "cta_url":          cta_url,
                "cta_label":        cta_label,
                "company_name":     company_name,
                "company_tagline":  company_tagline,
                "company_logo_url": company_logo_url,
                "company_address":  company_address,
                "unsubscribe_url":  unsubscribe_url,
                "social_facebook":  social_facebook,
                "social_twitter":   social_twitter,
                "social_linkedin":  social_linkedin,
                "social_instagram": social_instagram,
                "current_year":     datetime.datetime.now,
            },
        )

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
        print(e)
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
 
 
def _build_ordered_product_payload(product:Product, item, order, exception_id):
    """Return the dict appended to ordered_products in API responses."""
    return {
        "productType" : product.product_type,
        "size"        : item['size'],
        "quantity"    : item['quantity'],
        "category"    : product.category,
        "ref"         : product.ref,
        "name"        : product.name,
        "id"          : product.id,
        "image"       : product.image.url if product.image else '',
        "promo"       : product.promo,
        "price"       : product.price,
        "available"   : item.get('_available', True),
        "exception_id": str(exception_id) if order.exception else None,
    }

def origin_checker(request):
    # referer = request.META.get('HTTP_REFERER','')
    # if referer in ALLOWED_ORIGINS: return False
    # else : return True
    pass

def _release_reservations(order):
    """
    Release all ProductStock.reserved held by this order's pending OrderedProducts.
    Called when a payment fails or the YCPay URL generation itself errors out.
    """
    for op in OrderedProduct.objects.filter(order=order, stock_deducted=False):
        try:
            ps = ProductStock.objects.select_for_update().get(
                product_id=op.product_id, size=op.size
            )
            ps.reserved = max(0, ps.reserved - op.quantity)
            ps.save(update_fields=['reserved'])
        except ProductStock.DoesNotExist:
            continue








# Create your views here.         
     


# ─── View 1: getPaymentUrl ────────────────────────────────────────────────────
#
# Called when the user clicks "Pay Now" with online payment.
#
# Policy: RESERVE stock (not deduct). Stock is only deducted after the
# YCPay webhook confirms the payment in handle_webhook (or handle_payment).
#
# Reservation = increment ProductStock.reserved.
# available_quantity() = quantity - reserved.
# If available_quantity() < requested → partial exception, reserve what's left.
 
@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def getPaymentUrl(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)
 
    try:
        data            = json.loads(request.body)
        print('here is the data:',data)
        customer_params = data.get('customer', {})
        token_params    = data.get('tokenParams', {})
        items           = data.get('items', [])
 
        amount      = int(token_params.get('amount', 0))
        currency    = str(token_params.get('currency', 'MAD'))
        success_url = token_params.get('success_url')
        error_url   = token_params.get('error_url')
        lang        = token_params.get('lang')
        ip_address  = get_ip_address(request)
 
        # ── Create client ──────────────────────────────────────────────────────
        new_client = Client.objects.create(
            first_name = customer_params['first_name'],
            last_name  = customer_params['last_name'],
            email      = customer_params['email'],
            phone      = str(customer_params['phone']),
            city       = customer_params['city'],
            address    = customer_params['address'],
            ip_address = ip_address,
        )
 
        # ── Create order (pending, no transaction_id yet) ──────────────────────
        new_order = Order.objects.create(
            client       = new_client,
            amount       = amount,
            currency     = currency,
            payment_mode = True,   # online
            is_paid      = 'pending',
        )
        print('printing items:', items)
        print('entering loop')
        # ── Reserve stock for each item ────────────────────────────────────────
        for item in items:
            try:
                product_stock = ProductStock.objects.select_for_update().get(
                    product=item['id'], size=item['size']
                )
                product       = Product.objects.get(id=item['id'])
                requested_qty = item['quantity']
                exception_id  = uuid.uuid4()
 
                # How much is actually available right now (not held by other orders)
                available_qty = product_stock.available_quantity()
                can_fulfill   = available_qty >= requested_qty
 
                if can_fulfill:
                    # Reserve exactly what was requested
                    product_stock.reserved += requested_qty
                else:
                    # Reserve whatever is left; record the shortfall
                    shortfall = requested_qty - available_qty
                    product_stock.reserved += available_qty  # reserve what exists
 
                    QuantityExceptions.objects.create(
                        client           = new_client,
                        order            = new_order,
                        product_type     = product.product_type,
                        product_category = product.category,
                        product_ref      = product.ref,
                        product_name     = product.name,
                        product_size     = item['size'],
                        delta_quantity   = shortfall,
                        exception_id     = exception_id,
                    )
                    new_order.exception = True
                    new_order.save(update_fields=['exception'])
 
                product_stock.save(update_fields=['reserved'])
                print('creating ordered product')
                # Create OrderedProduct with stock_deducted=False (reservation only)
                ordered_product = OrderedProduct(
                    client         = new_client,
                    order          = new_order,
                    product_type   = product.product_type,
                    size           = item['size'],
                    quantity       = requested_qty,
                    category       = product.category,
                    ref            = product.ref,
                    name           = product.name,
                    product_id     = product.id,
                    price          = product.price,
                    available      = can_fulfill,
                    exception_id   = exception_id,
                    stock_deducted = False,   # ← reservation only, not yet sold
                )
                ordered_product.save()
                print('the ordered product:', ordered_product)
 
                item['_available'] = can_fulfill
 
            except ProductStock.DoesNotExist:
                continue
 
        # ── Generate YCPay payment URL ─────────────────────────────────────────
        try:
            if is_sandbox:
                YouCanPay.enable_sandbox_mode()
 
            youcan_pay    = YouCanPay.instance().use_keys(key1, key2)
            customer_info = Customer(
                name         = f"{new_client.first_name} {new_client.last_name}",
                address      = new_client.address,
                zip_code     = None,
                country_code = "MA",
                phone        = str(new_client.phone),
                email        = str(new_client.email),
            )
            token_data    = TokenData(
                order_id      = str(new_order.order_id),
                amount        = str(amount * 100),
                currency      = currency,
                customer_ip   = "",
                success_url   = success_url,
                error_url     = error_url,
                customer_info = customer_info,
                metadata      = {"info": "payment"},
            )
            payment_url = youcan_pay.token.create_from(token_data).get_payment_url(lang=lang)
 
            return JsonResponse({
                "payment_url": payment_url,
                "order_id"   : str(new_order.order_id),
            })
 
        except Exception as e:
            # YCPay call failed → release reservations so stock isn't locked
            _release_reservations(new_order)
            new_order.is_paid = 'failed'
            new_order.save(update_fields=['is_paid'])
            traceback.print_exc()
            return JsonResponse({
                'message': 'Failed to generate payment URL.',
                'type'   : type(e).__name__,
                'details': str(e),
            }, status=500)
 
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)
 

                    
# ─── View 2: handle_payment ───────────────────────────────────────────────────
#
# Called by the FRONTEND after the webhook has confirmed the payment
# (PaymentCallback polls verify until confirmed, then calls this).
#
# For online payment: converts reservations → real deductions.
# For COD:           creates the order and deducts stock immediately
#                    (customer is physically present / committing to pay).
 
@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def handle_payment(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)
 
    if request.method != 'POST':
        return JsonResponse({'message': 'Invalid request method.'}, status=405)
 
    try:
        data           = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        order_id       = data.get('orderId')
        trans_date     = data.get('date', '')
        online_payment = str(data.get('onlinePayment')).lower() == 'true'
        client_data    = data.get('client', {})
        items          = data.get('items', [])
 
        ordered_products = []
 
        # ── ONLINE PAYMENT ─────────────────────────────────────────────────────
        if online_payment:
            order = Order.objects.get(order_id=order_id, is_paid='confirmed')
            order.transaction_id = transaction_id
            order.save(update_fields=['transaction_id'])
 
            # Convert reservations → real deductions
            # select_related('order') so order.exception is accessible without extra query
            pending_ops = OrderedProduct.objects.filter(
                order=order, stock_deducted=False
            ).select_related()

            print('here is legth of pending:',len(pending_ops))
            print('before entering loop')
            for op in pending_ops:
                    product_stock = ProductStock.objects.select_for_update().get(
                        product_id=op.product_id, size=op.size
                    )
 
                    # Deduct only what was actually reserved (guards against edge cases)
                    deduct = min(op.quantity, product_stock.reserved)
                    product_stock.reserved -= deduct
                    product_stock.quantity -= deduct
                    product_stock.save(update_fields=['quantity', 'reserved'])
 
                    op.stock_deducted = True
                    op.save(update_fields=['stock_deducted'])

                    product = Product.objects.get(id=op.product_id)
                    print('appending')
                    ordered_products.append({
                        "productType" : op.product_type,
                        "size"        : op.size,
                        "quantity"    : op.quantity,
                        "category"    : op.category,
                        "ref"         : op.ref,
                        "name"        : op.name,
                        "id"          : op.product_id,
                        "price"       : op.price,
                        "image"       : product.image.url,
                        "promo"       : product.promo,
                        "available"   : op.available,
                        "exception_id": str(op.exception_id) if order.exception else None,
                    })

 
        # ── CASH ON DELIVERY ───────────────────────────────────────────────────
        else:
            new_client = Client.objects.create(
                first_name = client_data['FirstName'],
                last_name  = client_data['LastName'],
                email      = client_data['Email'],
                phone      = str(client_data['Phone']),
                city       = client_data['City'],
                address    = client_data['Address'],
                ip_address = get_ip_address(request),
            )
            order = Order.objects.create(
                transaction_id = transaction_id,
                date           = trans_date,
                payment_mode   = False,
                is_paid        = 'cod',
                client         = new_client,
                amount         = client_data['Amount'],
                currency       = client_data.get('Currency', 'MAD'),
            )
 
            for item in items:
                try:
                    product_stock = ProductStock.objects.select_for_update().get(
                        product=item['id'], size=item['size']
                    )
                    product       = Product.objects.get(id=item['id'])
                    requested_qty = item['quantity']
                    exception_id  = uuid.uuid4()
 
                    available_qty = product_stock.available_quantity()
                    can_fulfill   = available_qty >= requested_qty
 
                    if can_fulfill:
                        product_stock.quantity -= requested_qty
                    else:
                        shortfall = requested_qty - available_qty
                        product_stock.quantity = product_stock.reserved  # drain to reserved floor
 
                        QuantityExceptions.objects.create(
                            client           = new_client,
                            order            = order,
                            product_type     = product.product_type,
                            product_category = product.category,
                            product_ref      = product.ref,
                            product_name     = product.name,
                            product_size     = item['size'],
                            delta_quantity   = shortfall,
                            exception_id     = exception_id,
                        )
                        order.exception = True
 
                    product_stock.save(update_fields=['quantity'])
 
                    OrderedProduct.objects.create(
                        client         = new_client,
                        order          = order,
                        product_type   = product.product_type,
                        size           = item['size'],
                        quantity       = requested_qty,
                        category       = product.category,
                        ref            = product.ref,
                        name           = product.name,
                        product_id     = product.id,
                        price          = product.price,
                        available      = can_fulfill,
                        exception_id   = exception_id,
                        stock_deducted = True,
                    )
 
                    item['_available'] = can_fulfill
                    ordered_products.append(
                        _build_ordered_product_payload(product, item, order, exception_id)
                    )
 
                except ProductStock.DoesNotExist:
                    continue
 
            order.save()
 
        return JsonResponse({
            'ordered_products': ordered_products,
            'paymentResponse' : {
                'order_id': str(order.order_id),
                'amount'  : order.amount,
                'currency': order.currency,
            },
        }, status=200)
 
    except Order.DoesNotExist:
        return JsonResponse({'message': 'Order not found or not confirmed.'}, status=404)
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)
 
# ─── View 3: handle_verify ────────────────────────────────────────────────────
#
# Polled by the frontend after redirect from YCPay.
# Returns an explicit `status` field so the frontend never needs to
# match reason strings.
#
# status values:
#   'confirmed' → webhook confirmed, frontend can call handle_payment
#   'pending'   → webhook not yet arrived, frontend should retry
#   'failed'    → webhook reported failure, stop retrying
#   'error'     → unexpected server error
 
@api_view(['POST'])
@permission_classes([AllowAny])
def handle_verify(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"verified": False, "status": "error", "reason": "Invalid JSON."}, status=200)
 
    transaction_id = data.get("transaction_id", "").strip()
    order_id       = data.get("order_id", "").strip()
 
    if not transaction_id or not order_id:
        return JsonResponse(
            {"verified": False, "status": "error", "reason": "Missing transaction_id or order_id."},
            status=200,
        )
 
    try:
        try:
            order = Order.objects.get(order_id=order_id, transaction_id=transaction_id)
        except Order.DoesNotExist:
            # Order may not have the transaction_id stamped yet (webhook pending)
            try:
                order = Order.objects.get(order_id=order_id)
            except Order.DoesNotExist:
                # Order doesn't exist at all → still pending (webhook creates it for some flows)
                return JsonResponse(
                    {"verified": False, "status": "pending", "reason": "Order not found yet."},
                    status=200,
                )
 
        if order.is_paid == 'pending':
            return JsonResponse(
                {"verified": False, "status": "pending", "reason": "Payment not confirmed yet."},
                status=200,
            )
 
        if order.is_paid == 'failed':
            return JsonResponse(
                {"verified": False, "status": "failed", "reason": "Payment failed."},
                status=200,
            )
 
        # is_paid == 'confirmed' (set by webhook)
        return JsonResponse({"verified": True, "status": "confirmed"}, status=200)
 
    except Exception as e:
        print(f"[payment/verify] Unexpected error: {e}")
        traceback.print_exc()
        return JsonResponse(
            {"verified": False, "status": "error", "reason": "An error occurred while verifying."},
            status=200,
        )
 
 
# ─── View: retry_payment_url ──────────────────────────────────────────────────
#
# Called when the customer clicks "Try Again" after a failed payment.
#
# Policy:
#   - Reuse the existing Order (same order_id, same reserved stock)
#   - Do NOT touch ProductStock at all — reservation is still held
#   - Reset is_paid → 'pending' so verify polling works again
#   - Generate a fresh YCPay payment URL for the same order
#
# This means stock is never double-reserved and never prematurely released.
 
@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def retry_payment_url(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)
 
    try:
        data       = json.loads(request.body)
        order_id   = data.get('order_id', '').strip()
        token_params  = data.get('tokenParams', {})
        lang       = token_params.get('lang', 'en')
        success_url = token_params.get('success_url')
        error_url   = token_params.get('error_url')
 
        if not order_id:
            return JsonResponse({'message': 'Missing order_id.'}, status=400)
 
        # Fetch the existing failed/timed-out order
        try:
            order = Order.objects.select_for_update().get(
                order_id=order_id,
                payment_mode=True,          # must be an online order
            )
            if order.is_paid in ['confirmed', 'cod']:
                return JsonResponse({'message': 'Order is already treated.'}, status=423)

        except Order.DoesNotExist:
            return JsonResponse({'message': 'Order not found or not retryable.'}, status=404)
 
        # Reset status so verify polling treats it as a fresh attempt
        order.is_paid        = 'pending'
        order.transaction_id = None        # will be stamped by the new webhook
        order.save(update_fields=['is_paid', 'transaction_id'])
 
        client = order.client
 
        # Generate a new YCPay token for the same order_id and amount
        try:
            if is_sandbox:
                YouCanPay.enable_sandbox_mode()
 
            youcan_pay    = YouCanPay.instance().use_keys(key1, key2)
            customer_info = Customer(
                name         = f"{client.first_name} {client.last_name}",
                address      = client.address,
                zip_code     = None,
                country_code = "MA",
                phone        = str(client.phone),
                email        = str(client.email),
            )
            token_data = TokenData(
                order_id      = str(order.order_id),
                amount        = str(int(order.amount) * 100),
                currency      = order.currency,
                customer_ip   = "",
                success_url   = success_url,
                error_url     = error_url,
                customer_info = customer_info,
                metadata      = {"info": "payment_retry"},
            )
            payment_url = youcan_pay.token.create_from(token_data).get_payment_url(lang=lang)
 
            return JsonResponse({
                'payment_url': payment_url,
                'order_id'   : str(order.order_id),
                }, status = status.HTTP_200_OK)
 
        except Exception as e:
            # YCPay call failed — revert status so the order stays retryable
            order.is_paid = 'failed'
            order.save(update_fields=['is_paid'])
            traceback.print_exc()
            return JsonResponse({
                'message': 'Failed to generate retry payment URL.',
                'type'   : type(e).__name__,
                'details': str(e),
            }, status=500)
 
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)
 
 
# ─── View: cancel_payment ─────────────────────────────────────────────────────
#
# Called when the customer clicks "Cancel" on the retry screen.
#
# Policy:
#   - Mark the order as failed
#   - Release all ProductStock.reserved held by this order's OrderedProducts
#   - The order record stays in the DB for admin visibility
 
@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def cancel_payment(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)
 
    try:
        data     = json.loads(request.body)
        order_id = data.get('order_id', '').strip()
 
        if not order_id:
            return JsonResponse({'message': 'Missing order_id.'}, status=400)
 
        try:
            order = Order.objects.select_for_update().get(
                order_id=order_id,
                payment_mode=True,
                is_paid__in=['failed', 'pending'],
            )
        except Order.DoesNotExist:
            return JsonResponse({'message': 'Order not found or already processed.'}, status=423)
 
        # Release reservations
        _release_reservations(order)
 
        order.is_paid = 'failed'
        order.save(update_fields=['is_paid'])
 
        return JsonResponse({'message': 'Order cancelled and stock released.'}, status=200)
 
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)
 
 
 
 
    
@api_view(['POST'])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def get_searched_product(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)

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
@permission_classes([AllowAny])
def get_products(request):
    # if origin_checker(request):
    #     return HttpResponseForbidden(forbbiden_message)

    try:
        product_type = request.GET.get('productType')
        newest = request.GET.get('newest')

        filters = {}

        if product_type:
            filters['product_type'] = product_type

        if newest is not None:
            # Convert string to boolean
            filters['newest'] = newest.lower() == 'true'

        products = Product.objects.filter(**filters) if filters else Product.objects.all()

        serialized_products = ProductSerializer(products, many=True)

        return JsonResponse(
            {'products': serialized_products.data},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {"message": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    

@api_view(['GET'])
@permission_classes([AllowAny])
def check_order(request):
    try:
        order_id = request.GET.get('orderID')
        the_order = Order.objects.prefetch_related('ordered_products').select_related('client').get(order_id=order_id)
        serialized_order = OrderSerializer(the_order, many=False)
        client = serialized_order.data['client']
        products = [
            {
                'name': item.name,
                'ref': item.ref,
                'category': item.category,
                'product_type': item.product_type,
                'size': item.size,
                'quantity': item.quantity,
                'price': item.price,
            }
            for item in the_order.ordered_products.all()
        ]
        return JsonResponse(
            {
                'state': the_order.status,
                'found': True,
                'error': False,
                'client': client,
                'order': {
                    'order_id': str(the_order.order_id),
                    'amount': the_order.amount,
                    'currency': the_order.currency,
                    'is_paid': the_order.is_paid,
                    'payment_mode': 'online' if the_order.payment_mode else 'cash_on_delivery',
                    'delivered': the_order.delivered,
                    'status': the_order.status,
                    'date': the_order.date,
                    'products': products,
                },
            },
            status=200,
        )
    except Order.DoesNotExist:
        return JsonResponse({'found': False, 'error': False}, status=200)
    except Exception:
        return JsonResponse({'error': True}, status=500)









from collections import defaultdict

@api_view(['GET'])
@permission_classes([AllowAny])
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

