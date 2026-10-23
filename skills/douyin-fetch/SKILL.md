---
name: douyin-fetch
description: 抖音视频内容提取（元数据 / 无水印直链 / 本地语音转写文稿）。当用户发来抖音分享链接或分享口令（v.douyin.com 短链、douyin.com/video/、含「复制打开抖音」字样的整段文本），或说「解析这个抖音」「这个视频讲了什么」「提取抖音文案」「抖音无水印下载」时使用。
---

# 抖音视频内容提取（douyin-kit）

把一条抖音分享链接变成**结构化信息 + 视频里说的话**。解析部分零第三方依赖（纯标准库），转写全离线免费。

**项目根目录**：本文件所在仓库的根目录（即 `skills/` 的上一级）。

## 一条命令

```bash
# 只要元数据 + 无水印直链（秒级）
python douyin.py "<链接或整段口令>"

# 全套：视频 + 封面 + 本地转写文稿 + Markdown 报告 + JSON
python douyin.py "<链接>" --download --transcribe --md --json

# 纯 JSON（给后续处理用）
python douyin.py "<链接>" --json --quiet
```

输入可以是**整段分享口令**（带「3.05 复制打开抖音…」那种干扰文字也行），脚本会自己抠链接。

落盘文件都在 `out/`：`<id>.json` / `<id>.mp4` / `<id>_cover.webp` / `<id>.asr.json` / `<id>.md`

## 能拿到什么

| 类别 | 字段 |
| --- | --- |
| 作品 | `desc`（完整文案）、`hashtags`、`create_time_str`、`aweme_id`、`is_album` |
| 作者 | `nickname`、`unique_id`（抖音号）、`sec_uid`、`signature`、`avatar` |
| 数据 | `digg` 赞 / `comment` 评 / `collect` 藏 / `share` 转 |
| 视频 | `play_url`（**无水印直链**）、`play_url_watermark`、`cover`、`duration_sec`、分辨率 |
| 链接 | `links.web`、`links.share`、`links.author_home` |
| 文稿 | `text` 全文 + `segments` 逐段时间轴（`--transcribe`） |

## 典型工作流

用户丢过来一条视频 → 按这个顺序做：

1. **解析**：`--json` 拿结构化信息，`--transcribe` 拿文稿。
2. **校正文稿**（关键，别跳过）：本地 ASR 用的是 faster-whisper small，**专有名词必错**。实测原文里的错法：
   - `SAS` → 其实是 `SaaS`
   - `智能体育` → 其实是 `智能体`
   - `互承课` → 其实是 `护城河`
   校正时**以原文时间轴为据**，不要凭空改写；拿不准的专有名词（尤其是产品名/项目名）去查证，别猜。
3. **查证视频里提到的项目**（视频常是「某某开源项目火了」）：用 GitHub API 核对，别信口播数字。
   ```bash
   # 搜索候选项目
   https://api.github.com/search/repositories?q=<关键词>&sort=stars&order=desc
   # 核对单个项目（star/最近提交/许可/归档）
   https://api.github.com/repos/<owner>/<repo>
   ```
4. **评估后给建议**：star / 最近提交时间 / 许可证 / 语言 / 是否 archived / 依赖重量，最后明确回答「要不要部署、怎么部署」。若本机没有 Docker，重栈项目要提前说清代价。

## 已知坑（都踩过，别再踩）

- **别直连 PC 站** `www.douyin.com`：视频页是 JS 虚拟机（`_$jsvmprt`）渲染+签名校验，纯 HTTP 拿不到数据。必须走移动分享页 `iesdouyin.com/share/video/{id}/`（服务端渲染，数据就在 HTML 的 `_ROUTER_DATA` 里）。
- **两段式反爬（最容易踩的坑）**：分享页**第一次请求只下发 `ttwid` Cookie 并返回空壳页**（HTML 约 32KB，结构齐全但 `loaderData` 里没有 `videoInfoRes`），**带着这个 Cookie 再请求一次**才返回真数据（约 38KB）。所以重试**必须复用同一个会话**——每次新建会话会永远卡在空壳页。脚本已按此实现（`fetcher.has_video_page` + 同会话重试）。
- **无水印靠端点替换**：分享页给的 `play_addr` 是 `/playwm/`（带水印），换成 `/play/` 就是原始流。脚本已自动处理。
- **链接有时效**：封面 URL 带 `x-expires`；视频直链是即时签发的。要下载就当场下，别存着以后用。
- **可能触发风控**：连续高频请求会返回没有 `_ROUTER_DATA` 的页面。脚本会报「分享页里没有 _ROUTER_DATA」，隔一会重试即可，别无脑循环。
- **图集作品**：`is_album` 为真时视频流为空，图片在 `images` 里，别当成解析失败。
- **转写解释器**：默认自动探测带 faster-whisper 的 Python。可用 `--python` 指定，或设环境变量 `DOUYIN_ASR_PYTHON`。模型目录同理（`--model` / `DOUYIN_ASR_MODEL`）。视频用 PyAV 解码，**不需要额外装 ffmpeg.exe**。
- **转写有缓存**：`<id>.asr.json` 存在时直接复用，想重转先删它。

## 实测验收记录

| 环节 | 结果 |
| --- | --- |
| 短链展开 | `v.douyin.com` → `iesdouyin.com/share/video/{aweme_id}/` |
| 元数据 | 标题/话题/作者/发布时间/四项互动数据全中，与抖音页面一致 |
| 无水印直链 | 302 到 `douyinvod.com` 的 mp4，Content-Type: video/mp4 |
| 下载 | 1.87 MB / 4.9s |
| 转写 | 27.9s 音频 → 9.9s 出稿，212 字，含逐段时间轴 |
| 报告 | Markdown 落盘正常 |
