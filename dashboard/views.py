from django.contrib.auth.models import User
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes
from dotenv import load_dotenv
from rest_framework import status
from django.http import JsonResponse, HttpResponseForbidden
from .serializers import *
from store.models import *
from store.serializers import *
import os, json
from threading import Lock
# Create your views here.

load_dotenv()
allowed_origins = os.environ.get('REQUEST_ALLOWED_ORIGINS')
forbbiden_message = 'Forbidden-Acces denied'
def permission(): return IsAuthenticated
ALLOWED_ORIGINS = [allowed_origins]
def origin_checker(request):
    referer = request.META.get('HTTP_REFERER','')
    if referer in ALLOWED_ORIGINS: return False
    else : return True



class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permission()]

class ShoeViewSet(generics.ListCreateAPIView):
    queryset = Shoe.objects.all()
    serializer_class = ShoeSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class ShoeManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = Shoe.objects.all()
    serializer_class = ShoeSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)


class SandalViewSet(generics.ListCreateAPIView):
    queryset = Sandal.objects.all()
    serializer_class = SandalSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class SandalManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sandal.objects.all()
    serializer_class = SandalSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class ShirtViewSet(generics.ListCreateAPIView):
    queryset = Shirt.objects.all()
    serializer_class = ShirtSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class ShirtManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = Shirt.objects.all()
    serializer_class = ShirtSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class PantViewSet(generics.ListCreateAPIView):
    queryset = Pant.objects.all()
    serializer_class = PantSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class PantManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = Pant.objects.all()
    serializer_class = PantSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)

class ShoeDetailViewSet(generics.ListCreateAPIView):
    queryset = ShoeDetail.objects.all()
    serializer_class = ShoeDetailSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)


@api_view(['GET'])
@permission_classes([permission()])
def db_get_orders(request):
    if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
    try:
        queryset = Order.objects.filter(status = False, waiting = False).order_by('-exception')
        querySerializer = OrderSerializer(queryset, many=True)
        return JsonResponse({"orders":querySerializer.data}, status = status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
@permission_classes([permission()])
def get_deficiencies(request):
    if origin_checker(request):return HttpResponseForbidden(forbbiden_message)
    try:
        queryset = QuantityExceptions.objects.all()
        querySerializer = QuantityExceptionsSerializer(queryset, many = True)
        return JsonResponse({"deficiencies":querySerializer.data}, status = status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST)
    

@api_view(['POST'])
@permission_classes([permission()])
def updateShoeDetail(request):
    if origin_checker(request) : return HttpResponseForbidden(forbbiden_message)
    try:
        if request.method == 'POST':
            data  = json.loads(request.body)
            productId = int(data.get("productId", None))
            size = data.get("size", None)
            quantity = int(data.get('quantity'))
            product = Shoe.objects.get(id = productId) 
            productDetails = ShoeDetail.objects.filter(productId = product, size = size)
            if productDetails.exists():
                targeted_product = productDetails.first()
                targeted_product.quantity += quantity
                targeted_product.save()
            else :
                ShoeDetail.objects.create(productId = product, size = size, quantity = quantity)
            return JsonResponse({"message":"Ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST) 



@api_view(['POST'])
@permission_classes([permission()])
def updateSandalDetail(request): 
    if origin_checker(request) : return HttpResponseForbidden(forbbiden_message)
    try:
        if request.method == 'POST':
            data  = json.loads(request.body)
            productId = int(data.get("productId", None))
            size = data.get("size", None)
            quantity = int(data.get('quantity'))
            product = Sandal.objects.get(id = productId) 
            productDetails = SandalDetail.objects.filter(productId = product, size = size)
            if productDetails.exists():
                targeted_product = productDetails.first()
                targeted_product.quantity += quantity
                targeted_product.save()
            else :
                SandalDetail.objects.create(productId = product, size = size, quantity = quantity)
            return JsonResponse({"message":"Ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST) 

@api_view(['POST'])
@permission_classes([permission()])
def updateShirtDetail(request): 
    if origin_checker(request) : return HttpResponseForbidden(forbbiden_message)
    try:
        if request.method == 'POST':
            data  = json.loads(request.body)
            productId = int(data.get("productId", None))
            size = data.get("size", None)
            quantity = int(data.get('quantity'))
            product = Shirt.objects.get(id = productId) 
            productDetails = ShirtDetail.objects.filter(productId = product, size = size)
            if productDetails.exists():
                targeted_product = productDetails.first()
                targeted_product.quantity += quantity
                targeted_product.save()
            else :
                ShirtDetail.objects.create(productId = product, size = size, quantity = quantity)
            return JsonResponse({"message":"Ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST) 

@api_view(['POST'])
@permission_classes([permission()])
def updatePantDetail(request): 
    if origin_checker(request) : return HttpResponseForbidden(forbbiden_message)
    try:
        if request.method == 'POST':
            data  = json.loads(request.body)
            productId = int(data.get("productId", None))
            size = data.get("size", None)
            quantity = int(data.get('quantity'))
            product = Pant.objects.get(id = productId) 
            productDetails = PantDetail.objects.filter(productId = product, size = size)
            if productDetails.exists():
                targeted_product = productDetails.first()
                targeted_product.quantity += quantity
                targeted_product.save()
            else :
                PantDetail.objects.create(productId = product, size = size, quantity = quantity)
            return JsonResponse({"message":"Ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST)
    


# Fichier parameters.json
PARAMS_PATH = os.path.join(os.path.dirname(__file__), 'parameters.json')
file_lock = Lock()

def load_params():
    with file_lock, open(PARAMS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_params(data):
    with file_lock, open(PARAMS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@api_view(['POST'])
@permission_classes([permission()])
def add_product_parameters(request):
    try:
        data = json.loads(request.body)
        type = data.get("productType")
        label = data.get("label")
        values = data.get("values")

        params = load_params()

        if type in params:
            if label in params[type]:
                for i in values:
                    if i not in params[type][label]:
                        params[type][label].append(i)
            else:
                params[type][label] = values
        else:
            params[type] = {label: values}

        save_params(params)
        return JsonResponse({"message": "ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([permission()])
def get_choices(request):
    type_ = request.GET.get('productType')
    label = request.GET.get('label')
    params = load_params()
    values = params.get(type_, {}).get(label, [])
    choices = [(value, value) for value in values]
    return JsonResponse({"data":choices}, status = status.HTTP_200_OK)
