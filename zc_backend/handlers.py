"""
智创工具 — 外部 API 集成 Handler
================================
photogpt: 分镜图片生成
insmind:  视频生成

所有 handler 符合 pipeline.register_step_handler 签名:
  handler(project_data: dict, step_config: dict) -> dict
"""

import json
import logging
import time
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

DREAMINA_API = "http://localhost:8005"
POLL_INTERVAL = 60  # 秒
MAX_POLL = 4         # 最大轮询次数 (≈4分钟)

# ============================================================
# photogpt: 分镜图片生成
# ============================================================

def _photogpt_poll_job(job_id: int) -> Optional[dict]:
    """轮询 photogpt 任务直到完成或超时"""
    for i in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        try:
            resp = httpx.get(
                f"{DREAMINA_API}/api/photogpt/generate/jobs?page=1&page_size=200",
                timeout=10,
            )
            jobs = resp.json()
            for job in jobs:
                if job.get("id") != job_id:
                    continue
                status = job.get("status", "")
                if status == "success":
                    return {"success": True, "urls": job.get("output_urls", [])}
                elif status == "failed":
                    err = job.get("error_message", "生成失败")
                    return {"success": False, "error": err}
                # 还在生成中，继续轮询
                break
        except Exception as e:
            logger.warning(f"photogpt poll error (attempt {i+1}): {e}")
    return {"success": False, "error": "轮询超时"}


def photogpt_images_handler(project_data: dict, step_config: dict) -> dict:
    """
    为每个分镜生成首帧/尾帧图片。
    规则：
      - 镜头1：生成首帧 + 尾帧（2张）
      - 镜头2+：只生成尾帧（首帧继承上一镜尾帧）
    同步提交所有请求，再一起轮询等待结果。
    step_config 期望:
      - shots: [{index, scene, prompt, enhanced_prompt, duration}]
      - aspect_ratio: "16:9" (可选)
    """
    shots = step_config.get("shots", [])
    if not shots:
        return {"success": True, "output": {"images": [], "message": "无分镜，跳过"}, "error": ""}

    aspect_ratio = step_config.get("aspect_ratio", "16:9")
    ar_map = {"16:9": "16:9", "9:16": "9:16", "1:1": "1:1", "4:3": "4:3"}
    photogpt_ar = ar_map.get(aspect_ratio, "16:9")

    # 第一步：收集所有需要提交的任务
    tasks = []  # [(shot_idx, frame_type, prompt)]
    for shot in shots:
        idx = shot.get("index", 0)
        prompt = shot.get("enhanced_prompt") or shot.get("prompt", "")
        if not prompt:
            logger.warning(f"分镜 #{idx} 无 prompt，跳过")
            continue
        # 首帧：只有镜头1才生成
        if idx == 0:
            tasks.append((idx, "first_frame", prompt))
        # 尾帧：所有镜头都生成
        tasks.append((idx, "last_frame", prompt + ", end frame, concluding scene, zoom out"))

    if not tasks:
        return {"success": True, "output": {"images": [], "message": "无任务"}, "error": ""}

    logger.info(f"📷 photogpt: 同步提交 {len(tasks)} 个任务...")

    # 第二步：同步提交所有任务，收集 job_id
    submitted = []  # [(shot_idx, frame_type, job_id)]
    for shot_idx, frame_type, prompt in tasks:
        try:
            resp = httpx.post(
                f"{DREAMINA_API}/api/photogpt/generate",
                json={"prompt": prompt, "aspect_ratio": photogpt_ar, "output_num": 1, "quality": "medium", "resolution": "1K"},
                timeout=30,
            )
            data = resp.json()
            if data.get("success"):
                job_id = data["job_id"]
                submitted.append((shot_idx, frame_type, job_id))
                logger.info(f"  📤 分镜 #{shot_idx} {frame_type} → job_id={job_id}")
            else:
                logger.warning(f"  ❌ 分镜 #{shot_idx} {frame_type} 提交失败: {data.get('error','')}")
        except Exception as e:
            logger.warning(f"  ❌ 分镜 #{shot_idx} {frame_type} 提交异常: {e}")

    # 第三步：一起轮询所有 job
    shot_frames = {}  # {index: {"first_frame": url, "last_frame": url}}
    for idx in range(len(shots)):
        shot_frames[idx] = {"first_frame": "", "last_frame": ""}

    for shot_idx, frame_type, job_id in submitted:
        logger.info(f"  ⏳ 等待 分镜 #{shot_idx} {frame_type} (job_id={job_id})...")
        poll_result = _photogpt_poll_job(job_id)
        if poll_result.get("success"):
            urls = poll_result.get("urls", [])
            if urls:
                shot_frames[shot_idx][frame_type] = urls[0]
                logger.info(f"  ✅ 分镜 #{shot_idx} {frame_type}: {urls[0][:60]}...")
            else:
                logger.warning(f"  ⚠️ 分镜 #{shot_idx} {frame_type} 返回空 URL")
        else:
            logger.warning(f"  ❌ 分镜 #{shot_idx} {frame_type} 生成失败: {poll_result.get('error','')}")

    # 继承：镜头2+的首帧继承上一镜尾帧
    for idx in range(1, len(shots)):
        prev_last = shot_frames.get(idx - 1, {}).get("last_frame", "")
        if prev_last and not shot_frames[idx].get("first_frame"):
            shot_frames[idx]["first_frame"] = prev_last
            logger.info(f"  📎 分镜 #{idx} 首帧继承自上一镜尾帧")

    # 构建输出
    results = []
    success_count = 0
    for idx, frames in sorted(shot_frames.items()):
        urls = []
        if frames["first_frame"]:
            urls.append(frames["first_frame"])
        if frames["last_frame"]:
            urls.append(frames["last_frame"])
        if urls:
            success_count += 1
        results.append({
            "shot_index": idx,
            "urls": urls,
            "first_frame": frames.get("first_frame", ""),
            "last_frame": frames.get("last_frame", ""),
            "error": "",
        })

    return {
        "success": True,
        "output": {
            "images": results,
            "shot_frames": shot_frames,
            "shot_count": len(shots),
            "success_count": success_count,
            "errors": errors,
        },
        "error": "; ".join(errors) if errors else "",
    }


