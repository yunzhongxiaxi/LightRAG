"""
Prompt Storage Service for LightRAG - Redesigned

支持订阅机制、真实版本号、软删除的 Prompt 管理系统。
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from datetime import datetime, timezone
import json
import asyncpg
from lightrag.utils import logger


class PromptStorageService:
    """Prompt 存储服务，支持订阅机制和热更新"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """初始化数据库连接池"""
        self.pool = await asyncpg.create_pool(self.connection_string)
        logger.info("Prompt storage service initialized")

    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            logger.info("Prompt storage service closed")

    async def get_system_prompts(self) -> Dict[str, Any]:
        """获取系统默认 Prompt"""
        from lightrag.prompt import PROMPTS
        return PROMPTS.copy()

    async def create_template(
        self,
        creator: str,
        content: Dict[str, str],
    ) -> int:
        """创建新模板版本

        Args:
            creator: 创建者
            content: Prompt 内容（部分自定义）

        Returns:
            新版本号（真实版本号）
        """
        async with self.pool.acquire() as conn:
            # 获取该创建者的最大版本号
            max_version = await conn.fetchval(
                """
                SELECT MAX(version) FROM templates
                WHERE creator = $1 AND is_deleted = false
                """,
                creator
            )
            new_version = (max_version or 0) + 1

            # 插入新版本
            await conn.execute(
                """
                INSERT INTO templates (creator, version, content)
                VALUES ($1, $2, $3)
                """,
                creator, new_version, json.dumps(content)
            )

            logger.info(f"Created template for {creator}, version {new_version}")
            return new_version

    async def update_template(
        self,
        creator: str,
        version: int,
        content: Dict[str, str],
    ) -> int:
        """更新模板（实际是创建新版本）

        Args:
            creator: 创建者
            version: 要更新的版本号（真实版本号）
            content: 新的 Prompt 内容

        Returns:
            新版本号
        """
        # 更新就是创建新版本
        return await self.create_template(creator, content)

    async def get_template(
        self,
        creator: str,
        version: int
    ) -> Optional[Dict[str, Any]]:
        """获取特定版本的模板

        Args:
            creator: 创建者
            version: 版本号（真实版本号）

        Returns:
            模板数据或 None
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, creator, version, content, is_deleted,
                       created_at, updated_at
                FROM templates
                WHERE creator = $1 AND version = $2
                """,
                creator, version
            )

            if row:
                return {
                    "id": row["id"],
                    "creator": row["creator"],
                    "version": row["version"],
                    "content": json.loads(row["content"]),
                    "is_deleted": row["is_deleted"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                }
            return None

    async def get_latest_template(self, creator: str) -> Optional[Dict[str, Any]]:
        """获取创建者的最新版本模板"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, creator, version, content, is_deleted,
                       created_at, updated_at
                FROM templates
                WHERE creator = $1 AND is_deleted = false
                ORDER BY version DESC
                LIMIT 1
                """,
                creator
            )

            if row:
                return {
                    "id": row["id"],
                    "creator": row["creator"],
                    "version": row["version"],
                    "content": json.loads(row["content"]),
                    "is_deleted": row["is_deleted"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                }
            return None

    async def list_versions(self, creator: str) -> List[int]:
        """列出创建者的所有版本号（真实版本号，未删除的）

        Returns:
            版本号列表，按版本号降序排列
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT version FROM templates
                WHERE creator = $1 AND is_deleted = false
                ORDER BY version DESC
                """,
                creator
            )
            return [row["version"] for row in rows]

    async def soft_delete_template(self, creator: str, version: int):
        """软删除模板版本"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE templates
                SET is_deleted = true, updated_at = NOW()
                WHERE creator = $1 AND version = $2
                """,
                creator, version
            )
            logger.info(f"Soft deleted template {creator} v{version}")

    async def subscribe(
        self,
        user_id: str,
        creator: str,
        version: Optional[int] = None,
        is_auto_update: bool = True
    ):
        """订阅模板

        Args:
            user_id: 用户 ID
            creator: 创建者
            version: 订阅的版本号（None = 订阅最新版本）
            is_auto_update: 是否自动更新
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_template_subscriptions
                    (user_id, creator, subscribed_version, is_auto_update)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, creator)
                DO UPDATE SET
                    subscribed_version = $3,
                    is_auto_update = $4,
                    last_synced_at = NOW()
                """,
                user_id, creator, version, is_auto_update
            )
            logger.info(f"User {user_id} subscribed to {creator} v{version or 'latest'}")

    async def unsubscribe(self, user_id: str, creator: str):
        """取消订阅"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM user_template_subscriptions
                WHERE user_id = $1 AND creator = $2
                """,
                user_id, creator
            )
            logger.info(f"User {user_id} unsubscribed from {creator}")

    async def get_subscription(
        self,
        user_id: str,
        creator: str
    ) -> Optional[Dict[str, Any]]:
        """获取订阅信息"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT user_id, creator, subscribed_version,
                       is_auto_update, last_synced_at
                FROM user_template_subscriptions
                WHERE user_id = $1 AND creator = $2
                """,
                user_id, creator
            )

            if row:
                return {
                    "user_id": row["user_id"],
                    "creator": row["creator"],
                    "subscribed_version": row["subscribed_version"],
                    "is_auto_update": row["is_auto_update"],
                    "last_synced_at": row["last_synced_at"].isoformat(),
                }
            return None

    async def get_user_prompts(self, user_id: str) -> Dict[str, Any]:
        """获取用户当前使用的 Prompt（合并系统 Prompt 和订阅的模板）

        Args:
            user_id: 用户 ID

        Returns:
            合并后的 Prompt 字典
        """
        # 获取系统默认 Prompt
        prompts = await self.get_system_prompts()

        # 查找用户订阅（默认订阅自己的模板）
        subscription = await self.get_subscription(user_id, user_id)

        if subscription:
            # 获取订阅的模板
            if subscription["subscribed_version"] is None:
                # 订阅最新版本
                template = await self.get_latest_template(subscription["creator"])
            else:
                # 订阅特定版本
                template = await self.get_template(
                    subscription["creator"],
                    subscription["subscribed_version"]
                )

            if template and not template["is_deleted"]:
                # 合并用户自定义 Prompt（用户配置覆盖系统默认）
                prompts.update(template["content"])

        return prompts

    async def check_for_updates(
        self,
        user_id: str,
        creator: str
    ) -> Optional[Dict[str, Any]]:
        """检查订阅是否有更新

        Returns:
            如果有更新返回最新模板，否则返回 None
        """
        subscription = await self.get_subscription(user_id, creator)
        if not subscription or not subscription["is_auto_update"]:
            return None

        if subscription["subscribed_version"] is not None:
            # 订阅特定版本，不自动更新
            return None

        # 订阅最新版本，检查是否有更新
        latest = await self.get_latest_template(creator)
        if not latest:
            return None

        last_synced = datetime.fromisoformat(subscription["last_synced_at"])
        latest_updated = datetime.fromisoformat(latest["updated_at"])

        if latest_updated > last_synced:
            # 有更新，更新 last_synced_at
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE user_template_subscriptions
                    SET last_synced_at = NOW()
                    WHERE user_id = $1 AND creator = $2
                    """,
                    user_id, creator
                )
            return latest

        return None
