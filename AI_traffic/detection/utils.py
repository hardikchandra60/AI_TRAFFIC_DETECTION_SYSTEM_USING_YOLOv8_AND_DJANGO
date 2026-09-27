from twilio.rest import Client
from django.conf import settings

def send_violation_alert(owner, violation_type):
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    message = f"🚨 Violation detected ({violation_type}) for vehicle {owner.vehicle_number}. Please check your dashboard."

    client.messages.create(
        from_=settings.TWILIO_PHONE_NUMBER,
        body=message,
        to='+91' + owner.contact  # assuming Indian phone numbers
    )
