from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role', 'image', 'first_name', 'last_name']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        # Use create_user to handle password hashing
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            role=validated_data['role'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            image=validated_data.get('image')
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Ajoute les infos supplémentaires au token
        token['role'] = user.role
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        token['image'] = user.image.url if user.image else None

        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['username'] = self.user.username
        data['first_name'] = self.user.first_name
        data['last_name'] = self.user.last_name
        data['image'] = self.user.image.url if self.user.image else None

        return data





def ProductChoicesSerializer(class_: type):
    class Serializer(serializers.ModelSerializer):
        label = serializers.SerializerMethodField()
        value = serializers.SerializerMethodField()
        picture = serializers.SerializerMethodField()
        class Meta:
            model = class_
            fields = ['label', 'value', 'picture']
        def get_label(self, obj):
            return f"{obj.category} {obj.ref} {obj.name}"
        def get_value(self, obj):
            return int(obj.id)
        def get_picture(self, obj):
            return obj.image.url
    
    return Serializer