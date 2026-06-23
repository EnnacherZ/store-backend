import os, json
from .models import *
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse
from rest_framework import status
from .serializers import *
from dotenv import load_dotenv
from django.db import transaction
import traceback


from youcanpay.youcan_pay import YouCanPay
from youcanpay.models.token import TokenData
from youcanpay.models.data import Customer
from dashboard.authentication import CookieJWTAuthentication
from dashboard.permissions import OriginPermission


load_dotenv()
key1 = os.environ.get('payment_second_key')
key2 = os.environ.get('payment_first_key')
is_sandbox = os.environ.get('IS_SANDBOX_MODE') == 'True'


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_ip_address(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')



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


def _award_loyalty_points(profile, points):
    """
    Add `points` to the ClientProfile's loyalty_points balance.
    Uses F() expression + filter() to avoid race conditions and
    to be a no-op when profile is None (guest) or points == 0.
    """
    if not profile or points <= 0:
        return
    ClientProfile.objects.filter(pk=profile.pk).update(
        loyalty_points=models.F('loyalty_points') + points
    )


def get_or_create_client(client_data: dict, request) -> Client:
    """
    Creates (or reuses) a Client row and links it to a ClientProfile
    if the request carries a valid auth cookie.
    """
    profile = None

    try:
        auth = CookieJWTAuthentication()
        result = auth.authenticate(request)
        if result is not None:
            user, _ = result
            if getattr(user, 'role', None) == 'client':
                profile = ClientProfile.objects.get(user=user)
    except Exception:
        pass

    if profile:
        client, _ = Client.objects.get_or_create(
            email   = client_data['Email'].strip().lower(),
            profile = profile,
            defaults={
                'first_name': client_data['FirstName'],
                'last_name' : client_data['LastName'],
                'phone'     : client_data['Phone'],
                'city'      : client_data['City'],
                'address'   : client_data['Address'],
                'ip_address': client_data.get('ip_address'),
            }
        )
        client.first_name = client_data['FirstName']
        client.last_name  = client_data['LastName']
        client.phone      = client_data['Phone']
        client.city       = client_data['City']
        client.address    = client_data['Address']
        client.save()
    else:
        client = Client.objects.create(
            first_name = client_data['FirstName'],
            last_name  = client_data['LastName'],
            email      = client_data['Email'].strip().lower(),
            phone      = client_data['Phone'],
            city       = client_data['City'],
            address    = client_data['Address'],
            ip_address = client_data.get('ip_address'),
            profile    = None,
        )

    return client



def _resolve_profile(request):
    """
    Returns the ClientProfile linked to the authenticated user,
    or None if the request carries no valid client cookie.
    Never raises — guest flow must not be broken.
    """
    try:
        auth   = CookieJWTAuthentication()
        result = auth.authenticate(request)
        if result is None:
            return None
        user, _ = result
        if getattr(user, 'role', None) != 'client':
            return None
        return user.client_profile
    except Exception:
        return None


def _record_exception(client, order, product, size, shortfall):
    """
    Creates a QuantityExceptions row for a stock shortfall.
    Returns the new exception_id (UUID).
    """
    exception_id = uuid.uuid4()
    QuantityExceptions.objects.create(
        client           = client,
        order            = order,
        product_type     = product.product_type.name,
        product_category = product.category.name,
        product_ref      = product.id,
        product_name     = product.name,
        product_size     = size,
        delta_quantity   = shortfall,
        exception_id     = exception_id,
    )
    return exception_id


def _primary_image_url(product):
    """
    Returns the primary product image URL, or the first available image,
    or None if the product has no images at all.
    """
    image = product.images.filter(is_primary=True).first() or product.images.first()
    return image.image.url if image else None


# ─── Shipping ─────────────────────────────────────────────────────────────────
SHIPPING_FEE = 0.00   # Free shipping


# ─── View 1: getPaymentUrl ────────────────────────────────────────────────────
#
# Creates Client → Order → OrderedProducts (with stock reservation),
# calculates the total server-side, then requests a YouCanPay token.
#
@api_view(['POST'])
@permission_classes([OriginPermission])
@transaction.atomic
def getPaymentUrl(request):
    try:
        data = json.loads(request.body)

        customer_params = data.get('customer', {})
        token_params    = data.get('tokenParams', {})
        items           = data.get('items', [])

        currency    = str(token_params.get('currency', 'MAD'))
        success_url = token_params.get('success_url')
        error_url   = token_params.get('error_url')
        lang        = token_params.get('lang')
        ip_address  = get_ip_address(request)

        # ── Create client ─────────────────────────────────────────
        profile    = _resolve_profile(request)
        new_client = Client.objects.create(
            first_name = customer_params['first_name'],
            last_name  = customer_params['last_name'],
            email      = customer_params['email'],
            phone      = str(customer_params['phone']),
            city       = customer_params['city'],
            address    = customer_params['address'],
            ip_address = ip_address,
            profile    = profile,
        )

        # ── Create order (amount computed below) ──────────────────
        new_order = Order.objects.create(
            client       = new_client,
            amount       = 0,
            currency     = currency,
            payment_mode = True,
            is_paid      = 'pending',
        )

        total_amount = 0

        # ── Process items ─────────────────────────────────────────
        for item in items:
            try:
                product = Product.objects.select_related(
                    'category__product_type'
                ).get(id=item['id'])

                product_stock = ProductStock.objects.select_for_update().get(
                    product=product,
                    size=item['size']
                )

                requested_qty = int(item['quantity'])
                available_qty = product_stock.available_quantity()
                can_fulfill   = available_qty >= requested_qty
                reserved_qty  = min(requested_qty, available_qty)

                # Reserve stock
                product_stock.reserved += reserved_qty
                product_stock.save(update_fields=['reserved'])

                # ── Price calculation (server-side only) ──────────
                unit_price       = product.price
                promo            = product.promo or 0
                discounted_price = unit_price * (1 - promo / 100)
                line_total       = discounted_price * reserved_qty
                total_amount    += line_total

                exception_id = None

                if not can_fulfill:
                    shortfall    = requested_qty - available_qty
                    exception_id = _record_exception(
                        new_client, new_order, product, item['size'], shortfall
                    )
                    new_order.exception = True
                    new_order.save(update_fields=['exception'])

                OrderedProduct.objects.create(
                    client         = new_client,
                    order          = new_order,
                    product_type   = product.product_type.name,
                    size           = item['size'],
                    quantity       = requested_qty,
                    category       = product.category.name,
                    ref            = product.ref,
                    name           = product.name,
                    product_id     = product.id,
                    price          = product.price,
                    available      = can_fulfill,
                    exception_id   = exception_id,
                    stock_deducted = False,
                )

            except ProductStock.DoesNotExist:
                continue

        # ── Final amount (products + shipping) ────────────────────
        new_order.amount = round(total_amount + SHIPPING_FEE, 2)
        new_order.save(update_fields=['amount'])

        # ── Payment integration ───────────────────────────────────
        try:
            if is_sandbox:
                YouCanPay.enable_sandbox_mode()

            youcan_pay = YouCanPay.instance().use_keys(key1, key2)

            customer_info = Customer(
                name         = f"{new_client.first_name} {new_client.last_name}",
                address      = new_client.address,
                zip_code     = None,
                country_code = "MA",
                phone        = str(new_client.phone),
                email        = str(new_client.email),
            )

            token_data = TokenData(
                order_id      = str(new_order.order_id),
                amount        = str(int(new_order.amount * 100)),
                currency      = currency,
                customer_ip   = "",
                success_url   = f"{success_url}?order_id={new_order.order_id}",
                error_url     = error_url,
                customer_info = customer_info,
                metadata      = {"info": "payment"},
            )

            payment_url = youcan_pay.token.create_from(token_data).get_payment_url(lang=lang)

            return JsonResponse({
                "payment_url" : payment_url,
                "order_id"    : str(new_order.order_id),
                "amount"      : new_order.amount,
                "currency"    : currency,
                "shipping_fee": SHIPPING_FEE,
            })

        except Exception as e:
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
        return JsonResponse({
            'message': f'An error occurred: {str(e)}'
        }, status=400)


# ─── View 2: handle_payment ───────────────────────────────────────────────────
#
# Called by the FRONTEND after the webhook has confirmed the payment.
#
# Online payment : converts reservations → real deductions.
# COD            : creates the order and deducts stock immediately.
#
# Loyalty points : awarded to registered clients (profile != None) only,
#                  calculated as product.loyalty_points × fulfilled quantity.
#                  Points are only earned for stock that was actually deducted
#                  (shortfall items that couldn't be fulfilled are excluded).
#
@api_view(['POST'])
@permission_classes([OriginPermission])
@transaction.atomic
def handle_payment(request):

    if request.method != 'POST':
        return JsonResponse({'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)

        transaction_id = data.get('transaction_id')
        order_id       = data.get('orderId')
        online_payment = str(data.get('onlinePayment')).lower() == 'true'

        client_data = data.get('client', {})
        items       = data.get('items', [])

        ordered_products = []

        # ──────────────────────────────────────────────────────────
        # ONLINE PAYMENT — convert reservations to real deductions
        # ──────────────────────────────────────────────────────────
        if online_payment:

            order = Order.objects.select_for_update().get(
                order_id=order_id,
                is_paid='confirmed'
            )

            order.transaction_id = transaction_id
            order.save(update_fields=['transaction_id'])

            pending_ops = OrderedProduct.objects.filter(
                order=order,
                stock_deducted=False
            )

            # Accumulate loyalty points across all fulfilled items
            total_loyalty_points = 0

            for op in pending_ops:

                product_stock = ProductStock.objects.select_for_update().get(
                    product_id=op.product_id,
                    size=op.size
                )

                # `deduct` = quantity actually removed from physical stock
                deduct = min(op.quantity, product_stock.reserved)

                product_stock.reserved -= deduct
                product_stock.quantity -= deduct
                product_stock.save(update_fields=['quantity', 'reserved'])

                op.stock_deducted = True
                op.save(update_fields=['stock_deducted'])

                product = Product.objects.get(id=op.product_id)

                # Points are earned only for the quantity actually fulfilled
                total_loyalty_points += product.loyalty_points * deduct

                ordered_products.append({
                    "productType" : op.product_type,
                    "size"        : op.size,
                    "quantity"    : op.quantity,
                    "category"    : op.category,
                    "ref"         : op.ref,
                    "name"        : op.name,
                    "id"          : op.product_id,
                    "price"       : op.price,
                    "image"       : _primary_image_url(product),
                    "promo"       : product.promo,
                    "available"   : op.available,
                    "exception_id": str(op.exception_id) if op.exception_id else None,
                })

            # Award accumulated points to the registered client's profile (guests: no-op)
            _award_loyalty_points(order.client.profile, total_loyalty_points)

        # ──────────────────────────────────────────────────────────
        # CASH ON DELIVERY — create order and deduct stock now
        # ──────────────────────────────────────────────────────────
        else:

            profile    = _resolve_profile(request)
            new_client = Client.objects.create(
                first_name = client_data['FirstName'],
                last_name  = client_data['LastName'],
                email      = client_data['Email'],
                phone      = str(client_data['Phone']),
                city       = client_data['City'],
                address    = client_data['Address'],
                ip_address = get_ip_address(request),
                profile    = profile,
            )
            order = Order.objects.create(
                transaction_id = transaction_id,
                payment_mode   = False,
                is_paid        = 'cod',
                client         = new_client,
                amount         = 0,
                currency       = client_data.get('Currency', 'MAD'),
            )

            total_amount         = 0
            total_loyalty_points = 0   # accumulator for this order

            for item in items:
                try:
                    product = Product.objects.select_related(
                        'category__product_type'
                    ).get(id=item['id'])

                    product_stock = ProductStock.objects.select_for_update().get(
                        product=product,
                        size=item['size']
                    )

                    requested_qty = int(item['quantity'])
                    available_qty = product_stock.available_quantity()
                    can_fulfill   = available_qty >= requested_qty
                    deducted_qty  = min(requested_qty, available_qty)

                    # Deduct stock immediately for COD
                    product_stock.quantity -= deducted_qty
                    product_stock.save(update_fields=['quantity'])

                    # ── Price calculation (server-side only) ──────
                    unit_price       = product.price
                    promo            = product.promo or 0
                    discounted_price = unit_price * (1 - promo / 100)
                    line_total       = discounted_price * deducted_qty
                    total_amount    += line_total

                    # Points are earned only for the quantity actually deducted
                    total_loyalty_points += product.loyalty_points * deducted_qty

                    exception_id = None

                    if not can_fulfill:
                        shortfall    = requested_qty - available_qty
                        exception_id = _record_exception(
                            new_client, order, product, item['size'], shortfall
                        )
                        order.exception = True
                        order.save(update_fields=['exception'])

                    OrderedProduct.objects.create(
                        client         = new_client,
                        order          = order,
                        product_type   = product.product_type.name,
                        size           = item['size'],
                        quantity       = requested_qty,
                        category       = product.category.name,
                        ref            = product.ref,
                        name           = product.name,
                        product_id     = product.id,
                        price          = product.price,
                        available      = can_fulfill,
                        exception_id   = exception_id,
                        stock_deducted = True,
                    )

                    ordered_products.append({
                        "productType" : product.product_type.name,
                        "size"        : item['size'],
                        "quantity"    : requested_qty,
                        "category"    : product.category.name,
                        "ref"         : product.ref,
                        "name"        : product.name,
                        "id"          : product.id,
                        "price"       : product.price,
                        "image"       : _primary_image_url(product),
                        "promo"       : product.promo,
                        "available"   : can_fulfill,
                        "exception_id": str(exception_id) if exception_id else None,
                    })

                except ProductStock.DoesNotExist:
                    continue

            # Final amount = products + free shipping
            order.amount = round(total_amount + SHIPPING_FEE, 2)
            order.save(update_fields=['amount'])

            # Award accumulated points to the registered client's profile (guests: no-op)
            _award_loyalty_points(profile, total_loyalty_points)


        return JsonResponse({
            'ordered_products': ordered_products,
            'paymentResponse': {
                'order_id'    : str(order.order_id),
                'amount'      : order.amount,
                'currency'    : order.currency,
                'shipping_fee': SHIPPING_FEE,
            },
        }, status=200)

    except Order.DoesNotExist:
        return JsonResponse({
            'message': 'Order not found or not confirmed.'
        }, status=404)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            'message': f'An error occurred: {str(e)}'
        }, status=400)


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
@permission_classes([OriginPermission])
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
            try:
                order = Order.objects.get(order_id=order_id)
            except Order.DoesNotExist:
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

@api_view(['POST'])
@permission_classes([OriginPermission])
@transaction.atomic
def retry_payment_url(request):

    try:
        data        = json.loads(request.body)
        order_id    = data.get('order_id', '').strip()
        token_params = data.get('tokenParams', {})
        lang        = token_params.get('lang', 'en')
        success_url = token_params.get('success_url')
        error_url   = token_params.get('error_url')

        if not order_id:
            return JsonResponse({'message': 'Missing order_id.'}, status=400)

        try:
            order = Order.objects.select_for_update().get(
                order_id=order_id,
                payment_mode=True,
            )
            if order.is_paid in ['confirmed', 'cod']:
                return JsonResponse({'message': 'Order is already treated.'}, status=423)

        except Order.DoesNotExist:
            return JsonResponse({'message': 'Order not found or not retryable.'}, status=404)

        order.is_paid        = 'pending'
        order.transaction_id = None
        order.save(update_fields=['is_paid', 'transaction_id'])

        client = order.client

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
                }, status=status.HTTP_200_OK)

        except Exception as e:
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
@permission_classes([OriginPermission])
@transaction.atomic
def cancel_payment(request):

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

        _release_reservations(order)

        order.is_paid = 'failed'
        order.save(update_fields=['is_paid'])

        return JsonResponse({'message': 'Order cancelled and stock released.'}, status=200)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)