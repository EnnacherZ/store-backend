from django.contrib import admin
from store.models import *
# Register your models here.

admin.site.register(Product)
admin.site.register(ProductStock)
admin.site.register(Client)
admin.site.register(ProductOrdered)
admin.site.register(ProductReview)
admin.site.register(QuantityExceptions)
admin.site.register(Order)
admin.site.register(LoyalClient)