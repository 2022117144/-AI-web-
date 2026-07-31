"""
万象AI改 — 核心业务逻辑层

封装智创工具（zc_backend）的纯业务逻辑，供 api/ 和 pyqt5_frontend/ 共用。
"""
import sys
import os

# 将 zc_backend 目录加入路径，直接 import 模块文件
ZC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'zc_backend')
if ZC_DIR not in sys.path:
    sys.path.insert(0, ZC_DIR)

# 从 zc_backend 导入通用函数
import llm as llm_mod
import pipeline as pipeline_mod
import handlers as handlers_mod
import prompts as prompts_mod

__all__ = [
    "llm_mod", "pipeline_mod", "handlers_mod", "prompts_mod",
    "call_llm", "modify_copy", "save_copy", "generate_storyboard",
]