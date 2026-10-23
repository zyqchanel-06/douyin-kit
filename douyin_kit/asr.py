# -*- coding: utf-8 -*-
"""本地语音转写：视频 -> 文稿（全离线，不花钱）。

策略：
  1. 当前解释器能 import faster_whisper 就直接用；
  2. 否则探测常见位置（本机 stt/venv），用子进程调它跑 _asr_worker.py。
视频文件用 PyAV 解码（faster-whisper 内置），因此不需要单独安装 ffmpeg.exe。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

from . import media

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "_asr_worker.py")

def _env_paths(name: str) -> list[str]:
    """读环境变量里的路径列表（用 os.pathsep 分隔，Windows 上是 ;）。"""
    raw = os.environ.get(name, "")
    return [p.strip() for p in raw.split(os.pathsep) if p.strip()]


# 依次尝试的转写解释器 / 模型位置。优先用环境变量指定，其次探测常见位置：
#   DOUYIN_ASR_PYTHON  —— 带 faster-whisper 的解释器路径（可多个，用 ; 分隔）
#   DOUYIN_ASR_MODEL   —— 本地 faster-whisper 模型目录
PY_CANDIDATES = _env_paths("DOUYIN_ASR_PYTHON") + [
    os.path.join(os.path.expanduser("~"), ".venv", "Scripts", "python.exe"),
    os.path.join(os.path.expanduser("~"), ".venv", "bin", "python"),
    "/usr/bin/python3",
]
MODEL_CANDIDATES = _env_paths("DOUYIN_ASR_MODEL") + [
    os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
    os.path.join(os.path.expanduser("~"), ".cache", "whisper"),
]


class AsrError(Exception):
    pass


def _has_faster_whisper(py: str) -> bool:
    try:
        r = subprocess.run([py, "-c", "import faster_whisper"],
                           capture_output=True, timeout=90)
        return r.returncode == 0
    except Exception:
        return False


def find_python(explicit: str | None = None) -> str:
    if explicit:
        if _has_faster_whisper(explicit):
            return explicit
        raise AsrError("指定的解释器没有 faster-whisper：%s" % explicit)
    if _has_faster_whisper(sys.executable):
        return sys.executable
    for c in PY_CANDIDATES:
        if os.path.exists(c) and _has_faster_whisper(c):
            return c
    raise AsrError("找不到带 faster-whisper 的 Python（可用 --python 指定）")


def find_model(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for c in MODEL_CANDIDATES:
        if os.path.isdir(c):
            return c
    raise AsrError("找不到本地 faster-whisper 模型（可用 --model 指定）")


def transcribe(info: dict, outdir: str, pyexe: str | None = None,
               model: str | None = None, video_path: str | None = None,
               language: str = "zh") -> dict:
    """转写视频音轨，返回 {text, segments, ...}；结果同时缓存到 outdir。"""
    out_json = os.path.join(outdir, "%s.asr.json" % info["aweme_id"])
    if os.path.exists(out_json):
        with open(out_json, encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("text"):
            return cached

    if not video_path:
        video_path = os.path.join(outdir, "%s.mp4" % info["aweme_id"])
        if not os.path.exists(video_path):
            video_path = media.download_video(info, outdir)

    py = find_python(pyexe)
    mdl = find_model(model)
    r = subprocess.run(
        [py, WORKER, video_path, mdl, out_json, language],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
    )
    if r.returncode != 0 or not os.path.exists(out_json):
        raise AsrError("转写子进程失败：%s" % ((r.stderr or r.stdout or "")[-500:]))
    with open(out_json, encoding="utf-8") as f:
        return json.load(f)
