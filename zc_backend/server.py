"""
智创AI Tools Backend — 从项目文件提取的业务逻辑后端
独立部署，接入你自己的生成工具

启动: python server.py
数据目录: ./data/
工作流目录: ./workflows/
端口: 8765 (可通过 ZCTOOLS_PORT 环境变量设置)
"""
import json, os, uuid, sys, requests, threading
import json, os, uuid, sys, requests, threading, logging
logger = logging.getLogger("zc_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# 流水线引擎
import pipeline as pl

# LLM 客户端
import llm as llm_mod

# 外部 API 集成
import handlers as hd

# 系统提示词管理
import prompts as prompts_mod

# 角色管理
import characters as chars_mod
import scenes as scenes_mod
import props as props_mod

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
import uvicorn

# 反缓存头
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

# ============================================================
# 应用初始化
# ============================================================
app = FastAPI(title="智创工具", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册外部 API handler
pl.register_step_handler("photogpt_images", hd.photogpt_images_handler)
pl.register_step_handler("insmind_video", hd.insmind_video_handler)
pl.register_step_handler("bgm_send", hd.bgm_send_handler)

# 数据目录
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
WORKFLOWS_DIR = BASE_DIR / "workflows"
FRONTEND_DIR = BASE_DIR.parent / "web_frontend"
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

# 挂载前端静态文件
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR), html=False), name="frontend")

@app.get("/")
def serve_root():
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers=NO_CACHE_HEADERS)

@app.get("/css/{file}")
def serve_css(file: str):
    return FileResponse(str(FRONTEND_DIR / "css" / file), headers=NO_CACHE_HEADERS)

@app.get("/js/{file}")
def serve_js(file: str):
    return FileResponse(str(FRONTEND_DIR / "js" / file), headers=NO_CACHE_HEADERS)

@app.head("/css/{file}")
@app.head("/js/{file}")
async def head_static(file: str): pass



@app.get("/zc/")
def serve_zc_root():
    return FileResponse(str(FRONTEND_DIR / "zc_index.html"), headers=NO_CACHE_HEADERS)


@app.get("/zc/{rest:path}")
def serve_zc_static(rest: str):
    fp = FRONTEND_DIR / rest
    if fp.exists():
        return FileResponse(str(fp), headers=NO_CACHE_HEADERS)
    return FileResponse(str(FRONTEND_DIR / "zc_index.html"), headers=NO_CACHE_HEADERS)


@app.get("/zc/")
def serve_zc_root():
    return FileResponse(str(FRONTEND_DIR / "zc_index.html"), headers=NO_CACHE_HEADERS)


@app.get("/zc/{rest:path}")
def serve_zc_static(rest: str):
    fp = FRONTEND_DIR / rest
    if fp.exists():
        return FileResponse(str(fp), headers=NO_CACHE_HEADERS)
    return FileResponse(str(FRONTEND_DIR / "zc_index.html"), headers=NO_CACHE_HEADERS)
PROJECTS_FILE = DATA_DIR / "projects.json"
PROJECT_CONTENT_DIR = DATA_DIR / "project_content"
STYLES_FILE_INTERNAL = DATA_DIR / "builtin_styles.json"
STYLES_FILE_CUSTOM = DATA_DIR / "custom_styles.json"
PROMPT_TEMPLATES_FILE = DATA_DIR / "prompt_templates.json"

def load_json(path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return default if default is not None else {} if path.suffix == ".json" else {}
    return default() if callable(default) else (default if default is not None else ([] if "styles" in str(path).lower() else {}))

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# ============================================================
# 数据模型
# ============================================================
class ProjectContent(BaseModel):
    script_text: str = ""
    shots: list = []
    srt: list = []
    shot_data: dict = {}
    grid_size: int = 9


class Project(BaseModel):
    project_id: str = ""
    project_name: str = ""
    created_time: str = ""
    last_opened_time: str = ""
    video_path: str = ""
    project_path: str = ""

    original_story_desc: str = ""
    original_voiceover_text: str = ""
    original_full_script: str = ""
    rewritten_voiceover_text: str = ""
    rewritten_story_desc: str = ""
    rewritten_full_script: str = ""

    advanced_original_story_desc: str = ""
    advanced_original_voiceover_text: str = ""
    advanced_original_full_script: str = ""

    original_visual_style_anchor: str = ""
    advanced_original_visual_style_anchor: str = ""
    original_style_preset_id: str = ""
    advanced_original_style_preset_id: str = ""
    original_style_anchor_mode: str = ""
    advanced_original_style_anchor_mode: str = "preset"

    original_character_extract: str = ""
    original_character_roles: List = []
    original_character_global_style: str = ""
    original_user_character_style_anchor: str = ""
    advanced_original_character_extract: str = ""
    advanced_original_character_roles: List = []
    advanced_original_character_global_style: str = ""

    original_storyboard_shots: List = []
    original_video_shots: List = []
    advanced_original_storyboard_shots: List = []
    advanced_original_video_shots: List = []

    scenes: List = []
    keyframes: Dict = {}
    prompts: Dict = {}
    videos: Dict = {}
    pending_tasks: Dict = {}
    video_task_ids: Dict = {}

    original_tts_audio: str = ""
    original_tts_srt: str = ""
    original_tts_voice_display: str = ""
    original_tts_voice_name: str = ""

    original_cover_path: str = ""
    original_cover_titles: str = ""
    original_merged_video: str = ""

    video_aspect_ratio: str = "16:9"
    original_video_flow_type: str = "narration"
    advanced_original_video_flow_type: str = "narration"
    advanced_original_dialogue_language: str = "zh"
    original_studio_video_mode: str = "16:9"
    project_type: str = "advanced_original"


class StylePreset(BaseModel):
    id: str = ""
    name: str = ""
    video_anchor: str = ""
    character_anchor: str = ""

class PromptEnhanceRequest(BaseModel):
    prompt: str
    style_preset_id: str = ""
    mode: str = "t2v"
    image_description: str = ""

class PromptEnhanceResponse(BaseModel):
    enhanced_prompt: str
    style_anchor: str = ""
    character_anchor: str = ""

class ScriptGenerateRequest(BaseModel):
    topic: str
    style: str = ""
    tone: str = "叙事"
    duration_seconds: int = 30
    word_count: int = 200
    system_prompt_id: str = ""
    custom_prompt: str = ""
    project_id: str = ""

class GenerationRequest(BaseModel):
    prompt: str
    enhanced_prompt: str = ""
    task_type: str = "t2v"
    params: Dict[str, Any] = {}

class GenerationResponse(BaseModel):
    task_id: str
    status: str = "queued"
    created_at: str = ""

# ============================================================
# API: 项目
# ============================================================
@app.get("/api/projects")
def list_projects():
    return list(load_json(PROJECTS_FILE, {}).values())

@app.post("/api/projects")
def create_project(project: Project):
    projects = load_json(PROJECTS_FILE, {})
    if project.project_name and project.project_name.strip() and project.project_name.strip() != "未命名":
        for p in projects.values():
            if p.get("project_name") == project.project_name.strip():
                raise HTTPException(400, f"项目名称「{project.project_name}」已存在，请使用其他名称")
    if not project.project_id or not project.project_id.strip():
        project.project_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    project.project_id = project.project_id.strip()
    if not project.created_time:
        project.created_time = datetime.now().isoformat()
    project.last_opened_time = datetime.now().isoformat()
    projects[project.project_id] = project.model_dump()
    save_json(PROJECTS_FILE, projects)
    # 创建项目文件夹结构
    proj_dir = PROJECT_CONTENT_DIR / project.project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["文案", "视频提示词", "图片", "视频"]:
        (proj_dir / sub).mkdir(parents=True, exist_ok=True)
    return project

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    projects = load_json(PROJECTS_FILE, {})
    if project_id not in projects:
        raise HTTPException(404, "Project not found")
    return projects[project_id]

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request):
    projects = load_json(PROJECTS_FILE, {})
    if project_id not in projects:
        raise HTTPException(404, "项目不存在")
    body = await request.json()
    # 检查同名
    if "project_name" in body and body["project_name"].strip():
        new_name = body["project_name"].strip()
        for pid, p in projects.items():
            if pid != project_id and p.get("project_name") == new_name:
                raise HTTPException(400, f"项目名称「{new_name}」已存在，请使用其他名称")
        body["project_name"] = new_name
    existing = projects[project_id]
    for k, v in body.items():
        if k in existing:
            existing[k] = v
    existing["last_opened_time"] = datetime.now().isoformat()
    projects[project_id] = existing
    save_json(PROJECTS_FILE, projects)
    return existing

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    if not project_id or not project_id.strip():
        raise HTTPException(400, "Project ID is empty")
    project_id = project_id.strip()
    projects = load_json(PROJECTS_FILE, {})
    if project_id not in projects:
        raise HTTPException(404, "Project not found")
    del projects[project_id]
    save_json(PROJECTS_FILE, projects)
    # 删除项目文件夹
    proj_dir = PROJECT_CONTENT_DIR / project_id
    if proj_dir.exists():
        import shutil
        shutil.rmtree(str(proj_dir))
    return {"status": "deleted"}

