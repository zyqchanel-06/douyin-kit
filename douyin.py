# -*- coding: utf-8 -*-
"""douyin-kit 便捷入口：python douyin.py "<分享链接或口令>"

等价于 python -m douyin_kit.cli
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from douyin_kit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
