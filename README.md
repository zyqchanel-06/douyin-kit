# douyin-kit

抖音视频内容提取工具箱：**分享链接 → 结构化信息 + 无水印直链 + 视频里说的话**。

- 解析核心零第三方依赖（纯标准库），任何 Python 3.8+ 都能跑
- 语音转写全离线（faster-whisper + 本地模型），不花一分钱
- 视频解码用 PyAV，**不需要安装 ffmpeg.exe**

## 快速开始

```bash
# 只用解析（零依赖，Python 3.8+）
python douyin.py "https://v.douyin.com/xxxxx/" --json

# 全套：下载 + 本地转写 + Markdown 报告
python douyin.py "https://v.douyin.com/xxxxx/" --download --transcribe --md --json
```

| 参数 | 作用 |
| --- | --- |
| `--json` | 输出归一化 JSON 到 `out/<id>.json` |
| `--download` | 下载无水印视频 + 封面 |
| `--transcribe` | 本地语音转文字（含时间轴） |
| `--md` | 生成 Markdown 报告 |
| `--out DIR` | 指定输出目录（默认 `out/`） |
| `--python PATH` | 指定带 faster-whisper 的解释器 |
| `--quiet` | 不打印摘要 |

## 它是怎么工作的

```
短链 v.douyin.com/xxx
  └─ 302 → www.iesdouyin.com/share/video/{aweme_id}/
       └─ HTML 内嵌 window._ROUTER_DATA（服务端渲染的完整 videoInfoRes）
            └─ 归一化 → 元数据 / 统计 / 无水印直链 / 封面 / 话题
                 └─ PyAV 解码音轨 → faster-whisper → 文稿 + 时间轴
```

**为什么不直连 PC 站**：`www.douyin.com` 的视频页由 JS 虚拟机渲染并带签名校验，纯 HTTP 拿不到数据；移动分享页是 SSR 的，数据直接躺在 HTML 里，无需签名算法、无需 Cookie、无需数据库。

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
├─ skills/douyin-fetch/     # DSH 技能定义
└─ out/                     # 输出目录
```

## 作为 Python 库

```python
from douyin_kit import fetcher
info = fetcher.fetch("https://v.douyin.com/xxxxx/")
print(info["desc"], info["video"]["play_url"])
```

## 许可与边界

仅供个人学习、研究和内容归档使用。请遵守抖音的用户协议与相关法律，不要用于批量抓取、商业转载或规避平台风控的用途。解析依赖平台公开的分享页，平台改版后可能失效——失效时的修复点是 `fetcher.extract_router_data`。
