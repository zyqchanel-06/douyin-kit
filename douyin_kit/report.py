# -*- coding: utf-8 -*-
"""把归一化信息（+ 可选文稿）渲染成一份 Markdown 报告。"""
from __future__ import annotations

import os


def render_markdown(info: dict, transcript: dict | None = None) -> str:
    a, s, v = info["author"], info["stats"], info["video"]
    title = (info["desc"] or "").strip().splitlines()[0] if info["desc"] else "(无标题)"
    L = []
    L.append("# %s" % title)
    L.append("")
    L.append("> 抖音 · @%s · %s" % (a["nickname"], info["create_time_str"]))
    L.append("")
    L.append("## 基本信息")
    L.append("")
    L.append("| 项目 | 内容 |")
    L.append("| --- | --- |")
    L.append("| 视频 ID | %s |" % info["aweme_id"])
    L.append("| 完整文案 | %s |" % (info["desc"] or "").replace("|", "\\|"))
    L.append("| 话题 | %s |" % (" ".join("#" + t for t in info["hashtags"]) or "无"))
    L.append("| 作者 | %s%s |" % (a["nickname"], ("（%s）" % a["unique_id"]) if a["unique_id"] else ""))
    L.append("| 作者简介 | %s |" % (a["signature"] or "").replace("\n", " ").replace("|", "\\|"))
    L.append("| 发布时间 | %s |" % info["create_time_str"])
    L.append("| 时长 | %s 秒 |" % v["duration_sec"])
    L.append("| 分辨率 | %s x %s |" % (v["width"], v["height"]))
    L.append("| 数据 | 赞 %s / 评论 %s / 收藏 %s / 转发 %s |"
             % (s["digg"], s["comment"], s["collect"], s["share"]))
    L.append("| 类型 | %s |" % ("图集" if info["is_album"] else "视频"))
    L.append("")
    L.append("## 链接")
    L.append("")
    L.append("- 网页：%s" % info["links"]["web"])
    L.append("- 分享页：%s" % info["links"]["share"])
    if info["links"].get("author_home"):
        L.append("- 作者主页：%s" % info["links"]["author_home"])
    L.append("- **无水印直链**：%s" % v["play_url"])
    L.append("- 封面：%s" % v["cover"])
    if info.get("images"):
        L.append("")
        L.append("## 图集")
        L.append("")
        for i, u in enumerate(info["images"], 1):
            L.append("%d. %s" % (i, u))
    L.append("")
    L.append("## 视频文稿（本地语音转写）")
    L.append("")
    if transcript and transcript.get("text"):
        L.append(transcript["text"])
        L.append("")
        L.append("<details><summary>时间轴（%d 段，转写耗时 %ss）</summary>"
                 % (len(transcript.get("segments", [])), transcript.get("transcribe_sec")))
        L.append("")
        for seg in transcript.get("segments", []):
            L.append("- `[%6.1f - %6.1f]` %s" % (seg["start"], seg["end"], seg["text"]))
        L.append("")
        L.append("</details>")
    else:
        L.append("_未转写（加 --transcribe 生成）_")
    L.append("")
    return "\n".join(L)


def write_markdown(info: dict, outdir: str, transcript: dict | None = None) -> str:
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "%s.md" % info["aweme_id"])
    with open(p, "w", encoding="utf-8") as f:
        f.write(render_markdown(info, transcript))
    return p
