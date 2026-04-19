from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *



class ProductStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStock
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    stock = ProductStockSerializer(many=True, read_only = True)
    class Meta:
        model = Product
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'



class ProductReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = '__all__'


class ProductOrderedSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOrdered
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    client = ClientSerializer()
    ordered_products = ProductOrderedSerializer(many = True, read_only = True)
    class Meta:
        model = Order
        fields = '__all__'

class QuantityExceptionsSerializer(serializers.ModelSerializer):
    order = OrderSerializer()
    class Meta:
        model = QuantityExceptions
        fields = '__all__'