# ============================================================
# API: 项目文件服务
# ============================================================
@app.get("/api/project-files/{project_id}/{subdir}/{filename}")
def serve_project_file(project_id: str, subdir: str, filename: str):
    import mimetypes
    file_path = PROJECT_CONTENT_DIR / project_id / subdir / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    mime, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=mime or "application/octet-stream")


@app.put("/api/projects/{project_id}/content")
async def save_project_content(project_id: str, request: Request):
    """保存项目内容到文件夹结构，覆盖前自动备份旧版本为 _prev"""
    body = await request.json()
    proj_dir = PROJECT_CONTENT_DIR / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["文案", "视频提示词", "图片", "视频"]:
        (proj_dir / sub).mkdir(parents=True, exist_ok=True)
    # 备份旧文件：覆盖前把当前文件重命名为 _prev
    def _backup_if_exists(path):
        if path.exists():
            prev = path.with_name(path.stem + "_prev" + path.suffix)
            if prev.exists():
                prev.unlink()
            path.rename(prev)
    # 保存文案
    if "script_text" in body:
        _backup_if_exists(proj_dir / "文案" / "script.txt")
        (proj_dir / "文案" / "script.txt").write_text(body.get("script_text", ""), encoding="utf-8")
    # 保存分镜/提示词
    if "shots" in body:
        _backup_if_exists(proj_dir / "视频提示词" / "shots.json")
        save_json(proj_dir / "视频提示词" / "shots.json", body["shots"])
    if "srt" in body:
        _backup_if_exists(proj_dir / "视频提示词" / "srt.json")
        save_json(proj_dir / "视频提示词" / "srt.json", body["srt"])
    if "shot_data" in body:
        _backup_if_exists(proj_dir / "视频提示词" / "shot_data.json")
        save_json(proj_dir / "视频提示词" / "shot_data.json", body["shot_data"])
    # 保存完整 content.json 作为备份
    _backup_if_exists(proj_dir / "content.json")
    save_json(proj_dir / "content.json", body)
    return {"status": "saved", "project_dir": str(proj_dir)}

@app.get("/api/projects/{project_id}/content")
def get_project_content(project_id: str):
    """读取项目内容（从文件夹结构）"""
    proj_dir = PROJECT_CONTENT_DIR / project_id
    data = {}
    # 读取文案
    script_file = proj_dir / "文案" / "script.txt"
    if script_file.exists():
        data["script_text"] = script_file.read_text(encoding="utf-8")
    # 读取分镜
    shots_file = proj_dir / "视频提示词" / "shots.json"
    if shots_file.exists():
        data["shots"] = load_json(shots_file, [])
    srt_file = proj_dir / "视频提示词" / "srt.json"
    if srt_file.exists():
        data["srt"] = load_json(srt_file, [])
    shot_data_file = proj_dir / "视频提示词" / "shot_data.json"
    if shot_data_file.exists():
        data["shot_data"] = load_json(shot_data_file, {})
    return data


@app.get("/api/projects/{project_id}/pipeline-status")
def get_pipeline_status(project_id: str):
    """检查项目各流水线步骤的完成状态，用于前端自动判断从哪步开始"""
    proj_dir = PROJECT_CONTENT_DIR / project_id
    if not proj_dir.exists():
        return {"steps": [False] * 6}

    steps = [False] * 6

    # 步骤1: 文案 — 检查 文案/script.txt 是否有内容
    script_file = proj_dir / "文案" / "script.txt"
    if script_file.exists() and script_file.read_text(encoding="utf-8").strip():
        steps[0] = True

    # 步骤2: 分镜+字幕+音频 — 检查 视频提示词/shots.json 和 srt.json
    shots_file = proj_dir / "视频提示词" / "shots.json"
    srt_file = proj_dir / "视频提示词" / "srt.json"
    if shots_file.exists() and srt_file.exists():
        shots = load_json(shots_file, [])
        srt = load_json(srt_file, [])
        if shots and srt:
            steps[1] = True

    # 步骤3: 图片 — 检查图片数量是否满足分镜需求
    # 规则：第一个分镜需要首帧+尾帧（2张），其余分镜各1张尾帧，合计 shots_count + 1 张
    # 排除 _prev 备份文件
    img_dir = proj_dir / "图片"
    if img_dir.exists():
        imgs = [f for f in img_dir.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and not f.name.endswith("_prev.png") and not f.name.endswith("_prev.jpg") and not f.name.endswith("_prev.jpeg") and not f.name.endswith("_prev.webp")]
        # 获取分镜数量
        shots_file = proj_dir / "视频提示词" / "shots.json"
        shot_count = 0
        if shots_file.exists():
            shots = load_json(shots_file, [])
            shot_count = len(shots)
        # 所需图片数 = 分镜数 + 1（首帧1张 + 每分镜1张尾帧，没有分镜时不算完成）
        needed = shot_count + 1
        if shot_count > 0 and len(imgs) >= needed:
            steps[2] = True

# 步骤4: 视频 — 检查视频数量是否等于分镜数（排除 _prev 备份文件）
    video_dir = proj_dir / "视频"
    if video_dir.exists():
        videos = [f for f in video_dir.iterdir() if f.suffix.lower() in (".mp4", ".webm", ".mov") and not f.name.endswith("_prev.mp4") and not f.name.endswith("_prev.webm") and not f.name.endswith("_prev.mov")]
    # 获取分镜数量
        shots_file = proj_dir / "视频提示词" / "shots.json"
        shot_count = 0
        if shots_file.exists():
            shots = load_json(shots_file, [])
            shot_count = len(shots)
        # 所需视频数 = 分镜数（没有分镜时不算完成）
        if shot_count > 0 and len(videos) >= shot_count:
            steps[3] = True

    # 步骤5: 合成 — 检查是否有 merged_video.mp4
    merged = proj_dir / "视频" / "merged_video.mp4"
    if merged.exists():
        steps[4] = True

    # 步骤6: 发送 — 暂无可检查项，默认未完成
    steps[5] = False

    return {"steps": steps, "project_id": project_id}


# ============================================================
# API: 下载媒体文件到本地项目文件夹
    # ============================================================

@app.post("/api/projects/{project_id}/download-media")
def download_project_media(project_id: str, req: dict = Body(...)):
    """下载 URL 到项目本地文件夹，返回本地路径"""
    url = req.get("url", "")
    media_type = req.get("type", "image")
    if not url:
        raise HTTPException(400, "请提供 URL")
    proj_dir = PROJECT_CONTENT_DIR / project_id
    sub_dir = proj_dir / ("图片" if media_type == "image" else "视频")
    sub_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
    if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov"):
        ext = ".jpg" if media_type == "image" else ".mp4"
    filename = hashlib.md5(url.encode()).hexdigest()[:16] + ext
    local_path = sub_dir / filename
    if local_path.exists():
        return {"local_path": str(local_path), "url": url, "cached": True}
    try:
        import requests
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return {"local_path": str(local_path), "url": url, "cached": False}
    except Exception as e:
        raise HTTPException(500, f"下载失败: {e}")


# ============================================================
# API: 风格预设
# ============================================================
@app.get("/api/styles")
def list_styles():
    builtin = load_json(STYLES_FILE_INTERNAL, [])
    custom = load_json(STYLES_FILE_CUSTOM, [])
    return builtin + custom

@app.post("/api/styles")
def create_style(style: StylePreset):
    styles = load_json(STYLES_FILE_CUSTOM, [])
    if not style.id:
        style.id = f"user_{uuid.uuid4().hex[:16]}"
    styles.append(style.model_dump())
    save_json(STYLES_FILE_CUSTOM, styles)
    return style

@app.delete("/api/styles/{style_id}")
def delete_style(style_id: str):
    styles = load_json(STYLES_FILE_CUSTOM, [])
    styles = [s for s in styles if s.get("id") != style_id]
    save_json(STYLES_FILE_CUSTOM, styles)
    return {"status": "deleted"}

