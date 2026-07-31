"""
文案工具 — AI修改、保存文案、生成分镜
"""
import sys
import os
import json
from pathlib import Path

# 将 zc_backend 目录加入路径
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

from zc_backend import llm as llm_mod
from zc_backend import pipeline as pipeline_mod

# 数据目录
DATA_DIR = Path(__file__).parent / "data"
COPY_DIR = DATA_DIR / "copy"
COPY_DIR.mkdir(parents=True, exist_ok=True)


def modify_copy(text: str, instruction: str = "") -> str:
    """AI修改文案"""
    prompt = (
        f"原始文案：\n{text}\n\n修改要求："
        f"{instruction if instruction else '请优化这段文案，使其更通顺自然'}"
    )
    result = llm_mod.call_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一个文案编辑专家。",
        temperature=0.5,
        max_tokens=2048,
    )
    return result.strip() if result else ""


def save_copy(text: str, project_id: str = "") -> dict:
    """保存文案到文件"""
    if not text.strip():
        return {"success": False, "error": "文案内容为空", "path": ""}

    if project_id:
        save_path = COPY_DIR / f"{project_id}_script.txt"
    else:
        save_path = COPY_DIR / "current_script.txt"

    save_path.write_text(text, encoding="utf-8")
    return {"success": True, "path": str(save_path)}


def load_copy(project_id: str = "") -> str:
    """加载已保存的文案"""
    if project_id:
        path = COPY_DIR / f"{project_id}_script.txt"
    else:
        path = COPY_DIR / "current_script.txt"

    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate_storyboard(script_text: str, shot_count: int = 5) -> dict:
    """从文案生成分镜"""
    result = pipeline_mod._storyboard_prompts_handler(
        {}, {"script_text": script_text, "shot_count": shot_count}
    )
    return result


def generate_copy(topic: str, tone: str = "叙事") -> str:
    """AI生成文案"""
    tone_map = {
        "叙事": "自然流畅的旁白",
        "温暖": "温暖感人的语调",
        "幽默": "轻松幽默的风格",
        "科普": "通俗易懂的科普",
        "悬疑": "悬疑紧张的氛围",
    }
    system_prompt = (
        f"你是一个专业的短视频文案写手。"
        f"用{tone_map.get(tone, '自然流畅')}写一段30-60秒的短视频文案。"
    )
    result = llm_mod.call_llm(
        messages=[{"role": "user", "content": f"主题：{topic}\n请生成一段短视频文案。"}],
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=2048,
    )
    return result.strip() if result else ""