"""
智创工具 — 流水线引擎
=====================
按手绘流程图定义的 AI 视频自动生成管线：
  文案 → 分镜提示词+SRT字幕+配音 → 分镜首尾帧 → 视频
    → FFmpeg 拼接、字幕和可选配乐 → 验证成片并导出

media_engine 执行真实媒体任务；缺失素材、失败和取消均如实记录。

架构说明：
- 这是整个项目唯一的流水线定义。PIPELINE_STEPS 是唯一的数据源。
- 前端 zc_index.html 的 #tab-pipeline 通过 GET /api/pipeline/steps 动态渲染。
- 万象AI主界面 index.html 的 #wx-pipeline 只是一个 iframe 容器，嵌的是 zc_index.html?tab=pipeline。
- 后端任务是执行与状态的唯一来源，前端只提交任务、轮询和取消。
"""

import json, os, uuid, requests, time, threading
import media_engine as media
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# LLM 客户端（相对导入）
import sys
sys.path.insert(0, str(Path(__file__).parent))
import llm as llm_mod

# ============================================================
# 步骤定义
# ============================================================

# 标准步骤列表（按顺序执行）
PIPELINE_STEPS = [
    {
        "name": "script",
        "label": "文案",
        "description": "用户输入文案脚本",
        "optional": False,
        "inputs": ["script_text"],
    },
    {
        "name": "storyboard_with_audio",
        "label": "分镜提示词 + SRT字幕 + 音频",
        "description": "从文案生成分镜提示词、配音和真实时间戳字幕",
        "optional": False,
        "inputs": ["script_text", "shot_count", "characters", "voice_name"],
    },
    {
        "name": "photogpt_images",
        "label": "分镜图片 (photogpt)",
        "description": "调用 PhotoGPT 为每个分镜生成图片",
        "optional": False,
        "inputs": ["shots"],
    },
    {
        "name": "insmind_video",
        "label": "视频生成 (insm后端)",
        "description": "将分镜图片送入 insMind 后端生成视频片段",
        "optional": False,
        "inputs": ["shots", "shot_frames", "model"],
    },
    {
        "name": "ffmpeg_merge",
        "label": "整合视频 (ffmpeg)",
        "description": "拼接所有视频片段为完整视频 + 可选配乐",
        "optional": False,
        "inputs": ["video_paths", "bgm_path"],
    },
    {
        "name": "bgm_send",
        "label": "成片导出",
        "description": "验证成片音视频并提供下载",
        "optional": False,
        "inputs": ["merged_video_path", "bgm_path"],
    },
]

# ============================================================
# Handler 类型
# ============================================================
# handler(project_data: dict, step_config: dict) -> dict
# 返回: {"success": bool, "output": dict, "error": str}
StepHandler = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]

# ============================================================
# Handler 注册表
# ============================================================
_handlers: Dict[str, StepHandler] = {}

# 内置"待接"桩 handler
def _stub_handler(project_data: dict, step_config: dict) -> dict:
    return {
        "success": False,
        "output": {"stub": True, "message": "接口待接 — 输出占位"},
        "error": "",
    }

# 内置"已就绪"handler（不需要外部 API 的步骤）
def _script_handler(project_data: dict, step_config: dict) -> dict:
    """文案步骤 — 文案已在前端完成，这里只是确认"""
    script_text = step_config.get("script_text", "")
    if not script_text:
        script_text = project_data.get("original_full_script", "") or project_data.get("original_story_desc", "")
    if not script_text:
        script_text = project_data.get("original_voiceover_text", "") or project_data.get("rewritten_voiceover_text", "")
    return {
        "success": bool(script_text.strip()),
        "output": {"script_text": script_text},
        "error": "",
    }


def _style_prompt_handler(project_data: dict, step_config: dict) -> dict:
    style_id = step_config.get("style_preset_id", "")
    style_anchor = step_config.get("style_anchor", "")
    char_anchor = step_config.get("character_anchor", "")
    return {
        "success": True,
        "output": {
            "style_preset_id": style_id,
            "style_anchor": style_anchor,
            "character_anchor": char_anchor,
        },
        "error": "",
    }

