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
from youcanpay.youcan_pay import YouCanPay
from youcanpay.models.data import Customer
from youcanpay.models.token import TokenData
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication



@csrf_exempt
def envoyer_email(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        print("POST:", request.POST)
        print("FILES:", request.FILES)

        # 🔹 récupérer données
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        to = request.POST.get("to", "").strip()
        cc = request.POST.get("cc", "")
        bcc = request.POST.get("bcc", "")

        file = request.FILES.get("file")

        if not subject or not body or not to:
            return JsonResponse({"error": "Missing fields"}, status=400)

        # 🔹 emails
        to_list = [e.strip() for e in to.split(",") if e.strip()]
        cc_list = [e.strip() for e in cc.split(",") if e.strip()]
        bcc_list = [e.strip() for e in bcc.split(",") if e.strip()]

        all_recipients = to_list + cc_list + bcc_list

        # 🔹 config Gmail
        sender_email = settings.EMAIL_HOST_USER
        password = settings.EMAIL_HOST_PASSWORD

        # 🔥 créer email
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = ", ".join(to_list)
        msg["Cc"] = ", ".join(cc_list)
        msg["Subject"] = subject

        # ✨ HTML + TEXT
        html_content = f"""
        <div style="font-family:Arial;max-width:600px;margin:auto;">
            <h2>Hello 👋</h2>
            <p>{body}</p>
        </div>
        """

        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # 📎 fichier
        if file:
            part = MIMEApplication(file.read(), Name=file.name)
            part["Content-Disposition"] = f'attachment; filename="{file.name}"'
            msg.attach(part)

        # 🚀 SMTP
        smtp_server = "smtp.gmail.com"
        port = 587

        print("AVANT SMTP")

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender_email, password)

        server.sendmail(sender_email, all_recipients, msg.as_string())

        server.quit()

        print("EMAIL SENT SUCCESS")

        return JsonResponse({"message": "Email sent successfully via smtplib ✅"})

    except Exception as e:
        print("🔥 ERROR:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)


load_dotenv()
key1 = os.environ.get('payment_second_key')
key2 = os.environ.get('payment_first_key')
allowed_origins = os.environ.get('REQUEST_ALLOWED_ORIGINS')
is_sandbox = os.environ.get('IS_SANDBOX_MODE')
forbbiden_message = 'Forbidden-Acces denied'
ALLOWED_ORIGINS = [allowed_origins]
def origin_checker(request):
    referer = request.META.get('HTTP_REFERER','')
    if referer in ALLOWED_ORIGINS: return False
    else : return True


# Create your views here.         
     
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
@transaction.atomic
def handle_payment(request):
    if origin_checker(request):
        return HttpResponseForbidden(forbbiden_message)

    if request.method != 'POST':
        return JsonResponse({'message': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        order_id = data.get('orderId')
        trans_date = data.get('date', '')
        online_payment = str(data.get('onlinePayment')).lower() == 'true'
        client_data = data.get('client', {})
        items = data.get('items', [])

        ordered_products = []

        # Créer ou récupérer la commande
        if online_payment:
            order = Order.objects.get(order_id=order_id, waiting=True)
            order.transaction_id = transaction_id
            order.date = trans_date
            order.waiting = False
            order.payment_mode = online_payment
        else:
            new_client = Client.objects.create(
                first_name=client_data['FirstName'],
                last_name=client_data['LastName'],
                email=client_data['Email'],
                phone=str(client_data['Phone']),
                city=client_data['City'],
                address=client_data['Address']
            )
            order = Order.objects.create(
                transaction_id=transaction_id,
                date=trans_date,
                payment_mode=online_payment,
                client=new_client,
                amount=client_data['Amount'],
                waiting=False,
                currency=client_data['Currency']
            )

        # Traitement des produits

            for item in items:
                try:
                    product_stock = ProductStock.objects.select_for_update().get(product=item['id'], size=item['size'])
                    product = Product.objects.get(id=item['id'])

                    requested_qty = item['quantity']
                    available = product_stock.quantity >= requested_qty
                    exception_id = uuid.uuid4()
                    if available:
                        product_stock.quantity -= requested_qty
                    else:
                        delta = requested_qty - product_stock.quantity
                        product_stock.quantity = 0
                        exception = QuantityExceptions.objects.create(
                            client=order.client,
                            order=order,
                            product_type=product.product_type,
                            product_category=product.category,
                            product_ref=product.ref,
                            product_name=product.name,
                            product_size=item['size'],
                            delta_quantity=delta,
                            exception_id = exception_id
                        )
                        order.exception = True

                    product_stock.save()

                    # Enregistrement du produit commandé
                    ProductOrdered.objects.create(
                        client=order.client,
                        order=order,
                        product_type=product.product_type,
                        size=item['size'],
                        quantity=requested_qty,
                        category=product.category,
                        ref=product.ref,
                        name=product.name,
                        product_id=product.id,
                        price=product.price,
                        available=available,
                        exception_id = exception_id
                    )

                    ordered_products.append({
                        "productType": product.product_type,
                        "size": item['size'],
                        "quantity": requested_qty,
                        "category": product.category,
                        "ref": product.ref,
                        "name": product.name,
                        "id": product.id,
                        "image": product.image.url if product.image else '',
                        "promo": product.promo,
                        "price": product.price,
                        "available": available,
                        "exception_id": exception_id if order.exception else None
                    })

                except ProductStock.DoesNotExist:
                    continue  # ou enregistrer comme erreur produit inexistant

        order.save()
        return JsonResponse({
            'ordered_products': ordered_products,
            'paymentResponse': {
                'order_id': str(order.order_id),
                'amount': order.amount,
                'currency': order.currency
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)

                    
@api_view(['POST'])
@permission_classes([AllowAny])
def get_ip(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    return JsonResponse({'ip': ip})

@api_view(['POST'])
@permission_classes([AllowAny])
def getPaymentToken(request):
    if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
    
    if is_sandbox: YouCanPay.enable_sandbox_mode()

    youcan_pay = YouCanPay.instance().use_keys(
    key1,
    key2,
    )
    data = json.loads(request.body)
    customer_params = data.get('customer', {})
    token_params = data.get('tokenParams', {})

    new_client = Client.objects.create(
                        first_name = customer_params['first_name'],
                        last_name = customer_params['last_name'],
                        email = customer_params['email'],
                        phone = str(customer_params['phone']),
                        city = customer_params['city'],
                        address = customer_params['address'])

    new_order = Order.objects.create(
                        client = new_client,
                        amount = token_params.get('amount'),
                        )
    

    customer_info = Customer(
        name = str(customer_params.get("first_name") + customer_params.get("last_name")),
        address = customer_params.get('address'), 
        zip_code = customer_params.get('zip_code'), 
        city = customer_params.get('city'), 
        state = customer_params.get('state'),
        country_code = customer_params.get('country_code'), 
        phone = customer_params.get('phone'), 
        email = customer_params.get('email'),
    )
    
    token_params = TokenData(
        amount = token_params.get('amount')*100,
        currency = token_params.get('currency'),
        customer_ip = '', # token_params.get('customer'),
        order_id = str(new_order.order_id),
        success_url = token_params.get('success_url'),
        error_url = token_params.get('error_url'),
        customer_info= customer_info,
    )
    try:                                 
        token = youcan_pay.token.create_from(token_params)
        return  JsonResponse({'token': token.id, 'order_id': str(new_order.order_id)})
    except Exception as e :
        return JsonResponse({'message': f'error occured : {str(e)}'})
    
@api_view(['POST'])
@permission_classes([AllowAny])
def add_review(request):
    if request.method == 'POST':
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        else:
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
                return JsonResponse({'message': f'Error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_reviews(request):
    if origin_checker(request): return HttpResponseForbidden(forbbiden_message)
    else:
        try:
            pid = int(request.GET.get('productId'))
            product_type = request.GET.get('productType')
            product_reviews = ProductReview.objects.filter(product_id = pid, product_type = product_type)
            serialized_reviews = ProductReviewSerializer(product_reviews, many=True)
            products = Product.objects.filter(product_type=product_type, newest=True)
            serialized_products = ProductSerializer(products, many=True)
            return JsonResponse({'reviews':serialized_reviews.data, 'products':serialized_products.data}, status=status.HTTP_200_OK)
        except Exception as e:
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
            category=cat,
            ref=ref,
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
        the_order = Order.objects.get(order_id = order_id)
        state = the_order.status
        serialized_order = OrderSerializer(the_order, many = False)
        client = serialized_order.data["client"]
        return JsonResponse({'state': state, 'found': True, 'error':False, 'client' : client}, status=status.HTTP_200_OK)
    except Order.DoesNotExist:
        return JsonResponse({'found': False, 'error':False})
    except Exception as e :
        return JsonResponse({'error':True})









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












































#EventSoure functions
# def event_stream_shoes():
#     while True:
#         products = Shoe.objects.all()
#         serializer = ShoeSerializer(products, many=True)
#         data = json.dumps({'data': serializer.data})
#         yield f"data: {smart_str(data)}\n\n"
#         time.sleep(2)

# def sse_shoes(request):
#         if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
#         response = StreamingHttpResponse(event_stream_shoes(), content_type='text/event-stream')
#         response['Cache-Control'] = 'no-cache'
#         return response



