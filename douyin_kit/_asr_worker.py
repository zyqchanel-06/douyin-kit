# -*- coding: utf-8 -*-
"""转写子进程：在装了 faster-whisper 的解释器里跑，结果写 JSON 文件。

用法: python _asr_worker.py <media> <model_dir> <out_json> [language]
"""
import json
import sys
import time


def main() -> int:
    media, model_dir, out_json = sys.argv[1], sys.argv[2], sys.argv[3]
    lang = sys.argv[4] if len(sys.argv) > 4 else "zh"

    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    load_sec = time.time() - t0

    t1 = time.time()
    segs, info = model.transcribe(
        media,
        language=lang,
        beam_size=1,
        vad_filter=True,
        initial_prompt="以下是普通话的句子，请输出简体中文。",
    )
    seglist = list(segs)
    elapsed = time.time() - t1

    payload = {
        "engine": "faster-whisper",
        "model": model_dir,
        "language": lang,
        "duration": getattr(info, "duration", None),
        "load_sec": round(load_sec, 1),
        "transcribe_sec": round(elapsed, 1),
        "text": "".join(s.text for s in seglist).strip(),
        "segments": [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in seglist
        ],
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
