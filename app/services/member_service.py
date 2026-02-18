from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.member import Member, Relationship, Gender
from app.models.event import Event
from typing import Optional, List
from datetime import date, datetime, timedelta
from app.models.tree import Tree

class MemberService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(self, member_id: int) -> Optional[Member]:
        result = await self.db.execute(select(Member).filter(Member.id == member_id))
        return result.scalars().first()
    
    async def get_members_by_tree(self, tree_id: int) -> List[Member]:
        result = await self.db.execute(select(Member).filter(Member.tree_id == tree_id))
        return result.scalars().all()

    async def get_relationships_by_tree(self, tree_id: int) -> List[Relationship]:
        result = await self.db.execute(select(Relationship).filter(Relationship.tree_id == tree_id))
        return result.scalars().all()

    async def create_member(
        self, tree_id: int, name: str, dob: date, gender: Gender, generation_level: int, phone: Optional[str] = None
    ) -> Member:
        member = Member(
            tree_id=tree_id,
            name=name,
            dob=dob,
            gender=gender,
            generation_level=generation_level,
            phone=phone
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def add_relationship(self, tree_id: int, parent_id: int, child_id: int):
        relationship = Relationship(tree_id=tree_id, parent_id=parent_id, child_id=child_id)
        self.db.add(relationship)
        await self.db.commit()

    async def update_member(self, member_id: int, **kwargs):
        member = await self.get_member(member_id)
        if member:
            for key, value in kwargs.items():
                setattr(member, key, value)
            await self.db.commit()
            await self.db.refresh(member)
        return member

    async def lock_member(self, member_id: int, user_id: int, duration_minutes: int = 5) -> bool:
        member = await self.get_member(member_id)
        if not member:
            return False
            
        now = datetime.now(member.lock_expires_at.tzinfo if member.lock_expires_at else None)
        
        # Check if already locked by someone else
        if member.is_locked and member.locked_by != user_id:
             if member.lock_expires_at and member.lock_expires_at > now:
                 return False # Locked by someone else and valid
        
        # Lock or renew lock
        member.is_locked = True
        member.locked_by = user_id
        member.lock_expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        await self.db.commit()
        return True

    async def unlock_member(self, member_id: int, user_id: int) -> bool:
        member = await self.get_member(member_id)
        if not member:
            return False
            
        if member.is_locked and member.locked_by == user_id:
            member.is_locked = False
            member.locked_by = None
            member.lock_expires_at = None
            await self.db.commit()
            return True
        return False # Not locked by this user or not locked

    async def get_member_by_phone(self, phone: str) -> Optional[Member]:
        result = await self.db.execute(select(Member).filter(Member.phone == phone))
        return result.scalars().first()

    async def add_event(self, member_id: int, event_type: str, event_date: date, description: str = None) -> Event:
        event = Event(
            member_id=member_id,
            event_type=event_type,
            event_date=event_date,
            description=description
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_events(self, member_id: int) -> List[Event]:
        # Using execute/scalars for consistency with other methods, though could use relationship lazy loading if instance available
        result = await self.db.execute(
            select(Event).filter(Event.member_id == member_id).order_by(Event.event_date)
        )
        return result.scalars().all()
