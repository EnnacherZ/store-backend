from django.db import models
from django.contrib.auth.models import AbstractUser
from cloudinary_storage.storage import MediaCloudinaryStorage
# Create your models here.



from django.contrib.auth.models import BaseUserManager

class AuthUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Le nom d’utilisateur est requis.')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        role = extra_fields.get('role')
        if role != 'admin':
            raise ValueError('Le superutilisateur doit avoir role="admin".')

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(username, password, **extra_fields)



class AuthUser(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        DELIVERY = "delivery", "Delivery"
        CLIENT = "client", "Client"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CLIENT
    )

    image = models.FileField(storage=MediaCloudinaryStorage(), 
                             upload_to='documents/users', 
                             default='https://res.cloudinary.com/de2wpriie/image/upload/v1751961711/guest_shcrbi.png'
                             )
    
    objects = AuthUserManager()
    REQUIRED_FIELDS=['role']

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        # 🚨 clients should never have permissions
        if self.role == self.Roles.CLIENT:

            self.is_staff = False
            self.is_superuser = False

            super().save(update_fields=[
                "is_staff",
                "is_superuser"
            ])

            self.groups.clear()
            self.user_permissions.clear()