# ============================================================
# API: 工作流管理
# ============================================================
@app.get("/api/workflows")
def list_workflows():
    result = []
    for f in sorted(WORKFLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({"name": f.stem, "nodes": len(data)})
        except:
            pass
    return result

@app.get("/api/workflows/{name}")
def get_workflow(name: str):
    path = WORKFLOWS_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(404, "Workflow not found")
    return json.loads(path.read_text(encoding="utf-8"))

# ============================================================
# API: 提示词增强
# ============================================================
@app.post("/api/prompt/enhance", response_model=PromptEnhanceResponse)
def enhance_prompt(req: PromptEnhanceRequest):
    style_anchor = ""
    character_anchor = ""

    if req.style_preset_id:
        builtin = load_json(STYLES_FILE_INTERNAL, [])
        custom = load_json(STYLES_FILE_CUSTOM, [])
        for s in builtin + custom:
            if s.get("id") == req.style_preset_id:
                style_anchor = s.get("video_anchor", "")
                character_anchor = s.get("character_anchor", "")
                break

    parts = []
    if style_anchor:
        parts.append(f"Style: {style_anchor}")
    if req.mode == "i2v" and req.image_description:
        parts.append(f"Input Image: {req.image_description}")
    parts.append(f"Action/Scene: {req.prompt}")
    if character_anchor:
        parts.append(f"Character: {character_anchor}")

    enhanced = ". ".join(parts)

    return PromptEnhanceResponse(
        enhanced_prompt=enhanced,
        style_anchor=style_anchor,
        character_anchor=character_anchor,
    )


# ============================================================
# API: 文案生成（AI）
# ============================================================

@app.post("/api/script/generate")
def generate_script(req: ScriptGenerateRequest):
    """用 LLM 根据主题生成完整文案脚本"""
    if not req.topic:
        raise HTTPException(400, "请提供主题")

    system_prompt = prompts_mod.fill_template(req.system_prompt_id, req.custom_prompt)
    if not system_prompt:
        system_prompt = "你是一个专业的短视频文案写手。根据用户提供的主题，生成一段自然流畅的旁白文案。"
    user_prompt = (
                    f"主题：{req.topic}\n"
                    f"风格：{req.style or '通用'}\n"
                    f"语调：{req.tone}\n"
                    f"目标时长：约{req.duration_seconds}秒\n"
                    f"目标字数：约{req.word_count}字\n\n"
                f"要求：\n"
                            f"1. 生成一段短视频旁白/文案，直接输出文案文本，不要额外说明\n"
                            f"2. 文案需要通顺自然，适合配音旁白\n"
                            f"3. 文案必须接近{req.word_count}字左右，不足或超出太多都不合格\n"
                            f"4. 不要输出 JSON 格式，只输出纯文本文案\n"
            )

    result = llm_mod.call_llm(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=8192,
    )

    if result:
        return {"script": result.strip(), "generated": True}
    return {"script": "", "generated": False, "error": "LLM 生成失败，请检查配置"}


@app.post("/api/script/modify")
def modify_script(req: ScriptGenerateRequest):
    """用 LLM 根据用户要求修改已有文案"""
    current_script = req.topic or ""
    if not current_script:
        raise HTTPException(400, "请先生成文案")
    if not req.custom_prompt:
        raise HTTPException(400, "请输入修改要求")

    system_prompt = "你是一个专业的短视频文案编辑。根据用户的要求修改已有文案，保留原意的同时满足修改需求。"
    user_prompt = (
        f"当前文案：\n{current_script}\n\n"
        f"修改要求：{req.custom_prompt}\n\n"
        f"要求：\n"
        f"1. 根据修改要求改写文案\n"
        f"2. 直接输出修改后的完整文案，不要加说明\n"
        f"3. 保持口语化、有画面感"
    )

    result = llm_mod.call_llm(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=8192,
    )

    if result:
        return {"script": result.strip(), "modified": True}
    return {"script": "", "modified": False, "error": "LLM 修改失败，请检查配置"}


# ============================================================
# API: 异步 LLM 任务队列
# ============================================================

import uuid
import threading

_task_store = {}
_task_lock = threading.Lock()

def _run_llm_task(task_id: str, task_type: str, params: dict):
    """后台执行 LLM 任务，完成后存入 _task_store"""
    try:
        if task_type == "analyze":
            topic = params["topic"]
            project_id = params.get("project_id", "")
            style_anchor = params.get("style_anchor", "")
            char_text = ""
            scene_text = ""
            if project_id:
                try:
                    import characters as char_mod
                    import scenes as scene_mod
                    chars = char_mod.list_characters(project_id)
                    scenes = scene_mod.list_scenes(project_id)
                    if chars:
                        lines = []
                        for c in chars:
                            desc = c.get("description", "") or c.get("style", "") or ""
                            lines.append(f"- {c.get('name', '未命名')}" + (f"（{desc}）" if desc else ""))
                        char_text = "当前项目已定义的角色：\n" + "\n".join(lines) + "\n"
                    if scenes:
                        lines = []
                        for s in scenes:
                            desc = s.get("description", "") or s.get("style", "") or ""
                            lines.append(f"- {s.get('name', '未命名')}" + (f"：{desc}" if desc else ""))
                        scene_text = "当前项目已定义的场景：\n" + "\n".join(lines) + "\n"
                except:
                    pass
            extra_context = ""
            if char_text or scene_text:
                extra_context = f"\n【项目设定参考】\n{char_text}{scene_text}请根据以上角色和场景设定生成分镜，prompt 中引用角色名称和场景描述。\n\n"
            if style_anchor:
                extra_context += f"\n【视觉风格要求】\n{style_anchor}\n请严格按照以上视觉风格描述生成每个镜头的画面。\n\n"
            system_prompt = "你是一个专业的视频分镜师和字幕师。根据文案生成分镜表和SRT字幕。\n首帧提示词和尾帧提示词不能与画面提示词重复，要有起始/结束的区分感。"
            user_prompt = (
                f"文案内容：\n{topic}\n\n"
                f"{extra_context}"
                f"请生成以下内容，以 JSON 格式输出：\n"
                f'{{\n'
                f'  "shots": [\n'
                f'    {{\n'
                f'      "index": 1,\n'
                f'      "scene": "场景描述（中文，20-40字）",\n'
                f'      "prompt": "画面提示词（英文，适合AI出图，描述该镜头最核心的画面）",\n'
                f'      "first_frame_prompt": "起始画面（英文，强调镜头开始时的初始构图、角色入场动作、场景建立状态，与prompt有区分度，例如：Character enters from left, sunlight streams through window, wide establishing shot）",\n'
                f'      "last_frame_prompt": "结束画面（英文，强调镜头结束时的位置变化、情绪收束、过渡到下一镜头的状态，与prompt有区分度，例如：Character now center frame, turns toward camera, soft smile, scene fades to warm bokeh）",\n'
                f'      "duration": 3,\n'
                f'      "framing": "景别（可选：特写/近景/中景/全景）",\n'
                f'      "motion": "运镜（可选：固定/推轨/后拉/摇镜）",\n'
                f'      "lighting": "光照（可选：暖调/冷白/高对比/柔和）",\n'
                f'      "voiceover": "该镜头的旁白文本",\n'
                f'      "video_prompt": "完整英文prompt"\n'
                f'    }}\n'
                f'  ],\n'
                f'  "srt": [\n'
                f'    {{\n'
                f'      "index": 1,\n'
                f'      "start": "00:00:00,000",\n'
                f'      "end": "00:00:03,000",\n'
                f'      "text": "对应字幕文本"\n'
                f'    }}\n'
                f'  ]\n'
                f'}}\n\n'
                f"要求：\n"
                f"1. shots 数组每个元素对应一个镜头，prompt 用英文\n"
                f"2. framing/motion/lighting/voiceover/video_prompt 是可选的，尽量根据剧情推断\n"
                f"3. srt 数组每个元素对应一条字幕，时间轴与 shots 对齐\n"
                f"4. 只输出 JSON，不要额外说明"
            )
            result = llm_mod.call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=8192,
            )
            if result:
                import re
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        shots = parsed.get("shots", [])
                        srt = parsed.get("srt", [])
                        for shot in shots:
                            shot.setdefault("framing", "")
                            shot.setdefault("motion", "")
                            shot.setdefault("lighting", "")
                            shot.setdefault("voiceover", "")
                            shot.setdefault("video_prompt", "")
                            shot.setdefault("first_frame_prompt", shot.get("prompt", ""))
                            shot.setdefault("last_frame_prompt", shot.get("prompt", ""))
                            shot.setdefault("first_frame_prompt", shot.get("prompt", ""))
                            shot.setdefault("last_frame_prompt", shot.get("prompt", ""))
                        with _task_lock:
                            _task_store[task_id] = {"status": "completed", "result": {"shots": shots, "srt": srt, "generated": True}}
                        logger.info(f"[LLM任务] analyze 完成: {task_id}, shots={len(shots)}")
                        return
                    except:
                        pass
                with _task_lock:
                    _task_store[task_id] = {"status": "completed", "result": {"shots": [], "srt": [], "generated": True, "raw": result}}
                logger.info(f"[LLM任务] analyze 完成(原始): {task_id}, raw_len={len(result) if result else 0}")
                return
            with _task_lock:
                _task_store[task_id] = {"status": "error", "error": "LLM 分析失败"}
            logger.info(f"[LLM任务] analyze 失败: {task_id}")

        elif task_type == "generate":
            topic = params["topic"]
            tone = params.get("tone", "叙事")
            style = params.get("style", "")
            duration = params.get("duration_seconds", 30)
            word_count = params.get("word_count", 200)
            prompt_id = params.get("system_prompt_id", "")
            custom_prompt = params.get("custom_prompt", "")
            system_prompt = prompts_mod.fill_template(prompt_id, custom_prompt)
            if not system_prompt:
                system_prompt = "你是一个专业的短视频文案写手。根据用户提供的主题，生成一段自然流畅的旁白文案。"
            user_prompt = (
                f"主题：{topic}\n"
                f"风格：{style or '通用'}\n"
                f"语调：{tone}\n"
                f"目标时长：约{duration}秒\n"
                f"目标字数：约{word_count}字\n\n"
                f"要求：\n"
                f"1. 生成一段短视频旁白/文案，直接输出文案文本，不要额外说明\n"
                f"2. 文案需要通顺自然，适合配音旁白\n"
                f"3. 文案必须接近{word_count}字左右，不足或超出太多都不合格\n"
                f"4. 不要输出 JSON 格式，只输出纯文本文案\n"
            )
            result = llm_mod.call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=8192,
            )
            if result:
                with _task_lock:
                    _task_store[task_id] = {"status": "completed", "result": {"script": result.strip(), "generated": True}}
                logger.info(f"[LLM任务] generate 完成: {task_id}, len={len(result.strip())}")
            else:
                with _task_lock:
                    _task_store[task_id] = {"status": "error", "error": "LLM 生成失败，请检查配置"}
                logger.info(f"[LLM任务] generate 失败: {task_id}")

        elif task_type == "modify":
            current_script = params["topic"]
            instruction = params.get("custom_prompt", "")
            system_prompt = "你是一个专业的短视频文案编辑。根据用户的要求修改已有文案，保留原意的同时满足修改需求。"
            user_prompt = (
                f"当前文案：\n{current_script}\n\n"
                f"修改要求：{instruction}\n\n"
                f"要求：\n"
                f"1. 根据修改要求改写文案\n"
                f"2. 直接输出修改后的完整文案，不要加说明\n"
                f"3. 保持口语化、有画面感"
            )
            result = llm_mod.call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=8192,
            )
            if result:
                with _task_lock:
                    _task_store[task_id] = {"status": "completed", "result": {"script": result.strip(), "modified": True}}
                logger.info(f"[LLM任务] modify 完成: {task_id}, len={len(result.strip())}")
            else:
                with _task_lock:
                    _task_store[task_id] = {"status": "error", "error": "LLM 修改失败，请检查配置"}
                logger.info(f"[LLM任务] modify 失败: {task_id}")

    except Exception as e:
        with _task_lock:
            _task_store[task_id] = {"status": "error", "error": str(e)}
        logger.info(f"[LLM任务] 异常: {task_id}, {e}")


