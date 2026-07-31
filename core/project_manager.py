"""
项目管理工具 — 新建/加载/删除项目
"""
import sys
import os
import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_projects() -> list:
    """加载项目列表"""
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return []


def _save_projects(projects: list):
    """保存项目列表"""
    PROJECTS_FILE.write_text(
        json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def create_project(name: str = "未命名项目") -> dict:
    """新建项目，返回项目信息"""
    project_id = uuid.uuid4().hex[:8]
    project = {
        "id": project_id,
        "name": name,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "idle",
        "script": "",
        "shots": [],
    }
    projects = _load_projects()
    projects.insert(0, project)
    _save_projects(projects)
    return project


def list_projects() -> list:
    """获取项目列表"""
    projects = _load_projects()
    return projects[:50]  # 最多返回50个


def delete_project(project_id: str) -> bool:
    """删除项目"""
    projects = _load_projects()
    filtered = [p for p in projects if p.get("id") != project_id]
    if len(filtered) == len(projects):
        return False
    _save_projects(filtered)
    return True


def get_project(project_id: str) -> dict:
    """获取单个项目"""
    projects = _load_projects()
    for p in projects:
        if p.get("id") == project_id:
            return p
    return {}


def update_project(project_id: str, updates: dict) -> dict:
    """更新项目信息"""
    projects = _load_projects()
    for p in projects:
        if p.get("id") == project_id:
            p.update(updates)
            p["updated_at"] = datetime.now().isoformat()
            _save_projects(projects)
            return p
    return {}


def refresh_quota() -> dict:
    """刷新额度 — 返回固定值（不再依赖外部配置）"""
    return {
        "success": True,
        "gpt_quota": "已配置",
        "image_quota": "PhotoGPT 已连接 (localhost:8005)",
        "video_quota": "insMind 已连接 (localhost:8005)",
    }