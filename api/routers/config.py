"""
配置读写接口
- GET  /api/config — 返回所有配置项
- PUT  /api/config — 更新配置项
"""
import sys
import os
import copy

# 将万象AI-2改 源码路径加入 sys.path
sys.path.insert(0, r'E:\万象AI-2改\src')

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

# 直接从 万象AI-2改 导入 A0_config 模块
from 任务运行文件 import A0_config

router = APIRouter(prefix="/api", tags=["config"])


class ConfigUpdate(BaseModel):
    """配置更新请求体"""
    updates: Dict[str, Any] = Field(
        ...,
        description="要更新的配置项键值对字典",
        example={"ChatGPT版本": "gpt-4", "GPT_Token": "sk-xxx"}
    )


@router.get("/config")
async def get_config():
    """
    返回所有配置项。
    直接从 A0_config.config 字典读取。
    """
    return {
        "code": 200,
        "message": "success",
        "data": A0_config.config
    }


@router.put("/config")
async def update_config(body: ConfigUpdate):
    """
    更新配置项。
    接受 JSON body 中的 {updates: {key: value, ...}}，
    更新 A0_config.config 并调用 修改配置() 保存到文件。
    """
    updated = []
    not_found = []

    for key, value in body.updates.items():
        if key in A0_config.config:
            A0_config.config[key] = value
            updated.append(key)
        else:
            not_found.append(key)

    # 保存到文件
    A0_config.修改配置()

    return {
        "code": 200,
        "message": "配置更新成功",
        "updated": updated,
        "not_found": not_found
    }