@app.post("/api/script/task")
def create_llm_task(req: dict = Body(...)):
    """创建异步 LLM 任务"""
    task_type = req.get("type")
    params = req.get("params", {})
    if not task_type:
        raise HTTPException(400, "请指定任务类型")
    task_id = str(uuid.uuid4())[:12]
    with _task_lock:
        _task_store[task_id] = {"status": "running", "result": None}
    thread = threading.Thread(target=_run_llm_task, args=(task_id, task_type, params), daemon=True)
    thread.start()
    return {"task_id": task_id, "status": "running"}


@app.get("/api/script/task/{task_id}")
def get_llm_task_status(task_id: str):
    """查询异步 LLM 任务状态"""
    with _task_lock:
        task = _task_store.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


# ============================================================
# API: 系统提示词管理
# ============================================================

class PromptCreateRequest(BaseModel):
    name: str
    content: str

@app.get("/api/prompts")
def list_prompts():
    """列出所有系统提示词（内置+自定义）"""
    return prompts_mod.get_all()

@app.post("/api/prompts")
def create_prompt(req: PromptCreateRequest):
    """创建自定义提示词"""
    if not req.name or not req.content:
        raise HTTPException(400, "名称和内容不能为空")
    return prompts_mod.create(req.name, req.content)

@app.put("/api/prompts/{prompt_id}")
def update_prompt(prompt_id: str, req: PromptCreateRequest):
    """修改任意提示词（内置或自定义）"""
    if not req.name or not req.content:
        raise HTTPException(400, "名称和内容不能为空")
    ok = prompts_mod.update(prompt_id, req.name, req.content)
    if not ok:
        raise HTTPException(404, "提示词不存在")
    return {"status": "updated"}

@app.delete("/api/prompts/{prompt_id}")
def delete_prompt(prompt_id: str):
    """删除提示词（内置或自定义）"""
    ok = prompts_mod.delete(prompt_id)
    if not ok:
        raise HTTPException(404, "提示词不存在")
    return {"status": "deleted"}


# ============================================================
# API: 角色管理
# ============================================================

class CharacterRequest(BaseModel):
    project_id: str = ""
    char_id: str = ""
    name: str = ""
    style: str = ""
    voice: Dict[str, str] = {"gender": "男", "tone": "默认", "speed": "中"}
    reference_image: str = ""
    description: str = ""
    three_view: dict = {}
    uploaded_image: str = ""

class PropRequest(BaseModel):
    project_id: str = ""
    prop_id: str = ""
    name: str = ""
    style: str = ""
    voice: dict = {}
    reference_image: str = ""
    description: str = ""
    three_view: dict = {}
    uploaded_image: str = ""

@app.get("/api/characters")
def list_characters(project_id: str = ""):
    """列出项目角色"""
    if not project_id:
        return []
    return chars_mod.list_characters(project_id)

@app.post("/api/characters")
def create_character(req: CharacterRequest):
    """添加角色"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    return chars_mod.create_character(req.project_id, {
        "name": req.name,
        "style": req.style,
        "voice": req.voice,
        "reference_image": req.reference_image,
        "description": req.description,
    })

@app.put("/api/characters/{char_id}")
def update_character(char_id: str, req: CharacterRequest):
    """修改角色"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    updates = {
        "name": req.name,
        "style": req.style,
        "voice": req.voice,
        "reference_image": req.reference_image,
        "description": req.description,
        "three_view": req.three_view,
        "uploaded_image": req.uploaded_image,
    }
    # 如果上传了 data URL 图片，保存到项目文件夹
    if req.uploaded_image and req.uploaded_image.startswith("data:"):
        local_path = _save_data_url_to_project(req.project_id, "图片", req.uploaded_image, f"char_{char_id}")
        if local_path:
            rel_path = os.path.relpath(local_path, str(PROJECT_CONTENT_DIR))
            rel_parts = rel_path.replace("\\", "/").split("/")
            updates["uploaded_image"] = f"/api/project-files/{rel_parts[0]}/{rel_parts[1]}/{rel_parts[2]}"
    result = chars_mod.update_character(req.project_id, char_id, updates)
    if not result:
        raise HTTPException(404, "角色不存在")
    return result

@app.delete("/api/characters/{char_id}")
def delete_character(char_id: str, project_id: str = ""):
    """删除角色"""
    if not project_id:
        raise HTTPException(400, "请指定项目")
    ok = chars_mod.delete_character(project_id, char_id)
    if not ok:
        raise HTTPException(404, "角色不存在")
    return {"status": "deleted"}


# ============================================================
# API: 场景管理
# ============================================================

class SceneRequest(BaseModel):
    project_id: str = ""
    scene_id: str = ""
    name: str = ""
    style: str = ""
    description: str = ""
    uploaded_image: str = ""
    generated_image: str = ""


@app.get("/api/scenes")
def list_scenes(project_id: str = ""):
    """列出项目场景"""
    if not project_id:
        return []
    return scenes_mod.list_scenes(project_id)


