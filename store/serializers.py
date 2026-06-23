from rest_framework import serializers
from django.contrib.auth.models import User
from .models import *



class ProductStockSerializer(serializers.ModelSerializer):
    quantity = serializers.SerializerMethodField()
    class Meta:
        model = ProductStock
        fields = '__all__'
    
    def get_quantity(self, obj):
        return obj.available_quantity()


class ProductTypeSerializer(serializers.ModelSerializer):
    class Meta: 
        model = ProductType
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta: 
        model = Category
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    product_type = serializers.CharField(
        source="category.product_type.name",
        read_only=True
    )

    category = serializers.CharField(
        source="category.name",
        read_only=True
    )
    stock = ProductStockSerializer(many=True, read_only = True)
    price = serializers.FloatField()
    image = serializers.SerializerMethodField()
    image1 = serializers.SerializerMethodField()
    image2 = serializers.SerializerMethodField()
    image3 = serializers.SerializerMethodField()
    image4 = serializers.SerializerMethodField()

    class Meta:
        model = Product

        fields = [
            "id",
            "product_type",
            "category",
            "ref",
            "name",
            "price",
            "promo",
            "newest",
            "stock",
            "image",
            "image1",
            "image2",
            "image3",
            "image4",
        ]

    def _get_image(self, obj, index):
        images = list(obj.images.all())

        if len(images) > index:
            return images[index].image.url

        return None

    def get_image(self, obj):
        return self._get_image(obj, 0)

    def get_image1(self, obj):
        return self._get_image(obj, 1)

    def get_image2(self, obj):
        return self._get_image(obj, 2)

    def get_image3(self, obj):
        return self._get_image(obj, 3)

    def get_image4(self, obj):
        return self._get_image(obj, 4)

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
        model = OrderedProduct
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




class SubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ["id", "email", "status", "subscribed_at", "unsubscribed_at"]
        read_only_fields = ["id", "subscribed_at", "unsubscribed_at"]


class NewsletterCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterCampaign
        fields = [
            "id", "subject", "preview_text", "body_html", "body_text",
            "status", "scheduled_at", "sent_at", "created_at", "updated_at",
            "recipients_count", "sent_count", "failed_count",
        ]
        read_only_fields = [
            "id", "status", "sent_at", "created_at", "updated_at",
            "recipients_count", "sent_count", "failed_count",
        ]


class SendCampaignSerializer(serializers.Serializer):
    campaign_id = serializers.UUIDField()
    test_email = serializers.EmailField(required=False, allow_blank=True)