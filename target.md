## Refact: Enhance entity extraction stability

Breaking change proposal: replace `json_object` with Pydantic schema for entity extraction JSON mode, and completely remove `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES` in favor of prompt-template-based entity type guidance

> **All development must branch off from dev, with subsequent Pull Requests strictly targeted at the dev branch.**

## Background

LightRAG currently has two design issues in entity extraction that affect output stability:

1. **When `ENTITY_EXTRACTION_USE_JSON=true`, the OpenAI-compatible path still uses `response_format={"type": "json_object"}`**
   - This only constrains the model to return a JSON object at a high level.
   - It does not strongly constrain field names, field types, nesting, or required keys.
   - In practice, entity extraction output can still drift across models/providers and may require repair/parsing fallback.

2. **Entity type control is currently implemented through `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES`**
   - This mechanism only passes a flat list of type names to the LLM.
   - It does not communicate classification rules, boundary conditions, examples, or ambiguity handling.
   - As a result, entity type classification is unstable and difficult to control in domain-specific scenarios.

The current codebase still contains this design across multiple layers, including prompt templates, config loading, runtime addon params, and env examples.

## Problem

The existing design is not sufficient for stable entity extraction:

- `json_object` is too weak for robust structured extraction
- `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES` is too weak for stable classification
- backward-compatible support for the old entity type mechanism keeps the system tied to an inherently unstable control method

This means the system continues to expose a configuration path that is fundamentally not expressive enough to produce stable entity typing.

## Proposed Changes

### 1. When `ENTITY_EXTRACTION_USE_JSON=true`, use Pydantic schema-based structured output instead of `json_object`

Please replace the current `json_object`-based entity extraction structured output path with a **Pydantic schema-based structured output path** wherever provider support exists.

Suggested target schema:

```json
{
  "entities": [
    {
      "entity_name": "string",
      "entity_type": "string",
      "entity_description": "string"
    }
  ],
  "relationships": [
    {
      "source_entity": "string",
      "target_entity": "string",
      "relationship_keywords": "string",
      "relationship_description": "string"
    }
  ]
}
```

Suggested implementation direction:

- introduce dedicated Pydantic models for entity extraction result
- use the same structured-output approach already used for keyword extraction where applicable
- keep provider fallback behavior only for providers that truly cannot support schema-based parsing
- the default JSON extraction path should become **more strongly constrained by design**

### 2. Completely remove `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES` from the repository

This should be treated as a **breaking removal**, not a deprecation-with-compatibility path.

Please remove all references to:

- `ENTITY_TYPES`
- `DEFAULT_ENTITY_TYPES`

from the repository, including but not limited to:

- runtime config loading
- constants
- prompt rendering inputs
- addon params
- API config layer
- docs
- examples
- `env.example`
- any startup/status output that still presents entity types as an env-driven setting

The repository should no longer expose `ENTITY_TYPES` as a supported customization mechanism.

### 3. Replace entity type control with prompt-template-based guidance only

Instead of configuring entity types through env/config values, the entity typing behavior should be controlled **only through prompt template customization**.

Please introduce / standardize a dedicated prompt section such as:

```text
---Entity Types---
{entity_types_guidance}
```

This section should be the canonical mechanism for entity type guidance and should support rich instructions such as:

- type definitions
- classification principles
- positive / negative examples
- ambiguity handling rules
- fallback rules (e.g. when to use `Other`)

This guidance should be injected through the prompt/template system, similar in spirit to how examples are currently injected.

## Blocking Compatibility Policy

This request intentionally proposes a **blocking compatibility strategy**.

### Required behavior

- remove all repo-level support for `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES`
- if `ENTITY_TYPES` is still found at startup (for example from `.env` or environment variables), the program should **fail fast**
- the startup error message should clearly state that this mechanism has been removed and users must customize entity types by editing the prompt template instead

### Expected startup failure message behavior

At startup, if `ENTITY_TYPES` is detected, LightRAG should stop initialization and return a clear error similar to:

```text
ENTITY_TYPES has been removed and is no longer supported.
Please customize entity type guidance by editing the entity extraction prompt template (the `---Entity Types---` section) instead.
```

This should be a hard failure, not a warning.

## Why a Breaking Removal Is Preferred

Keeping backward compatibility for `ENTITY_TYPES` preserves a weak control mechanism that is itself the source of instability. 

A hard removal is preferable because it:

- **Laying the groundwork for customizable and interchangeable prompt templates in the next phase.**
- avoids users continuing to rely on an unstable interface
- simplifies the codebase
- makes prompt-template-based guidance the single source of truth

## Suggested Refactor Scope

Please update all code paths currently coupled to `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES`, including:

- `lightrag/constants.py`
  - remove `DEFAULT_ENTITY_TYPES`
- `lightrag/lightrag.py`
  - remove addon/config wiring that loads `ENTITY_TYPES`
  - add startup validation that fails if `ENTITY_TYPES` exists
- `lightrag/api/config.py`
  - remove `args.entity_types`
  - add equivalent startup validation in API/server config path
- `lightrag/operate.py`
  - stop reading entity type list from `global_config["addon_params"]`
  - switch to prompt-template guidance injection model
- `lightrag/prompt.py`
  - redesign prompts to use a dedicated `---Entity Types---` section
  - remove `<Entity_types>` session from user prompts
- `lightrag/llm/openai.py`
  - replace `json_object` entity extraction mode with schema-based structured output where supported
- `env.example`
  - remove `ENTITY_TYPES`
- related examples / README / README-zh / docs
  - remove all instructions that tell users to customize entity types through env/config
  - replace them with prompt-template customization guidance

## Technical Requirements

### Structured output

- [ ] when `ENTITY_EXTRACTION_USE_JSON=true`, prefer Pydantic schema-based structured output over plain `json_object`
- [ ] entity extraction output structure should be more strongly constrained and more stable
- [ ] downstream extraction pipeline should remain compatible with the normalized parsed structure

### Entity type configuration

- [ ] remove `ENTITY_TYPES` / `DEFAULT_ENTITY_TYPES` entirely from repo code and examples
- [ ] entity type guidance must come from prompt template content, not env list configuration
- [ ] prompts must contain a dedicated `---Entity Types---` section for injected guidance

### Startup validation

- [ ] if `ENTITY_TYPES` is present in environment variables or `.env`, initialization must fail immediately
- [ ] error message must clearly instruct users to customize the prompt template instead
- [ ] this should be a hard failure, not a warning or silent fallback

### Documentation

- [ ] remove all old docs/examples mentioning `ENTITY_TYPES`
- [ ] add migration guidance that explains prompt-template-based customization
- [ ] document the breaking nature of this change clearly

## Acceptance Criteria

- [ ] `json_object` is no longer the primary structured-output mechanism for entity extraction JSON mode
- [ ] `DEFAULT_ENTITY_TYPES` is removed from the repository
- [ ] `ENTITY_TYPES` is removed from the repository and `env.example`
- [ ] entity typing is controlled only through prompt-template guidance
- [ ] LightRAG fails fast at startup if `ENTITY_TYPES` is still configured
- [ ] startup error explicitly directs users to modify the prompt template instead
- [ ] related docs/examples are updated to reflect the breaking change
