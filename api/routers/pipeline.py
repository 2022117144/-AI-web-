"""
流水线路由 — 执行创作流水线
"""
import sys
import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from zc_backend import pipeline as pipeline_mod

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class PipelineRunRequest(BaseModel):
    script_text: str = Field(default="", description="文案内容")
    config: dict = Field(default={}, description="流水线配置")


@router.post("/run")
async def run_pipeline(req: PipelineRunRequest):
    """执行流水线"""
    try:
        run = pipeline_mod.PipelineRun()
        config = req.config or {}
        if req.script_text and "script_text" not in config.get("storyboard_prompts", {}):
            if "storyboard_prompts" not in config:
                config["storyboard_prompts"] = {}
            config["storyboard_prompts"]["script_text"] = req.script_text
        run.init_steps(config)
        result = run.run_sync({})
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/steps")
async def list_pipeline_steps():
    """列出流水线步骤"""
    steps = []
    for s in pipeline_mod.PIPELINE_STEPS:
        steps.append({
            "name": s["name"],
            "label": s["label"],
            "description": s["description"],
            "optional": s.get("optional", False),
        })
    return {"code": 200, "data": {"steps": steps}}


@router.get("/runs")
async def list_pipeline_runs():
    """列出流水线执行记录"""
    try:
        runs = pipeline_mod.load_runs()
        return {"code": 200, "data": runs}
    except Exception as e:
        return {"code": 200, "data": []}