from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.tree import Tree, TreeAccess, Role
from app.models.user import User
from app.models.member import Member, Relationship
from typing import Optional, List, Tuple
from datetime import datetime

class TreeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tree(self, owner: User) -> Tree:
        tree = Tree(owner_id=owner.id)
        self.db.add(tree)
        
        # Add owner to access list with OWNER role
        access = TreeAccess(tree=tree, user=owner, role=Role.OWNER)
        self.db.add(access)
        
        await self.db.commit()
        await self.db.refresh(tree)
        return tree

    async def get_tree_by_owner(self, owner_id: int) -> Optional[Tree]:
        result = await self.db.execute(
            select(Tree)
            .filter(Tree.owner_id == owner_id)
            .options(selectinload(Tree.members))
        )
        return result.scalars().first()

    async def get_tree_by_id(self, tree_id: int) -> Optional[Tree]:
         result = await self.db.execute(
            select(Tree)
            .filter(Tree.id == tree_id)
            .options(selectinload(Tree.members))
        )
         return result.scalars().first()

    async def get_active_tree(self, user_id: int) -> Tuple[Optional[Tree], Optional[Role]]:
        """
        Get the tree that the user either owns or has access to (viewer/editor).
        Returns (Tree, Role) or (None, None).
        """
        # 1. Check owned
        owned = await self.get_tree_by_owner(user_id)
        if owned:
             return owned, Role.OWNER
        
        # 2. Check shared
        result = await self.db.execute(
            select(TreeAccess)
            .filter(TreeAccess.user_id == user_id)
            .options(selectinload(TreeAccess.tree).selectinload(Tree.members))
        )
        access = result.scalars().first()
        if access:
             return access.tree, access.role
             
        return None, None

    async def grant_access(self, tree_id: int, user_id: int, role: Role = Role.VIEWER):
        # Check if access already exists
        result = await self.db.execute(
            select(TreeAccess).filter(TreeAccess.tree_id == tree_id, TreeAccess.user_id == user_id)
        )
        access = result.scalars().first()
        if access:
            if access.role != role:
                access.role = role
                await self.db.commit()
            return access
        
        access = TreeAccess(tree_id=tree_id, user_id=user_id, role=role)
        self.db.add(access)
        await self.db.commit()
        return access

    async def transfer_ownership(self, tree: Tree, new_owner: User):
        old_owner_id = tree.owner_id
        
        # Update tree owner
        tree.owner_id = new_owner.id
        
        # Update old owner to Editor
        await self.grant_access(tree.id, old_owner_id, Role.EDITOR)
        
        # Update new owner to Owner in access list (or just ensure they have access)
        # Usually owner is implicit, but we track in access list too
        await self.grant_access(tree.id, new_owner.id, Role.OWNER)
        
        await self.db.commit()

    async def delete_tree(self, tree: Tree):
        # Cascading delete should handle members and access list if configured
        await self.db.delete(tree)
        await self.db.commit()

    async def is_member_locked(self, member_id: int) -> bool:
        result = await self.db.execute(select(Member).filter(Member.id == member_id))
        member = result.scalars().first()
        if not member:
            return False
        
        if member.is_locked and member.lock_expires_at > datetime.now(member.lock_expires_at.tzinfo):
             return True
        
        # Auto-unlock if expired
        if member.is_locked:
             member.is_locked = False
             member.locked_by = None
             member.lock_expires_at = None
             await self.db.commit()
             
        return False
