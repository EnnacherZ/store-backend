from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
import os, json, uuid
from threading import Lock
from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage
from django.contrib.auth.hashers import make_password, check_password
# Create your models here.

base_dir = os.path.dirname(os.path.dirname(__file__))

# Construire le chemin vers le fichier JSON
PARAMS_PATH = os.path.join(base_dir, 'dashboard', 'parameters.json')

file_lock = Lock()

def load_params():
    with file_lock, open(PARAMS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_choices(type_, label):
    params = load_params()
    values = params.get(type_, {}).get(label, [])
    choices = [(value, value) for value in values]
    return choices


class Product(models.Model):
    product_type = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    ref = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    price = models.FloatField(validators=[MinValueValidator(0.0)])
    newest = models.BooleanField(default=False) 
    promo = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)], default=0)
    image = models.FileField(storage=MediaCloudinaryStorage(),
                            upload_to='documents/products', 
                            default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg')
    image1 = models.FileField(storage=MediaCloudinaryStorage(),
                            upload_to='documents/products', 
                            default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg')
    image2 = models.FileField(storage=MediaCloudinaryStorage(),
                            upload_to='documents/products', 
                            default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg')
    image3 = models.FileField(storage=MediaCloudinaryStorage(),
                            upload_to='documents/products', 
                            default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg')
    image4 = models.FileField(storage=MediaCloudinaryStorage(),
                            upload_to='documents/products', 
                            default='https://res.cloudinary.com/de2wpriie/image/upload/y9DpT_eouhy5.jpg')
    # class Meta:
    #     abstract = True
    def __str__(self):
        return "%s %s %s"%(self.category, self.ref, self.name)

class ProductStock(models.Model):
    product = models.ForeignKey(Product, related_name="stock", on_delete=models.CASCADE)
    size = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    # class Meta:
    #     abstract = True
    def __str__(self):
        return "%s %s %s"%(self.product, "size : " + str(self.size) , "quantity : "+str(self.quantity))



class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    name = models.CharField(max_length=50)
    email = models.EmailField()
    review = models.CharField(max_length=150)
    stars = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    date = models.DateTimeField()


class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=50)
    address = models.CharField(max_length=100)

    def __str__(self):
        return "%s %s"%(self.first_name, self.last_name)


class Order(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    order_id = models.UUIDField(default = uuid.uuid4, editable=False, unique=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    amount = models.FloatField(validators=[MinValueValidator(0.0)])
    date = models.CharField(max_length=100, default="")
    status = models.BooleanField(default=False)
    exception = models.BooleanField(default = False)
    waiting = models.BooleanField(default=True)
    payment_mode = models.BooleanField(default=True, editable=False) #True if is online,  False else
    currency = models.CharField(max_length=100, default='MAD')
    invoice = models.FileField(storage=RawMediaCloudinaryStorage(), upload_to='documents/invoices', null=True, blank=True)
    delivery_form = models.FileField(storage=RawMediaCloudinaryStorage(), upload_to='documents/delivery_forms', null=True, blank=True)
    delivered = models.BooleanField(default=False)
    delivery_man = models.CharField(max_length=100, null=True, default=None)
    def __str__(self):
        return "%s "%(self.order_id)

class ProductOrdered(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='ordered_products')
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product_id = models.PositiveIntegerField(editable=False)
    product_type = models.CharField(max_length=50)
    size = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField()
    category = models.CharField(max_length=50)
    ref = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    price = models.FloatField(validators=[MinValueValidator(0)])
    available = models.BooleanField(default=True)
    exception_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    def __str__(self):
        return "%s %s %s %s"%(self.client, self.product_type,self.category, self.name)

class QuantityExceptions(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, to_field='order_id', on_delete=models.CASCADE)
    exception_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    product_type = models.CharField(max_length=20)
    product_category = models.CharField(max_length=50)
    product_ref = models.PositiveIntegerField()
    product_name = models.CharField(max_length=50)
    product_size = models.CharField(max_length=50)
    delta_quantity = models.PositiveIntegerField()
    treated = models.BooleanField(default=False)



class LoyalClient(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255)
    address = models.TextField()
    phone = models.CharField(max_length=20, null=True, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)  # Pour vérifier si le client est activé
    activation_date = models.DateTimeField(null=True, blank=True)
    activation_code = models.UUIDField(default = uuid.uuid4, unique=True)

    def set_password(self, password):
        self.password = make_password(password)

    def check_password(self, password):
        return check_password(password, self.password)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'