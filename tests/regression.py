# -*- coding: utf-8 -*-
"""回归测试：四种输入形态都应该解析出同一个视频。"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from douyin_kit import fetcher  # noqa: E402

AID = "7695604320653446443"
CASES = [
    ("纯数字 ID", AID),
    ("PC 站链接", "https://www.douyin.com/video/%s" % AID),
    ("移动分享页", "https://www.iesdouyin.com/share/video/%s/" % AID),
    ("整段分享口令", "3.05 复制打开抖音，看看【算力炼丹炉的作品】号称可以逆向一切的REA 来了！ "
                 "# 科技 # 模... https://v.douyin.com/yRTz0emmZDA/ :5pm 10/20 TyT:/ L@w.fb"),
]

ok = 0
for idx, (name, text) in enumerate(CASES):
    if idx:
        time.sleep(1.5)  # 别把平台惹毛
    try:
        info = fetcher.fetch(text)
        assert info["aweme_id"] == AID, "id 不符：%s" % info["aweme_id"]
        assert info["author"]["nickname"], "缺作者"
        assert "/play/" in info["video"]["play_url"], "无水印直链不对"
        assert info["hashtags"], "缺话题"
        print("PASS  %-12s -> %s | %s" % (name, info["author"]["nickname"], info["desc"][:26]))
        ok += 1
    except Exception as e:
        print("FAIL  %-12s -> %s: %s" % (name, type(e).__name__, e))

print("")
print("通过 %d/%d" % (ok, len(CASES)))
sys.exit(0 if ok == len(CASES) else 1)
