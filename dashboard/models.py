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
    ROLES_CHOICES = [
        ('admin', 'admin'),
        ('manager', 'manager'),
        ('delivery', 'delivery')
    ]
    role = models.CharField(max_length=100, choices=ROLES_CHOICES, blank=False)
    image = models.FileField(storage=MediaCloudinaryStorage(), 
                             upload_to='documents/users', 
                             default='https://res.cloudinary.com/de2wpriie/image/upload/v1751961711/guest_shcrbi.png'
                             )
    
    objects = AuthUserManager()
    REQUIRED_FIELDS=['role']
