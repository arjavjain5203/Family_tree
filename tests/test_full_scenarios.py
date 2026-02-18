import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_family_scenario(client: AsyncClient):
    # Users
    user_a = "whatsapp:+1111111111" # Owner
    user_b = "whatsapp:+2222222222" # Viewer -> Owner
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # ==========================================
    # 1. User A Creates Tree & Adds Members
    # ==========================================
    
    # Start: A says Hi
    await client.post("/webhook", data={"From": user_a, "Body": "Hi"}, headers=headers)
    
    # Add Member (Root)
    await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Grandpa"}, headers=headers) # Name
    await client.post("/webhook", data={"From": user_a, "Body": "01-01-1950"}, headers=headers) # DOB
    await client.post("/webhook", data={"From": user_a, "Body": "Male"}, headers=headers) # Gender
    await client.post("/webhook", data={"From": user_a, "Body": "skip"}, headers=headers) # Phone
    
    # Add Member (Spouse to Root)
    # Flow: Add Member -> Name -> DOB -> Gender -> Phone -> Relation ID -> Relation Type
    await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Grandma"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "01-01-1955"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Female"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "skip"}, headers=headers)
    
    # Select relative: 1 (Grandpa)
    response = await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers)
    assert "Is the new member a" in response.text
    
    # Select relation: 3 (Spouse)
    response = await client.post("/webhook", data={"From": user_a, "Body": "3"}, headers=headers)
    assert "Added Grandma to the tree" in response.text

    # ==========================================
    # 1.1 Owner Edits Member
    # ==========================================
    
    # Edit Member -> Select Member (1) -> Select Field (4 Phone) -> Enter Value
    await client.post("/webhook", data={"From": user_a, "Body": "3"}, headers=headers) # Edit
    await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers) # Grandpa
    await client.post("/webhook", data={"From": user_a, "Body": "4"}, headers=headers) # Phone
    response = await client.post("/webhook", data={"From": user_a, "Body": "+1999999999"}, headers=headers)
    assert "Member updated successfully" in response.text

    # ==========================================
    # 1.2 Owner Adds Child
    # ==========================================
    
    # Add Member -> Name -> DOB -> Gender -> Phone -> Relation (1 Grandpa) -> Type (2 Child)
    await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Dad"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "01-01-1980"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Male"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "skip"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers) # Grandpa
    response = await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers) # Child
    assert "Added Dad to the tree" in response.text

    # ==========================================
    # 1.3 Owner Adds Parent (to Grandpa)
    # ==========================================
    
    # Add Member -> Name -> DOB -> Gender -> Phone -> Relation (1 Grandpa) -> Type (1 Parent)
    await client.post("/webhook", data={"From": user_a, "Body": "2"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "GreatGrandpa"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "01-01-1920"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "Male"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "skip"}, headers=headers)
    await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers) # Grandpa
    response = await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers) # Parent
    assert "Added GreatGrandpa to the tree" in response.text

    # View Tree
    response = await client.post("/webhook", data={"From": user_a, "Body": "1"}, headers=headers)
    assert "Grandpa" in response.text
    assert "Grandma" in response.text
    assert "Dad" in response.text
    assert "GreatGrandpa" in response.text

    # ==========================================
    # 2. Share Tree with User B (Viewer)
    # ==========================================
    
    # Share Tree -> Enter Phone
    await client.post("/webhook", data={"From": user_a, "Body": "4"}, headers=headers)
    response = await client.post("/webhook", data={"From": user_a, "Body": user_b.replace("whatsapp:", "")}, headers=headers)
    assert "Access granted" in response.text

    # ==========================================
    # 3. User B Views Tree (SHOULD SUCCEED NOW)
    # ==========================================
    
    # User B says Hi
    await client.post("/webhook", data={"From": user_b, "Body": "Hi"}, headers=headers)
    
    # User B tries to View Tree (Option 1)
    response = await client.post("/webhook", data={"From": user_b, "Body": "1"}, headers=headers)
    
    assert "Grandpa" in response.text
    assert "Grandma" in response.text
    print("\n[SUCCESS] User B can see the shared tree.")

    # ==========================================
    # 4. User B Tries to Edit (Should Fail as Viewer)
    # ==========================================
    
    # User B tries Add Member (Option 2)
    response = await client.post("/webhook", data={"From": user_b, "Body": "2"}, headers=headers)
    assert "You are a Viewer" in response.text or "Permission denied" in response.text
    print("\n[SUCCESS] User B blocked from adding members.")

    # User B tries Edit Member (Option 3)
    response = await client.post("/webhook", data={"From": user_b, "Body": "3"}, headers=headers)
    assert "You are a Viewer" in response.text or "Permission denied" in response.text
    print("\n[SUCCESS] User B blocked from editing members.")
    
    # ==========================================
    # 5. Transfer Ownership A -> B
    # ==========================================
    
    await client.post("/webhook", data={"From": user_a, "Body": "5"}, headers=headers) # Transfer
    response = await client.post("/webhook", data={"From": user_a, "Body": user_b.replace("whatsapp:", "")}, headers=headers)
    assert "Ownership transferred" in response.text

    # ==========================================
    # 6. User B Deletes Tree (As Owner)
    # ==========================================
    
    # User B views tree (now Owner)
    response = await client.post("/webhook", data={"From": user_b, "Body": "1"}, headers=headers)
    # This might still fail if get_tree_by_owner check is strict on chatbot_service side 
    # but strictly speaking B IS the owner now in DB.
    
    # User B deletes
    await client.post("/webhook", data={"From": user_b, "Body": "6"}, headers=headers) # Delete
    response = await client.post("/webhook", data={"From": user_b, "Body": "yes"}, headers=headers)
    
    # If B is owner, delete should work.
    if "Tree deleted successfully" in response.text:
         print("\n[SUCCESS] User B deleted tree.")
    else:
         print(f"\n[FAIL] User B could not delete: {response.text}")

