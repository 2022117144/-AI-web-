"""
智创工具 — 角色管理系统
====================
角色 CRUD，支持多项目隔离。
每个项目可定义多个角色（名称/风格/音色/参考图）。
数据存储在 ./data/characters/ 目录下。
"""

import json, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

CHARACTERS_DIR = Path(__file__).parent / "data" / "characters"

def _project_path(project_id: str) -> Path:
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    return CHARACTERS_DIR / f"{project_id}.json"

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


def list_characters(project_id: str) -> List[Dict[str, Any]]:
    """列出项目的所有角色"""
    return _load(project_id)


def create_character(project_id: str, character: Dict[str, Any]) -> Dict[str, Any]:
    """添加角色"""
    chars = _load(project_id)
    char_id = character.get("id", f"char_{uuid.uuid4().hex[:12]}")
    entry = {
        "id": char_id,
        "name": character.get("name", "新角色"),
        "style": character.get("style", ""),
        "voice": character.get("voice", {"gender": "男", "tone": "默认", "speed": "中"}),
        "reference_image": character.get("reference_image", ""),
        "description": character.get("description", ""),
        "created_at": datetime.now().isoformat(),
    }
    chars.append(entry)
    _save(project_id, chars)
    return entry


def update_character(project_id: str, char_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """修改角色"""
    chars = _load(project_id)
    for c in chars:
        if c["id"] == char_id:
            for key in ("name", "style", "voice", "reference_image", "description", "three_view", "uploaded_image"):
                if key in updates:
                    c[key] = updates[key]
            c["updated_at"] = datetime.now().isoformat()
            _save(project_id, chars)
            return c
    return None


def delete_character(project_id: str, char_id: str) -> bool:
    """删除角色"""
    chars = _load(project_id)
    new_chars = [c for c in chars if c["id"] != char_id]
    if len(new_chars) == len(chars):
        return False
    _save(project_id, new_chars)
    return True