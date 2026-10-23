# -*- coding: utf-8 -*-
"""媒体下载：无水印视频 / 封面（纯标准库，无第三方依赖）。"""
from __future__ import annotations

import http.cookiejar
import os
import urllib.request

from .fetcher import UA_MOBILE


class MediaError(Exception):
    pass


def _opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [
        ("User-Agent", UA_MOBILE),
        ("Referer", "https://www.douyin.com/"),
    ]
    return op


def download(url: str, dest: str, timeout: int = 300, progress=None) -> str:
    """流式下载，返回落盘路径。"""
    if not url:
        raise MediaError("下载地址是空的")
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    op = _opener()
    tmp = dest + ".part"
    got = 0
    try:
        with op.open(urllib.request.Request(url), timeout=timeout) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if progress:
                    progress(got, total)
        os.replace(tmp, dest)
    except Exception as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise MediaError("下载失败：%s" % e)
    return dest


def download_video(info: dict, outdir: str) -> str:
    dest = os.path.join(outdir, "%s.mp4" % info["aweme_id"])
    return download(info["video"]["play_url"], dest)


def download_cover(info: dict, outdir: str) -> str:
    url = info.get("cover") or info["video"].get("cover")
    if not url:
        raise MediaError("这条视频没有封面地址")
    dest = os.path.join(outdir, "%s_cover.webp" % info["aweme_id"])
    return download(url, dest, timeout=60)
