import asyncio
import json
import os
import traceback

from . import assemble, clients, db, prompts, providers

OUT_ROOT = "/data/liyangyang/ai_crossborder/output"
FRAME_NUM = 65

produce_tasks = {}
subscribers = {}


def job_dir(jid):
    d = os.path.join(OUT_ROOT, "jobs", jid)
    os.makedirs(d, exist_ok=True)
    return d


def video_dir(jid, vid):
    d = os.path.join(job_dir(jid), vid)
    os.makedirs(d, exist_ok=True)
    return d


async def broadcast(jid, event):
    event["job_id"] = jid
    for ws in list(subscribers.get(jid, [])):
        try:
            await ws.send_json(event)
        except Exception:
            subscribers[jid].discard(ws)


async def gen_one_script(job, product, video):
    vid = video["id"]
    script = await providers.llm_json(
        prompts.SCRIPT_SYSTEM,
        prompts.script_user(product, video["platform"], video["language"],
                            product["market"], video["variant"]))
    normalize_script(script)
    comp = await providers.llm_json(
        prompts.COMPLIANCE_SYSTEM,
        prompts.compliance_user(script, product["market"], video["language"]),
        max_tokens=1500)
    db.upsert_video(vid, job["id"], video["platform"], video["language"], video["variant"],
                    status="script_done", script=json.dumps(script, ensure_ascii=False),
                    compliance=json.dumps(comp, ensure_ascii=False))
    return vid


def normalize_script(script):
    if not (isinstance(script.get("shots"), list) and script["shots"]):
        for v in script.values():
            if isinstance(v, dict) and isinstance(v.get("shots"), list) and v["shots"]:
                script.clear()
                script.update(v)
                break
    assert isinstance(script.get("shots"), list) and script["shots"], "shots missing"
    script.setdefault("hook", "")
    script.setdefault("cta", "Shop now!")
    script.setdefault("caption", "")
    for s in script["shots"]:
        s.setdefault("type", "scene")
        if s["type"] not in ("scene", "product", "card"):
            s["type"] = "scene"
        s.setdefault("duration", 4)
        s.setdefault("overlay_text", "")
        s.setdefault("vo_line", "")
        if s["type"] == "scene":
            if not s.get("video_prompt"):
                s["video_prompt"] = s.get("scene_prompt", "lifestyle scene, camera slowly pushing in")
            if not s.get("scene_prompt"):
                s["scene_prompt"] = s["video_prompt"]
    if script["shots"] and not script["shots"][0].get("vo_line") and script.get("hook"):
        script["shots"][0]["vo_line"] = script["hook"]


async def run_scripts(jid):
    job = db.get_job(jid)
    product = db.get_product(job["product_id"])
    videos = db.videos_of_job(jid)
    db.update_job(jid, status="running", stage="script")
    await broadcast(jid, {"type": "stage", "stage": "script", "status": "running"})
    try:
        sem = asyncio.Semaphore(4)

        async def _g(v):
            async with sem:
                try:
                    await gen_one_script(job, product, v)
                    await broadcast(jid, {"type": "video", "video": v["id"], "stage": "script", "status": "done"})
                except Exception as e:
                    db.upsert_video(v["id"], jid, v["platform"], v["language"], v["variant"], status="failed")
                    await broadcast(jid, {"type": "video", "video": v["id"], "stage": "script", "status": "failed", "error": str(e)})
                    raise
        await asyncio.gather(*[_g(v) for v in videos])
        db.update_job(jid, status="script_done", stage="script")
        await broadcast(jid, {"type": "stage", "stage": "script", "status": "done"})
    except Exception as e:
        traceback.print_exc()
        db.update_job(jid, status="failed", stage="script")
        await broadcast(jid, {"type": "stage", "stage": "script", "status": "failed", "error": str(e)})
        raise


async def produce_scene_image(jid, vid, idx, shot, product):
    style = clients.MARKET_STYLE.get(product["market"], "modern lifestyle")
    prompt = (f"{shot['scene_prompt']}, {style}, vertical composition, "
              f"professional advertising photography, cinematic lighting, high quality")
    seed = abs(hash(vid + str(idx))) % (2**31)
    img = await providers.txt2img(prompt, seed, f"{vid}_scene{idx}")
    path = os.path.join(OUT_ROOT, "jobs", jid, vid, f"scene{idx}.png")
    with open(path, "wb") as f:
        f.write(img)
    return path


