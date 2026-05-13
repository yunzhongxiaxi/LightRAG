# Prompt 管理系统实现文档

## 概述

为 LightRAG 实现一个完整的 Prompt 管理系统，支持：
- 系统 Prompt（硬编码）和用户 Prompt（数据库存储）
- 单个 Prompt 配置和模板批量配置
- 公开共享机制
- 自动版本管理和回退
- 独立的 React 管理界面

## 已完成的工作

### 1. 数据库 Schema
**文件**: `lightrag/migrations/001_create_prompt_tables.sql`

创建了三个核心表：
- `prompt_templates`: 存储 Prompt 模板
- `prompt_versions`: 存储版本历史（自动递增版本号）
- `user_prompt_configs`: 存储用户当前使用的模板

### 2. 存储服务
**文件**: `lightrag/prompt_storage.py`

实现了 `PromptStorageService` 类，提供：
- `create_template()`: 创建新模板
- `update_template()`: 更新模板（自动创建版本）
- `get_template()`: 获取模板
- `list_templates()`: 列出模板
- `get_versions()`: 获取版本历史
- `rollback_to_version()`: 回退到指定版本
- `set_user_config()`: 设置用户配置
- `get_user_prompts()`: 获取用户 Prompt（带回退到系统 Prompt）

## 待实现的工作

### 3. Backend API 端点

需要在 `lightrag/api/lightrag_server.py` 中添加以下端点：

```python
# Prompt 管理 API
GET    /api/prompts/system              # 获取系统默认 Prompt
GET    /api/prompts/templates           # 获取所有模板
GET    /api/prompts/templates/:id       # 获取单个模板
POST   /api/prompts/templates           # 创建新模板
PUT    /api/prompts/templates/:id       # 更新模板
DELETE /api/prompts/templates/:id       # 删除模板
GET    /api/prompts/templates/:id/versions  # 获取版本历史
POST   /api/prompts/templates/:id/rollback/:version  # 回退版本
GET    /api/prompts/user/:userId        # 获取用户配置
POST   /api/prompts/user/activate       # 激活用户配置
```

### 4. LightRAG 集成

修改 `lightrag/lightrag.py` 的初始化逻辑：

```python
class LightRAG:
    def __init__(self, ..., user_id: str = None):
        # 初始化 Prompt 存储服务
        if os.getenv("PROMPT_STORAGE_ENABLED") == "true":
            self.prompt_storage = PromptStorageService(
                connection_string=os.getenv("DATABASE_URL")
            )
            await self.prompt_storage.initialize()
            
            # 加载用户 Prompt（带回退）
            if user_id:
                self.prompts = await self.prompt_storage.get_user_prompts(user_id)
            else:
                self.prompts = PROMPTS
        else:
            self.prompts = PROMPTS
```

### 5. Frontend UI

创建独立的 Prompt 管理界面（React + TypeScript）：

**目录结构**:
```
lightrag_webui/src/pages/PromptManagement/
├── index.tsx                 # 主页面
├── PromptList.tsx           # Prompt 列表
├── PromptEditor.tsx         # Prompt 编辑器
├── TemplateSelector.tsx     # 模板选择器
├── VersionHistory.tsx       # 版本历史
└── components/
    ├── PromptCard.tsx       # Prompt 卡片
    ├── VersionDiff.tsx      # 版本对比
    └── PromptPreview.tsx    # 预览组件
```

**核心功能**:
1. **Prompt 列表页**: 展示系统/用户/共享 Prompt
2. **Prompt 编辑器**: 支持单个/批量编辑（Monaco Editor）
3. **模板选择器**: 快速应用预设模板
4. **版本历史**: 查看和回退版本（带 diff 对比）

### 6. 可配置的 Prompt 列表

从 `lightrag/prompt.py` 中提取的所有可配置 Prompt：

```json
{
  "entity_extraction_system_prompt": "...",
  "entity_extraction_user_prompt": "...",
  "entity_continue_extraction_user_prompt": "...",
  "entity_extraction_json_system_prompt": "...",
  "entity_extraction_json_user_prompt": "...",
  "entity_continue_extraction_json_user_prompt": "...",
  "summarize_entity_descriptions": "...",
  "rag_response": "...",
  "naive_rag_response": "...",
  "keywords_extraction": "...",
  "fail_response": "...",
  "kg_query_context": "...",
  "naive_query_context": "...",
  "default_entity_types_guidance": "...",
  "DEFAULT_TUPLE_DELIMITER": "<|#|>",
  "DEFAULT_COMPLETION_DELIMITER": "<|COMPLETE|>"
}
```

