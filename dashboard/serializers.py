from rest_framework import serializers
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","username","password"]
        extra_kwargs = {'password':{"write_only":True}}
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user
    

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