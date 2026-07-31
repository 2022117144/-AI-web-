"""
配置读写接口
- GET  /api/config — 返回所有配置项
- PUT  /api/config — 更新配置项

从 zc_backend/llm.py 读取 LLM 配置。
"""
import sys
import os
import copy

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from zc_backend import llm as llm_mod

router = APIRouter(prefix="/api", tags=["config"])


class ConfigUpdate(BaseModel):
    """配置更新请求体"""
    updates: Dict[str, Any] = Field(
        ...,
        description="要更新的配置项键值对字典",
        example={"base_url": "https://api.openai.com/v1", "model": "gpt-4"}
    )


@router.get("/config")
async def get_config():
    """
    返回所有配置项。
    从 zc_backend/llm.py 读取 LLM 配置。
    """
    config = llm_mod.get_config()
    status = llm_mod.get_status()
    return {
        "code": 200,
        "message": "success",
        "data": {
            **config,
            "status": status,
        }
    }


@router.put("/config")
async def update_config(body: ConfigUpdate):
    """
    更新配置项。
    更新 zc_backend/llm.py 的配置。
    """
    updates = body.updates
    config = llm_mod.get_config()
    updated = []
    not_found = []

    for key, value in updates.items():
        if key in config:
            config[key] = value
            updated.append(key)
        else:
            not_found.append(key)

    if updated:
        llm_mod.save_config(config)

    return {
        "code": 200,
        "message": "配置更新成功",
        "updated": updated,
        "not_found": not_found
    }