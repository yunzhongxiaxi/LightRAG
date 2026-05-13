"""
Prompt Management API Routes

Provides REST API endpoints for managing prompt templates, versions, and user configurations.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from lightrag.prompt_storage import PromptStorageService
from lightrag.api.auth import auth_handler


# Pydantic models for request/response
class PromptTemplateCreate(BaseModel):
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    content: Dict[str, str] = Field(..., description="Prompt content as key-value pairs")
    is_template: bool = Field(False, description="Whether this is a reusable template")
    type: str = Field("user", description="Template type: system/user/shared")


class PromptTemplateUpdate(BaseModel):
    content: Dict[str, str] = Field(..., description="Updated prompt content")
    comment: Optional[str] = Field(None, description="Version comment")


class PromptTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    type: str
    content: Dict[str, str]
    created_by: str
    created_at: str
    updated_at: str
    is_template: bool
    is_active: bool


class PromptVersionResponse(BaseModel):
    id: int
    version: int
    content: Dict[str, str]
    created_at: str
    created_by: str
    comment: Optional[str]


class UserConfigRequest(BaseModel):
    user_id: str
    template_id: int


class RollbackRequest(BaseModel):
    rolled_back_by: str


def create_prompt_routes(prompt_storage: PromptStorageService) -> APIRouter:
    """Create prompt management routes.

    Args:
        prompt_storage: Initialized PromptStorageService instance

    Returns:
        APIRouter with all prompt management endpoints
    """
    router = APIRouter(prefix="/api/prompts", tags=["prompts"])

    # Dependency for authentication
    def get_current_user(username: str = Depends(auth_handler.get_current_user)):
        return username

    @router.get("/system", response_model=Dict[str, Any])
    async def get_system_prompts():
        """Get system default prompts."""
        return await prompt_storage.get_system_prompts()

    @router.get("/templates", response_model=List[PromptTemplateResponse])
    async def list_templates(
        type: Optional[str] = None,
        is_active: bool = True,
        username: str = Depends(get_current_user)
    ):
        """List prompt templates.

        Args:
            type: Filter by type (system/user/shared)
            is_active: Filter by active status
        """
        templates = await prompt_storage.list_templates(
            template_type=type,
            is_active=is_active
        )
        return templates

    @router.get("/templates/{template_id}", response_model=PromptTemplateResponse)
    async def get_template(
        template_id: int,
        username: str = Depends(get_current_user)
    ):
        """Get a specific prompt template."""
        template = await prompt_storage.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template

    @router.post("/templates", response_model=Dict[str, int])
    async def create_template(
        template: PromptTemplateCreate,
        username: str = Depends(get_current_user)
    ):
        """Create a new prompt template."""
        try:
            template_id = await prompt_storage.create_template(
                name=template.name,
                content=template.content,
                created_by=username,
                description=template.description,
                is_template=template.is_template,
                template_type=template.type
            )
            return {"id": template_id}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.put("/templates/{template_id}", response_model=Dict[str, int])
    async def update_template(
        template_id: int,
        update: PromptTemplateUpdate,
        username: str = Depends(get_current_user)
    ):
        """Update a prompt template (creates new version automatically)."""
        try:
            version = await prompt_storage.update_template(
                template_id=template_id,
                content=update.content,
                updated_by=username,
                comment=update.comment
            )
            return {"version": version}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.delete("/templates/{template_id}")
    async def delete_template(
        template_id: int,
        username: str = Depends(get_current_user)
    ):
        """Soft delete a prompt template."""
        try:
            await prompt_storage.delete_template(template_id)
            return {"status": "success", "message": "Template deleted"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/templates/{template_id}/versions", response_model=List[PromptVersionResponse])
    async def get_versions(
        template_id: int,
        username: str = Depends(get_current_user)
    ):
        """Get version history for a template."""
        versions = await prompt_storage.get_versions(template_id)
        return versions

    @router.post("/templates/{template_id}/rollback/{version}", response_model=Dict[str, int])
    async def rollback_version(
        template_id: int,
        version: int,
        rollback: RollbackRequest,
        username: str = Depends(get_current_user)
    ):
        """Rollback template to a specific version."""
        try:
            new_version = await prompt_storage.rollback_to_version(
                template_id=template_id,
                version=version,
                rolled_back_by=rollback.rolled_back_by or username
            )
            return {"new_version": new_version}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/user/{user_id}", response_model=Dict[str, Any])
    async def get_user_prompts(
        user_id: str,
        username: str = Depends(get_current_user)
    ):
        """Get prompts for a user (user config or system default)."""
        prompts = await prompt_storage.get_user_prompts(user_id)
        return prompts

    @router.post("/user/activate")
    async def activate_user_config(
        config: UserConfigRequest,
        username: str = Depends(get_current_user)
    ):
        """Activate a template for a user."""
        try:
            await prompt_storage.set_user_config(
                user_id=config.user_id,
                template_id=config.template_id
            )
            return {"status": "success", "message": "Template activated"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/user/{user_id}/config", response_model=Dict[str, Optional[int]])
    async def get_user_config(
        user_id: str,
        username: str = Depends(get_current_user)
    ):
        """Get active template ID for a user."""
        template_id = await prompt_storage.get_user_config(user_id)
        return {"template_id": template_id}

    return router