@app.post("/api/scenes")
def create_scene(req: SceneRequest):
    """添加场景"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    return scenes_mod.create_scene(req.project_id, {
        "name": req.name or "新场景",
        "style": req.style,
        "description": req.description,
        "uploaded_image": req.uploaded_image,
        "generated_image": req.generated_image,
    })


@app.put("/api/scenes/{scene_id}")
def update_scene(scene_id: str, req: SceneRequest):
    """修改场景"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    updates = {
        "name": req.name,
        "style": req.style,
        "description": req.description,
        "uploaded_image": req.uploaded_image,
        "generated_image": req.generated_image,
    }
    # 如果上传了 data URL 图片，保存到项目文件夹
    if req.uploaded_image and req.uploaded_image.startswith("data:"):
        local_path = _save_data_url_to_project(req.project_id, "图片", req.uploaded_image, f"scene_{scene_id}")
        if local_path:
            rel_path = os.path.relpath(local_path, str(PROJECT_CONTENT_DIR))
            rel_parts = rel_path.replace("\\", "/").split("/")
            updates["uploaded_image"] = f"/api/project-files/{rel_parts[0]}/{rel_parts[1]}/{rel_parts[2]}"
    result = scenes_mod.update_scene(req.project_id, scene_id, updates)
    if not result:
        raise HTTPException(404, "场景不存在")
    return result


@app.delete("/api/scenes/{scene_id}")
def delete_scene(scene_id: str, project_id: str = ""):
    """删除场景"""
    if not project_id:
        raise HTTPException(400, "请指定项目")
    ok = scenes_mod.delete_scene(project_id, scene_id)
    if not ok:
        raise HTTPException(404, "场景不存在")
    return {"status": "deleted"}


# API: 道具管理
@app.get("/api/props")
def list_props(project_id: str = ""):
    """列出项目道具"""
    if not project_id:
        return []
    return props_mod.list_props(project_id)

