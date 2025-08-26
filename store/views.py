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


models_dict = {'Shoe':(Shoe, ShoeSerializer, ShoeDetail, ShoeDetailSerializer), 
               'Sandal':(Sandal, SandalSerializer, SandalDetail, SandalDetailSerializer), 
               'Shirt':(Shirt, ShirtSerializer, ShirtDetail, ShirtDetailSerializer), 
               'Pant':(Pant, PantSerializer, PantDetail, PantDetailSerializer)}

# Create your views here.         
     
def data_dict(data, model, modelDetail, productType):return({'data':data, 'model':model, 'modelDetail':modelDetail, 'productType':productType})
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

        # Chargement des données produits
        products_data = {
            'Shoes': (data.get('shoes_order', []), Shoe, ShoeDetail),
            'Sandals': (data.get('sandals_order', []), Sandal, SandalDetail),
            'Shirts': (data.get('shirts_order', []), Shirt, ShirtDetail),
            'Pants': (data.get('pants_order', []), Pant, PantDetail),
        }

        ordered_products = {ptype: [] for ptype in products_data}

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
        for product_type, (items_data, model, model_detail) in products_data.items():
            for item in items_data:
                try:
                    detail_obj = model_detail.objects.select_for_update().get(productId=item['id'], size=item['size'])
                    product_obj = model.objects.get(id=item['id'])

                    requested_qty = item['quantity']
                    available = detail_obj.quantity >= requested_qty
                    exception_id = uuid.uuid4()
                    if available:
                        detail_obj.quantity -= requested_qty
                    else:
                        delta = requested_qty - detail_obj.quantity
                        detail_obj.quantity = 0
                        exception = QuantityExceptions.objects.create(
                            client=order.client,
                            order=order,
                            product_type=product_obj.productType,
                            product_category=product_obj.category,
                            product_ref=product_obj.ref,
                            product_name=product_obj.name,
                            product_size=item['size'],
                            delta_quantity=delta,
                            exception_id = exception_id
                        )
                        order.exception = True

                    detail_obj.save()

                    # Enregistrement du produit commandé
                    ProductOrdered.objects.create(
                        client=order.client,
                        order=order,
                        product_type=product_obj.productType,
                        size=item['size'],
                        quantity=requested_qty,
                        category=product_obj.category,
                        ref=product_obj.ref,
                        name=product_obj.name,
                        product_id=product_obj.id,
                        price=product_obj.price,
                        available=available,
                        exception_id = exception_id
                    )

                    ordered_products[product_type].append({
                        "productType": product_obj.productType,
                        "size": item['size'],
                        "quantity": requested_qty,
                        "category": product_obj.category,
                        "ref": product_obj.ref,
                        "name": product_obj.name,
                        "id": product_obj.id,
                        "image": product_obj.image.url if product_obj.image else '',
                        "promo": product_obj.promo,
                        "price": product_obj.price,
                        "available": available,
                        "exception_id": exception_id if order.exception else None
                    })

                except model_detail.DoesNotExist:
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
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        else:                                   
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
                product_type = data.get('productType', '')
                product_id = data.get('productId', None)
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
                new_review = ProductReviews(
                    product_type=product_type,
                    product_id=product_id,
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
            pro_id = int(request.GET.get('productId'))
            pro_type = request.GET.get('productType')
            product_reviews = ProductReviews.objects.filter(product_id = pro_id, product_type = pro_type)
            serialized_reviews = ProductReviewsSerializer(product_reviews, many=True)
            products = models_dict[pro_type][0].objects.filter(newest=True)
            serialized_products = models_dict[pro_type][1](products, many=True)
            return JsonResponse({'reviews':serialized_reviews.data, 'products':serialized_products.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({'message': f'Error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([AllowAny])
def get_searched_product(request):
    if origin_checker(request) : return HttpResponseForbidden(forbbiden_message)
    else:
        try:
            prod= request.GET.get('product',None)
            cat = request.GET.get('category',None)
            ref = request.GET.get('ref',None)
            pid = int(request.GET.get('id',None))
            data_dict = models_dict[prod]
            searched_product = data_dict[0].objects.filter(category=cat, ref=ref, id=pid)
            serialized = data_dict[1](searched_product, many=True)
            product_reviews = ProductReviews.objects.filter(product_id = pid, product_type = prod).order_by('-stars')
            serialized_reviews = ProductReviewsSerializer(product_reviews, many=True)
            products = models_dict[prod][0].objects.filter(newest=True)
            serialized_products = models_dict[prod][1](products, many=True)
            return JsonResponse({"product":serialized.data, "products":serialized_products.data, 'reviews':serialized_reviews.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({'message': f'error occured : {str(e)}'})   


@api_view(['GET'])
@permission_classes([AllowAny])
def get_newest_products(request,):
    try:
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        else:
            shoes_products = Shoe.objects.filter(newest=True)
            sandals_products = Sandal.objects.filter(newest=True)
            shirts_products = Shirt.objects.filter(newest=True)
            pants_products = Pant.objects.filter(newest=True)
            shoes_serializer = ShoeSerializer(shoes_products, many=True)
            sandals_serializer = SandalSerializer(sandals_products, many=True)
            shirts_serializer = ShirtSerializer(shirts_products, many=True)
            pants_serializer = PantSerializer(pants_products, many=True)
            return JsonResponse({'list_shoes': shoes_serializer.data,
                                'list_sandals': sandals_serializer.data,
                                'list_shirts' : shirts_serializer.data,
                                'list_pants':pants_serializer.data,}, status=status.HTTP_200_OK
                                )
    except Exception as e:
        print(e)
        return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_newest_shoes(request):
    products = Shoe.objects.filter(newest=True)
    products_serializers = ShoeSerializer(products, many =True)
    try : 
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 

@api_view(['GET'])
@permission_classes([AllowAny])
def get_newest_sandals(request): 
    products = Sandal.objects.filter(newest=True)
    products_serializers = SandalSerializer(products, many =True)
    try : 
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_newest_shirts(request):
    products = Shirt.objects.filter(newest=True)
    products_serializers = ShirtSerializer(products, many =True)
    try :
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_newest_pants(request):
    products = Pant.objects.filter(newest=True)
    products_serializers = PantSerializer(products, many =True)
    try :
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([AllowAny])
def get_products(request):
    if not(origin_checker(request)):
        try:
            productType = request.GET.get('productType',None)
            type_models :tuple = models_dict[productType]
            products = type_models[0].objects.all()
            products_details = type_models[2].objects.all()
            serialized_products = type_models[1](products, many=True)
            serialized_details = type_models[3](products_details, many=True)
            return JsonResponse({'products':serialized_products.data, 'products_details':serialized_details.data}, status=status.HTTP_200_OK)
        except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else : return HttpResponseForbidden(forbbiden_message) 

    

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
























































#EventSoure functions
def event_stream_shoes():
    while True:
        products = Shoe.objects.all()
        serializer = ShoeSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def event_stream_shoes_newest():
    while True:
        products = Shoe.objects.filter(newest=True)
        serializer = ShoeSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)   
def event_stream_shoesSizes():
    while True:
        products = ShoeDetail.objects.all()
        serializer = ShoeDetailSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def sse_shoes(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shoes(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        return response
def sse_shoes_new(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shoes_newest(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_sizes_shoes(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shoesSizes(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response


def event_stream_sandals():
    while True:
        products = Sandal.objects.all()
        serializer = SandalSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def event_stream_sandals_newest():
    while True:
        products = Sandal.objects.filter(newest=True)
        serializer = SandalSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)   
def event_stream_sandalsSizes():
    while True:
        products = SandalDetail.objects.all()
        serializer = SandalDetailSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def sse_sandals(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_sandals(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_sandals_new(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_sandals_newest(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_sizes_sandals(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_sandalsSizes(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response



def event_stream_shirts():
    while True:
        products = Shirt.objects.all()
        serializer = ShirtSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def event_stream_shirts_newest():
    while True:
        products = Shirt.objects.filter(newest=True)
        serializer = ShirtSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)   
def event_stream_shirtsSizes():
    while True:
        products = ShirtDetail.objects.all()
        serializer = ShirtDetailSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def sse_shirts(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shirts(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_shirts_new(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shirts_newest(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_sizes_shirts(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_shirtsSizes(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response



def event_stream_pants():
    while True:
        products = Pant.objects.all()
        serializer = PantSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def event_stream_pants_newest():
    while True:
        products = Pant.objects.filter(newest=True)
        serializer = PantSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)   
def event_stream_pantsSizes():
    while True:
        products = PantDetail.objects.all()
        serializer = PantDetailSerializer(products, many=True)
        data = json.dumps({'data': serializer.data})
        yield f"data: {smart_str(data)}\n\n"
        time.sleep(2)
def sse_pants(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_pants(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_pants_new(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_pants_newest(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response
def sse_sizes_pants(request):
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        response = StreamingHttpResponse(event_stream_pantsSizes(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        origin = request.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            response['Access-Control-Allow-Origin'] = origin
        return response