## 使用流程

### 管理员/用户使用流程

1. **访问 Prompt 管理界面**
   ```
   http://localhost:9621/prompts
   ```

2. **创建自定义 Prompt**
   - 选择"创建新模板"
   - 选择配置方式：
     - 单个 Prompt 配置：逐个编辑
     - 模板配置：一次性配置所有 Prompt
   - 编辑 Prompt 内容
   - 保存（自动创建版本 1）

3. **使用其他人的 Prompt**
   - 浏览"共享 Prompt"列表
   - 点击"使用此模板"
   - 可选：复制并修改

4. **版本管理**
   - 每次修改自动创建新版本
   - 查看版本历史
   - 对比版本差异
   - 一键回退到任意版本

5. **激活 Prompt**
   - 选择要使用的模板
   - 点击"激活"
   - 后续查询自动使用该 Prompt

### 开发者集成

```python
import asyncio
from lightrag import LightRAG

async def main():
    # 启用 Prompt 管理（需要设置环境变量）
    rag = LightRAG(
        working_dir="./storage",
        user_id="user123"  # 传入用户 ID
    )
    await rag.initialize_storages()
    
    # 自动加载用户配置的 Prompt
    # 如果用户未配置，自动回退到系统 Prompt
    result = await rag.aquery("Your question")
    
asyncio.run(main())
```

## 环境变量配置

在 `.env` 中添加：

```bash
# Prompt 管理系统
PROMPT_STORAGE_ENABLED=true
DATABASE_URL=postgresql://user:password@localhost:5432/lightrag

# 或使用现有的 PostgreSQL 配置
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DB=lightrag
# POSTGRES_USER=user
# POSTGRES_PASSWORD=password
```

## 数据库初始化

```bash
# 运行迁移脚本
psql -U user -d lightrag -f lightrag/migrations/001_create_prompt_tables.sql
```

## API 使用示例

### 创建模板

```bash
curl -X POST http://localhost:9621/api/prompts/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Legal Document Prompts",
    "description": "Optimized for legal/regulatory documents",
    "content": {
      "entity_extraction_system_prompt": "...",
      "rag_response": "..."
    },
    "created_by": "user123",
    "is_template": true
  }'
```

### 更新模板（自动创建版本）

```bash
curl -X PUT http://localhost:9621/api/prompts/templates/1 \
  -H "Content-Type: application/json" \
  -d '{
    "content": {
      "entity_extraction_system_prompt": "Updated prompt..."
    },
    "updated_by": "user123",
    "comment": "Improved entity extraction accuracy"
  }'
```

### 回退版本

```bash
curl -X POST http://localhost:9621/api/prompts/templates/1/rollback/2 \
  -H "Content-Type: application/json" \
  -d '{
    "rolled_back_by": "user123"
  }'
```

### 激活用户配置

```bash
curl -X POST http://localhost:9621/api/prompts/user/activate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "template_id": 1
  }'
```

## 下一步实现优先级

1. **Backend API** (高优先级)
   - 实现所有 REST 端点
   - 集成到现有的 FastAPI 服务器
   - 添加认证中间件

2. **LightRAG 集成** (高优先级)
   - 修改初始化逻辑
   - 实现 Prompt 加载机制
   - 添加回退逻辑

3. **Frontend UI** (中优先级)
   - 创建 React 组件
   - 实现编辑器（Monaco Editor）
   - 实现版本对比（diff 库）

4. **测试和文档** (中优先级)
   - 单元测试
   - 集成测试
   - 用户文档

## 技术栈

- **Backend**: FastAPI + asyncpg (PostgreSQL)
- **Frontend**: React 19 + TypeScript + Tailwind CSS
- **编辑器**: Monaco Editor (VS Code 编辑器)
- **Diff**: react-diff-viewer-continued
- **认证**: 现有的 AUTH_ACCOUNTS 机制

## 注意事项

1. **性能优化**: 使用连接池（asyncpg.Pool）
2. **安全性**: SQL 注入防护（参数化查询）
3. **并发控制**: 版本号自动递增（数据库触发器）
4. **数据一致性**: 事务保证
5. **缓存策略**: 可选的 Redis 缓存层

## 预期效果

- 用户可以快速创建和共享 Prompt
- 版本管理确保可以安全试验新 Prompt
- 模板功能减少配置工作量
- 独立界面不影响现有功能
