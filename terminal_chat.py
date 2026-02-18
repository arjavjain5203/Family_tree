import os
import sys
import asyncio
import xml.etree.ElementTree as ET
from httpx import AsyncClient, ASGITransport

# --- CONFIGURATION: MUST BE BEFORE IMPORTING APP ---
# We use a file-based SQLite database so state persists between runs.
# This allows you to restart the script and keep your family tree data.
DB_FILE = "terminal_test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_FILE}"
os.environ["TWILIO_ACCOUNT_SID"] = "AC_TEST"
os.environ["TWILIO_AUTH_TOKEN"] = "AUTH_TEST"
os.environ["TWILIO_PHONE_NUMBER"] = "whatsapp:+1234567890"

# Now import app (which uses the env vars above)
try:
    from app.main import app
    from app.database import Base, engine
except ImportError:
    print("Error: Could not import app. Make sure you are in the root directory and dependencies are installed.")
    sys.exit(1)

async def init_db():
    """Initialize the database tables."""
    print(f"Initializing database: {DB_FILE}...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def parse_twiml(xml_string):
    """Extract the Message Body from TwiML XML."""
    try:
        root = ET.fromstring(xml_string)
        # Twilio XML structure: <Response><Message><Body>...</Body></Message></Response>
        # Or just <Response><Message>...</Message></Response>
        message = root.find(".//Body")
        if message is not None:
            return message.text
        message = root.find(".//Message")
        if message is not None and message.text:
             return message.text
        return "No text in response."
    except ET.ParseError:
        return f"Could not parse XML: {xml_string}"

async def chat_loop():
    """Run the interactive chat loop."""
    print("\n" + "="*50)
    print(" FAMILY TREE TERMINAL CHATBOT TESTER")
    print("="*50)
    print("Type 'exit' or 'quit' to stop.")
    
    # Simulate a user phone number
    phone_input = input("\nEnter your simulated phone number (e.g., +1234567890): ").strip()
    if not phone_input:
        phone_input = "+1234567890"
    
    # Ensure usage of whatsapp prefix if logic expects it (chatbot logic adds it if missing)
    # But let's send what the webhook expects in 'From' field
    user_phone = f"whatsapp:{phone_input}" if not phone_input.startswith("whatsapp:") else phone_input
    
    print(f"\nSimulating user: {user_phone}")
    print("You can now chat with the bot!\n")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        while True:
            try:
                user_msg = input(f"You ({phone_input}): ").strip()
                if user_msg.lower() in ["exit", "quit"]:
                    break
                
                if not user_msg:
                    continue

                # Send to webhook
                response = await client.post(
                    "/webhook",
                    data={"From": user_phone, "Body": user_msg},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    bot_reply = parse_twiml(response.text)
                    print(f"\nBot: {bot_reply}\n")
                else:
                    print(f"\n[Error] Status: {response.status_code}")
                    print(f"Response: {response.text}\n")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n[Exception]: {e}")

    print("\nGoodbye!")

async def main():
    await init_db()
    await chat_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
