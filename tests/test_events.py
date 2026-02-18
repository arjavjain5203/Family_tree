import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_member_events(client: AsyncClient):
    user_a = "whatsapp:+1111111111"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # 1. Create Tree & Add Member
    await client.post("/webhook", data={"From": user_a, "Body": "Hi"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers) # Add Member
    await client.post("/webhook", data={"From": user_a, "Body": "Root"}, headers=headers) # Name
    await client.post("/webhook", data={"From": user_a, "Body": "01-01-1980"}, headers=headers) # DOB
    await client.post("/webhook", data={"From": user_a, "Body": "Male"}, headers=headers) # Gender
    await client.post("/webhook", data={"From": user_a, "Body": "skip"}, headers=headers) # Phone

    # 2. Manage Events
    # Select Option 8
    response = await client.post("/webhook", data={"From": user_a, "Body": "8"}, headers=headers)
    assert "Select a member to manage events for" in response.text
    
    # Select Member 1
    response = await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers)
    assert "What would you like to do?" in response.text
    assert "1. Add Special Date" in response.text
    assert "2. View Special Dates" in response.text

    # 3. Add Event
    # Select 1 (Add)
    await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers)
    
    # Enter Type
    await client.post("/webhook", data={"From": user_a, "Body": "Anniversary"}, headers=headers)
    
    # Enter Date
    response = await client.post("/webhook", data={"From": user_a, "Body": "10-01-1998"}, headers=headers)
    assert "Added Anniversary on 10-01-1998" in response.text

    # 4. View Events
    # Option 8 -> Member 1 -> Option 2 (View)
    await client.post("/webhook", data={"From": user_a, "Body": "8"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers)
    response = await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers)
    
    assert "Special Dates:" in response.text
    assert "10-01-1998: Anniversary" in response.text

    # 5. Permission Check (Viewer)
    user_b = "whatsapp:+2222222222"
    user_b_phone = "+2222222222"
    # Share tree with B
    await client.post("/webhook", data={"From": user_a, "Body": "4"}, headers=headers) # Share
    await client.post("/webhook", data={"From": user_a, "Body": user_b_phone}, headers=headers) # Enter Phone

    # User B tries to Add Event
    await client.post("/webhook", data={"From": user_b, "Body": "Hi"}, headers=headers)
    await client.post("/webhook", data={"From": user_b, "Body": "8"}, headers=headers) # Manage Events
    await client.post("/webhook", data={"From": user_b, "Body": "1"}, headers=headers) # Select Member 1
    response = await client.post("/webhook", data={"From": user_b, "Body": "1"}, headers=headers) # Select Add Event
    
    assert "Only Owners and Editors can add events" in response.text
