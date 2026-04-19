from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import LoyalClient
from .serializers import ClientSerializer
import uuid
from django.core.mail import send_mail
from django.conf import settings
from datetime import timezone, timedelta
from rest_framework_simplejwt.tokens import RefreshToken


activation_website_url = "https://127.0.0.1:8000/api/client/activate/"

class SignUpClientView(APIView):
    permission_classes = [permissions.AllowAny]  # Tout le monde peut s'inscrire

    def post(self, request):
        data = request.data
        try:
            client = LoyalClient.objects.create(
                email=data['email'],
                last_name=data['last_name'],
                first_name=data['first_name'],
            )
            client.set_password(data['password'])
            client.save()

            # Gérer l'activation du compte, par exemple, avec un lien d'activation par email
            activation_code = client.activation_code
            activation_url = f"{activation_website_url}{activation_code}"
            send_mail(
                'Active ton compte',
                f"Welcome {client.first_name},\nTo activate tour account, please clinck on the following link : {activation_url}",
                settings.DEFAULT_FROM_EMAIL,
                [client.email],
                fail_silently=False,
            )

            return Response({"message": "Compte créé, un email d'activation a été envoyé."}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class ActivateClientView(APIView):

    def get(self, request, activation_code):
        try:
            # Vérifie si le code d'activation est valide et associe-le au client
            client = LoyalClient.objects.get(activation_code=activation_code)
            client.is_active = True
            client.activation_date = timezone.now()
            client.save()
            return Response({"message": "Compte activé avec succès!"}, status=status.HTTP_200_OK)

        except LoyalClient.DoesNotExist:
            return Response({"error": "Code d'activation invalide"}, status=status.HTTP_400_BAD_REQUEST)
        



class SignInClientView(APIView):

    def post(self, request):
        data = request.data
        email = data.get('email')
        mot_de_passe = data.get('mot_de_passe')

        try:
            # Recherche du client basé sur l'email
            client = LoyalClient.objects.get(email=email)

            # Vérification du mot de passe
            if client.check_password(mot_de_passe):
                if client.is_active:
                    # Création du refresh token et du access token
                    refresh = RefreshToken.for_user(client)  # Utilisation du client directement
                    access_token = str(refresh.access_token)
                    refresh_token = str(refresh)

                    # Créer la réponse avec les cookies HttpOnly
                    response = Response({"message": "Connexion réussie."}, status=status.HTTP_200_OK)

                    # Ajouter les tokens dans les cookies HttpOnly
                    response.set_cookie(
                        key='client_access_token_alfirdaousstore', 
                        value=access_token, 
                        httponly=True, 
                        secure=True,  # Si tu es en production, utilise HTTPS
                        samesite='None',
                        max_age=timedelta(minutes=15),  # Access token expirant après 15 minutes
                        path='/'
                    )

                    response.set_cookie(
                        key='client_refresh_token_alfirdaousstore', 
                        value=refresh_token, 
                        httponly=True, 
                        secure=True,  # Si en production
                        samesite='None',
                        max_age=timedelta(days=7),  # Refresh token expirant après 7 jours

                    )

                    return response
                else:
                    return Response({"error": "Compte non activé"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"error": "Identifiants invalides"}, status=status.HTTP_400_BAD_REQUEST)

        except LoyalClient.DoesNotExist:
            return Response({"error": "Identifiants invalides"}, status=status.HTTP_400_BAD_REQUEST)
