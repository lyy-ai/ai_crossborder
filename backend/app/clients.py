import asyncio
import json

import httpx

LLM_URL = "http://127.0.0.1:10048/v1/chat/completions"
COMFY_URL = "http://127.0.0.1:10047"
VIDEO_URL = "http://127.0.0.1:10050"
TTS_URL = "http://127.0.0.1:10049"

WF_PATH = "/data/liyangyang/ai_crossborder/crossborder_video/workflows/sdxl_txt2img.json"

MARKET_STYLE = {
    "美国": "american lifestyle, bright natural lighting, modern home",
    "欧洲": "european minimalist lifestyle, soft daylight, scandinavian interior",
    "日本": "japanese lifestyle, clean minimal interior, soft natural light",
    "东南亚": "southeast asian lifestyle, vibrant colors, tropical daylight",
    "中东": "middle eastern modern lifestyle, warm elegant interior",
}


async def llm_json(system: str, user: str, retries: int = 3, timeout: float = 300.0, max_tokens: int = 3000):
    last = None
    for _ in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(LLM_URL, json={
                    "model": "qwen35-9b",
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                    "temperature": 0.8,
                    "response_format": {"type": "json_object"},
                    "max_tokens": max_tokens,
                })
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            last = e
            await asyncio.sleep(2)
    raise RuntimeError(f"LLM failed: {last}")


async def comfy_txt2img(prompt_en: str, seed: int, prefix: str, timeout: float = 300.0):
    wf = json.load(open(WF_PATH))
    wf["6"]["inputs"]["text"] = prompt_en
    wf["3"]["inputs"]["seed"] = seed
    wf["9"]["inputs"]["filename_prefix"] = prefix
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(f"{COMFY_URL}/prompt", json={"prompt": wf})
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]
        t0 = asyncio.get_event_loop().time()
        img = None
        while True:
            await asyncio.sleep(2)
            h = await cli.get(f"{COMFY_URL}/history/{prompt_id}")
            data = h.json()
            if prompt_id in data and data[prompt_id].get("status", {}).get("completed"):
                for node in data[prompt_id]["outputs"].values():
                    if "images" in node:
                        img = node["images"][0]
                        break
                break
            if asyncio.get_event_loop().time() - t0 > timeout:
                raise TimeoutError("comfy timeout")
        if not img:
            raise RuntimeError("no image output")
        v = await cli.get(f"{COMFY_URL}/view", params={
            "filename": img["filename"], "subfolder": img.get("subfolder", ""),
            "type": img.get("type", "output")})
        v.raise_for_status()
        return v.content


async def comfy_free():
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            await cli.post(f"{COMFY_URL}/free", json={"unload_models": True, "free_memory": True})
    except Exception:
        pass


async def video_generate(prompt: str, job_id: str, seed: int = 42, size: str = "480*832",
                         frame_num: int = 65, timeout: float = 2400.0, progress_cb=None):
    async with httpx.AsyncClient(timeout=60) as cli:
        r = await cli.post(f"{VIDEO_URL}/generate", json={
            "prompt": prompt, "job_id": job_id, "seed": seed,
            "size": size, "frame_num": frame_num})
        r.raise_for_status()
        t0 = asyncio.get_event_loop().time()
        errors = 0
        while True:
            await asyncio.sleep(5)
            try:
                s = await cli.get(f"{VIDEO_URL}/progress/{job_id}")
                info = s.json()
                errors = 0
            except Exception:
                errors += 1
                if errors > 12:
                    raise
                continue
            if progress_cb and info.get("step"):
                await progress_cb(info["step"], info.get("total_steps", 50))
            if info.get("status") == "done":
                return info["video"]
            if info.get("status") == "failed":
                raise RuntimeError(f"video failed: {info.get('error', '')[-400:]}")
            if asyncio.get_event_loop().time() - t0 > timeout:
                raise TimeoutError("video timeout")


VOICE_MAP = {
    ("en", "male"): "英文男", ("en", "female"): "英文女",
    ("ja", "male"): "日语男", ("ja", "female"): "日语男",
    ("zh", "male"): "中文男", ("zh", "female"): "中文女",
}


async def tts_generate(text: str, language: str, gender: str, job_id: str, speed: float = 1.05, retries: int = 2):
    spk = VOICE_MAP.get((language, gender), "英文女" if gender == "female" else "英文男")
    last = None
    for _ in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120) as cli:
                r = await cli.post(f"{TTS_URL}/tts", json={
                    "text": text, "spk": spk, "job_id": job_id, "speed": speed})
                r.raise_for_status()
                return r.json()
        except Exception as e:
            last = e
            await asyncio.sleep(1)
    raise RuntimeError(f"tts failed: {last}")


async def service_health():
    out = {}
    async with httpx.AsyncClient(timeout=5) as cli:
        for name, url in [("llm", "http://127.0.0.1:10048/v1/models"),
                          ("comfy", f"{COMFY_URL}/system_stats"),
                          ("video", f"{VIDEO_URL}/health"),
                          ("tts", f"{TTS_URL}/health")]:
            try:
                r = await cli.get(url)
                out[name] = r.status_code == 200
            except Exception:
                out[name] = False
    return out
