from django.test import TestCase


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
import json
import logging

from store.models import Order

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def youcanpay_webhook(request):
    try:
        payload = json.loads(request.body)

        logger.info("🔥 Webhook received: %s", payload)

        event_name = payload.get("event_name")
        data = payload.get("payload", {})

        transaction = data.get("transaction", {})
        transaction_id = transaction.get("id")
        order_id = transaction.get("order_id")
        status = transaction.get("status")

        # 🔥 TEST LOGIC ONLY (NO DB Y
        the_order = Order.objects.get(order_id = order_id)
        if the_order.payment_mode and the_order.is_paid=='pending' :
            the_order.transaction_id = transaction_id
            if event_name == "transaction.paid" and status == 1:
                the_order.is_paid = 'confirmed'
            else: 
                the_order.is_paid = 'failed'
            the_order.save()

        return JsonResponse({"received": True}, status=200)

    except Exception as e:
        logger.error("Webhook error: %s", str(e))
        return JsonResponse({"received": False, "error": str(e)}, status=200)