"""修复已完成视频中的乱码文字卡：重生成 card 镜头并重新合成成片。
用法: /data/liyangyang/qwen35_env/bin/python scripts/repair_cards.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/data/liyangyang/ai_crossborder/backend")
from app import assemble, db


async def repair_video(v):
    script = json.loads(v["script"]) if v.get("script") else None
    if not script:
        return False
    jid = v["job_id"]
    d = os.path.join(assemble.OUT_ROOT, "jobs", jid, v["id"])
    if not os.path.isdir(d):
        return False
    card_idxs = [i for i, s in enumerate(script["shots"]) if s["type"] == "card"]
    if not card_idxs:
        return False
    print(f"[repair] {v['id']} card shots: {card_idxs}")
    for i in card_idxs:
        shot = script["shots"][i]
        out = os.path.join(d, f"shot{i}.mp4")
        await assemble.text_card(shot.get("overlay_text") or "", out,
                                 float(shot.get("duration", 4)),
                                 sub=shot.get("vo_line", ""))
        wav = f"/data/liyangyang/ai_drama/output/audio/{v['id']}_s{i}.wav"
        merged = os.path.join(d, f"merged{i}.mp4")
        await assemble.merge_shot(out, wav if os.path.exists(wav) else None, merged)
    merged_files, events, t = [], [], 0.0
    for i, shot in enumerate(script["shots"]):
        mp = os.path.join(d, f"merged{i}.mp4")
        dur = await assemble.ffprobe_duration(mp)
        if shot.get("overlay_text"):
            events.append({"start": t + 0.15, "end": t + dur - 0.1,
                           "style": "Overlay", "text": shot["overlay_text"]})
        if shot.get("vo_line"):
            events.append({"start": t + 0.15, "end": t + dur - 0.1,
                           "style": "Sub", "text": shot["vo_line"]})
        merged_files.append(mp)
        t += dur
    final = os.path.join(d, "final.mp4")
    await assemble.concat_and_subtitle(merged_files, events, v["platform"], final)
    print(f"[done] {v['id']} -> {final}")
    return True


async def main():
    with db.conn() as c:
        rows = c.execute("SELECT * FROM videos WHERE status='done'").fetchall()
    videos = [dict(r) for r in rows]
    print(f"{len(videos)} done videos")
    n = 0
    for v in videos:
        try:
            if await repair_video(v):
                n += 1
        except Exception as e:
            print(f"[fail] {v['id']}: {e}")
    print(f"repaired {n}")


asyncio.run(main())
