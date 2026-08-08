import json
import os
import sqlite3
import time

DB_PATH = "/data/liyangyang/ai_crossborder/crossborder_video/backend/data/cbv.db"
OUT_ROOT = "/data/liyangyang/ai_crossborder/crossborder_video/output"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS products(
            id TEXT PRIMARY KEY, name TEXT, selling_points TEXT,
            market TEXT, category TEXT, images TEXT, created REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, product_id TEXT, platforms TEXT, languages TEXT,
            variants INTEGER, voice_gender TEXT, status TEXT, stage TEXT,
            created REAL, updated REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS videos(
            id TEXT PRIMARY KEY, job_id TEXT, platform TEXT, language TEXT,
            variant INTEGER, status TEXT, script TEXT, compliance TEXT,
            final TEXT, created REAL, updated REAL)""")
        c.commit()


def _exec(sql, args=()):
    with conn() as c:
        c.execute(sql, args)
        c.commit()


def _one(sql, args=()):
    with conn() as c:
        r = c.execute(sql, args).fetchone()
    return dict(r) if r else None


def _all(sql, args=()):
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def create_product(pid, name, selling_points, market, category, images):
    _exec("INSERT INTO products VALUES(?,?,?,?,?,?,?)",
          (pid, name, json.dumps(selling_points, ensure_ascii=False), market, category,
           json.dumps(images), time.time()))


def get_product(pid):
    p = _one("SELECT * FROM products WHERE id=?", (pid,))
    if p:
        p["selling_points"] = json.loads(p["selling_points"])
        p["images"] = json.loads(p["images"])
    return p


def list_products():
    rows = _all("SELECT * FROM products ORDER BY created DESC")
    for p in rows:
        p["selling_points"] = json.loads(p["selling_points"])
        p["images"] = json.loads(p["images"])
    return rows


def create_job(jid, product_id, platforms, languages, variants, voice_gender):
    now = time.time()
    _exec("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",
          (jid, product_id, json.dumps(platforms), json.dumps(languages),
           variants, voice_gender, "created", "script", now, now))


def update_job(jid, **kw):
    kw["updated"] = time.time()
    sets = ",".join(f"{k}=?" for k in kw)
    _exec(f"UPDATE jobs SET {sets} WHERE id=?", (*kw.values(), jid))


def get_job(jid):
    j = _one("SELECT * FROM jobs WHERE id=?", (jid,))
    if j:
        j["platforms"] = json.loads(j["platforms"])
        j["languages"] = json.loads(j["languages"])
    return j


def list_jobs():
    rows = _all("SELECT * FROM jobs ORDER BY created DESC")
    for j in rows:
        j["platforms"] = json.loads(j["platforms"])
        j["languages"] = json.loads(j["languages"])
    return rows


def upsert_video(vid, job_id, platform, language, variant, **kw):
    now = time.time()
    old = _one("SELECT id FROM videos WHERE id=?", (vid,))
    if old:
        kw["updated"] = now
        sets = ",".join(f"{k}=?" for k in kw)
        _exec(f"UPDATE videos SET {sets} WHERE id=?", (*kw.values(), vid))
    else:
        _exec("INSERT INTO videos VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (vid, job_id, platform, language, variant,
               kw.get("status", "pending"), kw.get("script"), kw.get("compliance"),
               kw.get("final"), now, now))


def get_video(vid):
    return _one("SELECT * FROM videos WHERE id=?", (vid,))


def videos_of_job(jid):
    return _all("SELECT * FROM videos WHERE job_id=? ORDER BY platform, language, variant", (jid,))
