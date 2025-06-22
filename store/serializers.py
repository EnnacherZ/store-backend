from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *


class ShoeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shoe
        fields = '__all__'

class ShoeDetailSerializer(serializers.ModelSerializer):
    # Sérialisation du champ 'size' en tant que chaîne de caractères
    # size = serializers.CharField(read_only=True)
    class Meta:
        model = ShoeDetail
        fields = '__all__'

class SandalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sandal
        fields = '__all__'

class SandalDetailSerializer(serializers.ModelSerializer):
    # size = serializers.CharField(read_only=True)
    class Meta:
        model = SandalDetail
        fields = '__all__'


class ShirtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shirt
        fields = '__all__'

class ShirtDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShirtDetail
        fields = '__all__'

class PantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pant
        fields = '__all__'

class PantDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PantDetail
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'



class ProductReviewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReviews
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
    class Meta:
        model = QuantityExceptions
        fields = '__all__'