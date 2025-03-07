from django.utils.encoding import smart_str
import time
from .models import *
from rest_framework.decorators import api_view
from django.http import HttpResponseForbidden, JsonResponse, StreamingHttpResponse
import datetime
from rest_framework import status
from .serializers import *
import json
import os
from dotenv import load_dotenv
from youcanpay.youcan_pay import YouCanPay
from youcanpay.models.data import Customer
from youcanpay.models.token import TokenData

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
def handlePayment(request):
    try:
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        else:
            if request.method == 'POST':
                data = json.loads(request.body)

                # Extraction des données de la requête
                shoes_data = data.get('shirts_order', [])
                sandals_data = data.get('shoes_order', [])
                shirts_data = data.get('sandals_order', [])
                pants_data = data.get('pants_order', [])
                
                # Créez un dictionnaire des données
                shirts_order = data_dict(shoes_data, Shirt, ShirtDetail, 'Shirts')
                shoes_order = data_dict(sandals_data, Shoe, ShoeDetail, 'Shoes')
                sandals_order = data_dict(shirts_data, Sandal, SandalDetail, 'Sandals')  # Corrigé ici pour utiliser Sandal et SandalDetail
                pants_order = data_dict(pants_data, Pant, PantDetail, 'Pants')
                
                # Récupérer le transaction_id et client_data de la requête
                transaction_id = data.get('transaction_id', '')
                client_data = data.get('client_data', {})
                trans_date = data.get('date','')
                # Liste pour stocker les produits commandés
                ordered_product = {'Shoes':[], 'Sandals':[], 'Shirts':[], 'Pants':[]}
                orders = [shoes_order, sandals_order, shirts_order, pants_order]

                if client_data:
                    new_client =Client.objects.create(
                        transaction_id = transaction_id,
                        order_id = client_data['OrderId'],
                        first_name = client_data['FirstName'],
                        last_name = client_data['LastName'],
                        email = client_data['Email'],
                        phone = str(client_data['Tel']),
                        city = client_data['City'],
                        address = client_data['Address'],
                        amount = client_data['Amount'],
                        date = trans_date)
                
                # Parcourez toutes les commandes
                for item in orders:
                    if len(item['data']) > 0:
                        for p in item['data']:
                            # Obtenez le produit selon le modèle et les détails associés
                            prod = item['modelDetail'].objects.get(productId=p['id'], size=p['size'])
                            prod1 = item['model'].objects.get(id=p['id'])
                            
                            # Si le produit est trouvé, mettez à jour la quantité et sauvegardez
                            if prod:
                                if prod.quantity >= p['quantity']:
                                    prod.quantity -= p['quantity']
                                else :
                                    delta = p['quantity'] - prod.quantity
                                    prod.quantity=0
                                    new_exception = QuantityExceptions(client = new_client,
                                                                       product_type = prod1.productType,
                                                                       product_category = prod1.category,
                                                                       product_ref = prod1.ref,
                                                                       product_name=prod1.name,
                                                                       product_size=p['size'],
                                                                       delta_quantity = delta)
                                    new_exception.save()
                                prod.save()
                                
                                # Ajoutez les informations du produit commandé à la réponse
                                ordered_product[item['productType']].append({
                                    "productType": prod1.productType,
                                    "size": p['size'],
                                    "quantity": p['quantity'],
                                    "category": prod1.category,
                                    "ref": prod1.ref,
                                    "name": prod1.name,
                                    "id": prod1.id,
                                    "image":prod1.image.url,
                                    "promo":prod1.promo,
                                    "price":prod1.price, })
                if new_client:
                    for key in ordered_product.keys():
                        for p in ordered_product[key]:
                            ProductOrdered.objects.create(
                                client = new_client,
                                product_type = p["productType"],
                                size = p["size"],
                                quantity = p["quantity"],
                                category = p["category"],
                                ref = p["ref"],
                                name = p["name"],
                                product_id = p["id"]
                            )
                # Retourner une réponse JSON avec la liste des produits commandés
                return JsonResponse({'ordered_products': ordered_product}, status=200)

    except Exception as e:
        print(e)
        return JsonResponse({'message': f'An error occurred: {str(e)}'}, status=400)
                    
@api_view(['POST'])
def get_ip(request):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    return JsonResponse({'ip': ip})

@api_view(['POST'])
def getPaymentToken(request):
    if is_sandbox: YouCanPay.enable_sandbox_mode()
    youcan_pay = YouCanPay.instance().use_keys(
    key1,
    key2,
    )
    data = json.loads(request.body)
    customer_params = data.get('customer', {})
    token_params = data.get('tokenParams', {})
    customer_info = Customer(
        name = customer_params.get("name"), 
        address = customer_params.get('address'), 
        zip_code = customer_params.get('zip_code'), 
        city = customer_params.get('city'), 
        state = customer_params.get('state'),
        country_code = customer_params.get('country_code'), 
        phone = customer_params.get('phone'), 
        email = customer_params.get('email'),
    )
    
    token_params = TokenData(
        amount = token_params.get('amount'),
        currency = token_params.get('currency'),
        customer_ip = token_params.get('customer'),
        order_id = token_params.get('order_id'),
        success_url = token_params.get('success_url'),
        error_url = token_params.get('error_url'),
        customer_info= customer_info,
    )
    try:
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        else:                                   
            token = youcan_pay.token.create_from(token_params)
            return  JsonResponse({'token': token.id})
    except Exception as e :
        return JsonResponse({'message': f'error occured : {str(e)}'})
    
@api_view(['POST'])
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
def get_newest_shoes(request):
    products = Shoe.objects.filter(newest=True)
    products_serializers = ShoeSerializer(products, many =True)
    try : 
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 

@api_view(['GET'])
def get_newest_sandals(request): 
    products = Sandal.objects.filter(newest=True)
    products_serializers = SandalSerializer(products, many =True)
    try : 
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_newest_shirts(request):
    products = Shirt.objects.filter(newest=True)
    products_serializers = ShirtSerializer(products, many =True)
    try :
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_newest_pants(request):
    products = Pant.objects.filter(newest=True)
    products_serializers = PantSerializer(products, many =True)
    try :
        if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
        return JsonResponse({'products' :products_serializers.data}, status=status.HTTP_200_OK)
    except Exception as e : return JsonResponse({"message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_req(request):
    referer = request.META.get('X-Forwarded-For','none')
    return JsonResponse({'req':origin_checker(request)})


    



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

