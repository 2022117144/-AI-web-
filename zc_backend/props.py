"""
智创工具 — 道具管理系统
====================
道具 CRUD，支持多项目隔离。
每个项目可定义多个道具（名称/风格/音色/三视图/参考图）。
数据存储在 ./data/project_content/ 目录下，每个项目一个 JSON 文件。
"""

import json, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

PROPS_DIR = Path(__file__).parent / "data" / "project_content"

def _project_path(project_id: str) -> Path:
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    return PROPS_DIR / project_id / "props.json"

def _load(project_id: str) -> List[Dict[str, Any]]:
    p = _project_path(project_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save(project_id: str, data: List[Dict[str, Any]]):
    p = _project_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_props(project_id: str) -> List[Dict[str, Any]]:
    """列出项目的所有道具"""
    return _load(project_id)


def create_prop(project_id: str, prop: Dict[str, Any]) -> Dict[str, Any]:
    """添加道具"""
    props = _load(project_id)
    prop_id = prop.get("id", f"prop_{uuid.uuid4().hex[:12]}")
    entry = {
        "id": prop_id,
        "name": prop.get("name", "新道具"),
        "style": prop.get("style", ""),
        "voice": prop.get("voice", {"gender": "男", "tone": "默认", "speed": "中"}),
        "reference_image": prop.get("reference_image", ""),
        "description": prop.get("description", ""),
        "created_at": datetime.now().isoformat(),
    }
    props.append(entry)
    _save(project_id, props)
    return entry


def update_prop(project_id: str, prop_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """修改道具"""
    props = _load(project_id)
    for p in props:
        if p["id"] == prop_id:
            for key in ("name", "style", "voice", "reference_image", "description", "three_view", "uploaded_image"):
                if key in updates:
                    p[key] = updates[key]
            p["updated_at"] = datetime.now().isoformat()
            _save(project_id, props)
            return p
    return None


def delete_prop(project_id: str, prop_id: str) -> bool:
    """删除道具"""
    props = _load(project_id)
    new_props = [p for p in props if p["id"] != prop_id]
    if len(new_props) == len(props):
        return False
    _save(project_id, new_props)
    return True