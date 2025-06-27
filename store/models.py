from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from cloudinary.models import CloudinaryField
import os, json, uuid
from threading import Lock
from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage
# Create your models here.

base_dir = os.path.dirname(os.path.dirname(__file__))

# Construire le chemin vers le fichier JSON
PARAMS_PATH = os.path.join(base_dir, 'dashboard', 'parameters.json')

file_lock = Lock()

def load_params():
    with file_lock, open(PARAMS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

shoe_choices= [
    ('Mocassin', 'Mocassin'),
    ('Basket', 'Basket'),
    ('Medical', 'Medical'),
    ('Classic', 'Classic'),
]
sandal_choices=[]
shirt_choices=[]
pant_choices=[]
choices = {
    'Shoe':shoe_choices,
    'Sandal':sandal_choices,
    'Shirt':shirt_choices,
    'Pant':pant_choices
}

def get_choices(type_, label):
    params = load_params()
    values = params.get(type_, {}).get(label, [])
    choices = [(value, value) for value in values]
    return choices


class Product(models.Model):
    ref = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    price = models.FloatField(validators=[MinValueValidator(0.0)])
    newest = models.BooleanField(default=False) 
    promo = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)], default=0)
    image = CloudinaryField("Image", default = 'empty_q2cypk.png')
    image1 = CloudinaryField("Image1", default = 'empty_q2cypk.png')
    image2 = CloudinaryField("Image2", default = 'empty_q2cypk.png')
    image3 = CloudinaryField("Image3", default = 'empty_q2cypk.png')
    image4 = CloudinaryField("Image4", default = 'empty_q2cypk.png')
    class Meta:
        abstract = True

class ProductDetailN(models.Model):
    size = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    class Meta:
        abstract = True

class ProductReviews(models.Model):
    product_type=models.CharField(max_length=10)
    product_id = models.IntegerField()
    name = models.CharField(max_length=50)
    email = models.EmailField()
    review = models.CharField(max_length=150)
    stars = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    date = models.DateTimeField()


class ProductDetailC(models.Model):
    size = models.CharField(max_length=10)
    quantity = models.PositiveIntegerField()
    class Meta:
        abstract = True


class Shoe(Product):
    productType = models.CharField(default='Shoe', max_length=20, editable=False)
    category = models.CharField(max_length=100, choices=get_choices("Shoe", "categories"))
    def __str__(self):
        return "%s %s %s"%(self.category, self.ref, self.name)

class ShoeDetail(ProductDetailN):
    productId = models.ForeignKey(Shoe,on_delete=models.CASCADE)
    def __str__(self):
        return "%s %s %s"%(self.productId, "size : " + str(self.size) , "quantity : "+str(self.quantity))

class Sandal(Product):
    productType = models.CharField(default='Sandal', max_length=20, editable=False)
    category = models.CharField(max_length=100)
    def __str__(self):
        return "%s %s %s"%(self.category, self.ref, self.name)

class SandalDetail(ProductDetailN):
    productId = models.ForeignKey(Sandal, on_delete=models.CASCADE)
    def __str__(self):
        return "%s %s %s"%(self.productId, self.size, self.quantity)
    
class Shirt(Product):
    productType = models.CharField(default='Shirt', max_length=20, editable=False)
    category = models.CharField(max_length=100)
    def __str__(self):
        return "%s %s %s"%(self.category, self.ref, self.name)
    
class ShirtDetail(ProductDetailC):
    productId = models.ForeignKey(Shirt, on_delete=models.CASCADE)
    def __str__(self):
        return "%s %s %s"%(self.productId, self.size, self.quantity)

class  Pant(Product):
    productType = models.CharField(default='Pant', max_length=20, editable=False)
    category = models.CharField(max_length=100)
    def __str__(self):
        return "%s %s %s"%(self.category, self.ref, self.name)
    
class PantDetail(ProductDetailC):
    productId = models.ForeignKey(Pant, on_delete=models.CASCADE)
    def __str__(self):
        return "%s %s %s"%(self.productId, self.size, self.quantity)

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

