"""
Prompt Storage Service for LightRAG

Provides PostgreSQL-based storage for prompt templates, versions, and user configurations.
"""

from __future__ import annotations
from typing import Any, Optional, List, Dict
from datetime import datetime
import json
import asyncpg
from lightrag.utils import logger


class PromptStorageService:
    """Service for managing prompt templates and versions in PostgreSQL."""

    def __init__(self, connection_string: str):
        """Initialize the prompt storage service.

        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool."""
        self.pool = await asyncpg.create_pool(self.connection_string)
        logger.info("Prompt storage service initialized")

    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Prompt storage service closed")

    async def get_system_prompts(self) -> Dict[str, Any]:
        """Get system default prompts.

        Returns:
            Dictionary of system prompts
        """
        from lightrag.prompt import PROMPTS
        return PROMPTS.copy()

    async def create_template(
        self,
        name: str,
        content: Dict[str, str],
        created_by: str,
        description: Optional[str] = None,
        is_template: bool = False,
        template_type: str = "user"
    ) -> int:
        """Create a new prompt template.

        Args:
            name: Template name
            content: Prompt content as JSON
            created_by: Username of creator
            description: Optional description
            is_template: Whether this is a reusable template
            template_type: Type of template (system/user/shared)

        Returns:
            Template ID
        """
        async with self.pool.acquire() as conn:
            template_id = await conn.fetchval(
                """
                INSERT INTO prompt_templates (name, description, type, content, created_by, is_template)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                name, description, template_type, json.dumps(content), created_by, is_template
            )

            # Create initial version
            await conn.execute(
                """
                INSERT INTO prompt_versions (template_id, content, created_by, comment)
                VALUES ($1, $2, $3, $4)
                """,
                template_id, json.dumps(content), created_by, "Initial version"
            )

            logger.info(f"Created prompt template: {name} (ID: {template_id})")
            return template_id

    async def update_template(
        self,
        template_id: int,
        content: Dict[str, str],
        updated_by: str,
        comment: Optional[str] = None
    ) -> int:
        """Update a prompt template and create a new version.

        Args:
            template_id: Template ID
            content: New prompt content
            updated_by: Username of updater
            comment: Optional version comment

        Returns:
            New version number
        """
        async with self.pool.acquire() as conn:
            # Update template
            await conn.execute(
                """
                UPDATE prompt_templates
                SET content = $1, updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(content), template_id
            )

            # Create new version
            version = await conn.fetchval(
                """
                INSERT INTO prompt_versions (template_id, content, created_by, comment)
                VALUES ($1, $2, $3, $4)
                RETURNING version
                """,
                template_id, json.dumps(content), updated_by, comment or "Updated"
            )

            logger.info(f"Updated template {template_id} to version {version}")
            return version

    async def get_template(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Get a prompt template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template data or None if not found
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, description, type, content, created_by,
                       created_at, updated_at, is_template, is_active
                FROM prompt_templates
                WHERE id = $1
                """,
                template_id
            )

            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "type": row["type"],
                    "content": json.loads(row["content"]),
                    "created_by": row["created_by"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                    "is_template": row["is_template"],
                    "is_active": row["is_active"]
                }
            return None

    async def list_templates(
        self,
        template_type: Optional[str] = None,
        is_active: bool = True
    ) -> List[Dict[str, Any]]:
        """List prompt templates.

        Args:
            template_type: Filter by type (system/user/shared)
            is_active: Filter by active status

        Returns:
            List of templates
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, name, description, type, created_by,
                       created_at, updated_at, is_template
                FROM prompt_templates
                WHERE is_active = $1
            """
            params = [is_active]

            if template_type:
                query += " AND type = $2"
                params.append(template_type)

            query += " ORDER BY created_at DESC"

            rows = await conn.fetch(query, *params)

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "type": row["type"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                    "is_template": row["is_template"]
                }
                for row in rows
            ]

    async def get_versions(self, template_id: int) -> List[Dict[str, Any]]:
        """Get version history for a template.

        Args:
            template_id: Template ID

        Returns:
            List of versions
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, version, content, created_at, created_by, comment
                FROM prompt_versions
                WHERE template_id = $1
                ORDER BY version DESC
                """,
                template_id
            )

            return [
                {
                    "id": row["id"],
                    "version": row["version"],
                    "content": json.loads(row["content"]),
                    "created_at": row["created_at"].isoformat(),
                    "created_by": row["created_by"],
                    "comment": row["comment"]
                }
                for row in rows
            ]

    async def rollback_to_version(
        self,
        template_id: int,
        version: int,
        rolled_back_by: str
    ) -> int:
        """Rollback template to a specific version.

        Args:
            template_id: Template ID
            version: Version number to rollback to
            rolled_back_by: Username performing rollback

        Returns:
            New version number
        """
        async with self.pool.acquire() as conn:
            # Get content from target version
            content = await conn.fetchval(
                """
                SELECT content
                FROM prompt_versions
                WHERE template_id = $1 AND version = $2
                """,
                template_id, version
            )

            if not content:
                raise ValueError(f"Version {version} not found for template {template_id}")

            # Update template and create new version
            await conn.execute(
                """
                UPDATE prompt_templates
                SET content = $1, updated_at = NOW()
                WHERE id = $2
                """,
                content, template_id
            )

            new_version = await conn.fetchval(
                """
                INSERT INTO prompt_versions (template_id, content, created_by, comment)
                VALUES ($1, $2, $3, $4)
                RETURNING version
                """,
                template_id, content, rolled_back_by, f"Rolled back to version {version}"
            )

            logger.info(f"Rolled back template {template_id} to version {version} (new version: {new_version})")
            return new_version

    async def set_user_config(self, user_id: str, template_id: int):
        """Set active template for a user.

        Args:
            user_id: User ID
            template_id: Template ID to activate
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_prompt_configs (user_id, template_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET template_id = $2, updated_at = NOW()
                """,
                user_id, template_id
            )
            logger.info(f"Set template {template_id} for user {user_id}")

    async def get_user_config(self, user_id: str) -> Optional[int]:
        """Get active template ID for a user.

        Args:
            user_id: User ID

        Returns:
            Template ID or None if not configured
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT template_id
                FROM user_prompt_configs
                WHERE user_id = $1
                """,
                user_id
            )

    async def get_user_prompts(self, user_id: str) -> Dict[str, Any]:
        """Get prompts for a user (user config or system default).

        Args:
            user_id: User ID

        Returns:
            Dictionary of prompts
        """
        template_id = await self.get_user_config(user_id)

        if template_id:
            template = await self.get_template(template_id)
            if template and template["is_active"]:
                return template["content"]

        # Fallback to system prompts
        return await self.get_system_prompts()

    async def delete_template(self, template_id: int):
        """Soft delete a template.

        Args:
            template_id: Template ID
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE prompt_templates
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = $1
                """,
                template_id
            )
            logger.info(f"Deleted template {template_id}")
