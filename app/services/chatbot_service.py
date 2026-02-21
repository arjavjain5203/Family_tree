import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.services.tree_service import TreeService
from app.services.member_service import MemberService
from app.models.user import User
from app.models.tree import Role
from app.models.member import Gender
from app.models.event import Event
from twilio.twiml.messaging_response import MessagingResponse
from app.utils.validators import validate_dob, validate_gender
from datetime import date
from collections import defaultdict

logger = logging.getLogger(__name__)

class ChatbotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
        self.tree_service = TreeService(db)
        self.member_service = MemberService(db)

    async def handle_message(self, from_number: str, body: str) -> str:
        # Normalize phone number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"
        
        db_phone = from_number.replace("whatsapp:", "") # Store without prefix? Or with?
        # Let's store consistent with incoming, but user service might strip it.
        # User service create_user stores as is for now.
        
        user = await self.user_service.get_or_create_user(db_phone)
        response = MessagingResponse()
        
        state = user.current_state
        data = (user.state_data or {}).copy()
        
        if body.lower() == "reset":
             await self.user_service.clear_state(user.id)
             await self.show_main_menu(response)
             await self.user_service.update_state(user.id, "MAIN_MENU")
             return str(response)

        try:
            if not state or state == "MAIN_MENU":
                await self.handle_main_menu(user, body, response)
            
            # --- ADD MEMBER FLOW ---
            elif state == "ADD_MEMBER_NAME":
                await self.user_service.update_state(user.id, "ADD_MEMBER_DOB", {"name": body})
                response.message("Enter Date of Birth (DD-MM-YYYY):")
            
            elif state == "ADD_MEMBER_DOB":
                try:
                    dob = validate_dob(body)
                    data['dob'] = dob.isoformat()
                    await self.user_service.update_state(user.id, "ADD_MEMBER_GENDER", data)
                    response.message("Enter Gender (Male/Female/Other):")
                except ValueError as e:
                    response.message(str(e))

            elif state == "ADD_MEMBER_GENDER":
                try:
                    gender = validate_gender(body)
                    data['gender'] = gender.value
                    await self.user_service.update_state(user.id, "ADD_MEMBER_PHONE", data)
                    response.message("Enter Phone Number (optional, send 'skip' to skip):")
                except ValueError as e:
                    response.message(str(e))

            elif state == "ADD_MEMBER_PHONE":
                phone = body.strip()
                if phone.lower() != 'skip':
                    data['phone'] = phone # Validate?
                await self.user_service.update_state(user.id, "ADD_MEMBER_RELATION", data)
                # Fetch existing members to show options
                tree, role = await self.tree_service.get_active_tree(user.id)
                members = await self.member_service.get_members_by_tree(tree.id) if tree else []
                
                if not tree or not members:
                     # First member (Root)
                     await self.finalize_add_member(user, data, response, is_root=True)
                else:
                    msg = "Who is this member related to? Enter the ID of the relative:\n"
                    for m in members:
                        msg += f"{m.id}. {m.name} ({m.generation_level})\n"
                    response.message(msg)

            elif state == "ADD_MEMBER_RELATION":
                if 'parent_id' not in data:
                    try:
                        relative_id = int(body)
                        data['relative_id'] = relative_id
                        await self.user_service.update_state(user.id, "ADD_MEMBER_RELATION_TYPE", data)
                        response.message("What is the relationship of the NEW member to the relative?\n1. Mother\n2. Father\n3. Child\n4. Spouse\n5. Brother\n6. Sister")
                    except ValueError:
                        response.message("Invalid ID. Please enter a number.")
                
            elif state == "ADD_MEMBER_RELATION_TYPE":
                try:
                    choice = int(body.strip())
                    relative_id = data['relative_id']
                    relative = await self.member_service.get_member(relative_id)
                    
                    if not relative:
                         response.message("Relative not found. Aborting.")
                         await self.user_service.clear_state(user.id)
                         return str(response)

                    if choice == 1: # Mother
                        new_gen = relative.generation_level - 1
                        relationship_type = "parent"
                        data['gender'] = Gender.FEMALE.value
                    elif choice == 2: # Father
                        new_gen = relative.generation_level - 1
                        relationship_type = "parent"
                        data['gender'] = Gender.MALE.value
                    elif choice == 3: # Child
                        new_gen = relative.generation_level + 1
                        relationship_type = "child"
                    elif choice == 4: # Spouse
                        new_gen = relative.generation_level
                        relationship_type = "spouse"
                    elif choice == 5: # Brother
                        new_gen = relative.generation_level
                        relationship_type = "sibling"
                        data['gender'] = Gender.MALE.value
                    elif choice == 6: # Sister
                        new_gen = relative.generation_level
                        relationship_type = "sibling"
                        data['gender'] = Gender.FEMALE.value
                    else:
                        response.message("Invalid choice. Enter 1-6.")
                        return str(response)

                    data['generation'] = new_gen
                    data['relationship_type'] = relationship_type
                    
                    await self.finalize_add_member(user, data, response)
                except ValueError:
                     response.message("Invalid input. Please enter a number.")

            # --- EDIT MEMBER FLOW ---
            elif state == "EDIT_SELECT_MEMBER":
                 try:
                     member_id = int(body.strip())
                     # Check if member exists in user's tree
                     tree, role = await self.tree_service.get_active_tree(user.id)
                     if not tree:
                          response.message("Tree not found.")
                          return str(response)
                     
                     member = await self.member_service.get_member(member_id)
                     if not member or member.tree_id != tree.id:
                          response.message("Member not found in your tree.")
                          return str(response)
                     
                     if role not in [Role.OWNER, Role.EDITOR]:
                          response.message("Permission denied. Viewers cannot edit.")
                          await self.user_service.clear_state(user.id)
                          return str(response)
                     
                     # Check locking
                     if await self.tree_service.is_member_locked(member_id):
                          if member.locked_by != user.id:
                               response.message(f"Member is currently being edited by another user. Try again later.")
                               await self.user_service.clear_state(user.id)
                               return str(response)

                     # Lock member
                     await self.member_service.lock_member(member_id, user.id)
                     data['member_id'] = member_id
                     await self.user_service.update_state(user.id, "EDIT_SELECT_FIELD", data)
                     response.message(f"Editing {member.name}. What do you want to change?\n1. Name\n2. DOB\n3. Gender\n4. Phone\n5. Relation")
                 except ValueError:
                      response.message("Invalid ID.")

            elif state == "EDIT_SELECT_FIELD":
                 choice = body.strip()
                 data['edit_field'] = choice
                 
                 if choice == '5':
                      # Editing relation
                      tree, role = await self.tree_service.get_active_tree(user.id)
                      members = await self.member_service.get_members_by_tree(tree.id) if tree else []
                      msg = "Select the relative to link to:\n"
                      for m in members:
                           if m.id != data['member_id']:
                               msg += f"{m.id}. {m.name}\n"
                      await self.user_service.update_state(user.id, "EDIT_RELATION_TARGET", data)
                      response.message(msg)
                 else:
                      await self.user_service.update_state(user.id, "EDIT_ENTER_VALUE", data)
                      if choice == '1': response.message("Enter new Name:")
                      elif choice == '2': response.message("Enter new DOB (DD-MM-YYYY):")
                      elif choice == '3': response.message("Enter new Gender (Male/Female/Other):")
                      elif choice == '4': response.message("Enter new Phone:")
                      else:
                           response.message("Invalid choice.")
            
            elif state == "EDIT_RELATION_TARGET":
                 try:
                     target_id = int(body.strip())
                     data['edit_relation_target'] = target_id
                     await self.user_service.update_state(user.id, "EDIT_RELATION_TYPE", data)
                     response.message("What is the relationship of the edited member to this relative?\n1. Mother\n2. Father\n3. Child\n4. Spouse\n5. Brother\n6. Sister")
                 except ValueError:
                     response.message("Invalid ID. Enter a number.")

            elif state == "EDIT_RELATION_TYPE":
                 try:
                     choice = int(body.strip())
                     member_id = data['member_id']
                     target_id = data['edit_relation_target']
                     
                     target = await self.member_service.get_member(target_id)
                     if not target:
                          response.message("Relative not found.")
                          return str(response)

                     # Delete old relationships where this member is a child (assuming single parent linkage usually, or just drop all and reset)
                     # For simplicity, we just add the new relationship
                     rel_type = ""
                     updates = {}
                     if choice == 1:
                         rel_type = "parent"
                         updates['gender'] = Gender.FEMALE
                     elif choice == 2:
                         rel_type = "parent"
                         updates['gender'] = Gender.MALE
                     elif choice == 3:
                         rel_type = "child"
                     elif choice == 4:
                         rel_type = "spouse"
                     elif choice == 5:
                         rel_type = "sibling"
                         updates['gender'] = Gender.MALE
                     elif choice == 6:
                         rel_type = "sibling"
                         updates['gender'] = Gender.FEMALE
                     
                     if updates:
                          await self.member_service.update_member(member_id, **updates)
                     
                     if rel_type == "child":
                          await self.member_service.add_relationship(target.tree_id, target_id, member_id, "parent")
                     elif rel_type == "parent":
                          await self.member_service.add_relationship(target.tree_id, member_id, target_id, "parent")
                     elif rel_type in ["spouse", "sibling"]:
                          await self.member_service.add_relationship(target.tree_id, target_id, member_id, rel_type)

                     await self.member_service.unlock_member(member_id, user.id)
                     response.message("✅ Relationship updated successfully!")
                     await self.user_service.clear_state(user.id)
                     await self.show_main_menu(response)
                 except ValueError:
                     response.message("Invalid choice. Enter 1-6.")
            
            elif state == "EDIT_ENTER_VALUE":
                 member_id = data['member_id']
                 field_choice = data['edit_field']
                 new_value = body.strip()
                 
                 updates = {}
                 try:
                     if field_choice == '1':
                          updates['name'] = new_value
                     elif field_choice == '2':
                          updates['dob'] = validate_dob(new_value)
                     elif field_choice == '3':
                          updates['gender'] = validate_gender(new_value)
                     elif field_choice == '4':
                          # Phone validation
                          updates['phone'] = new_value
                     
                     await self.member_service.update_member(member_id, **updates)
                     await self.member_service.unlock_member(member_id, user.id)
                     response.message("✅ Member updated successfully!")
                     await self.user_service.clear_state(user.id)
                     await self.show_main_menu(response)
                 except ValueError as e:
                      response.message(str(e))

            # --- SHARE TREE FLOW ---
            elif state == "SHARE_ENTER_PHONE":
                 phone = body.strip()
                 if not phone.startswith('+'): phone = '+' + phone 
                 
                 target_user = await self.user_service.get_or_create_user(phone)
                 tree, role = await self.tree_service.get_active_tree(user.id)
                 
                 if tree and role == Role.OWNER:
                     await self.tree_service.grant_access(tree.id, target_user.id, Role.VIEWER)
                     response.message(f"✅ Access granted to {phone} as Viewer.")
                 else:
                     response.message("You do not have permission to share this tree.")
                 
                 await self.user_service.clear_state(user.id)
                 await self.show_main_menu(response)

            # --- TRANSFER OWNERSHIP FLOW ---
            elif state == "TRANSFER_ENTER_PHONE":
                 phone = body.strip()
                 if not phone.startswith('+'): phone = '+' + phone
                 
                 target_user = await self.user_service.get_or_create_user(phone)
                 tree, role = await self.tree_service.get_active_tree(user.id)
                 
                 if tree and role == Role.OWNER:
                     if target_user.id == user.id:
                          response.message("You already own this tree.")
                     else:
                          await self.tree_service.transfer_ownership(tree, target_user)
                          response.message(f"✅ Ownership transferred to {phone}. You are now an Editor.")
                 else:
                     response.message("You do not have permission to transfer ownership.")
                 
                 await self.user_service.clear_state(user.id)
                 await self.show_main_menu(response)

            # --- DELETE TREE FLOW ---
            elif state == "DELETE_CONFIRM":
                 if body.lower() == "yes":
                     tree, role = await self.tree_service.get_active_tree(user.id)
                     if tree and role == Role.OWNER:
                         await self.tree_service.delete_tree(tree)
                         response.message("✅ Tree deleted successfully.")
                     else:
                         response.message("Permission denied or tree not found.")
                 else:
                     response.message("Deletion cancelled.")
                 
                 await self.user_service.clear_state(user.id)
                 await self.show_main_menu(response)


            # --- EVENT FLOW ---
            elif state == "EVENT_SELECT_MEMBER":
                 try:
                     member_id = int(body.strip())
                     tree, role = await self.tree_service.get_active_tree(user.id)
                     if not tree:
                          response.message("Tree not found.")
                          return str(response)
                     
                     member = await self.member_service.get_member(member_id)
                     if not member or member.tree_id != tree.id:
                          response.message("Member not found in your tree.")
                          return str(response)

                     # Store selected member
                     data['member_id'] = member_id
                     await self.user_service.update_state(user.id, "EVENT_ACTION", data)
                     response.message(f"Selected {member.name}. What would you like to do?\n1. Add Special Date\n2. View Special Dates")
                 except ValueError:
                      response.message("Invalid ID. Please enter a number.")

            elif state == "EVENT_ACTION":
                 choice = body.strip()
                 if choice == "1":
                      # Add Event
                      tree, role = await self.tree_service.get_active_tree(user.id)
                      if role not in [Role.OWNER, Role.EDITOR]:
                           response.message("🔒 Only Owners and Editors can add events.")
                           await self.user_service.clear_state(user.id)
                           await self.show_main_menu(response)
                           return str(response)

                      await self.user_service.update_state(user.id, "EVENT_TYPE", data)
                      response.message("Enter the Event Type (e.g. Birthday, Anniversary, Death Anniversary):")
                 elif choice == "2":
                      # View Events
                      member_id = data['member_id']
                      events = await self.member_service.get_events(member_id)
                      if not events:
                           response.message("No special dates found for this member.")
                      else:
                           msg = "*Special Dates:*\n"
                           for e in events:
                                msg += f"📅 {e.event_date.strftime('%d-%m-%Y')}: {e.event_type}\n"
                           response.message(msg)
                      
                      await self.user_service.clear_state(user.id)
                      await self.show_main_menu(response)
                 else:
                      response.message("Invalid choice. Enter 1 or 2.")
            
            elif state == "EVENT_TYPE":
                 data['event_type'] = body.strip()
                 await self.user_service.update_state(user.id, "EVENT_DATE", data)
                 response.message("Enter the Date (DD-MM-YYYY):")

            elif state == "EVENT_DATE":
                 try:
                      event_date = validate_dob(body) # Reuse DOB validator for date format
                      member_id = data['member_id']
                      event_type = data['event_type']
                      
                      await self.member_service.add_event(member_id, event_type, event_date)
                      response.message(f"✅ Added {event_type} on {event_date.strftime('%d-%m-%Y')}!")
                      await self.user_service.clear_state(user.id)
                      await self.show_main_menu(response)
                 except ValueError as e:
                      response.message(str(e))

        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"Error handling message: {e}")
            response.message("An error occurred. Please try again or type 'reset'.")

        return str(response)


    async def show_main_menu(self, response: MessagingResponse):
        msg = response.message()
        msg.body(
            "🌳 *Family Tree Bot* 🌳\n\n"
            "1. 👁 View Tree\n"
            "2. ➕ Add Member\n"
            "3. ✏️ Edit Member\n"
            "4. 📤 Share Tree\n"
            "5. 🔄 Transfer Ownership\n"
            "6. 🗑 Delete Tree\n"
            "7. ℹ️ Help\n"
            "8. 📅 Manage Events"
        )

    async def handle_main_menu(self, user: User, body: str, response: MessagingResponse):
        choice = body.strip()
        tree, role = await self.tree_service.get_active_tree(user.id)

        if choice == "1":
            if not tree:
                 response.message("You don't have a tree yet. Select 'Add Member' to start!")
            else:
                members = await self.member_service.get_members_by_tree(tree.id)
                relationships = await self.member_service.get_relationships_by_tree(tree.id)
                tree_text = self._build_tree_text(members, relationships)
                response.message(tree_text)
            
            await self.show_main_menu(response)
                
        elif choice == "2":
            # Add Member
            if tree and role not in [Role.OWNER, Role.EDITOR]:
                response.message("🔒 You are a Viewer. You cannot add members.")
                return

            if not tree:
                tree = await self.tree_service.create_tree(user)
                
            await self.user_service.update_state(user.id, "ADD_MEMBER_NAME")
            response.message("Enter the name of the new member:")
            
        elif choice == "3":
             # Edit Member
             if not tree:
                  response.message("No tree found.")
                  return
             
             if role not in [Role.OWNER, Role.EDITOR]:
                  response.message("🔒 You are a Viewer. You cannot edit members.")
                  return

             members = await self.member_service.get_members_by_tree(tree.id) if tree else []
             
             if not members:
                  response.message("No members to edit.")
             else:
                  msg = "Enter the ID of the member to edit:\n"
                  for m in members:
                       msg += f"{m.id}. {m.name}\n"
                  response.message(msg)
                  await self.user_service.update_state(user.id, "EDIT_SELECT_MEMBER")
             
        elif choice == "7":
             response.message("Send 'reset' anytime to return to the main menu.")
             await self.show_main_menu(response)
        
        else:
             if choice == "4":
                 # Share Tree
                 if not tree:
                      response.message("You do not own a tree to share.")
                      await self.show_main_menu(response)
                 elif role != Role.OWNER:
                      response.message("🔒 Only the Owner can share the tree.")
                      await self.show_main_menu(response)
                 else:
                      await self.user_service.update_state(user.id, "SHARE_ENTER_PHONE")
                      response.message("Enter the phone number to share with (e.g. +1234567890):")

             elif choice == "5":
                 # Transfer
                 if not tree:
                      response.message("You do not own a tree.")
                      await self.show_main_menu(response)
                 elif role != Role.OWNER:
                      response.message("🔒 Only the Owner can transfer ownership.")
                      await self.show_main_menu(response)
                 else:
                      await self.user_service.update_state(user.id, "TRANSFER_ENTER_PHONE")
                      response.message("Enter the phone number of the new owner:")

             elif choice == "6":
                 # Delete
                 if not tree:
                      response.message("You do not own a tree.")
                      await self.show_main_menu(response)
                 elif role != Role.OWNER:
                      response.message("🔒 Only the Owner can delete the tree.")
                      await self.show_main_menu(response)
                 else:
                      await self.user_service.update_state(user.id, "DELETE_CONFIRM")
                      response.message("Are you sure you want to delete your tree? This cannot be undone. Reply 'yes' to confirm.")
              
             elif choice == "8":
                  # Manage Events
                  if not tree:
                       response.message("No tree found.")
                  else:
                       members = await self.member_service.get_members_by_tree(tree.id)
                       if not members:
                            response.message("No members found. Add members first.")
                       else:
                            msg = "Select a member to manage events for:\n"
                            for m in members:
                                 msg += f"{m.id}. {m.name}\n"
                            response.message(msg)
                            await self.user_service.update_state(user.id, "EVENT_SELECT_MEMBER")

             elif body.lower() in ["hi", "hello", "menu", "start"]:
                  await self.show_main_menu(response)
             else:
                  response.message("Invalid option. Send 'menu' to see options.")

    async def finalize_add_member(self, user, data, response, is_root=False):
         user_id = user.id
         tree, role = await self.tree_service.get_active_tree(user_id)
         if not tree or role not in [Role.OWNER, Role.EDITOR]:
              response.message("Permission denied.")
              await self.user_service.clear_state(user_id)
              return

         tree_id = tree.id
         try:
             # Create member
             member = await self.member_service.create_member(
                 tree_id=tree_id,
                 name=data['name'],
                 dob=date.fromisoformat(data['dob']),
                 gender=Gender(data['gender']),
                 generation_level=1 if is_root else data.get('generation'),
                 phone=data.get('phone')
             )
             member_name = member.name
             member_id = member.id
             
             if not is_root and 'relative_id' in data:
                  # Add relationship
                  relative_id = data['relative_id']
                  rel_type = data['relationship_type']
                  
                  if rel_type == "child":
                       await self.member_service.add_relationship(tree_id, relative_id, member_id, "parent")
                  elif rel_type == "parent":
                       await self.member_service.add_relationship(tree_id, member_id, relative_id, "parent")
                  elif rel_type == "sibling":
                       parents = await self.member_service.get_parents(tree_id, relative_id)
                       if parents:
                           for p_id in parents:
                               await self.member_service.add_relationship(tree_id, p_id, member_id, "parent")
                       else:
                           await self.member_service.add_relationship(tree_id, relative_id, member_id, "sibling")
                  elif rel_type == "spouse":
                       await self.member_service.add_relationship(tree_id, relative_id, member_id, "spouse")
                  
             response.message(f"✅ Added {member_name} to the tree!")
             await self.user_service.clear_state(user_id)
             await self.show_main_menu(response)
         except Exception as e:
             response.message(f"❌ Failed to add member: {str(e)}")
             await self.user_service.clear_state(user_id)

    def _build_tree_text(self, members, relationships) -> str:
        if not members:
            return "Tree is empty."
            
        member_map = {m.id: m for m in members}
        children_map = defaultdict(list)
        child_to_parents = defaultdict(list)
        partners_map = defaultdict(set)
        
        for r in relationships:
            # Handle default empty strings in DB from old migrations
            rtype = getattr(r, 'relation_type', 'parent') or 'parent'
            
            if rtype == "parent":
                children_map[r.parent_id].append(r.child_id)
                child_to_parents[r.child_id].append(r.parent_id)
            elif rtype == "spouse":
                partners_map[r.parent_id].add(r.child_id)
                partners_map[r.child_id].add(r.parent_id)
            elif rtype == "sibling":
                pass # Currently rendered separately if no parent
                
        # Link partners who share children implicitly
        for child, parents in child_to_parents.items():
            if len(parents) > 1:
                for p1 in parents:
                    for p2 in parents:
                        if p1 != p2:
                            partners_map[p1].add(p2)
                            
        # Roots are nodes with no parents
        child_ids = set()
        for r in relationships:
            rtype = getattr(r, 'relation_type', 'parent') or 'parent'
            if rtype == "parent": child_ids.add(r.child_id)
            
        roots = [m for m in members if m.id not in child_ids]
        roots.sort(key=lambda m: (m.generation_level, m.id))
        
        output = [f"🌳 *Your Family Tree* ({len(members)} members)\n"]
        drawn_members = set()
        
        def format_member(m):
            g_str = str(m.gender).lower()
            gender_symbol = "F" if "female" in g_str else "M" if "male" in g_str else "O"
            return f"{m.name} ({gender_symbol})"

        def print_tree(member_id, prefix, is_last):
            if member_id in drawn_members: return
            member = member_map.get(member_id)
            if not member: return
            
            # Identify partners to draw together
            partners = []
            for pid in partners_map.get(member_id, set()):
                p_member = member_map.get(pid)
                if p_member and p_member.id not in drawn_members:
                    partners.append(p_member)
                    drawn_members.add(p_member.id)
                    
            drawn_members.add(member_id)
            
            connector = "└── " if is_last else "├── "
            nodes = [format_member(member)] + [format_member(p) for p in partners]
            nodes_text = " & ".join(nodes)
            
            line = f"{prefix}{connector}{nodes_text}, Gen {member.generation_level}"
            output.append(line)
            
            # Combine children of member and partners
            all_children_ids = set(children_map.get(member_id, []))
            for p in partners:
                all_children_ids.update(children_map.get(p.id, []))
                
            children = list(all_children_ids)
            children.sort(key=lambda cid: member_map[cid].dob if member_map.get(cid) and member_map[cid].dob else date.max)
            
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, child_id in enumerate(children):
                print_tree(child_id, new_prefix, i == len(children) - 1)

        for i, root in enumerate(roots):
            if root.id in drawn_members: continue
            
            partners = []
            for pid in partners_map.get(root.id, set()):
                p_member = member_map.get(pid)
                if p_member and p_member.id not in drawn_members:
                    partners.append(p_member)
                    drawn_members.add(p_member.id)
            
            drawn_members.add(root.id)
            
            nodes = [format_member(root)] + [format_member(p) for p in partners]
            nodes_text = " & ".join(nodes)
            line = f"{nodes_text}, Gen {root.generation_level}"
            output.append(line)
            
            all_children_ids = set(children_map.get(root.id, []))
            for p in partners:
                all_children_ids.update(children_map.get(p.id, []))
                
            children = list(all_children_ids)
            children.sort(key=lambda cid: member_map[cid].dob if member_map.get(cid) and member_map[cid].dob else date.max)
            
            for j, child_id in enumerate(children):
                 print_tree(child_id, "", j == len(children) - 1)
                 
            output.append("") # Separator between trees

        return "\n".join(output)
