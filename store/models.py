from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth import get_user_model
import os, json, uuid
from threading import Lock
from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage
# Create your models here.

User = get_user_model()

base_dir = os.path.dirname(os.path.dirname(__file__))

is_paid_choices = [
    ('pending',   'Pending'),    # online: waiting for webhook confirmation
    ('confirmed', 'Confirmed'),  # online: webhook confirmed payment
    ('failed',    'Failed'),     # online: webhook reported failure
    ('cod',       'Cash on Delivery'),  # COD: paid on delivery
]


# ─── Models ───────────────────────────────────────────────────────────────────
 






 
class ProductType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        unique_together = ("product_type", "name")

    def __str__(self):
        return f"{self.product_type.name} - {self.name}"


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products"
    )

    ref = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)

    price = models.FloatField(
        validators=[MinValueValidator(0)]
    )

    newest = models.BooleanField(default=False)

    promo = models.FloatField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    loyalty_points = models.PositiveIntegerField(
        default=0,
        help_text="Points awarded to the client when this product is purchased"
    )
    
    def __str__(self):
        return f"{self.ref} - {self.name}"

    @property
    def product_type(self):
        return self.category.product_type


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.FileField(
        storage=MediaCloudinaryStorage(),
        upload_to="documents/products",
        default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg'
    )

    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"
 
 
class ProductStock(models.Model):
    product  = models.ForeignKey(Product, related_name="stock", on_delete=models.CASCADE)
    size     = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()       # real available stock
    reserved = models.PositiveIntegerField(default=0)  # held by pending online payments
 
    def available_quantity(self):
        """Stock the customer can actually buy right now."""
        return max(0, self.quantity - self.reserved)
 
    def __str__(self):
        return "%s size:%s qty:%s reserved:%s" % (self.product, self.size, self.quantity, self.reserved)
 
 
class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    name    = models.CharField(max_length=50)
    email   = models.EmailField()
    review  = models.CharField(max_length=150)
    stars   = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    date    = models.DateTimeField(auto_now_add=True,)
 

class ClientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="client_profile"
    )

    country        = models.CharField(max_length=50, default="")
    city           = models.CharField(max_length=50, default="")
    address        = models.TextField(blank=True, default="")
    phone          = models.CharField(max_length=20, blank=True, null=True)
    loyalty_points = models.PositiveIntegerField(default=0)

    creation_date = models.DateTimeField(auto_now_add=True)

    activation_date = models.DateTimeField(null=True, blank=True)
    activation_code = models.UUIDField(default=uuid.uuid4, unique=True)

    def __str__(self):
        return self.user.get_full_name()
    

 
class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    email      = models.EmailField()
    phone      = models.CharField(max_length=20)
    city       = models.CharField(max_length=50)
    address    = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
 
    # ← NEW: link to registered account (null = guest order)
    profile    = models.ForeignKey(
        ClientProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders_as_client',
    )

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)
 



class Order(models.Model):
    client         = models.ForeignKey(Client, on_delete=models.CASCADE)
    order_id       = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    amount         = models.FloatField(validators=[MinValueValidator(0.0)])
    date           = models.CharField(max_length=100, default="")
    status         = models.BooleanField(default=False)
    exception      = models.BooleanField(default=False)
 
    # True  = online payment (YCPay)
    # False = cash on delivery
    payment_mode   = models.BooleanField(default=True, editable=False)
 
    # pending   → online order created, awaiting webhook
    # confirmed → webhook confirmed payment
    # failed    → webhook reported failure OR polling timeout
    # cod       → cash on delivery order (no online payment)
    is_paid        = models.CharField(max_length=50, default='pending', choices=is_paid_choices, )
 
    currency       = models.CharField(max_length=100, default='MAD')
    invoice        = models.FileField(storage=RawMediaCloudinaryStorage(), upload_to='documents/invoices',
                                      null=True, blank=True)
    delivery_form  = models.FileField(storage=RawMediaCloudinaryStorage(), upload_to='documents/delivery_forms',
                                      null=True, blank=True)
    delivered      = models.BooleanField(default=False)
    delivery_man   = models.CharField(max_length=100, null=True, default=None)
    date           = models.DateTimeField(auto_now_add=True,)  # used by cleanup job
 
    def __str__(self):
        return str(self.order_id)
 
 
class OrderedProduct(models.Model):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='ordered_products')
    client       = models.ForeignKey(Client, on_delete=models.CASCADE)
    product_id   = models.PositiveIntegerField(editable=False)
    product_type = models.CharField(max_length=50)
    size         = models.CharField(max_length=20)
    quantity     = models.PositiveIntegerField()
    category     = models.CharField(max_length=50)
    ref          = models.CharField(max_length=50)
    name         = models.CharField(max_length=50)
    price        = models.FloatField(validators=[MinValueValidator(0)])
    available    = models.BooleanField(default=True)
    exception_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, null=True)
    # True  = stock has been physically deducted (confirmed/COD)
    # False = still just reserved (pending online payment)
    stock_deducted = models.BooleanField(default=False, editable=False)
 
    def __str__(self):
        return "%s %s %s %s %s" % (self.client, self.order, self.product_type, self.category, self.name)
 
 
class QuantityExceptions(models.Model):
    client           = models.ForeignKey(Client, on_delete=models.CASCADE)
    order            = models.ForeignKey(Order, to_field='order_id', on_delete=models.CASCADE)
    exception_id     = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    product_type     = models.CharField(max_length=20)
    product_category = models.CharField(max_length=50)
    product_ref      = models.PositiveIntegerField()
    product_name     = models.CharField(max_length=50)
    product_size     = models.CharField(max_length=50)
    delta_quantity   = models.PositiveIntegerField()
    treated          = models.BooleanField(default=False)





class Subscriber(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("unsubscribed", "Unsubscribed"),
        ("bounced", "Bounced"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        ordering = ["-subscribed_at"]
 
    def __str__(self):
        return f"{self.email} ({self.status})"
 
 
class NewsletterCampaign(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=255)
    preview_text = models.CharField(max_length=255, blank=True)
    body_html = models.TextField(help_text="HTML content of the newsletter body")
    body_text = models.TextField(blank=True, help_text="Plain-text fallback")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    recipients_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering = ["-created_at"]
 
    def __str__(self):
        return f"{self.subject} [{self.status}]"