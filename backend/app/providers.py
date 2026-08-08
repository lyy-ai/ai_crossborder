"""AI 能力 Provider 层 —— 本地引擎 / 阿里云百炼(Model Router) 双引擎切换。

配置：backend/providers.json
  - bailian_api_key: 百炼 Key 发放后填这里
  - providers.llm/image/video/tts: "local" 或 "bailian"，可按模块混合
  - bailian_models: 各能力对应的百炼模型名

接口与 clients.py 保持一致，pipeline 只调本模块。
注意：百炼视频/语音端点按 OpenAI 兼容惯例编写，Key 到手后请对照
《Model Router API 完整文档》核对 bailian_video / bailian_tts 两处路径与字段。
"""
import asyncio
import base64
import json
import os

import httpx

from . import clients

CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "providers.json")

_cache = {"mtime": 0, "cfg": None}


def cfg():
    mtime = os.path.getmtime(CFG_PATH)
    if _cache["cfg"] is None or mtime != _cache["mtime"]:
        _cache["cfg"] = json.load(open(CFG_PATH, encoding="utf-8"))
        _cache["mtime"] = mtime
    return _cache["cfg"]


def mode(capability: str) -> str:
    c = cfg()
    p = c.get("providers", {}).get(capability, "local")
    if p == "bailian" and not c.get("bailian_api_key"):
        return "local"
    return p


def _bailian_headers():
    return {"Authorization": f"Bearer {cfg()['bailian_api_key']}",
            "Content-Type": "application/json"}


def _bailian_url(path):
    return cfg()["bailian_base_url"].rstrip("/") + path


def _bailian_model(capability):
    return cfg()["bailian_models"][capability]


# ---------------- LLM ----------------

async def llm_json(system: str, user: str, retries: int = 3, timeout: float = 300.0,
                   max_tokens: int = 3000):
    if mode("llm") == "bailian":
        return await bailian_llm_json(system, user, retries, timeout, max_tokens)
    return await clients.llm_json(system, user, retries, timeout, max_tokens)


async def bailian_llm_json(system, user, retries, timeout, max_tokens):
    last = None
    for _ in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                r = await cli.post(_bailian_url("/chat/completions"),
                                   headers=_bailian_headers(),
                                   json={"model": _bailian_model("llm"),
                                         "messages": [{"role": "system", "content": system},
                                                      {"role": "user", "content": user}],
                                         "temperature": 0.8,
                                         "response_format": {"type": "json_object"},
                                         "max_tokens": max_tokens})
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            last = e
            await asyncio.sleep(2)
    raise RuntimeError(f"bailian llm failed: {last}")


# ---------------- 图像 ----------------

async def txt2img(prompt_en: str, seed: int, prefix: str, width: int = 768, height: int = 1344):
    if mode("image") == "bailian":
        return await bailian_txt2img(prompt_en, seed, width, height)
    return await clients.comfy_txt2img(prompt_en, seed, prefix)


async def bailian_txt2img(prompt_en, seed, width, height):
    size = f"{width}x{height}"
    if width * height > 1024 * 1024 * 2:
        size = "1024x1024"
    async with httpx.AsyncClient(timeout=300) as cli:
        r = await cli.post(_bailian_url("/images/generations"),
                           headers=_bailian_headers(),
                           json={"model": _bailian_model("image"),
                                 "prompt": prompt_en, "n": 1, "size": size})
        r.raise_for_status()
        d = r.json()["data"][0]
        if d.get("b64_json"):
            return base64.b64decode(d["b64_json"])
        img = await cli.get(d["url"])
        img.raise_for_status()
        return img.content


# ---------------- 视频 ----------------

async def video_generate(prompt: str, job_id: str, seed: int = 42, size: str = "480*832",
                         frame_num: int = 65, progress_cb=None):
    if mode("video") == "bailian":
        w, h = size.split("*")
        return await bailian_video(prompt, seed, f"{w}x{h}", frame_num, progress_cb)
    return await clients.video_generate(prompt, job_id, seed, size, frame_num,
                                        progress_cb=progress_cb)


async def bailian_video(prompt, seed, size, frame_num, progress_cb):
    """百炼视频生成（异步任务式）。端点路径待 Key 到手后按官方文档核对。"""
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(_bailian_url("/video/generations"),
                           headers=_bailian_headers(),
                           json={"model": _bailian_model("video"),
                                 "prompt": prompt, "size": size, "seed": seed})
        r.raise_for_status()
        d = r.json()
        task_id = d.get("id") or d.get("task_id")
        t0 = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(10)
            s = await cli.get(_bailian_url(f"/video/generations/{task_id}"),
                              headers=_bailian_headers())
            info = s.json()
            st = info.get("status")
            if progress_cb and info.get("progress"):
                await progress_cb(int(info["progress"] * 50), 50)
            if st in ("succeeded", "completed", "done"):
                url = info.get("video_url") or info.get("output", {}).get("video_url")
                v = await cli.get(url)
                v.raise_for_status()
                path = os.path.join("/data/liyangyang/ai_drama/output/video_clips",
                                    f"bailian_{task_id}.mp4")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(v.content)
                return f"video_clips/bailian_{task_id}.mp4"
            if st in ("failed", "canceled"):
                raise RuntimeError(f"bailian video failed: {info}")
            if asyncio.get_event_loop().time() - t0 > 1800:
                raise TimeoutError("bailian video timeout")


# ---------------- 配音 ----------------

async def tts_generate(text: str, language: str, gender: str, job_id: str, speed: float = 1.05):
    if mode("tts") == "bailian":
        return await bailian_tts(text, language, gender, job_id, speed)
    return await clients.tts_generate(text, language, gender, job_id, speed=speed)


async def bailian_tts(text, language, gender, job_id, speed):
    """百炼 TTS。音色名待 Key 到手后按官方文档核对映射。"""
    voice = {"en": "Cherry", "ja": "Cherry", "zh": "Cherry"}.get(language, "Cherry")
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(_bailian_url("/audio/speech"),
                           headers=_bailian_headers(),
                           json={"model": _bailian_model("tts"),
                                 "input": text, "voice": voice, "speed": speed})
        r.raise_for_status()
        out_dir = "/data/liyangyang/ai_drama/output/audio"
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{job_id}.wav")
        with open(path, "wb") as f:
            f.write(r.content)
        from . import assemble
        dur = await assemble.ffprobe_duration(path)
        return {"job_id": job_id, "audio": f"audio/{job_id}.wav", "duration": dur}


# ---------------- 状态 ----------------

async def service_health():
    h = await clients.service_health()
    c = cfg()
    h["_providers"] = c.get("providers", {})
    h["_bailian_key_set"] = bool(c.get("bailian_api_key"))
    return h
