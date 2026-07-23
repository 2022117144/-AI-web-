"""
万象AI改 — 核心业务逻辑层

封装智创工具（zctools）的纯业务逻辑，供 api/ 和 pyqt5_frontend/ 共用。
"""
import sys
import os

# 将万象AI-2改源码加入路径
WANXIANG_2_SRC = r"E:\万象AI-2改\src"
if WANXIANG_2_SRC not in sys.path:
    sys.path.insert(0, WANXIANG_2_SRC)

# 从 zctools 导入通用函数（无 PyQt5 依赖）
from zctools import zc_llm as llm_mod
from zctools import zc_pipeline as pipeline_mod
from zctools import zc_handlers as handlers_mod
from zctools import zc_prompts as prompts_mod

__all__ = [
    "llm_mod", "pipeline_mod", "handlers_mod", "prompts_mod",
    "call_llm", "modify_copy", "save_copy", "generate_storyboard",
]


def get_config():
    """延迟加载 A0_config（有 cv2 依赖，需要时再导入）"""
    from 任务运行文件 import A0_config
    return A0_config


def update_config(updates: dict):
    """更新配置（延迟加载 A0_config）"""
    from 任务运行文件 import A0_config
    for key, value in updates.items():
        if key in A0_config.config:
            A0_config.config[key] = value
    A0_config.修改配置()