# ============================================================
# insmind: 视频生成
# ============================================================

def _content_poll_job(job_id: int, max_poll: int = 120) -> Optional[dict]:
    """轮询 content generation 任务"""
    for i in range(max_poll):
        time.sleep(POLL_INTERVAL)
        try:
            resp = httpx.get(f"{DREAMINA_API}/api/content/jobs/{job_id}", timeout=10)
            if resp.status_code == 404:
                return {"success": False, "error": "任务不存在"}
            job = resp.json()
            status = job.get("status", "")
            if status == "success":
                return {"success": True, "urls": job.get("output_urls", [])}
            elif status in ("failed", "error"):
                err = job.get("error_message", "生成失败")
                return {"success": False, "error": err}
        except Exception as e:
            logger.warning(f"content poll error (attempt {i+1}): {e}")
    return {"success": False, "error": "轮询超时"}


def insmind_video_handler(project_data: dict, step_config: dict) -> dict:
    """
    为每个分镜生成视频片段。
    step_config 期望:
      - shots: [{index, scene, prompt, duration, first_frame_url, last_frame_url}]
      - model: "Pixverse-V6.0" (可选)
      - ratio: "16:9" (可选)
    """
    shots = step_config.get("shots", [])
    if not shots:
        return {"success": True, "output": {"videos": [], "message": "无分镜，跳过"}, "error": ""}

    model = step_config.get("model", "Pixverse-V6.0")
    ratio = step_config.get("ratio", "16:9")
    resolution = step_config.get("resolution", "360p")
    duration = step_config.get("duration", 10)

    results = []
    errors = []

    for shot in shots:
        idx = shot.get("index", 0)
        prompt = shot.get("enhanced_prompt") or shot.get("prompt", "")
        if not prompt:
            results.append({"shot_index": idx, "video_url": "", "error": "无 prompt"})
            continue

        # 收集输入图片（首帧/尾帧）
        # 先查 shot_frames（来自 photogpt 步骤的累积输出），再查 shot 本身
        input_images = []
        shot_frames_dict = step_config.get("shot_frames", {})
        shot_frames_entry = shot_frames_dict.get(idx, {}) if isinstance(shot_frames_dict, dict) else {}
        first_url = shot_frames_entry.get("first_frame", "") or shot.get("first_frame_url") or shot.get("first_frame", "")
        last_url = shot_frames_entry.get("last_frame", "") or shot.get("last_frame_url") or shot.get("last_frame", "")
        if first_url:
            input_images.append(first_url)
        if last_url:
            input_images.append(last_url)

        logger.info(f"🎬 insmind 提交分镜 #{idx}, model={model}...")
        try:
            payload = {
                "job_type": "video",
                "prompt": prompt,
                "model": model,
                "ratio": ratio,
                "resolution": resolution,
                "duration": duration,
            }
            if input_images:
                payload["input_images"] = input_images
                logger.info(f"  首尾帧: {len(input_images)} 张图片")

            resp = httpx.post(
                f"{DREAMINA_API}/api/content/generate",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                
                # 402 = 无可用 insMind 账号 → 自动注册
                if resp.status_code == 402 or "No available insMind accounts" in err:
                    logger.info("⚠️ 无 insMind 账号，尝试自动注册...")
                    try:
                        reg_resp = httpx.post(
                            f"{DREAMINA_API}/api/insmind/accounts/auto-register",
                            timeout=90,  # 注册约 30-60 秒
                        )
                        reg_data = reg_resp.json()
                        if reg_data.get("success"):
                            logger.info(f"✅ insMind 账号注册成功: {reg_data.get('email', '')}")
                            # 重试视频生成
                            time.sleep(3)  # 等账号生效
                            retry_resp = httpx.post(
                                f"{DREAMINA_API}/api/content/generate",
                                json=payload, timeout=30,
                                headers={"Content-Type": "application/json"},
                            )
                            if retry_resp.status_code == 200:
                                retry_data = retry_resp.json()
                                job_id = retry_data.get("id")
                                if job_id:
                                    logger.info(f"insmind job #{job_id} 已提交（重试）")
                                    poll_result = _content_poll_job(job_id, max_poll=120)
                                    if poll_result.get("success"):
                                        urls = poll_result.get("urls", [])
                                        video_url = urls[0] if urls else ""
                                        results.append({"shot_index": idx, "video_url": video_url, "error": ""})
                                        continue
                                    else:
                                        err = poll_result.get("error", "重试后仍失败")
                                        errors.append(f"分镜 #{idx}: {err}")
                                        results.append({"shot_index": idx, "video_url": "", "error": err})
                                        continue
                            err = f"注册后重试仍失败: 账号可能未就绪"
                        else:
                            err = f"自动注册失败: {reg_data.get('error', '未知错误')}"
                    except Exception as reg_e:
                        err = f"自动注册异常: {reg_e}"
                
                logger.warning(f"insmind 提交失败 (shot #{idx}): {err}")
                errors.append(f"分镜 #{idx}: {err}")
                results.append({"shot_index": idx, "video_url": "", "error": err})
                continue

            data = resp.json()
            job_id = data.get("id")
            if not job_id:
                err = f"返回无 job_id: {resp.text[:200]}"
                errors.append(err)
                results.append({"shot_index": idx, "video_url": "", "error": err})
                continue

            logger.info(f"insmind job #{job_id} 已提交，开始轮询...")
            poll_result = _content_poll_job(job_id, max_poll=120)  # 视频生成约6分钟

            if poll_result.get("success"):
                urls = poll_result.get("urls", [])
                video_url = urls[0] if urls else ""
                logger.info(f"分镜 #{idx} 视频生成成功: {video_url}")
                results.append({"shot_index": idx, "video_url": video_url, "error": ""})
            else:
                err = poll_result.get("error", "生成失败")
                logger.warning(f"分镜 #{idx} 视频生成失败: {err}")
                errors.append(f"分镜 #{idx}: {err}")
                results.append({"shot_index": idx, "video_url": "", "error": err})

        except httpx.ConnectError:
            err_msg = f"无法连接后端 ({DREAMINA_API})"
            logger.error(err_msg)
            errors.append(err_msg)
            return {"success": False, "output": {"videos": results, "errors": errors}, "error": err_msg}
        except Exception as e:
            err = f"分镜 #{idx} 异常: {e}"
            logger.error(err)
            errors.append(err)
            results.append({"shot_index": idx, "video_url": "", "error": str(e)})

    return {
        "success": True,
        "output": {
            "videos": results,
            "shot_count": len(shots),
            "success_count": sum(1 for r in results if r.get("video_url")),
            "errors": errors,
        },
        "error": "; ".join(errors) if errors else "",
    }


# ============================================================
# BGM → 发送 (桩)
# ============================================================

def bgm_send_handler(project_data: dict, step_config: dict) -> dict:
    """BGM+发送 — 返回占位，等待集成"""
    merged_video = step_config.get("merged_video_path", "")
    bgm_path = step_config.get("bgm_path", "")
    return {
        "success": True,
        "output": {
            "merged_video_path": merged_video,
            "bgm_path": bgm_path,
            "message": "BGM+发送功能待接",
        },
        "error": "",
    }