@app.post("/api/props")
def create_prop(req: PropRequest):
    """添加道具"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    return props_mod.create_prop(req.project_id, {
        "name": req.name,
        "style": req.style,
        "voice": req.voice,
        "reference_image": req.reference_image,
        "description": req.description,
    })

@app.put("/api/props/{prop_id}")
def update_prop(prop_id: str, req: PropRequest):
    """修改道具"""
    if not req.project_id:
        raise HTTPException(400, "请指定项目")
    updates = {
        "name": req.name,
        "style": req.style,
        "voice": req.voice,
        "reference_image": req.reference_image,
        "description": req.description,
        "three_view": req.three_view,
        "uploaded_image": req.uploaded_image,
    }
    result = props_mod.update_prop(req.project_id, prop_id, updates)
    if not result:
        raise HTTPException(404, "道具不存在")
    return result

@app.delete("/api/props/{prop_id}")
def delete_prop(prop_id: str, project_id: str = ""):
    """删除道具"""
    if not project_id:
        raise HTTPException(400, "请指定项目")
    ok = props_mod.delete_prop(project_id, prop_id)
    if not ok:
        raise HTTPException(404, "道具不存在")
    return {"status": "deleted"}


        # ============================================================
        # API: 生成任务（框架，接入你自己的工具）
        # ============================================================
GENERATION_HANDLER = None

def register_generation_handler(handler):
    global GENERATION_HANDLER
    GENERATION_HANDLER = handler

@app.post("/api/generate", response_model=GenerationResponse)
def generate(req: GenerationRequest):
    task_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat()

    if GENERATION_HANDLER:
        try:
            result = GENERATION_HANDLER(
                task_type=req.task_type,
                prompt=req.prompt,
                enhanced_prompt=req.enhanced_prompt,
                params=req.params,
            )
            return GenerationResponse(task_id=task_id, status="completed", created_at=created_at)
        except Exception as e:
            return GenerationResponse(task_id=task_id, status=f"error: {e}", created_at=created_at)

    return GenerationResponse(task_id=task_id, status="queued (no handler)", created_at=created_at)

@app.get("/api/generate/{task_id}/status")
def task_status(task_id: str):
    return {"task_id": task_id, "status": "unknown"}

# ============================================================
# API: 系统
# ============================================================
@app.get("/api/health")
def health():
    builtin = load_json(STYLES_FILE_INTERNAL, [])
    return {
        "status": "ok",
        "version": "1.0.0",
        "builtin_styles": len(builtin),
        "data_dir": str(DATA_DIR),
    }

@app.get("/api/info")
def info():
    builtin = load_json(STYLES_FILE_INTERNAL, [])
    return {
        "extracted_from": "智创AI高级版3.6",
        "components": {
            "workflows": ["default_t2v (text-to-video)", "default_i2v (image-to-video)"],
            "style_presets": [s["name"] for s in builtin],
            "pipeline": [
                "story/script input",
                "prompt enhancement (Gemma style)",
                "style anchor application",
                "character preset application",
                "TTS voice generation",
                "ComfyUI video generation",
                "output assembly",
            ],
        },
    }


# ============================================================
# API: LLM 配置（中转站设置）
# ============================================================

class LLMConfigRequest(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""

@app.get("/api/llm/config")
def get_llm_config():
    return llm_mod.get_status()

@app.post("/api/llm/config")
def set_llm_config(req: LLMConfigRequest):
    if req.base_url:
        llm_mod.save_config({"base_url": req.base_url, "model": req.model or "deepseek-v4-flash:cloud"})
    if req.api_key:
        llm_mod.save_api_key(req.api_key)
    return llm_mod.get_status()

@app.post("/api/llm/test")
def test_llm_connection(req: LLMConfigRequest = None):
    """测试 LLM 连通性。只验证 base_url 可达 + api_key 有效，不依赖模型。"""
    if req and req.base_url and req.api_key:
        base_url = req.base_url.rstrip("/")
        api_key = req.api_key
    else:
        config = llm_mod.get_config()
        base_url = config.get("base_url", "").rstrip("/")
        api_key = llm_mod.get_api_key()
    if not base_url or not api_key:
        return {"ok": False, "reply": "请填写 API 地址和 Key"}
    try:
        resp = requests.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
            proxies={"http": "", "https": ""},
        )
        # 能收到响应就算连通（即使是 403/401 也说明通了）
        if resp.status_code < 500:
            return {"ok": True, "reply": f"连通 ✅ (响应码 {resp.status_code})"}
        return {"ok": False, "reply": f"服务端错误 (响应码 {resp.status_code})"}
    except requests.ConnectionError:
        return {"ok": False, "reply": "无法连接，请检查地址和网络/代理"}
    except requests.Timeout:
        return {"ok": False, "reply": "连接超时，请检查地址和网络/代理"}
    except Exception as e:
        return {"ok": False, "reply": f"连接失败: {str(e)[:60]}"}


@app.get("/api/llm/keys")
def list_llm_keys():
    """列出所有 API Key（不暴露完整 key）"""
    keys = llm_mod.get_all_key_previews()
    # 标记当前活跃的 key
    if keys:
        keys[0]["is_active"] = True
    return {"keys": keys, "count": len(keys)}


class LLMKeyRequest(BaseModel):
    api_key: str
    label: str = ""
    model: str = ""


@app.post("/api/llm/keys")
def add_llm_key(req: LLMKeyRequest):
    """添加一个 API Key"""
    if not req.api_key:
        raise HTTPException(400, "API Key 不能为空")
    entry = llm_mod.add_key(req.api_key, req.label)
    # 保存关联的模型名
    if req.model:
        keys = llm_mod.get_keys()
        for k in keys:
            if k["id"] == entry["id"]:
                k["model"] = req.model
                break
        llm_mod.save_keys(keys)
    return {"success": True, "entry": {
        "id": entry["id"],
        "label": entry["label"],
        "model": req.model or "",
        "preview": entry["key"][:12] + "...",
    }}


@app.delete("/api/llm/keys/{key_id}")
def delete_llm_key(key_id: str):
    """删除一个 API Key"""
    ok = llm_mod.delete_key(key_id)
    if not ok:
        raise HTTPException(404, "Key not found")
    return {"success": True}


@app.post("/api/llm/keys/{key_id}/activate")
def activate_llm_key(key_id: str):
    """激活指定 key 为当前使用"""
    keys = llm_mod.get_keys()
    found = False
    for k in keys:
        if k["id"] == key_id:
            found = True
            break
    if not found:
        raise HTTPException(404, "Key not found")
    # 把该 key 移到列表第一个位置
    keys = [k for k in keys if k["id"] != key_id]
    # 重新加载获取完整 key 数据
    keys = llm_mod.get_keys()
    target = None
    for k in keys:
        if k["id"] == key_id:
            target = k
            break
    if target:
        keys.remove(target)
        keys.insert(0, target)
        llm_mod.save_keys(keys)
    return {"success": True}


class LLMRenameRequest(BaseModel):
    label: str


@app.post("/api/llm/keys/{key_id}/rename")
def rename_llm_key(key_id: str, req: LLMRenameRequest):
    """重命名 API Key"""
    if not req.label:
        raise HTTPException(400, "名称不能为空")
    ok = llm_mod.rename_key(key_id, req.label)
    if not ok:
        raise HTTPException(404, "Key not found")
    return {"success": True}



@app.get("/api/llm/models")
def list_llm_models(base_url: str = "", api_key: str = ""):
    """从配置的中转站获取可用模型列表。商汤返回已知模型。"""
    config = llm_mod.get_config()
    use_url = base_url or config.get("base_url", "")
    use_key = api_key or llm_mod.get_api_key()
    if not use_url or not use_key:
        return {"models": []}

    try:
        resp = requests.get(
            f"{use_url}/models",
            headers={"Authorization": f"Bearer {use_key}"},
            timeout=10,
            proxies={"http": "", "https": ""},
        )
        if resp.status_code != 200:
            return {"models": []}
        data = resp.json()
        models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        return {"models": models}
        return {"models": models}
    except Exception as e:
        print(f"Fetch models error: {e}")
        return {"models": []}

        # ============================================================
# ============================================================
# API: 流水线 (Pipeline)
class PipelineRunRequest(BaseModel):
    project_id: str = ""
    config: Dict[str, Any] = {}

class PipelineHandlerStatus(BaseModel):
    step_name: str
    label: str
    registered: bool
    stub: bool

@app.get("/api/pipeline/steps")
def list_pipeline_steps():
    return [{
        "name": s["name"],
        "label": s["label"],
        "description": s["description"],
        "optional": s.get("optional", False),
        "stub": s.get("stub", False),
        "inputs": s.get("inputs", []),
    } for s in pl.PIPELINE_STEPS]

@app.get("/api/pipeline/handlers")
def list_pipeline_handlers():
    from pipeline import _handlers
    return [PipelineHandlerStatus(
        step_name=s["name"],
        label=s["label"],
        registered=s["name"] in _handlers,
        stub=not (s["name"] in _handlers or s["name"] in {"script", "storyboard_with_audio", "ffmpeg_merge"}),
    ) for s in pl.PIPELINE_STEPS]

@app.post("/api/pipeline/run")
def run_pipeline(req: PipelineRunRequest):
    project_data = {}
    if req.project_id:
        projects = load_json(PROJECTS_FILE, {})
        project_data = projects.get(req.project_id, {})

    run = pl.PipelineRun(project_id=req.project_id)
    run.init_steps(req.config)
    pl.save_run(run)

    # 后台线程执行，API 立即返回
    def _run_bg():
        try:
            run.run_sync(project_data)
        except Exception as e:
            run.status = "error"
            run.error = str(e)
            pl.save_run(run)

    t = threading.Thread(target=_run_bg, daemon=True)
    t.start()

    return run.to_dict()

@app.post("/api/pipeline/runs/{run_id}/step")
def update_pipeline_step(run_id: str, req: dict = Body(...)):
    runs = load_json(pl.RUNS_FILE, {})
    if run_id in runs:
        r = runs[run_id]
        step_idx = req.get("step_index", -1)
        status = req.get("status", "pending")
        steps = r.get("steps", [])
        if status == "completed":
            for i in range(step_idx + 1):
                if i < len(steps):
                    steps[i]["status"] = "completed"
        if 0 <= step_idx < len(steps):
            steps[step_idx]["status"] = status
        r["steps"] = steps
        r["status"] = req.get("run_status", r.get("status", "pending"))
        save_json(pl.RUNS_FILE, runs)
        # 同步到内存字典（将 dict 转回 PipelineRun 对象）
        _run = pl.PipelineRun(project_id=r.get("project_id", ""))
        _run.run_id = run_id
        _run.steps = r.get("steps", [])
        _run.status = r.get("status", "idle")
        pl._runs[run_id] = _run
        return {"status": "ok", "run": r}
    # 创建新运行记录
    run = pl.PipelineRun(project_id=req.get("project_id", ""))
    run.init_steps({})
    run.run_id = run_id
    step_idx = req.get("step_index", -1)
    status = req.get("status", "pending")
    if status == "completed":
        for i in range(step_idx + 1):
            if i < len(run.steps):
                run.steps[i]["status"] = "completed"
    if 0 <= step_idx < len(run.steps):
        run.steps[step_idx]["status"] = status
    # 同步到内存和文件
    pl.save_run(run)
    return {"status": "ok", "run": run.to_dict()}

@app.get("/api/pipeline/runs")
def list_pipeline_runs(project_id: str = ""):
    if project_id:
        runs = pl.get_project_runs(project_id)
    else:
        runs = list(pl._runs.values())
    runs.sort(key=lambda r: r.created_at, reverse=True)
    return [r.to_dict() for r in runs[:20]]

@app.get("/api/pipeline/runs/{run_id}")
def get_pipeline_run(run_id: str):
    run = pl.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run.to_dict()

@app.post("/api/pipeline/runs/{run_id}/retry")
def retry_pipeline_run(run_id: str):
    run = pl.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "error":
        raise HTTPException(400, "Only failed runs can be retried")
    project_data = {}
    if run.project_id:
        projects = load_json(PROJECTS_FILE, {})
        project_data = projects.get(run.project_id, {})
    for step in run.steps:
        if step["status"] == "error":
            step["status"] = "pending"
            step["error"] = ""
            step["output"] = {}
    result = run.run_sync(project_data)
    pl.save_run(run)
    return result

@app.post("/api/pipeline/runs/{run_id}/cancel")
def cancel_pipeline_run(run_id: str):
    """取消正在执行的流水线"""
    run = pl.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "running":
        return {"status": "already_stopped", "message": "流水线已结束"}
    run.cancel_requested = True
    pl.save_run(run)
    return {"status": "cancelling"}


# ============================================================
# API: 单帧/视频生成（前端调用）
# ============================================================

class FrameGenRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    mode: str = "first_frame"
    project_id: str = ""
    shot_idx: int = 0
    reference_images: list = []  # 参考图 URL 列表，用于角色/场景一致性

class VideoGenRequest(BaseModel):
    prompt: str = ""
    first_frame: str = ""
    last_frame: str = ""
    model: str = "Pixverse-V6.0"
    ratio: str = "16:9"
    resolution: str = "360p"
    duration: int = 5
    project_id: str = ""
    shot_idx: int = 0

import httpx as _httpx

@app.get("/api/image-proxy")
def image_proxy(url: str):
    """代理加载图片（绕过CORS/CDN限制），带本地磁盘缓存"""
    if not url:
        raise HTTPException(400, "url 参数不能为空")

    # 先尝试从 relay 加载（走 photogpt 的代理）
    try:
        relay_url = f"http://localhost:8005/api/photogpt/image-proxy?url={url}"
        resp = _httpx.get(relay_url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/png")
            return Response(content=resp.content, media_type=ct)
    except:
        pass

    # 直接下载（带本地缓存）
    import hashlib
    cache_dir = Path("D:/万象AI改/zc_backend/data/project_content/_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    ext = ".png"
    for e in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
        if e in url.lower():
            ext = e
            break
    cache_file = cache_dir / f"{url_hash}{ext}"

    if cache_file.exists():
        ct = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/webp' if ext == '.webp' else 'image/gif'
        return Response(content=cache_file.read_bytes(), media_type=ct)
    
    proxy_url = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY') or ''
    proxies = {'all://': proxy_url} if proxy_url else None
    try:
        with _httpx.Client(proxies=proxies, timeout=30, follow_redirects=True) as client:
            resp = client.get(url,
                              headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://photogpt.io/'})
        if resp.status_code == 200:
            cache_file.write_bytes(resp.content)
            ct = resp.headers.get('content-type', 'image/png')
            return Response(content=resp.content, media_type=ct)
    except Exception as e:
        print(f"[image-proxy] httpx 下载失败: {e}")
        try:
            import requests as _requests
            proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
            proxies_dict = {"https": proxy_url, "http": proxy_url} if proxy_url else None
            r = _requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://photogpt.io/"}, proxies=proxies_dict)
            if r.status_code == 200:
                cache_file.write_bytes(r.content)
                ct = r.headers.get("content-type", "image/png")
                return Response(content=r.content, media_type=ct)
        except Exception as e2:
            print(f"[image-proxy] requests 也失败: {e2}")
        raise HTTPException(502, f"图片加载失败: {e}")

    raise HTTPException(404, "图片不存在或已失效")


@app.get("/api/video-proxy")
def video_proxy(url: str):
    """代理加载视频（带本地磁盘缓存）"""
    if not url:
        raise HTTPException(400, "url 参数不能为空")
    import hashlib
    cache_dir = Path("D:/万象AI改/zc_backend/data/project_content/_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    ext = ".mp4"
    for e in [".mp4", ".webm", ".mov"]:
        if e in url.lower():
            ext = e
            break
    cache_file = cache_dir / f"{url_hash}{ext}"
    if cache_file.exists():
        ct = "image/png" if ext == ".png" else "image/jpeg" if ext in (".jpg", ".jpeg") else "image/webp" if ext == ".webp" else "image/gif"
        return Response(content=cache_file.read_bytes(), media_type=ct)

    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    proxies = {"all://": proxy_url} if proxy_url else None
    try:
        with _httpx.Client(proxies=proxies, timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            resp = client.get(url,
                              headers={"User-Agent": "Mozilla/5.0", "Referer": "https://photogpt.io/"})
        if resp.status_code == 200:
            cache_file.write_bytes(resp.content)
            ct = resp.headers.get("content-type", "image/png")
            return Response(content=resp.content, media_type=ct)
    except Exception as e:
        print(f"[video-proxy] 下载失败: {e}")
    raise HTTPException(502, "视频加载失败")


@app.post("/api/generate-frame")
async def generate_frame(req: FrameGenRequest):
    """单张分镜图片生成 — 调 photogpt（异步，不阻塞其他请求）"""
    if not req.prompt:
        raise HTTPException(400, "prompt 不能为空")
    try:
        data = {}
        payload = {
            "prompt": req.prompt,
            "aspect_ratio": req.aspect_ratio,
            "output_num": 1,
            "quality": "medium",
            "resolution": "1K",
        }
        # 如果有参考图，传给 photogpt
        if req.reference_images:
            # 本地路径转 data URL（外部 API 无法访问本地路径）
            input_urls = []
            for ref in req.reference_images:
                if ref.startswith("/api/project-files/"):
                    # 本地路径 → 读文件转 data URL
                    parts = ref.replace("/api/project-files/", "").split("/")
                    if len(parts) >= 3:
                        fpath = PROJECT_CONTENT_DIR / parts[0] / parts[1] / parts[2]
                        if fpath.exists():
                            import base64, mimetypes
                            mime, _ = mimetypes.guess_type(str(fpath))
                            b64 = base64.b64encode(fpath.read_bytes()).decode()
                            input_urls.append(f"data:{mime or 'image/png'};base64,{b64}")
                        else:
                            input_urls.append(ref)
                    else:
                        input_urls.append(ref)
                else:
                    input_urls.append(ref)
            payload["input_urls"] = input_urls
        async with _httpx.AsyncClient(timeout=120, trust_env=False) as client:
            resp = await client.post(
                "http://localhost:8005/api/photogpt/generate",
                json=payload,
            )
        data = resp.json()
        if data.get("success"):
            job_id = data["job_id"]
            image_url = await _poll_photogpt_result_async(job_id)
            if image_url:
                # 下载到项目本地缓存，返回本地路径
                if req.project_id:
                    local_path = _download_to_project(req.project_id, "图片", image_url, f"shot_{req.shot_idx}_{req.mode}")
                    if local_path:
                        # 转为本地项目文件路径
                        rel_path = os.path.relpath(local_path, str(PROJECT_CONTENT_DIR))
                        rel_parts = rel_path.replace("\\", "/").split("/")
                        image_url = f"/api/project-files/{rel_parts[0]}/{rel_parts[1]}/{rel_parts[2]}"
                return {"success": True, "image_url": image_url, "job_id": job_id}
        return {"success": False, "error": data.get("error", "提交失败")}
    except _httpx.ConnectError:
        raise HTTPException(502, "无法连接 PhotoGPT 后端 (localhost:8005)")
    except Exception as e:
        raise HTTPException(502, f"生成失败: {e}")

async def _poll_photogpt_result_async(job_id: int, max_poll: int = 4) -> str:
    """异步轮询 photogpt 直到拿到图片 URL（4次 × 60秒 = 4分钟，不阻塞其他请求）"""
    import asyncio
    for i in range(max_poll):
        if i > 0:
            await asyncio.sleep(60)
        try:
            async with _httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"http://localhost:8005/api/photogpt/generate/jobs?page=1&page_size=200",
                )
            if resp.status_code != 200:
                continue
            jobs = resp.json()
            for job in jobs:
                if job.get("id") == job_id:
                    if job.get("status") == "success":
                        urls = job.get("output_urls", [])
                        if urls:
                            return urls[0]
                        return ""
                    elif job.get("status") == "failed":
                        err = job.get("error_message", "") or job.get("error", "") or "图片生成失败"
                        print(f"图片生成失败 (job {job_id}): {err}")
                        return ""
                    break
        except Exception as e:
            print(f"轮询图片结果异常 (job {job_id}): {e}")
    return ""

def _poll_photogpt_result(job_id: int, max_poll: int = 4) -> str:
    """轮询 photogpt 直到拿到图片 URL（4次 × 60秒 = 4分钟）"""
    import time
    for i in range(max_poll):
        if i > 0:
            time.sleep(60)
        try:
            resp = _httpx.get(
                f"http://localhost:8005/api/photogpt/generate/jobs?page=1&page_size=200",
                timeout=10, trust_env=False,
            )
            if resp.status_code != 200:
                continue
            jobs = resp.json()
            for job in jobs:
                if job.get("id") == job_id:
                    if job.get("status") == "success":
                        urls = job.get("output_urls", [])
                        if urls:
                            return urls[0]
                        return ""
                    elif job.get("status") == "failed":
                        err = job.get("error_message", "") or job.get("error", "") or "图片生成失败"
                        print(f"图片生成失败 (job {job_id}): {err}")
                        return ""
                    break
        except Exception as e:
            print(f"轮询图片结果异常 (job {job_id}): {e}")
    return ""


# ============================================================
# API: 批量生成图片（避免浏览器并发限制）
# ============================================================
import asyncio as _asyncio
import uuid as _uuid

_batch_tasks: dict = {}


class BatchFrameRequest(BaseModel):
    project_id: str = ""
    aspect_ratio: str = "16:9"
    frames: list = []
    reference_images: list = []


@app.post("/api/batch-generate-frames")
async def batch_generate_frames(req: BatchFrameRequest):
    task_id = _uuid.uuid4().hex[:12]
    frames = req.frames or []
    if not frames:
        raise HTTPException(400, "frames 不能为空")

    async def _run():
        async def _gen_one(frame):
            try:
                f_req = FrameGenRequest(
                    prompt=frame.get("prompt", ""),
                    aspect_ratio=req.aspect_ratio,
                    mode=frame.get("mode", "first_frame"),
                    project_id=req.project_id,
                    shot_idx=frame.get("shot_idx", 0),
                    reference_images=req.reference_images,
                )
                result = await generate_frame(f_req)
                return {"shot_idx": frame.get("shot_idx"), "mode": frame.get("mode"), "success": result.get("success"), "image_url": result.get("image_url", ""), "error": result.get("error", "")}
            except Exception as e:
                return {"shot_idx": frame.get("shot_idx"), "mode": frame.get("mode"), "success": False, "image_url": "", "error": str(e)}

        results = await _asyncio.gather(*[_gen_one(f) for f in frames])
        _batch_tasks[task_id] = {"status": "completed", "results": results, "total": len(frames)}

    _batch_tasks[task_id] = {"status": "running", "results": [], "total": len(frames)}
    _asyncio.ensure_future(_run())

    return {"task_id": task_id, "total": len(frames), "status": "running"}


@app.get("/api/batch-generate-frames/{task_id}")
async def batch_generate_frames_status(task_id: str):
    task = _batch_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@app.post("/api/generate-video")
async def generate_video(req: VideoGenRequest):
    """单段分镜视频生成 — 调 insmind（异步轮询，不阻塞其他请求）"""
    if not req.prompt:
        raise HTTPException(400, "prompt 不能为空")
    try:
        payload = {
            "job_type": "video",
            "prompt": req.prompt,
            "model": req.model,
            "ratio": req.ratio,
            "resolution": req.resolution,
            "duration": req.duration,
        }
        input_images = []
        if req.first_frame:
            input_images.append(req.first_frame)
        if req.last_frame:
            input_images.append(req.last_frame)
        if input_images:
            payload["input_images"] = input_images

        # 调 8005 不走代理（trust_env=False 跳过环境变量代理）
        async with _httpx.AsyncClient(timeout=30, trust_env=False) as _client:
            resp = await _client.post(
                f"http://localhost:8005/api/content/generate",
                json=payload,
            )
        if resp.status_code != 200:
            return {"success": False, "error": f"提交失败 (HTTP {resp.status_code})"}

        data = resp.json()
        job_id = data.get("id")
        if not job_id:
            return {"success": False, "error": f"返回无 job_id: {data}"}

        # 异步轮询，不阻塞其他请求
        video_url, err_msg = await _poll_video_result_async(job_id)
        if err_msg:
            return {"success": False, "error": err_msg, "job_id": job_id}
        if video_url:
            # 下载视频到项目文件夹，返回本地路径
            local_path = ""
            if req.project_id:
                try:
                    local_path = _download_to_project(req.project_id, "视频", video_url, f"shot_{req.shot_idx}")
                    if local_path:
                        rel_path = os.path.relpath(local_path, str(PROJECT_CONTENT_DIR))
                        rel_parts = rel_path.replace("\\", "/").split("/")
                        video_url = f"/api/project-files/{rel_parts[0]}/{rel_parts[1]}/{rel_parts[2]}"
                except Exception as e:
                    print(f"视频下载到本地失败: {e}")
            return {"success": True, "video_url": video_url, "local_path": local_path, "job_id": job_id}
    except _httpx.ConnectError:
        raise HTTPException(502, "无法连接视频生成后端 (localhost:8005)")
    except Exception as e:
        raise HTTPException(502, f"视频生成失败: {e}")


@app.get("/api/insmind-accounts/count")
async def insmind_accounts_count():
    """查询 insMind 可用账号数"""
    import sqlite3
    try:
        # 优先尝试本地 data 目录，其次 insMind 项目目录
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'dreamina.db')
        if not os.path.exists(db_path):
            alt_path = r"E:\视频生成\dreamina-auto-register-main\backend\data\dreamina.db"
            if os.path.exists(alt_path):
                db_path = alt_path
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM insmind_accounts WHERE status='active' AND token IS NOT NULL AND token != ''")
        count = cur.fetchone()[0]
        conn.close()
        return {"success": count, "total": count}
    except Exception as e:
        print(f"查询 insmind 账号数失败: {e}")
        return {"success": 0, "total": 0, "error": str(e)}


def _download_to_project(project_id: str, subdir: str, url: str, filename_prefix: str) -> str:
    """下载文件到项目文件夹对应子目录，返回本地路径"""
    import httpx as dl_httpx
    proj_dir = PROJECT_CONTENT_DIR / project_id / subdir
    proj_dir.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    for e in [".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".mov"]:
        if e in url.lower():
            ext = e
            break
    local_file = proj_dir / f"{filename_prefix}{ext}"
    try:
        # 如果旧文件存在，备份为 _prev（保留上一次）
        if local_file.exists():
            prev_file = local_file.with_name(local_file.stem + "_prev" + ext)
            if prev_file.exists():
                prev_file.unlink()
            local_file.rename(prev_file)
        proxy_url = "http://127.0.0.1:7897"
        proxies = {"all://": proxy_url} if proxy_url else None
        with _httpx.Client(proxies=proxies, timeout=60, follow_redirects=True, trust_env=False) as client:
            resp = client.get(url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://photogpt.io/"})
        if resp.status_code == 200:
            # 先写临时文件，成功后再覆盖，避免失败时丢旧图
            tmp_file = local_file.with_suffix(".tmp" + ext)
            tmp_file.write_bytes(resp.content)
            if tmp_file.exists():
                if local_file.exists():
                    local_file.unlink()
                tmp_file.rename(local_file)
            return str(local_file)
        print(f"下载失败: HTTP {resp.status_code} for {url[:50]}")
    except Exception as e:
        print(f"下载异常: {e}")
    return ""


def _save_data_url_to_project(project_id: str, subdir: str, data_url: str, filename_prefix: str) -> str:
    """保存 data URL 图片到项目文件夹，返回本地路径"""
    import base64
    proj_dir = PROJECT_CONTENT_DIR / project_id / subdir
    proj_dir.mkdir(parents=True, exist_ok=True)
    # 解析 data URL 格式: data:image/png;base64,xxxx
    ext = ".png"
    if "," in data_url:
        header = data_url.split(",")[0]
        if "png" in header:
            ext = ".png"
        elif "jpeg" in header or "jpg" in header:
            ext = ".jpg"
        elif "webp" in header:
            ext = ".webp"
        elif "gif" in header:
            ext = ".gif"
        b64_data = data_url.split(",")[1]
    else:
        return ""
    local_file = proj_dir / f"{filename_prefix}{ext}"
    try:
        img_data = base64.b64decode(b64_data)
        tmp_file = local_file.with_suffix(".tmp" + ext)
        tmp_file.write_bytes(img_data)
        if tmp_file.exists():
            if local_file.exists():
                local_file.unlink()
            tmp_file.rename(local_file)
        return str(local_file)
    except Exception as e:
        print(f"保存 data URL 异常: {e}")
        return ""



async def _poll_video_result_async(job_id: int, max_poll: int = 10) -> tuple:
    """异步轮询，返回 (video_url, error_message)"""
    import asyncio
    for i in range(max_poll):
        if i > 0:
            await asyncio.sleep(60)
        try:
            async with _httpx.AsyncClient(timeout=10, trust_env=False) as _client:
                resp = await _client.get("http://localhost:8005/api/content/jobs/" + str(job_id))
            if resp.status_code == 404:
                return ("", "任务不存在")
            job_data = resp.json()
            status = job_data.get("status", "")
            if status == "success":
                urls = job_data.get("output_urls", [])
                if urls:
                    return (urls[0], "")
                return ("", "生成成功但无输出 URL")
            elif status in ("failed", "error"):
                err = job_data.get("error_message", "") or job_data.get("error", "") or "生成失败"
                return ("", err)
        except:
            pass
    return ("", "视频生成超时")


def _poll_video_result(job_id: int, max_poll: int = 10) -> str:
    """轮询 content generation 直到拿到 video URL（10次 × 60秒 = 10分钟）"""
    import time
    for i in range(max_poll):
        time.sleep(60)
        try:
            resp = _httpx.get(f"http://localhost:8005/api/content/jobs/{job_id}", timeout=10, trust_env=False)
            if resp.status_code == 404:
                return ""
            job_data = resp.json()
            status = job_data.get("status", "")
            if status == "success":
                urls = job_data.get("output_urls", [])
                if urls:
                    return urls[0]
                return ""
            elif status in ("failed", "error"):
                return ""
        except:
            pass
    return ""


# ============================================================
# 入口
# ============================================================
def main():
    port = int(os.environ.get("ZCTOOLS_PORT", "8765"))
    host = os.environ.get("ZCTOOLS_HOST", "0.0.0.0")

    print("=" * 50)
    print(f"ZCTools Backend v1.0.0")
    print(f"Extracted from 智创AI高级版3.6")
    print("=" * 50)
    print(f"Listening on http://{host}:{port}")
    print(f"Data dir: {DATA_DIR}")
    print()
    print("Endpoints:")
    print(f"  GET  /api/health           Health check")
    print(f"  GET  /api/info             Extracted info")
    print(f"  GET  /api/projects         List projects")
    print(f"  POST /api/projects         Create project")
    print(f"  GET  /api/styles           List style presets")
    print(f"  POST /api/styles           Create custom style")
    print(f"  GET  /api/workflows        List ComfyUI workflows")
    print(f"  POST /api/prompt/enhance   Enhance prompt with style")
    print(f"  POST /api/script/generate  AI生成文案")
    print(f"  POST /api/generate         Submit generation task")
    print()
    print("Pipeline Endpoints:")
    print(f"  GET  /api/pipeline/steps   List pipeline steps")
    print(f"  POST /api/pipeline/run     Execute pipeline")
    print(f"  GET  /api/pipeline/runs    List pipeline runs")
    print(f"  POST /api/pipeline/runs/{id}/retry  Retry failed run")
    print(f"  POST /api/pipeline/runs/{id}/cancel Cancel running pipeline")
    print()
    print("LLM Config:")
    print(f"  GET  /api/llm/config       Get LLM config status")
    print(f"  POST /api/llm/config       Save LLM config")
    print(f"  POST /api/llm/test         Test LLM connection")
    print()
    print("To connect your own generator:")
    print("  from server import register_generation_handler")
    print("  register_generation_handler(my_handler)")
    print("=" * 50)

    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":
    main()