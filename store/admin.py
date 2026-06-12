from django.contrib import admin
from store.models import *
# Register your models here.

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "ref",
        "name",
        "get_type",
        "category",
        "price",
        "promo",
        "newest"
    )

    inlines = [ProductImageInline]

    def get_type(self, obj):
        return obj.category.product_type.name

    get_type.short_description = "Type"


admin.site.register(ProductStock)
admin.site.register(Client)
admin.site.register(OrderedProduct)
admin.site.register(ProductReview)
admin.site.register(QuantityExceptions)
admin.site.register(Order)
admin.site.register(ClientProfile)
