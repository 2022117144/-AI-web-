"""
智创工具 — LLM 客户端
====================
通过中转站（NewAPI）调用 LLM，支持多 key 轮询。
不内置任何默认中转站地址，必须通过前端设置页配置。
"""

import json, os, uuid
from pathlib import Path
from typing import Dict, List, Optional
import requests

CONFIG_DIR = Path(__file__).parent / "data"
CREDENTIALS_DIR = CONFIG_DIR / "credentials"
CONFIG_FILE = CONFIG_DIR / "llm_config.json"
KEYS_FILE = CREDENTIALS_DIR / "llm_keys.json"

# 内存中的轮询状态
_current_key_index = 0
_failed_keys = {}  # {key_id: timestamp} 记录挂掉的 key 和挂掉时间


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)


def get_config() -> dict:
    """读取 LLM 配置。无默认值——未配置则返回空字典。"""
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def save_config(config: dict):
    """保存 LLM 配置（不含 API key）"""
    ensure_dirs()
    safe = {k: v for k, v in config.items() if k != "api_key"}
    CONFIG_FILE.write_text(json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8")


# ========== 多 Key 管理 ==========

def get_keys() -> list:
    """读取所有 key，返回 [{id, key_preview, failed_at, label}]"""
    ensure_dirs()
    if not KEYS_FILE.exists():
        return []
    try:
        return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    except:
        return []


def save_keys(keys: list):
    """保存所有 key 到文件"""
    ensure_dirs()
    KEYS_FILE.write_text(json.dumps(keys, indent=2, ensure_ascii=False), encoding="utf-8")


def add_key(key: str, label: str = "") -> dict:
    """添加一个 key，返回 key 条目。自动生成 Key-1, Key-2... 名称"""
    keys = get_keys()
    # 去重：检查是否已存在相同 key
    for k in keys:
        if k.get("key") == key:
            return k
    # 自动生成名称
    if not label:
        existing_nums = []
        for k in keys:
            lbl = k.get("label", "")
            if lbl.startswith("Key-"):
                try:
                    existing_nums.append(int(lbl[4:]))
                except:
                    pass
        next_num = max(existing_nums) + 1 if existing_nums else 1
        label = f"Key-{next_num}"
    entry = {
        "id": uuid.uuid4().hex[:8],
        "key": key,
        "label": label,
        "model": "",
        "failed_at": None,
    }
    keys.append(entry)
    save_keys(keys)
    return entry


def rename_key(key_id: str, new_label: str) -> bool:
    """重命名指定 key"""
    keys = get_keys()
    for k in keys:
        if k["id"] == key_id:
            k["label"] = new_label
            save_keys(keys)
            return True
    return False


def delete_key(key_id: str) -> bool:
    """删除指定 key"""
    keys = get_keys()
    new_keys = [k for k in keys if k.get("id") != key_id]
    if len(new_keys) == len(keys):
        return False
    save_keys(new_keys)
    return True


def get_all_key_previews() -> list:
    """返回所有 key 的预览（不暴露完整 key）"""
    keys = get_keys()
    return [{
        "id": k["id"],
        "label": k.get("label", "Key-" + k["id"][:6]),
        "model": k.get("model", ""),
        "failed_at": k.get("failed_at"),
        "is_active": False,
    } for k in keys]


def get_api_key() -> str:
    """兼容旧接口：返回第一个 key，没有则返回空"""
    keys = get_keys()
    if keys:
        return keys[0].get("key", "")
    return ""


def save_api_key(key: str):
    """兼容旧接口：保存为第一个 key"""
    add_key(key)


def is_configured() -> bool:
    """检查 LLM 是否完全配置（有 base_url + 至少一个 key + model）"""
    config = get_config()
    keys = get_keys()
    return bool(config.get("base_url")) and bool(config.get("model")) and len(keys) > 0


# ========== 多 Key 轮询调用 ==========

def _is_dead_key(key_entry: dict) -> bool:
    """检查 key 是否被标记为挂掉且还在冷却期（60秒）"""
    import time
    failed_at = key_entry.get("failed_at")
    if not failed_at:
        return False
    return time.time() - failed_at < 60


def _mark_key_dead(key_entry: dict):
    """标记 key 为挂掉状态"""
    import time
    key_entry["failed_at"] = time.time()
    keys = get_keys()
    for k in keys:
        if k["id"] == key_entry["id"]:
            k["failed_at"] = time.time()
            break
    save_keys(keys)


def _recover_key(key_entry: dict):
    """恢复 key（清除挂掉标记）"""
    key_entry["failed_at"] = None
    keys = get_keys()
    for k in keys:
        if k["id"] == key_entry["id"]:
            k["failed_at"] = None
            break
    save_keys(keys)


def call_llm(
    messages: List[Dict[str, str]],
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0,
    max_tokens: int = 2048,
    override_base_url: str = "",
    override_api_key: str = "",
) -> Optional[str]:
    """
    调用中转站 LLM，支持多 key 轮询。
    自动跳过挂掉的 key，切换到下一个可用的 key。
    如果所有 key 都挂了，等待 60 秒后重试。
    """
    config = get_config()
    base_url = (override_base_url or config.get("base_url", "")).rstrip("/")
    model = model or config.get("model", "")
    temp = temperature if temperature > 0 else config.get("temperature", 0.7)
    mt = min(max_tokens, config.get("max_tokens", 4096))

    if not base_url or not model:
        print("LLM call skipped: base_url 或 model 为空")
        return None

    # 获取所有 key
    keys = get_keys()
    if not keys:
        print("LLM call skipped: 没有配置 API Key")
        return None

    # 如果是单 key 模式（override_api_key），直接使用
    if override_api_key:
        keys = [{"id": "override", "key": override_api_key, "failed_at": None}]

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    body = {
        "model": model,
        "messages": full_messages,
        "temperature": temp,
        "max_tokens": mt,
    }

    import time
    global _current_key_index

    # 最多尝试所有 key 两轮
    for attempt in range(len(keys) * 2):
        # 找到下一个可用的 key
        available_keys = []
        for i in range(len(keys)):
            idx = (_current_key_index + i) % len(keys)
            if not _is_dead_key(keys[idx]):
                available_keys.append(keys[idx])
                _current_key_index = (idx + 1) % len(keys)
                break

        if not available_keys:
            # 所有 key 都挂了，等 60 秒让冷却期过去
            print("所有 LLM Key 都已挂掉，等待 60 秒后重试...")
            time.sleep(60)
            # 清除所有挂掉标记
            for k in keys:
                k["failed_at"] = None
            save_keys(keys)
            _current_key_index = 0
            continue

        key_entry = available_keys[0]
        api_key = key_entry["key"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                json=body,
                headers=headers,
                timeout=60,
            )

            if resp.status_code == 200:
                # 调用成功，如果这个 key 之前挂了，恢复它
                if key_entry.get("failed_at"):
                    _recover_key(key_entry)
                data = resp.json()
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                return content

            elif resp.status_code in (429, 401, 402):
                # key 挂了，标记并切下一个
                print(f"LLM Key [{key_entry['id'][:8]}] 挂掉: {resp.status_code} {resp.text[:100]}")
                _mark_key_dead(key_entry)
                continue

            else:
                # 其他错误（400, 500 等），直接返回失败
                print(f"LLM API error: {resp.status_code} {resp.text[:200]}")
                return None

        except Exception as e:
            print(f"LLM call exception: {e}")
            # 网络错误也标记 key 挂掉并切下一个
            _mark_key_dead(key_entry)
            continue

    print("所有 LLM Key 均已耗尽，调用失败")
    return None


# ============================================================
# 配置 API（给前端调用）
# ============================================================

def get_status() -> dict:
    """返回当前 LLM 配置状态（不含 API key 原文）"""
    config = get_config()
    keys = get_keys()
    base_url = config.get("base_url", "")
    model = config.get("model", "")
    return {
        "configured": bool(base_url) and bool(model) and len(keys) > 0,
        "base_url": base_url,
        "model": model,
        "has_key": len(keys) > 0,
        "key_count": len(keys),
        "key_preview": keys[0]["key"][:12] + "..." if keys else "",
    }