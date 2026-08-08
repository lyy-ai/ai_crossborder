import asyncio
import json
import os
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import clients, db, pipeline, providers

app = FastAPI(title="跨境爆品短视频工厂")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init()

OUT_ROOT = "/data/liyangyang/ai_crossborder/crossborder_video/output"
app.mount("/static/output", StaticFiles(directory=OUT_ROOT), name="output")


@app.middleware("http")
async def log_products_ct(request, call_next):
    if request.url.path == "/api/products" and request.method == "POST":
        ct = request.headers.get("content-type")
        cl = request.headers.get("content-length")
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = receive
        print(f"[dbg] POST /api/products ct={ct} declared_len={cl} actual_len={len(body)}", flush=True)
        print(f"[dbg] body head: {body[:600]!r}", flush=True)
    return await call_next(request)


@app.post("/api/products")
async def create_product(name: str = Form(...), selling_points: str = Form(...),
                         market: str = Form("美国"), category: str = Form("通用"),
                         files: list[UploadFile] = File(default=[])):
    pid = uuid.uuid4().hex[:10]
    if not name.strip() or not selling_points.strip():
        raise HTTPException(400, "产品名称和卖点不能为空")
    pdir = os.path.join(OUT_ROOT, "products", pid)
    os.makedirs(pdir, exist_ok=True)
    images = []
    for i, f in enumerate(files):
        ext = os.path.splitext(f.filename or "img.png")[1] or ".png"
        fname = f"img_{i}{ext}"
        with open(os.path.join(pdir, fname), "wb") as fp:
            fp.write(await f.read())
        images.append(fname)
    if not images:
        raise HTTPException(400, "至少上传 1 张产品图")
    points = [p.strip() for p in selling_points.replace("；", ";").split(";") if p.strip()]
    db.create_product(pid, name, points, market, category, images)
    return {"product_id": pid}


@app.get("/api/products")
async def list_products():
    return {"products": db.list_products()}


@app.delete("/api/products/{pid}")
async def delete_product(pid: str):
    import shutil
    p = db.get_product(pid)
    if not p:
        raise HTTPException(404)
    with db.conn() as c:
        c.execute("DELETE FROM products WHERE id=?", (pid,))
        c.commit()
    shutil.rmtree(os.path.join(OUT_ROOT, "products", pid), ignore_errors=True)
    return {"ok": True}


class JobReq(BaseModel):
    product_id: str
    platforms: list[str] = ["tiktok"]
    languages: list[str] = ["en"]
    variants: int = 2
    voice_gender: str = "female"
    auto_produce: bool = False


@app.post("/api/jobs")
async def create_job(req: JobReq):
    if not db.get_product(req.product_id):
        raise HTTPException(404, "product not found")
    jid = uuid.uuid4().hex[:10]
    db.create_job(jid, req.product_id, req.platforms, req.languages,
                  req.variants, req.voice_gender)
    for platform in req.platforms:
        for lang in req.languages:
            for vi in range(1, req.variants + 1):
                vid = f"{jid}_{platform[:2]}{lang}{vi}"
                db.upsert_video(vid, jid, platform, lang, vi, status="pending")

    async def _run():
        try:
            await pipeline.run_scripts(jid)
            if req.auto_produce:
                pipeline.start_production(jid)
        except Exception:
            pass
    asyncio.create_task(_run())
    return {"job_id": jid}


@app.get("/api/jobs")
async def list_jobs():
    return {"jobs": db.list_jobs()}


@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = db.get_job(jid)
    if not job:
        raise HTTPException(404)
    videos = db.videos_of_job(jid)
    for v in videos:
        v["script"] = json.loads(v["script"]) if v.get("script") else None
        v["compliance"] = json.loads(v["compliance"]) if v.get("compliance") else None
    return {"job": job, "videos": videos, "product": db.get_product(job["product_id"])}


@app.put("/api/videos/{vid}/script")
async def save_script(vid: str, script: dict):
    v = db.get_video(vid)
    if not v:
        raise HTTPException(404)
    pipeline.normalize_script(script)
    db.upsert_video(vid, v["job_id"], v["platform"], v["language"], v["variant"],
                    script=json.dumps(script, ensure_ascii=False))
    return {"ok": True}


@app.post("/api/videos/{vid}/regen_script")
async def regen_script(vid: str):
    v = db.get_video(vid)
    if not v:
        raise HTTPException(404)
    job = db.get_job(v["job_id"])
    product = db.get_product(job["product_id"])

    async def _run():
        try:
            await pipeline.gen_one_script(job, product, v)
            await pipeline.broadcast(v["job_id"], {"type": "video", "video": vid, "stage": "script", "status": "done"})
        except Exception as e:
            await pipeline.broadcast(v["job_id"], {"type": "video", "video": vid, "stage": "script", "status": "failed", "error": str(e)})
    asyncio.create_task(_run())
    return {"ok": True}


@app.post("/api/jobs/{jid}/produce")
async def produce(jid: str):
    ok = pipeline.start_production(jid)
    return {"started": ok}


@app.post("/api/videos/{vid}/reproduce")
async def reproduce(vid: str):
    v = db.get_video(vid)
    if not v or not v.get("script"):
        raise HTTPException(400, "script not ready")
    job = db.get_job(v["job_id"])
    product = db.get_product(job["product_id"])

    async def _run():
        try:
            await pipeline.produce_video(job, product, v)
        except Exception as e:
            db.upsert_video(vid, job["id"], v["platform"], v["language"], v["variant"], status="failed")
            await pipeline.broadcast(job["id"], {"type": "video", "video": vid, "stage": "all", "status": "failed", "error": str(e)})
    asyncio.create_task(_run())
    return {"ok": True}


@app.get("/api/jobs/{jid}/download")
async def download(jid: str):
    videos = [v for v in db.videos_of_job(jid) if v.get("final")]
    if not videos:
        raise HTTPException(404, "no finished videos")
    files = [os.path.join(OUT_ROOT, v["final"]) for v in videos]
    zip_path = os.path.join(pipeline.job_dir(jid), f"{jid}_videos.zip")
    await assemble_zip(files, zip_path)
    return FileResponse(zip_path, filename=f"cbv_videos_{jid}.zip")


async def assemble_zip(files, zip_path):
    import zipfile
    if os.path.exists(zip_path):
        os.remove(zip_path)

    def _z():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            seen = {}
            for f in files:
                name = os.path.basename(os.path.dirname(f)) + "_" + os.path.basename(f)
                z.write(f, name)
    await asyncio.to_thread(_z)


@app.get("/api/health/services")
async def health():
    return await providers.service_health()


@app.get("/api/config/providers")
async def get_providers():
    return providers.cfg()


class ProviderCfg(BaseModel):
    bailian_api_key: str | None = None
    providers: dict | None = None


@app.post("/api/config/providers")
async def set_providers(req: ProviderCfg):
    import json as _json
    cfg = providers.cfg()
    if req.bailian_api_key is not None:
        cfg["bailian_api_key"] = req.bailian_api_key
    if req.providers:
        cfg["providers"].update(req.providers)
    with open(providers.CFG_PATH, "w", encoding="utf-8") as f:
        _json.dump(cfg, f, ensure_ascii=False, indent=2)
    providers._cache["mtime"] = 0
    return {"ok": True, "cfg": providers.cfg()}


@app.websocket("/ws/{jid}")
async def ws(ws: WebSocket, jid: str):
    await ws.accept()
    pipeline.subscribers.setdefault(jid, set()).add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        pipeline.subscribers.get(jid, set()).discard(ws)
