# -*- coding: utf-8 -*-
"""命令行入口：douyin <链接> [--download] [--transcribe] [--md] [--json]"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import fetcher

try:  # Windows 控制台默认 GBK，会让中文报告乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="douyin",
        description="抖音视频内容提取：元数据 + 无水印直链 + 本地语音转写文稿",
    )
    p.add_argument("input", help="分享链接 / 分享口令整段文本 / 19 位视频 ID")
    p.add_argument("--json", action="store_true", help="额外输出结构化 JSON")
    p.add_argument("--download", action="store_true", help="下载无水印视频到输出目录")
    p.add_argument("--transcribe", action="store_true", help="本地语音转文字（faster-whisper）")
    p.add_argument("--md", action="store_true", help="生成 Markdown 报告")
    p.add_argument("--out", default=None, help="输出目录（默认 douyin-kit/out）")
    p.add_argument("--python", dest="pyexe", default=None,
                   help="跑转写用的 Python 解释器，默认自动探测（含 faster-whisper 的那个）")
    p.add_argument("--quiet", action="store_true", help="不打印摘要，只落盘")
    return p


def _outdir(arg) -> str:
    d = arg or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
    os.makedirs(d, exist_ok=True)
    return d


def print_summary(info: dict) -> None:
    a, s, v = info["author"], info["stats"], info["video"]
    print("=" * 62)
    print("标题文案 : %s" % info["desc"])
    print("作者     : %s%s" % (a["nickname"], ("（抖音号 %s）" % a["unique_id"]) if a["unique_id"] else ""))
    print("发布时间 : %s" % info["create_time_str"])
    print("话题     : %s" % (" ".join("#" + t for t in info["hashtags"]) or "无"))
    print("数据     : 赞 %s / 评论 %s / 收藏 %s / 转发 %s" % (s["digg"], s["comment"], s["collect"], s["share"]))
    print("规格     : %ss  %sx%s%s" % (v["duration_sec"], v["width"], v["height"], "  [图集]" if info["is_album"] else ""))
    print("无水印   : %s" % v["play_url"])
    print("封面     : %s" % v["cover"])
    print("网页链接 : %s" % info["links"]["web"])
    print("=" * 62)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        info = fetcher.fetch(args.input)
    except fetcher.DouyinError as e:
        print("[解析失败] %s" % e, file=sys.stderr)
        return 2
    except Exception as e:
        print("[意外错误] %s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 3

    outdir = _outdir(args.out)
    base = os.path.join(outdir, info["aweme_id"])

    if not args.quiet:
        print_summary(info)

    if args.json:
        p = base + ".json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print("[JSON] %s" % p)

    video_path = None
    if args.download:
        from . import media
        video_path = media.download_video(info, outdir)
        print("[视频] %s" % video_path)
        if info["video"]["cover"]:
            try:
                print("[封面] %s" % media.download_cover(info, outdir))
            except Exception as e:
                print("[封面] 跳过：%s" % e)

    transcript = None
    if args.transcribe:
        from . import asr
        try:
            transcript = asr.transcribe(info, outdir, pyexe=args.pyexe,
                                        video_path=video_path)
            print("[文稿] 已转写 %d 字" % len(transcript.get("text", "")))
        except Exception as e:
            print("[文稿] 转写失败：%s" % e, file=sys.stderr)

    if args.md:
        from . import report
        p = report.write_markdown(info, outdir, transcript=transcript)
        print("[报告] %s" % p)

    return 0
