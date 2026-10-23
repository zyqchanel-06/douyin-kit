# douyin-kit

**抖音视频内容提取工具箱：分享链接 → 结构化信息 + 无水印直链 + 视频里说的话。**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

- 解析核心**零第三方依赖**（纯标准库），任何 Python 3.8+ 都能跑
- 语音转写**全离线**（faster-whisper + 本地模型），不花一分钱
- 视频解码用 PyAV，**不需要安装 ffmpeg.exe**
- 输出 JSON / Markdown / 视频 / 封面 / 逐段时间轴文稿

---

## 安装

```bash
git clone https://github.com/zyqchanel-06/douyin-kit.git
cd douyin-kit
```

解析功能不需要安装任何依赖。只有启用 `--transcribe` 时才需要：

```bash
pip install faster-whisper
```

## 快速开始

```bash
# 只要元数据 + 无水印直链（秒级）
python douyin.py "https://v.douyin.com/xxxxx/"

# 全套：视频 + 封面 + 本地转写文稿 + Markdown 报告 + JSON
python douyin.py "https://v.douyin.com/xxxxx/" --download --transcribe --md --json

# 纯 JSON（给后续处理用）
python douyin.py "https://v.douyin.com/xxxxx/" --json --quiet
```

输入可以是**整段分享口令**（带「3.05 复制打开抖音…」那种干扰文字也行），脚本会自己抠链接；也可以直接传 19 位视频 ID。

### 参数

| 参数 | 作用 |
| --- | --- |
| `--json` | 输出归一化 JSON 到 `out/<id>.json` |
| `--download` | 下载无水印视频 + 封面 |
| `--transcribe` | 本地语音转文字（含时间轴） |
| `--md` | 生成 Markdown 报告 |
| `--out DIR` | 指定输出目录（默认 `out/`） |
| `--python PATH` | 指定带 faster-whisper 的解释器 |
| `--quiet` | 不打印摘要 |

### 输出字段

| 类别 | 字段 |
| --- | --- |
| 作品 | `desc`（完整文案）、`hashtags`、`create_time_str`、`aweme_id`、`is_album` |
| 作者 | `nickname`、`unique_id`（抖音号）、`sec_uid`、`signature`、`avatar` |
| 数据 | `digg` 赞 / `comment` 评 / `collect` 藏 / `share` 转 |
| 视频 | `play_url`（**无水印直链**）、`play_url_watermark`、`cover`、`duration_sec`、分辨率 |
| 链接 | `links.web`、`links.share`、`links.author_home` |
| 文稿 | `text` 全文 + `segments` 逐段时间轴 |

## 它是怎么工作的

```
短链 v.douyin.com/xxx
  └─ 302 → www.iesdouyin.com/share/video/{aweme_id}/
       └─ HTML 内嵌 window._ROUTER_DATA（服务端渲染的完整 videoInfoRes）
            └─ 归一化 → 元数据 / 统计 / 无水印直链 / 封面 / 话题
                 └─ PyAV 解码音轨 → faster-whisper → 文稿 + 时间轴
```

**为什么不直连 PC 站**：`www.douyin.com` 的视频页由 JS 虚拟机（`_$jsvmprt`）渲染并带签名校验，纯 HTTP 拿不到数据；移动分享页是 SSR 的，数据直接躺在 HTML 里，无需签名算法、无需 Cookie、无需数据库。

### 两个实现上的坑（已处理）

1. **两段式反爬**：分享页第一次请求只下发 `ttwid` Cookie 并返回空壳页（HTML 约 32KB，结构齐全但 `loaderData` 里没有 `videoInfoRes`），**带着这个 Cookie 再请求一次**才返回真数据。重试必须复用同一个会话，否则永远卡在空壳页。
2. **无水印靠端点替换**：分享页给的 `play_addr` 是 `/playwm/`（带水印），换成 `/play/` 即原始流。

## 目录

```
douyin-kit/
├─ douyin.py                # 便捷入口
├─ douyin_kit/
│  ├─ fetcher.py            # 解析核心（短链展开 / _ROUTER_DATA / 归一化）
│  ├─ media.py              # 视频与封面下载
│  ├─ asr.py                # 转写调度（自动探测解释器）
│  ├─ _asr_worker.py        # 转写子进程
│  ├─ report.py             # Markdown 报告
│  └─ cli.py                # 命令行
├─ skills/douyin-fetch/     # DSH 技能定义（给 Agent 用的使用说明）
├─ tests/regression.py      # 回归测试
└─ out/                     # 输出目录（已 gitignore）
```

## 作为 Python 库

```python
from douyin_kit import fetcher

info = fetcher.fetch("https://v.douyin.com/xxxxx/")
print(info["desc"], info["video"]["play_url"])
```

## 转写配置

`asr.py` 会依次尝试：当前解释器 → 环境变量指定 → 常见虚拟环境位置。

| 环境变量 | 作用 |
| --- | --- |
| `DOUYIN_ASR_PYTHON` | 带 faster-whisper 的解释器路径（多个用 `;` 分隔） |
| `DOUYIN_ASR_MODEL` | 本地 faster-whisper 模型目录 |

也可以用 `--python` / `--model` 单次指定。转写结果会缓存成 `<id>.asr.json`，想重转先删掉它。

## 已知限制

- **链接有时效**：封面 URL 带 `x-expires`，视频直链即时签发。要下载就当场下。
- **可能触发风控**：连续高频请求会返回没有 `_ROUTER_DATA` 的页面，隔一会重试即可，别无脑循环。
- **图集作品**：`is_album` 为真时视频流为空，图片在 `images` 里，不是解析失败。
- **平台改版会失效**：修复点集中在 `fetcher.extract_router_data`。
- **转写专有名词会错**：small 模型对产品名/项目名识别不准（实测 `SaaS`→`SAS`、`智能体`→`智能体育`、`护城河`→`互承课`），需要人工校正。

## 许可与边界

MIT License。**仅供个人学习、研究和内容归档使用。** 请遵守抖音的用户协议与相关法律法规，不要用于批量抓取、商业转载或规避平台风控的用途。

解析依赖平台公开的分享页，平台改版后可能失效——这是这类工具的常态，欢迎提 issue 一起修。
