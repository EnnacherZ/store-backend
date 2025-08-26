from django.contrib.auth import get_user_model
from .permissions import IsAdmin, IsDeliveryMan, IsManager
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, permission_classes
from dotenv import load_dotenv
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponseForbidden
from .serializers import *
from store.models import *
from store.serializers import *
import os, json
from threading import Lock
from django.conf import settings

# Create your views here.

User = get_user_model()

load_dotenv()
allowed_origins = os.environ.get('REQUEST_ALLOWED_ORIGINS')
forbbiden_message = 'Forbidden-Acces denied'
def permission(): return IsAuthenticated
ALLOWED_ORIGINS = [allowed_origins]
def origin_checker(request):
    referer = request.META.get('HTTP_REFERER','')
    if referer in ALLOWED_ORIGINS: return False
    else : return True



product_types = {"Shoe":Shoe, "Sandal":Sandal, "Shirt":Shirt, "Pant":Pant}
productDetail_types = {"Shoe":ShoeDetail, "Sandal":SandalDetail, "Shirt":ShirtDetail, "Pant":PantDetail}
productSerializer_types = {"Shoe":ShoeSerializer, "Sandal":SandalSerializer, "Shirt":ShirtSerializer, "Pant":PantSerializer}
productDetailSerializer_types = {"Shoe":ShoeDetailSerializer, "Sandal":SandalDetailSerializer, "Shirt":ShirtDetailSerializer, "Pant":PantDetailSerializer}



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data

        refresh = tokens['refresh']
        access = tokens['access']

        res = Response({
            "message": "Login successful",
            "user": {
                "username": serializer.user.username,
                "role": serializer.user.role,
                "first_name": serializer.user.first_name,
                "last_name": serializer.user.last_name,
                "image": serializer.user.image.url if serializer.user.image else None
            }
        }, status=status.HTTP_200_OK)

        cookie_max_age = 3600 * 24  # 1 day
        secure = not settings.DEBUG

        res.set_cookie(
            key='access_token',
            value=str(access),
            httponly=True,
            secure=secure,
            samesite='None',
            max_age=cookie_max_age,
            domain= os.environ.get('domain')
            
        )
        res.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure= secure,
            samesite='None',
            max_age=cookie_max_age,
            domain= os.environ.get('domain')
            
        )

        return res


class RefreshTokenCookieView(APIView):
    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response({'detail': 'Refresh token missing'}, status=400)
        secure = not settings.DEBUG
        try:
            token = RefreshToken(refresh_token)
            access_token = str(token.access_token)
            res = Response({'message': 'Token refreshed'})
            res.set_cookie(
                'access_token',
                access_token,
                httponly=True,
                secure= secure ,
                samesite='None',
                max_age=3600,
                domain= os.environ.get('domain')
                
            )
            return res
        except Exception:
            return Response({'detail': 'Invalid token'}, status=401)


class LogoutView(APIView):
    def post(self, request):
        res = Response({'message': 'Logged out'})
        res.delete_cookie('access_token')
        res.delete_cookie('refresh_token')
        return res
    
class CheckAuthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'message': 'Authenticated',
            'user': {
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            }
        }, status=200)


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

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

class OrderViewSet(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)   

class OrderManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser)  

class QuantityExceptionsManager(generics.RetrieveUpdateDestroyAPIView):
    queryset = QuantityExceptions.objects.all()
    serializer_class = QuantityExceptionsSerializer
    permission_classes = [permission()]
    parser_classes = (MultiPartParser, FormParser) 


    # def partial_update(self, request, *args, **kwargs):
    #     instance = self.get_object()

    #     # Upload conditionnel pour pdf_invoice
    #     if 'invoice' in request.FILES:
    #         result_invoice = upload(request.FILES['invoice'], resource_type='raw')
    #         instance.invoice = result_invoice['secure_url']

    #     # Upload conditionnel pour pdf_receipt
    #     if 'delivery_form' in request.FILES:
    #         result_delivery_form= upload(request.FILES['delivery_form'], resource_type='raw')
    #         instance.delivery_form = result_delivery_form['secure_url']

    #     instance.save()
    #     return super().partial_update(request, *args, **kwargs)


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
        queryset = QuantityExceptions.objects.filter(treated = False)
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
    


