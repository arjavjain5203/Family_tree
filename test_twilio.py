import os
from twilio.rest import Client
from app.config import get_settings

def test_send():
    settings = get_settings()
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    client = Client(account_sid, auth_token)

    try:
        message = client.messages.create(
            from_=settings.TWILIO_PHONE_NUMBER,
            body="Hello from Render test!",
            to="whatsapp:+919310080000" # NOTE: Using fake number just to see if the API Auth works
        )
        print(f"Success! Message SID: {message.sid}")
    except Exception as e:
        print(f"Failed to send: {e}")

test_send()
