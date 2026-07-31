"""
智创工具 — 场景管理系统
====================
场景 CRUD，支持多项目隔离。
每个项目可定义多个场景（名称/风格/参考图）。
数据存储在 ./data/project_content/ 目录下，每个项目一个 JSON 文件。
"""

import json, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

SCENES_DIR = Path(__file__).parent / "data" / "project_content"

def _project_path(project_id: str) -> Path:
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    return SCENES_DIR / project_id / "scenes.json"

def _load(project_id: str) -> List[Dict[str, Any]]:
    p = _project_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save(project_id: str, data: List[Dict[str, Any]]):
    _project_path(project_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_scenes(project_id: str) -> List[Dict[str, Any]]:
    """列出项目的所有场景"""
    return _load(project_id)


def create_scene(project_id: str, scene: Dict[str, Any]) -> Dict[str, Any]:
    """添加场景"""
    scenes = _load(project_id)
    scene_id = scene.get("id", f"scene_{uuid.uuid4().hex[:12]}")
    entry = {
        "id": scene_id,
        "name": scene.get("name", "新场景"),
        "style": scene.get("style", ""),
        "description": scene.get("description", ""),
        "uploaded_image": scene.get("uploaded_image", ""),
        "generated_image": scene.get("generated_image", ""),
        "created_at": datetime.now().isoformat(),
    }
    scenes.append(entry)
    _save(project_id, scenes)
    return entry


def update_scene(project_id: str, scene_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """修改场景"""
    scenes = _load(project_id)
    for s in scenes:
        if s["id"] == scene_id:
            for key in ("name", "style", "description", "uploaded_image", "generated_image"):
                if key in updates:
                    s[key] = updates[key]
            s["updated_at"] = datetime.now().isoformat()
            _save(project_id, scenes)
            return s
    return None


def delete_scene(project_id: str, scene_id: str) -> bool:
    """删除场景"""
    scenes = _load(project_id)
    new_scenes = [s for s in scenes if s["id"] != scene_id]
    if len(new_scenes) == len(scenes):
        return False
    _save(project_id, new_scenes)
    return True