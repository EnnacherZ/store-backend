from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
 
from store.email_service import send_campaign
from store.models import NewsletterCampaign, Subscriber
from store.serializers import (
    NewsletterCampaignSerializer,
    SendCampaignSerializer,
    SubscriberSerializer,
)








@api_view(["GET"])
@permission_classes([IsAdminUser])
def subscriber_list(request):
    """List all subscribers with optional status filter."""
    qs = Subscriber.objects.all()
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    serializer = SubscriberSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "results": serializer.data,
    })
 
 
@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def campaign_list(request):
    """List all campaigns or create a new draft."""
    if request.method == "GET":
        campaigns = NewsletterCampaign.objects.all()
        serializer = NewsletterCampaignSerializer(campaigns, many=True)
        return Response(serializer.data)
 
    serializer = NewsletterCampaignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    campaign = serializer.save()
    return Response(NewsletterCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)
 
 
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAdminUser])
def campaign_detail(request, pk):
    """Retrieve, update, or delete a campaign."""
    try:
        campaign = NewsletterCampaign.objects.get(pk=pk)
    except NewsletterCampaign.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
 
    if request.method == "GET":
        return Response(NewsletterCampaignSerializer(campaign).data)
 
    if request.method == "PATCH":
        if campaign.status == "sent":
            return Response({"detail": "Cannot edit a sent campaign."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = NewsletterCampaignSerializer(campaign, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        campaign = serializer.save()
        return Response(NewsletterCampaignSerializer(campaign).data)
 
    if request.method == "DELETE":
        if campaign.status == "sent":
            return Response({"detail": "Cannot delete a sent campaign."}, status=status.HTTP_400_BAD_REQUEST)
        campaign.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
 
 
@api_view(["POST"])
@permission_classes([IsAdminUser])
def send_newsletter(request):
    """
    Send a campaign to all active subscribers.
    Pass `test_email` to do a dry-run to a single address.
    """
    serializer = SendCampaignSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
    try:
        campaign = NewsletterCampaign.objects.get(pk=serializer.validated_data["campaign_id"])
    except NewsletterCampaign.DoesNotExist:
        return Response({"detail": "Campaign not found."}, status=status.HTTP_404_NOT_FOUND)
 
    if campaign.status == "sent":
        return Response({"detail": "Campaign has already been sent."}, status=status.HTTP_400_BAD_REQUEST)
 
    test_email = serializer.validated_data.get("test_email")
    result = send_campaign(campaign, test_email=test_email or None)
 
    return Response({
        "detail": "Test email sent." if test_email else "Campaign sent successfully.",
        **result,
    })
 
 
@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """Aggregate stats for the dashboard header cards."""
    total = Subscriber.objects.count()
    active = Subscriber.objects.filter(status="active").count()
    unsubscribed = Subscriber.objects.filter(status="unsubscribed").count()
    campaigns_sent = NewsletterCampaign.objects.filter(status="sent").count()
 
    return Response({
        "total_subscribers": total,
        "active_subscribers": active,
        "unsubscribed": unsubscribed,
        "campaigns_sent": campaigns_sent,
    })
 