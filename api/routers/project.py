"""
项目管理路由 — 新建/加载/删除项目
"""
import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 将项目根目录加入路径
PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJ_ROOT not in sys.path:
    sys.path.insert(0, PROJ_ROOT)

from core.project_manager import create_project, list_projects, delete_project, get_project, update_project, refresh_quota

router = APIRouter(prefix="/api/project", tags=["project"])


class CreateRequest(BaseModel):
    name: str = Field(default="未命名项目", description="项目名称")


class UpdateRequest(BaseModel):
    updates: dict = Field(..., description="要更新的字段")


@router.post("/create")
async def api_create_project(req: CreateRequest):
    """新建项目"""
    try:
        project = create_project(req.name)
        return {"code": 200, "data": project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def api_list_projects():
    """获取项目列表"""
    try:
        projects = list_projects()
        return {"code": 200, "data": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get")
async def api_get_project(project_id: str):
    """获取单个项目"""
    try:
        project = get_project(project_id)
        return {"code": 200, "data": project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def api_delete_project(project_id: str):
    """删除项目"""
    try:
        success = delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"code": 200, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update")
async def api_update_project(project_id: str, req: UpdateRequest):
    """更新项目信息"""
    try:
        project = update_project(project_id, req.updates)
        return {"code": 200, "data": project}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quota")
async def api_refresh_quota():
    """刷新额度"""
    try:
        result = refresh_quota()
        return {"code": 200, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))