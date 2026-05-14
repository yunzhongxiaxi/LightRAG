"""
Prompt Management API Routes - Redesigned

支持订阅机制、真实版本号、ETag 的 REST API。
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import hashlib
import json
from lightrag.prompt_storage import PromptStorageService
from lightrag.api.auth import auth_handler


# Pydantic models
class TemplateCreate(BaseModel):
    content: Dict[str, str] = Field(..., description="Prompt content (partial)")


class SubscribeRequest(BaseModel):
    creator: str = Field(..., description="Creator to subscribe to")
    version: Optional[int] = Field(None, description="Version to subscribe (None = latest)")
    is_auto_update: bool = Field(True, description="Auto update to latest")


def create_prompt_routes(prompt_storage: PromptStorageService) -> APIRouter:
    router = APIRouter(prefix="/api/prompts", tags=["prompts"])

    def get_current_user(username: str = Depends(auth_handler.get_current_user)):
        return username

    @router.get("/system")
    async def get_system_prompts():
        """获取系统默认 Prompt"""
        return await prompt_storage.get_system_prompts()

    @router.post("/{creator}/templates")
    async def create_template(
        creator: str,
        template: TemplateCreate,
        username: str = Depends(get_current_user)
    ):
        """创建新模板版本

        Returns:
            {"version": 新版本号}
        """
        if creator != username:
            raise HTTPException(403, "Can only create templates for yourself")

        version = await prompt_storage.create_template(creator, template.content)
        return {"version": version}

    @router.get("/{creator}/versions")
    async def list_versions(
        creator: str,
        username: str = Depends(get_current_user)
    ):
        """列出创建者的所有版本号（真实版本号，降序）"""
        versions = await prompt_storage.list_versions(creator)
        return {"versions": versions}

    @router.get("/{creator}/templates/{version}")
    async def get_template(
        creator: str,
        version: int,
        if_none_match: Optional[str] = Header(None),
        username: str = Depends(get_current_user)
    ):
        """获取特定版本的模板（支持 ETag）"""
        template = await prompt_storage.get_template(creator, version)
        if not template:
            raise HTTPException(404, "Template not found")

        if template["is_deleted"]:
            raise HTTPException(410, "Template version deleted")

        # 计算 ETag
        content_hash = hashlib.md5(
            f"{template['updated_at']}{json.dumps(template['content'])}".encode()
        ).hexdigest()
        etag = f'"{content_hash}"'

        # 检查 ETag
        if if_none_match == etag:
            return Response(status_code=304)

        return Response(
            content=json.dumps(template),
            media_type="application/json",
            headers={
                "ETag": etag,
                "Cache-Control": "no-cache"
            }
        )

    @router.get("/{creator}/templates/latest")
    async def get_latest_template(
        creator: str,
        if_none_match: Optional[str] = Header(None),
        username: str = Depends(get_current_user)
    ):
        """获取最新版本的模板（支持 ETag）"""
        template = await prompt_storage.get_latest_template(creator)
        if not template:
            raise HTTPException(404, "No templates found")

        # 计算 ETag
        content_hash = hashlib.md5(
            f"{template['updated_at']}{json.dumps(template['content'])}".encode()
        ).hexdigest()
        etag = f'"{content_hash}"'

        # 检查 ETag
        if if_none_match == etag:
            return Response(status_code=304)

        return Response(
            content=json.dumps(template),
            media_type="application/json",
            headers={
                "ETag": etag,
                "Cache-Control": "no-cache"
            }
        )

    @router.delete("/{creator}/templates/{version}")
    async def delete_template(
        creator: str,
        version: int,
        username: str = Depends(get_current_user)
    ):
        """软删除模板版本"""
        if creator != username:
            raise HTTPException(403, "Can only delete your own templates")

        await prompt_storage.soft_delete_template(creator, version)
        return {"status": "deleted"}

    @router.post("/subscriptions")
    async def subscribe(
        request: SubscribeRequest,
        username: str = Depends(get_current_user)
    ):
        """订阅模板"""
        await prompt_storage.subscribe(
            user_id=username,
            creator=request.creator,
            version=request.version,
            is_auto_update=request.is_auto_update
        )
        return {"status": "subscribed"}

    @router.delete("/subscriptions/{creator}")
    async def unsubscribe(
        creator: str,
        username: str = Depends(get_current_user)
    ):
        """取消订阅"""
        await prompt_storage.unsubscribe(username, creator)
        return {"status": "unsubscribed"}

    @router.get("/subscriptions/{creator}")
    async def get_subscription(
        creator: str,
        username: str = Depends(get_current_user)
    ):
        """获取订阅信息"""
        subscription = await prompt_storage.get_subscription(username, creator)
        if not subscription:
            raise HTTPException(404, "Not subscribed")
        return subscription

    @router.get("/subscriptions")
    async def list_subscriptions(
        username: str = Depends(get_current_user)
    ):
        """列出用户的所有订阅"""
        # TODO: 实现列出所有订阅
        return {"subscriptions": []}

    @router.get("/user/prompts")
    async def get_user_prompts(
        username: str = Depends(get_current_user)
    ):
        """获取用户当前使用的 Prompt（合并后）"""
        prompts = await prompt_storage.get_user_prompts(username)
        return prompts

    return router