@api_view(['POST'])
@permission_classes([permission()])
def process_deficiency(request):
    data = json.loads(request.body)
    exception_id = data.get('exceptionID')
    order_id = data.get('orderID')
    quantity_exception = QuantityExceptions.objects.get(exception_id = exception_id)
    ordered_product = ProductOrdered.objects.get(exception_id = exception_id)
    the_order = Order.objects.get(order_id = order_id)
    quantity_exception.treated = True;ordered_product.available = True;the_order.exception = False
    quantity_exception.save();ordered_product.save();the_order.save()
    return JsonResponse({"message": 'ok'}, status = status.HTTP_200_OK)



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

        type_ = data.get("productType")
        param = data.get("param")
        values = data.get("values")

        if not isinstance(param, str) or not isinstance(type_, str):
            raise ValueError("param and productType must be strings.")

        if not isinstance(values, list):
            raise ValueError("values must be a list.")

        params = load_params()

        if param in params:
            if type_ in params[param]:
                # S'assurer que c'est une liste de tuples
                current_values = params[param][type_]
                if not isinstance(current_values, list):
                    current_values = []
                for i in values:
                    tup = (i, i)
                    if tup not in current_values:
                        current_values.append(tup)
                params[param][type_] = current_values
            else:
                # Nouvelle liste de tuples
                params[param][type_] = [(i, i) for i in values]

        save_params(params)
        return JsonResponse({"message": "ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([permission()])
def add_product_types(request):
    try:
        data = json.loads(request.body)
        type_ = 'types'
        values = data.get("values")

        params = load_params()
        if type_ in params:
            for i in values:
                if i not in params[type_]:
                    params[type_].append(i)
        else:
            params[type_] = values


        save_params(params)
        return JsonResponse({"message": "ok!"}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([AllowAny])
def get_params(request):
    parameters = {}
    try:
        param = request.GET.get('param')
        params = load_params()
        values = params.get(param, {})
        for type_ in values:
            parameters[type_] = []
            for attribut in values[type_]:
                parameters[type_].append(attribut[0])
        return JsonResponse({f"{param}":parameters}, status = status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
@permission_classes([permission()])
def get_products_types(request):
    params = load_params()
    values = params.get('types', [])
    choices = [value for value in values]
    return JsonResponse({f"types":choices}, status = status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permission()])
def get_products_choices(request):
    product_type = request.GET.get('productType')
    product = product_types[product_type]
    querySet = product.objects.all()
    serializer = ProductChoicesSerializer(product)
    data = serializer(querySet, many = True).data
    return JsonResponse({"choices":data}, status= status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([permission()])
def get_product_details(request):
    try:
        product_id = request.GET.get('productId')
        product_type = request.GET.get('productType')
        product = productDetail_types[product_type]
        querySet = product.objects.filter(productId = product_id)
        serializer = productDetailSerializer_types[product_type](querySet, many = True)
        return JsonResponse({"data":serializer.data}, status= status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
@api_view(['GET'])
@permission_classes([permission()])
def get_orders(request):
    try:
        all_orders = Order.objects.filter(waiting  = False).order_by('-exception')
        remaining_orders = Order.objects.filter(status = False, waiting=False).order_by('-exception')
        waitin_delivery_orders = Order.objects.filter(status = True, waiting=False, delivered= False).order_by('-exception')
        delivered_orders = Order.objects.filter(status=True, waiting=False, delivered= True).order_by('-exception')
        all_serialized = OrderSerializer(all_orders, many=True).data
        remaining_serialized = OrderSerializer(remaining_orders, many=True).data
        delivered_serialized = OrderSerializer(delivered_orders, many=True).data
        waiting_delivery_serialized = OrderSerializer(waitin_delivery_orders, many=True).data
        return JsonResponse({"allOrders":all_serialized, "remainingOrders":remaining_serialized, "deliveredOrders":delivered_serialized, 'waitingDeliveryOrders':waiting_delivery_serialized}, status= status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([permission()])
def get_searched_order(request):
    try:
        order_id = request.GET.get('orderID')
        the_order = Order.objects.get(order_id = order_id)
        serialized_order = OrderSerializer(the_order, many = False)
        deficiencies = QuantityExceptions.objects.filter(order = order_id)
        serialized_deficiencies = QuantityExceptionsSerializer(deficiencies, many = True)
        return JsonResponse({'order': serialized_order.data, 'deficiencies': serialized_deficiencies.data, 'found': True, 'error':False}, status=status.HTTP_200_OK)
    except Order.DoesNotExist:
        return JsonResponse({'found': False, 'error':False})
    except Exception as e:
        return JsonResponse({'error':True})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsDeliveryMan])
def delivery_man_orders(request):
    try:
        waiting_queryset = Order.objects.filter(status = True, waiting = False, delivered = False)
        delivered_queryset = Order.objects.filter(status = True, waiting = False, delivered = True)
        waiting_querySerializer = OrderSerializer(waiting_queryset, many=True)
        delivered_querySerializer = OrderSerializer(delivered_queryset, many=True)
        return JsonResponse({"orders":waiting_querySerializer.data}, status = status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return JsonResponse({"message" : f"An error occured: {str(e)}"}, status = status.HTTP_400_BAD_REQUEST)  
    

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsDeliveryMan])
def confirm_delivery(request, pk):
    username = request.data.get('username')
    try:
        order = Order.objects.get(pk=pk)
        order.delivery_man = username; order.delivered = True
        order.save()
        return JsonResponse({'message':'delivered!'})
    except Exception as e:
        return JsonResponse({"message" : f"An error occured: {str(e)}"})  
