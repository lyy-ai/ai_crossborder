"""AI 能力 Provider 层 —— 本地引擎 / 阿里云百炼 Token Plan 双引擎切换。

配置：backend/providers.json
  - bailian_api_key: Token Plan 专属 Key（sk-sp- 开头）
  - bailian_base_url: OpenAI 兼容地址（LLM 用），图像/视频/语音自动推导
    为同域名原生端点 /api/v1/...
  - providers.llm/image/video/tts: "local" 或 "bailian"，可按模块混合
  - bailian_models: 各能力对应的模型名

接口与 clients.py 保持一致，pipeline 只调本模块。
Token Plan 各能力端点（华北2 北京，专属域名）：
  - LLM:  POST {base_url}/chat/completions            (OpenAI 兼容)
  - 图像: POST /api/v1/services/aigc/multimodal-generation/generation
  - 视频: POST /api/v1/services/aigc/video-generation/video-synthesis (异步, 轮询 /api/v1/tasks/{id})
  - 语音: POST /api/v1/services/audio/tts/SpeechSynthesizer
"""
import asyncio
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


def _native_url(path):
    """把 OpenAI 兼容基地址推导为原生 DashScope 端点：
    https://host/compatible-mode/v1 -> https://host/api/v1 + path"""
    base = cfg()["bailian_base_url"].rstrip("/")
    for suffix in ("/compatible-mode/v1", "/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base + "/api/v1" + path


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
    size = f"{width}*{height}"
    async with httpx.AsyncClient(timeout=300) as cli:
        r = await cli.post(_native_url("/services/aigc/multimodal-generation/generation"),
                           headers=_bailian_headers(),
                           json={"model": _bailian_model("image"),
                                 "input": {"messages": [{"role": "user",
                                                         "content": [{"text": prompt_en}]}]},
                                 "parameters": {"size": size, "seed": seed}})
        r.raise_for_status()
        d = r.json()
        for part in d["output"]["choices"][0]["message"]["content"]:
            if part.get("image"):
                img = await cli.get(part["image"])
                img.raise_for_status()
                return img.content
        raise RuntimeError(f"bailian image: no image in response: {str(d)[:300]}")


# ---------------- 视频 ----------------

async def video_generate(prompt: str, job_id: str, seed: int = 42, size: str = "480*832",
                         frame_num: int = 65, progress_cb=None):
    if mode("video") == "bailian":
        w, h = size.split("*")
        return await bailian_video(prompt, seed, f"{w}x{h}", frame_num, progress_cb)
    return await clients.video_generate(prompt, job_id, seed, size, frame_num,
                                        progress_cb=progress_cb)


async def bailian_video(prompt, seed, size, frame_num, progress_cb):
    """Token Plan 视频生成（happyhorse-1.1-t2v，异步任务：提交→轮询→下载）。"""
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(_native_url("/services/aigc/video-generation/video-synthesis"),
                           headers={**_bailian_headers(), "X-DashScope-Async": "enable"},
                           json={"model": _bailian_model("video"),
                                 "input": {"prompt": prompt},
                                 "parameters": {"resolution": "720P", "ratio": "9:16",
                                                "duration": 5}})
        r.raise_for_status()
        task_id = r.json()["output"]["task_id"]
        t0 = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(10)
            s = await cli.get(_native_url(f"/tasks/{task_id}"),
                              headers=_bailian_headers())
            out = s.json().get("output", {})
            st = out.get("task_status")
            if progress_cb:
                await progress_cb(1, 3)
            if st == "SUCCEEDED":
                v = await cli.get(out["video_url"], timeout=300)
                v.raise_for_status()
                path = os.path.join("/data/liyangyang/ai_drama/output/video_clips",
                                    f"bailian_{task_id}.mp4")
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(v.content)
                return f"video_clips/bailian_{task_id}.mp4"
            if st in ("FAILED", "CANCELED"):
                raise RuntimeError(f"bailian video failed: {str(s.json())[:400]}")
            if asyncio.get_event_loop().time() - t0 > 1800:
                raise TimeoutError("bailian video timeout")


# ---------------- 配音 ----------------

async def tts_generate(text: str, language: str, gender: str, job_id: str, speed: float = 1.05):
    if mode("tts") == "bailian":
        return await bailian_tts(text, language, gender, job_id, speed)
    return await clients.tts_generate(text, language, gender, job_id, speed=speed)


BAILIAN_VOICE_MAP = {
    ("en", "male"): "longanlufeng", ("en", "female"): "longanlingxin",
    ("ja", "male"): "longanlufeng", ("ja", "female"): "longanlingxin",
    ("zh", "male"): "longanlufeng", ("zh", "female"): "longanlingxin",
}


async def bailian_tts(text, language, gender, job_id, speed):
    """Token Plan 语音合成（qwen-audio-3.0-tts-plus，非流式，返回音频 URL）。"""
    voice = BAILIAN_VOICE_MAP.get((language, gender), "longanlingxin")
    payload = {"model": _bailian_model("tts"),
               "input": {"text": text, "voice": voice,
                         "format": "wav", "sample_rate": 24000}}
    if language == "ja":
        payload["input"]["instruction"] = "请用自然流畅的日语朗读"
    async with httpx.AsyncClient(timeout=120) as cli:
        r = await cli.post(_native_url("/services/audio/tts/SpeechSynthesizer"),
                           headers=_bailian_headers(), json=payload)
        r.raise_for_status()
        url = r.json()["output"]["audio"]["url"]
        a = await cli.get(url)
        a.raise_for_status()
        out_dir = "/data/liyangyang/ai_drama/output/audio"
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{job_id}.wav")
        with open(path, "wb") as f:
            f.write(a.content)
        from . import assemble
        dur = await assemble.ffprobe_duration(path)
        return {"job_id": job_id, "audio": f"audio/{job_id}.wav", "duration": dur}


# ---------------- 状态 ----------------

async def service_health():
    h = await clients.service_health()
    c = cfg()
    h["_providers"] = c.get("providers", {})
    h["_bailian_key_set"] = bool(c.get("bailian_api_key"))
    if c.get("bailian_api_key"):
        try:
            async with httpx.AsyncClient(timeout=8) as cli:
                r = await cli.get(_bailian_url("/models"), headers=_bailian_headers())
                h["bailian"] = r.status_code == 200
        except Exception:
            h["bailian"] = False
    return h
