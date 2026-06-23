import logging
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from .models import Subscriber, NewsletterCampaign
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from dashboard.permissions import OriginPermission
from rest_framework.response import Response
 
from .models import NewsletterCampaign, Subscriber
from .serializers import (
    SubscribeSerializer,
)

logger = logging.getLogger(__name__)

UNSUBSCRIBE_BASE_URL = getattr(settings, "UNSUBSCRIBE_BASE_URL", "https://yourdomain.com/unsubscribe")
FROM_NAME = getattr(settings, "NEWSLETTER_FROM_NAME", "Your Brand")
FROM_EMAIL = getattr(settings, "NEWSLETTER_FROM_EMAIL", "newsletter@yourdomain.com")


def build_html_email(subject: str, preview_text: str, body_html: str, unsubscribe_url: str) -> str:
    """
    Wraps the campaign body in a polished, responsive HTML email shell.
    """
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{subject}</title>
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background-color: #F5F4F0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 16px;
      line-height: 1.7;
      color: #2C2C2A;
      -webkit-font-smoothing: antialiased;
    }}

    .email-wrapper {{
      background-color: #F5F4F0;
      padding: 40px 16px;
    }}

    .email-container {{
      max-width: 600px;
      margin: 0 auto;
    }}

    /* Header */
    .email-header {{
      background-color: #1A1A18;
      border-radius: 16px 16px 0 0;
      padding: 32px 40px;
      text-align: center;
    }}

    .email-logo {{
      display: inline-block;
      font-size: 20px;
      font-weight: 600;
      color: #FFFFFF;
      letter-spacing: -0.5px;
      text-decoration: none;
    }}

    .email-logo span {{
      color: #9FE1CB;
    }}

    /* Hero */
    .email-hero {{
      background-color: #FFFFFF;
      padding: 48px 40px 40px;
      border-left: 1px solid #E8E6E0;
      border-right: 1px solid #E8E6E0;
    }}

    .email-eyebrow {{
      display: inline-block;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #0F6E56;
      background-color: #E1F5EE;
      padding: 4px 12px;
      border-radius: 100px;
      margin-bottom: 20px;
    }}

    .email-subject {{
      font-size: 28px;
      font-weight: 600;
      line-height: 1.3;
      color: #1A1A18;
      margin-bottom: 12px;
      letter-spacing: -0.5px;
    }}

    .email-preview {{
      font-size: 15px;
      color: #888780;
      margin-bottom: 0;
    }}

    /* Divider */
    .email-divider {{
      background-color: #FFFFFF;
      padding: 0 40px;
      border-left: 1px solid #E8E6E0;
      border-right: 1px solid #E8E6E0;
    }}

    .email-divider hr {{
      border: none;
      border-top: 1px solid #ECEAE4;
      margin: 0;
    }}

    /* Body */
    .email-body {{
      background-color: #FFFFFF;
      padding: 36px 40px 48px;
      border-left: 1px solid #E8E6E0;
      border-right: 1px solid #E8E6E0;
      font-size: 16px;
      line-height: 1.8;
      color: #2C2C2A;
    }}

    .email-body h2 {{
      font-size: 20px;
      font-weight: 600;
      color: #1A1A18;
      margin: 28px 0 10px;
    }}

    .email-body h3 {{
      font-size: 17px;
      font-weight: 600;
      color: #1A1A18;
      margin: 20px 0 8px;
    }}

    .email-body p {{
      margin-bottom: 16px;
      color: #444441;
    }}

    .email-body a {{
      color: #0F6E56;
      text-decoration: underline;
    }}

    .email-body ul, .email-body ol {{
      padding-left: 20px;
      margin-bottom: 16px;
      color: #444441;
    }}

    .email-body li {{
      margin-bottom: 6px;
    }}

    .email-body blockquote {{
      border-left: 3px solid #9FE1CB;
      margin: 24px 0;
      padding: 12px 20px;
      background-color: #F5FDFB;
      border-radius: 0 8px 8px 0;
      color: #2C2C2A;
      font-style: italic;
    }}

    /* CTA Button */
    .email-cta-wrapper {{
      text-align: center;
      margin: 32px 0 8px;
    }}

    .email-cta {{
      display: inline-block;
      background-color: #1A1A18;
      color: #FFFFFF !important;
      text-decoration: none !important;
      font-size: 15px;
      font-weight: 500;
      padding: 14px 32px;
      border-radius: 8px;
      letter-spacing: -0.1px;
    }}

    /* Footer */
    .email-footer {{
      background-color: #ECEAE4;
      border-radius: 0 0 16px 16px;
      padding: 28px 40px;
      text-align: center;
      border-left: 1px solid #E8E6E0;
      border-right: 1px solid #E8E6E0;
      border-bottom: 1px solid #E8E6E0;
    }}

    .email-footer p {{
      font-size: 12px;
      color: #888780;
      margin-bottom: 6px;
    }}

    .email-footer a {{
      color: #5F5E5A;
      text-decoration: underline;
      font-size: 12px;
    }}

    /* Mobile */
    @media (max-width: 620px) {{
      .email-wrapper {{ padding: 20px 12px; }}
      .email-header {{ padding: 24px 24px; }}
      .email-hero {{ padding: 32px 24px 28px; }}
      .email-divider {{ padding: 0 24px; }}
      .email-body {{ padding: 28px 24px 36px; }}
      .email-footer {{ padding: 24px; }}
      .email-subject {{ font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-container">

      <!-- Header -->
      <div class="email-header">
        <a href="#" class="email-logo">{FROM_NAME}<span>.</span></a>
      </div>

      <!-- Hero -->
      <div class="email-hero">
        <span class="email-eyebrow">Newsletter</span>
        <h1 class="email-subject">{subject}</h1>
        {f'<p class="email-preview">{preview_text}</p>' if preview_text else ''}
      </div>

      <!-- Divider -->
      <div class="email-divider"><hr /></div>

      <!-- Body -->
      <div class="email-body">
        {body_html}
      </div>

      <!-- Footer -->
      <div class="email-footer">
        <p>You're receiving this because you subscribed to {FROM_NAME} updates.</p>
        <p>
          <a href="{unsubscribe_url}">Unsubscribe</a>
          &nbsp;&middot;&nbsp;
          <a href="#">View in browser</a>
        </p>
        <p style="margin-top: 10px;">&copy; {year} {FROM_NAME}. All rights reserved.</p>
      </div>

    </div>
  </div>
</body>
</html>"""


def build_text_email(subject: str, body_text: str, unsubscribe_url: str) -> str:
    return f"""{subject}
{"=" * len(subject)}

{body_text}

---
To unsubscribe, visit: {unsubscribe_url}
© {datetime.now().year} {FROM_NAME}
"""


def send_campaign(campaign: NewsletterCampaign, test_email: str = None) -> dict:
    """
    Send a newsletter campaign to all active subscribers (or a test address).
    Returns a summary dict with sent/failed counts.
    """
    if test_email:
        recipients = [test_email]
    else:
        recipients = list(
            Subscriber.objects.filter(status="active").values_list("email", flat=True)
        )

    if not recipients:
        return {"sent": 0, "failed": 0, "total": 0, "error": "No active subscribers."}

    campaign.status = "sending"
    campaign.recipients_count = len(recipients)
    campaign.save(update_fields=["status", "recipients_count"])

    sent, failed = 0, 0

    for email in recipients:
        unsubscribe_url = f"{UNSUBSCRIBE_BASE_URL}?email={email}"
        try:
            html_content = build_html_email(
                subject=campaign.subject,
                preview_text=campaign.preview_text,
                body_html=campaign.body_html,
                unsubscribe_url=unsubscribe_url,
            )
            text_content = build_text_email(
                subject=campaign.subject,
                body_text=campaign.body_text or "",
                unsubscribe_url=unsubscribe_url,
            )

            msg = EmailMultiAlternatives(
                subject=campaign.subject,
                body=text_content,
                from_email=f"{FROM_NAME} <{FROM_EMAIL}>",
                to=[email],
                headers={"List-Unsubscribe": f"<{unsubscribe_url}>"},
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            sent += 1

        except Exception as exc:
            logger.error("Failed to send newsletter to %s: %s", email, exc)
            failed += 1

    if not test_email:
        campaign.status = "sent" if failed == 0 else "failed"
        campaign.sent_at = timezone.now()
        campaign.sent_count = sent
        campaign.failed_count = failed
        campaign.save(update_fields=["status", "sent_at", "sent_count", "failed_count"])

    return {"sent": sent, "failed": failed, "total": len(recipients)}



# ─── Public endpoints ────────────────────────────────────────────────────────
 
@api_view(["POST"])
@permission_classes([OriginPermission])
def subscribe(request):
    """Subscribe a new email address."""
    serializer = SubscribeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
    email = serializer.validated_data["email"]
    subscriber, created = Subscriber.objects.get_or_create(
        email=email,
        defaults={"status": "active"},
    )
 
    if not created:
        if subscriber.status == "unsubscribed":
            subscriber.status = "active"
            subscriber.unsubscribed_at = None
            subscriber.save(update_fields=["status", "unsubscribed_at"])
            return Response({"detail": "Welcome back! You've been resubscribed."}, status=status.HTTP_200_OK)
        return Response({"detail": "You're already subscribed."}, status=status.HTTP_200_OK)
 
    return Response({"detail": "Successfully subscribed!"}, status=status.HTTP_201_CREATED)
 
 
@api_view(["POST"])
@permission_classes([OriginPermission])
def unsubscribe(request):
    """Unsubscribe an email address."""
    email = request.data.get("email") or request.query_params.get("email")
    if not email:
        return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
 
    try:
        subscriber = Subscriber.objects.get(email=email.lower().strip())
        if subscriber.status != "unsubscribed":
            subscriber.status = "unsubscribed"
            subscriber.unsubscribed_at = timezone.now()
            subscriber.save(update_fields=["status", "unsubscribed_at"])
        return Response({"detail": "You've been unsubscribed."}, status=status.HTTP_200_OK)
    except Subscriber.DoesNotExist:
        return Response({"detail": "Email not found."}, status=status.HTTP_404_NOT_FOUND)