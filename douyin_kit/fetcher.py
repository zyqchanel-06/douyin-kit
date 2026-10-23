# -*- coding: utf-8 -*-
"""抖音解析核心：分享链接 / 分享口令 -> 结构化视频信息。

走的路径（已实测）：
    短链 v.douyin.com/xxx
        -> 302 到 www.iesdouyin.com/share/video/{aweme_id}/
        -> HTML 内嵌 window._ROUTER_DATA（完整 videoInfoRes）
        -> 归一化为 dict

为什么不用 PC 站 www.douyin.com：
    它的视频页由 JS 虚拟机（_$jsvmprt）渲染并带签名校验，纯 HTTP 拿不到数据。
    移动分享页是服务端渲染（SSR）的，数据直接躺在 HTML 里，无需签名。
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
CST = timezone(timedelta(hours=8))
SHARE_TMPL = "https://www.iesdouyin.com/share/video/{aweme_id}/"
WEB_TMPL = "https://www.douyin.com/video/{aweme_id}"

# 文本里抠链接：排除中文标点和常见包裹符
_URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff，。、；：？！“”‘’（）()\[\]【】<>]+")
# 各类链接/ID 形态里的 aweme_id
_AWEME_RE = re.compile(r"(?:/video/|/share/video/|modal_id=|item_ids=)(\d{15,25})")
_BARE_ID_RE = re.compile(r"(?<!\d)(\d{19})(?!\d)")


class DouyinError(Exception):
    """解析过程中的可预期错误。"""


def extract_url(text: str) -> str:
    """从分享口令或任意文本里抠出第一个链接；允许直接传纯数字 ID。"""
    if not text or not text.strip():
        raise DouyinError("输入是空的")
    text = text.strip()
    m = _URL_RE.search(text)
    if m:
        return m.group(0)
    m = _BARE_ID_RE.search(text)
    if m:
        return WEB_TMPL.format(aweme_id=m.group(1))
    raise DouyinError("在输入里没找到链接或 19 位视频 ID")


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [
        ("User-Agent", UA_MOBILE),
        ("Accept-Language", "zh-CN,zh;q=0.9"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ]
    return op


def _get(op, url: str, timeout: int = 30):
    req = urllib.request.Request(url)
    with op.open(req, timeout=timeout) as r:
        return r.status, r.geturl(), r.read().decode("utf-8", "ignore")


def extract_router_data(html: str):
    """从分享页 HTML 里抠出 _ROUTER_DATA 的 JSON（花括号配对，避免被转义坑）。"""
    i = html.find("_ROUTER_DATA")
    if i < 0:
        return None
    j = html.find("{", i)
    if j < 0:
        return None
    depth, in_str, esc = 0, False, False
    for k in range(j, len(html)):
        ch = html[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[j : k + 1])
                    except json.JSONDecodeError as e:
                        raise DouyinError("_ROUTER_DATA 不是合法 JSON：%s" % e)
    return None


def has_video_page(data) -> bool:
    """判断这份 _ROUTER_DATA 里到底有没有真数据。

    抖音的反爬是这样的：**首次请求只下发 ttwid Cookie，返回一个空壳页**
    （HTML 长度约 32KB，_ROUTER_DATA 结构齐全但没有 videoInfoRes）；
    带着 ttwid 再请求一次，才会返回 37KB 的真数据。
    所以必须用**同一个会话**重试，换新会话永远卡在空壳页。
    """
    ld = (data or {}).get("loaderData") or {}
    return any(isinstance(v, dict) and "videoInfoRes" in v for v in ld.values())


def _pick_video_page(data: dict) -> dict:
    """loaderData 里的 key 会随版本变化（如 video_(id)/page），按值特征找。"""
    ld = (data or {}).get("loaderData") or {}
    for key, val in ld.items():
        if isinstance(val, dict) and "videoInfoRes" in val:
            return val
    raise DouyinError("分享页里没有 videoInfoRes（可能触发了风控或视频已删）")


def _aweme_id_from(text: str):
    m = _AWEME_RE.search(text) or _BARE_ID_RE.search(text)
    return m.group(1) if m else None


def fetch_raw(share_text: str, timeout: int = 30, retry: int = 3) -> dict:
    """完整流程：文本 -> aweme_id -> 移动分享页 -> _ROUTER_DATA。

    三个已实测的坑，这里都绕开了：
      1. 凡是能从输入直接确定 aweme_id 的（纯 ID、PC 链接、分享页链接），
         **绝不先去请求原始链接** —— www.douyin.com 会下发反爬 Cookie 并返回
         经 JS 虚拟机渲染的空页，纯 HTTP 拿不到任何数据。
      2. 分享页有**两段式反爬**：首次请求只下发 ttwid 并返回空壳页，
         带 Cookie 再请求才有数据。所以重试必须**复用同一个会话**。
      3. 短链展开本身就顺带完成了会话预热，若展开结果里已有数据就直接用。
    """
    url = extract_url(share_text)
    op = _opener()  # 全程同一个会话：Cookie（ttwid）是能不能拿到数据的关键
    aweme_id = _aweme_id_from(url)

    if not aweme_id:
        # 短链（v.douyin.com/xxxx）必须先展开一次才知道是哪条视频
        status, final, body = _get(op, url, timeout)
        aweme_id = _aweme_id_from(final) or _aweme_id_from(body)
        if not aweme_id:
            raise DouyinError("没能从 %s 里解析出视频 ID" % final)
        data = extract_router_data(body)
        if has_video_page(data):
            return {"data": data, "aweme_id": aweme_id, "final_url": final,
                    "html_len": len(body)}

    share_url = SHARE_TMPL.format(aweme_id=aweme_id)
    last_err = None
    for attempt in range(max(2, retry)):
        try:
            status, final, body = _get(op, share_url, timeout)
            data = extract_router_data(body)
            if has_video_page(data):
                return {"data": data, "aweme_id": aweme_id, "final_url": share_url,
                        "html_len": len(body)}
            last_err = "分享页返回了空壳数据（第 %d 次，HTML %d 字节）" % (attempt + 1, len(body))
        except Exception as e:
            last_err = "%s: %s" % (type(e).__name__, e)
        if attempt < max(2, retry) - 1:
            time.sleep(1.2)
    raise DouyinError("%s（平台风控或视频不可见，稍后重试）" % last_err)


def _no_watermark(url: str) -> str:
    """抖音的 playwm 端点带水印，换成 play 就是原始无水印流。"""
    return url.replace("/playwm/", "/play/") if url else url


def _ts(sec) -> str:
    try:
        return datetime.fromtimestamp(int(sec), CST).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def parse_item(item: dict, aweme_id: str) -> dict:
    """把平台原始 item 归一化成稳定结构（只保留我们承诺的字段）。"""
    author = item.get("author") or {}
    stats = item.get("statistics") or {}
    video = item.get("video") or {}
    music = item.get("music") or {}

    play_list = ((video.get("play_addr") or {}).get("url_list")) or []
    play_wm = play_list[0] if play_list else ""
    cover_list = ((video.get("cover") or {}).get("url_list")) or []
    avatar_list = ((author.get("avatar_thumb") or {}).get("url_list")) or []

    hashtags = []
    for t in item.get("text_extra") or []:
        name = t.get("hashtag_name")
        if name:
            hashtags.append(name)

    images = []
    for img in (item.get("images") or []):
        urls = (img.get("url_list") if isinstance(img, dict) else None) or []
        if urls:
            images.append(urls[0])

    return {
        "aweme_id": aweme_id,
        "desc": item.get("desc") or "",
        "hashtags": hashtags,
        "create_time": item.get("create_time"),
        "create_time_str": _ts(item.get("create_time")),
        "aweme_type": item.get("aweme_type"),
        "is_album": bool(images),
        "author": {
            "nickname": author.get("nickname") or "",
            "unique_id": author.get("unique_id") or "",
            "short_id": author.get("short_id") or "",
            "sec_uid": author.get("sec_uid") or "",
            "signature": author.get("signature") or "",
            "avatar": avatar_list[0] if avatar_list else "",
        },
        "stats": {
            "digg": stats.get("digg_count"),
            "comment": stats.get("comment_count"),
            "share": stats.get("share_count"),
            "collect": stats.get("collect_count"),
            "play": stats.get("play_count"),
        },
        "video": {
            "duration_ms": video.get("duration"),
            "duration_sec": round((video.get("duration") or 0) / 1000, 1),
            "width": video.get("width"),
            "height": video.get("height"),
            "uri": ((video.get("play_addr") or {}).get("uri")) or "",
            "play_url": _no_watermark(play_wm),
            "play_url_watermark": play_wm,
            "cover": cover_list[0] if cover_list else "",
        },
        "music": {
            "title": music.get("title") or "",
            "author": music.get("author") or "",
            "mid": music.get("mid") or "",
        },
        "images": images,
        "links": {
            "web": WEB_TMPL.format(aweme_id=aweme_id),
            "share": SHARE_TMPL.format(aweme_id=aweme_id),
            "author_home": ("https://www.douyin.com/user/%s" % author.get("sec_uid"))
            if author.get("sec_uid")
            else "",
        },
    }


def fetch(share_text: str, timeout: int = 30) -> dict:
    """对外主入口：任意分享文本 -> 归一化视频信息 dict。"""
    raw = fetch_raw(share_text, timeout=timeout)
    page = _pick_video_page(raw["data"])
    res = page.get("videoInfoRes") or {}
    items = res.get("item_list") or []
    if not items:
        code = res.get("status_code")
        raise DouyinError("平台没返回视频数据（status_code=%s；可能视频已删除或需要登录）" % code)
    info = parse_item(items[0], raw["aweme_id"])
    info["links"]["final_url"] = raw["final_url"]
    return info