async def produce_clip(jid, vid, idx, shot, product):
    d = video_dir(jid, vid)
    out = os.path.join(d, f"shot{idx}.mp4")
    dur = float(shot.get("duration", 4))
    if shot["type"] == "scene":
        seed = abs(hash(vid + str(idx) + "v")) % (2**31)
        rel = await providers.video_generate(shot["video_prompt"], f"{vid}_s{idx}", seed=seed)
        src = os.path.join("/data/liyangyang/ai_drama/output", rel)
        await assemble.run(["ffmpeg", "-y", "-i", src, "-c", "copy", out])
    elif shot["type"] == "product":
        images = product["images"]
        img = os.path.join(OUT_ROOT, "products", product["id"], images[idx % len(images)])
        await assemble.kenburns(img, out, dur)
    else:
        await assemble.text_card(shot.get("overlay_text") or product["name"], out, dur,
                                 sub=shot.get("vo_line", ""))
    return out


async def produce_voice(vid, idx, shot, language, gender):
    line = shot.get("vo_line", "").strip()
    if not line:
        return None
    r = await providers.tts_generate(line, language, gender, f"{vid}_s{idx}")
    return os.path.join("/data/liyangyang/ai_drama/output", r["audio"])


async def produce_video(job, product, video):
    jid, vid = job["id"], video["id"]
    script = json.loads(video["script"])
    lang, gender = video["language"], job.get("voice_gender", "female")
    d = video_dir(jid, vid)

    db.upsert_video(vid, jid, video["platform"], lang, video["variant"], status="producing_scene")
    scene_paths = {}
    for i, shot in enumerate(script["shots"]):
        if shot["type"] == "scene":
            scene_paths[i] = await produce_scene_image(jid, vid, i, shot, product)
            await broadcast(jid, {"type": "video", "video": vid, "stage": "scene",
                                  "status": "progress", "shot": i})

    db.upsert_video(vid, jid, video["platform"], lang, video["variant"], status="producing_clip")
    await clients.comfy_free()
    clip_paths = []
    for i, shot in enumerate(script["shots"]):
        p = await produce_clip(jid, vid, i, shot, product)
        clip_paths.append(p)
        await broadcast(jid, {"type": "video", "video": vid, "stage": "clip",
                              "status": "progress", "shot": i})

    db.upsert_video(vid, jid, video["platform"], lang, video["variant"], status="producing_voice")
    wav_paths = []
    for i, shot in enumerate(script["shots"]):
        w = await produce_voice(vid, i, shot, lang, gender)
        wav_paths.append(w)
        await broadcast(jid, {"type": "video", "video": vid, "stage": "voice",
                              "status": "progress", "shot": i})

    db.upsert_video(vid, jid, video["platform"], lang, video["variant"], status="merging")
    merged, events, t = [], [], 0.0
    for i, shot in enumerate(script["shots"]):
        merged_path = os.path.join(d, f"merged{i}.mp4")
        dur = await assemble.merge_shot(clip_paths[i], wav_paths[i], merged_path)
        if shot.get("overlay_text"):
            events.append({"start": t + 0.15, "end": t + dur - 0.1,
                           "style": "Overlay", "text": shot["overlay_text"]})
        if shot.get("vo_line"):
            events.append({"start": t + 0.15, "end": t + dur - 0.1,
                           "style": "Sub", "text": shot["vo_line"]})
        merged.append(merged_path)
        t += dur

    final = os.path.join(d, "final.mp4")
    await assemble.concat_and_subtitle(merged, events, video["platform"], final)
    rel = os.path.relpath(final, OUT_ROOT)
    db.upsert_video(vid, jid, video["platform"], lang, video["variant"],
                    status="done", final=rel)
    await broadcast(jid, {"type": "video", "video": vid, "stage": "all", "status": "done",
                          "final": rel})


async def run_production(jid):
    job = db.get_job(jid)
    product = db.get_product(job["product_id"])
    videos = [v for v in db.videos_of_job(jid) if v["status"] not in ("done",)]
    db.update_job(jid, status="running", stage="production")
    await broadcast(jid, {"type": "stage", "stage": "production", "status": "running"})
    try:
        for v in videos:
            if not v.get("script"):
                db.upsert_video(v["id"], jid, v["platform"], v["language"], v["variant"], status="failed")
                continue
            try:
                await produce_video(job, product, v)
            except Exception as e:
                traceback.print_exc()
                db.upsert_video(v["id"], jid, v["platform"], v["language"], v["variant"], status="failed")
                await broadcast(jid, {"type": "video", "video": v["id"], "stage": "all",
                                      "status": "failed", "error": str(e)})
        left = [v for v in db.videos_of_job(jid) if v["status"] == "failed"]
        db.update_job(jid, status="done" if not left else "partial", stage="done")
        await broadcast(jid, {"type": "job", "status": "done" if not left else "partial"})
    finally:
        produce_tasks.pop(jid, None)


def start_production(jid):
    if jid in produce_tasks and not produce_tasks[jid].done():
        return False
    produce_tasks[jid] = asyncio.create_task(run_production(jid))
    return True