DOUBAO_TTS_API_KEY = os.environ.get("DOUBAO_SPEECH_API_KEY", "")
DOUBAO_TTS_RESOURCE_ID = "seed-tts-2.0"
DOUBAO_TTS_SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/tts/submit"
DOUBAO_TTS_QUERY_URL = "https://openspeech.bytedance.com/api/v3/tts/query"
TTS_OUTPUT_DIR = Path(__file__).parent / "data" / "tts_output"


def _call_edge_tts(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> dict:
    try:
        path = TTS_OUTPUT_DIR / (uuid.uuid4().hex + '.mp3')
        data = json.loads(media.process([sys.executable, Path(__file__).parent / '_edge_tts_wrapper.py', '-', voice, path],
                         timeout=max(120, min(900, len(text)*2)), input_text=text))
        duration, _ = media.probe(path, 'audio')
        return {'success': True, 'output': {'audio_path': str(path), 'duration_ms': round(duration*1000), 'events': data['events']}}
    except Exception as error:
        return {'success': False, 'output': {}, 'error': str(error)}



def _script_audio_handler(project_data: dict, step_config: dict) -> dict:
    script_text = step_config.get('script_text') or project_data.get('original_full_script') or ''
    if not script_text.strip(): return {'success': False, 'output': {}, 'error': '配音文本为空'}
    return _call_edge_tts(script_text, step_config.get('voice_name', 'zh-CN-XiaoxiaoNeural'))


def _storyboard_with_audio_handler(project_data: dict, step_config: dict) -> dict:
    try:
        pid = step_config.get('project_id') or project_data.get('project_id')
        doc = media.content(pid)
        result = media.narrate(pid, doc['shots'], step_config.get('voice_name', 'zh-CN-XiaoxiaoNeural'))
        return {'success': True, 'output': {'shots': doc['shots'], 'shot_count': len(doc['shots']), 'narration': result}}
    except Exception as error:
        return {'success': False, 'output': {}, 'error': str(error)}


def _ffmpeg_merge_handler(project_data: dict, step_config: dict) -> dict:
    try:
        result = media.assemble(step_config.get('project_id') or project_data.get('project_id'), step_config)
        return {'success': True, 'output': result, 'error': ''}
    except Exception as error:
        return {'success': False, 'output': {}, 'error': str(error)}



def register_step_handler(step_name: str, handler: StepHandler):
    """注册步骤 handler。调用后该步骤不再返回"待接"桩。"""
    _handlers[step_name] = handler


def get_step_handler(step_name: str) -> StepHandler:
    """获取步骤 handler，未注册时根据步骤定义决定用内置还是桩"""
    if step_name in _handlers:
        return _handlers[step_name]
    # 内置 handler
    builtin = {
        "script": _script_handler,
        "storyboard_with_audio": _storyboard_with_audio_handler,
        "ffmpeg_merge": _ffmpeg_merge_handler,
    }
    if step_name in builtin:
        return builtin[step_name]
    # 默认桩
    return _stub_handler


# ============================================================
# 流水线状态管理
# ============================================================

class PipelineRun:
    """单次流水线执行的状态"""
    def __init__(self, project_id: str = ""):
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.project_id = project_id
        self.status = "idle"  # idle | running | completed | error | cancelled
        self.steps: List[Dict[str, Any]] = []
        self.current_step: int = -1
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.error = ""
        self.cancel_requested = False
        self.config = {}

    def init_steps(self, config: Dict[str, Any]):
        """用配置初始化步骤状态"""
        self.config = config
        self.steps = []
        for step_def in PIPELINE_STEPS:
            name = step_def["name"]
            step_config = config.get(name, {})
            self.steps.append({
                "name": name,
                "label": step_def["label"],
                "description": step_def["description"],
                "optional": step_def.get("optional", False),
                "stub": step_def.get("stub", False),
                "status": "pending",
                "config": step_config,
                "output": {},
                "error": "",
            })
        self.status = "idle"
        self.current_step = -1

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "config": self.config,
            "final_url": next((s.get("output", {}).get("final_url", "") for s in reversed(self.steps) if s.get("output", {}).get("final_url")), ""),
            "project_id": self.project_id,
            "status": self.status,
            "current_step": self.current_step,
            "steps": [
                {
                    "name": s["name"],
                    "label": s["label"],
                    "description": s["description"],
                    "optional": s["optional"],
                    "stub": s.get("stub", False),
                    "status": s["status"],
                    "output_summary": _summarize_output(s.get("output", {})),
                    "error": s.get("error", ""),
                    "output": s.get("output", {}),
                }
                for s in self.steps
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    def run_sync(self, project_data: dict) -> dict:
        lock = media.project_lock(self.project_id)
        if not lock.acquire(blocking=False):
            self.status = 'error'; self.error = '该项目已有媒体任务正在执行'; save_run(self)
            return self.to_dict()
        try:
            self.status = 'running'; save_run(self)
            media.execute(self, self.config)
            media.check(lambda: self.cancel_requested)
            self.status = 'completed'
        except media.Cancelled as error:
            self.status = 'cancelled'; self.error = str(error)
            if self.current_step >= 0: self.steps[self.current_step]['status'] = 'cancelled'
        except Exception as error:
            self.status = 'error'; self.error = str(error)
            if self.current_step >= 0:
                self.steps[self.current_step]['status'] = 'error'
                self.steps[self.current_step]['error'] = str(error)
        finally:
            self.updated_at = datetime.now().isoformat()
            try:
                save_run(self)
            finally:
                lock.release()
        return self.to_dict()



def _summarize_output(output: dict) -> str:
    """输出摘要（避免塞原始数据到前端）"""
    if not output:
        return ""
    if output.get("stub"):
        return "🔌 接口待接"
    if "images" in output and "shot_count" in output:
        ok = output.get("success_count", 0)
        total = output.get("shot_count", 0)
        return f"🖼 {ok}/{total} 张图片"
    if "videos" in output and "shot_count" in output:
        ok = output.get("success_count", 0)
        total = output.get("shot_count", 0)
        return f"🎬 {ok}/{total} 个视频"
    if "shots" in output:
        shots = output.get('shot_count', 0)
        audio = ' 🔊' if output.get('audio_path') else ''
        return f"📋 {shots} 个分镜{audio}"
    if "merged_path" in output:
        return "🎬 合成完成"
    if "script_text" in output:
        text_len = len(output.get('script_text', ''))
        return f"📝 {text_len} 字"
    return "✓ 完成"


# ============================================================
# 全局 Pipeline 存储（内存 + 持久化）
# ============================================================

_runs: Dict[str, PipelineRun] = {}
RUNS_FILE = Path(__file__).parent / "data" / "pipeline_runs.json"
_runs_lock = threading.RLock()


def save_run(run: PipelineRun):
    run.updated_at = datetime.now().isoformat()
    with _runs_lock:
        _runs[run.run_id] = run
        media.write(RUNS_FILE, {k: v.to_dict() for k, v in _runs.items()})



def load_runs():
    global _runs
    try:
        if RUNS_FILE.exists():
            data = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
            for run_id, d in data.items():
                if run_id in _runs: continue
                run = PipelineRun(d.get("project_id", ""))
                run.run_id = run_id
                run.status = d.get("status", "idle")
                run.current_step = d.get("current_step", -1)
                run.created_at = d.get("created_at", "")
                run.updated_at = d.get("updated_at", "")
                run.error = d.get("error", "")
                run.init_steps(d.get("config", {}))
                run.current_step = d.get("current_step", -1)
                run.steps = [{**base, **old} for base, old in zip(run.steps, d.get("steps", run.steps))]
                run.status = d.get("status", "idle")
                if run.status == "running":
                    run.status = "error"; run.error = "服务重启中断了任务，请重新执行"
                _runs[run_id] = run
    except:
        pass


def get_project_runs(project_id: str) -> List[PipelineRun]:
    return [r for r in _runs.values() if r.project_id == project_id]


def get_run(run_id: str) -> Optional[PipelineRun]:
    return _runs.get(run_id)


def clear_project_runs(project_id: str):
    with _runs_lock:
        if any(r.status == 'running' for r in get_project_runs(project_id)):
            raise ValueError('请先停止该项目的任务再清除记录')
        for key in [k for k, value in _runs.items() if value.project_id == project_id]: del _runs[key]
        media.write(RUNS_FILE, {k: v.to_dict() for k, v in _runs.items()})



# 启动时加载历史
load_runs()
