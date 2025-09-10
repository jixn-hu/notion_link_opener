import os
import sys
import base64
import hmac
import hashlib
import sqlite3
import time
import random
import string
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ================== 配置 ==================
HOST = "127.0.0.1"
HOST = "10.17.214.31"
PORT = 6060
# 修改为更复杂的密钥，或用环境变量 NFO_SECRET 提供
SECRET_KEY = os.environ.get("NFO_SECRET", "change_me_to_a_long_random_secret")

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "links.db"

ACTIONS = {"open", "reveal"}


# ================== 工具函数 ==================
def b64url_encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")


def b64url_decode(s: str) -> str:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode("ascii")).decode("utf-8")


def sign(path_b64: str, action: str) -> str:
    msg = f"path={path_b64}&action={action}"
    return hmac.new(SECRET_KEY.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_sig(path_b64: str, sig_: str, action: str) -> None:
    expect = sign(path_b64, action)
    if not hmac.compare_digest(expect, sig_):
        raise HTTPException(status_code=400, detail="签名错误")


def open_path(p: Path, action: str = "open") -> None:
    if sys.platform.startswith("win"):
        if action == "reveal":
            if p.is_dir():
                subprocess.run(["explorer", str(p)], check=False)
            else:
                subprocess.run(["explorer", "/select,", str(p)], check=False)
        else:
            if p.is_dir():
                subprocess.run(["explorer", str(p)], check=False)
            else:
                os.startfile(str(p))  # type: ignore
    elif sys.platform == "darwin":
        if action == "reveal":
            subprocess.run(["open", "-R", str(p)], check=False)
        else:
            subprocess.run(["open", str(p)], check=False)
    else:
        if action == "reveal" and p.is_file():
            subprocess.run(["xdg-open", str(p.parent)], check=False)
        else:
            subprocess.run(["xdg-open", str(p)], check=False)


# ================== DB ==================
def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            token TEXT PRIMARY KEY,
            url   TEXT NOT NULL,
            path  TEXT,
            action TEXT,
            created_at INTEGER NOT NULL
        )
        """)
        # 兼容老版本的升级：如果缺少列则添加
        cols = {row[1] for row in conn.execute("PRAGMA table_info(links)")}
        if "path" not in cols:
            conn.execute("ALTER TABLE links ADD COLUMN path TEXT")
        if "action" not in cols:
            conn.execute("ALTER TABLE links ADD COLUMN action TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_created_at ON links(created_at DESC)")
        conn.commit()
    finally:
        conn.close()


def save_short_link(token: str, url: str, path_raw: str, action: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO links (token, url, path, action, created_at) VALUES (?, ?, ?, ?, ?)",
            (token, url, path_raw, action, int(time.time()))
        )
        conn.commit()
    finally:
        conn.close()


def get_link_url(token: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT url FROM links WHERE token = ?", (token,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def list_links(limit: int = 500) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "SELECT token, url, path, action, created_at FROM links ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        return [
            {"token": r[0], "url": r[1], "path": r[2] or "", "action": r[3] or "", "created_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_link(token: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("DELETE FROM links WHERE token = ?", (token,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def gen_token(n: int = 7) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


# ================== Pydantic ==================
class BatchItem(BaseModel):
    target: str
    alias: Optional[str] = None


class BatchReq(BaseModel):
    items: List[BatchItem]
    action: str = "open"


# ================== APP ==================
ensure_db()
app = FastAPI(title="Notion Folder Opener", docs_url=None, redoc_url=None)

# 静态资源
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/static/index.html")


@app.get("/open", response_class=PlainTextResponse)
def open_from_link(
    path: str = Query(..., description="Base64-URL 编码的绝对路径"),
    sig: str = Query(..., description="签名(HMAC-SHA256)"),
    action: str = Query("open", description="open | reveal"),
):
    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="action 不合法（open|reveal）")

    verify_sig(path, sig, action)
    raw = b64url_decode(path)
    p = Path(raw)

    if not p.exists():
        raise HTTPException(status_code=404, detail="路径不存在")

    try:
        open_path(p, action)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开失败: {e}")

    return f"已请求 {action}: {p}"


@app.get("/gen", response_class=JSONResponse)
def gen_link(
    target: str = Query(..., description="绝对路径，例如 D:/CODE/fastapi_app"),
    action: str = Query("open", description="open | reveal"),
    alias: Optional[str] = Query(None, description="可选：自定义短链 token（字母数字）"),
):
    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="action 不合法（open|reveal）")

    # 规范化
    t = target.strip().strip('"').strip("'").replace("\\", "/")
    p = Path(t)

    if not p.is_absolute():
        raise HTTPException(status_code=400, detail="必须是绝对路径")
    if not p.exists():
        raise HTTPException(status_code=404, detail="路径不存在")

    path_b64 = b64url_encode(str(p))
    sig_ = sign(path_b64, action)
    full_url = f"http://{HOST}:{PORT}/open?path={path_b64}&action={action}&sig={sig_}"

    token = alias if (alias and alias.isalnum()) else gen_token()
    save_short_link(token, full_url, str(p), action)
    short_url = f"http://{HOST}:{PORT}/s/{token}"

    return {"full_url": full_url, "short_url": short_url, "token": token}


@app.post("/gen_batch", response_class=JSONResponse)
def gen_batch(req: BatchReq):
    action = req.action or "open"
    if action not in ACTIONS:
        raise HTTPException(status_code=400, detail="action 不合法（open|reveal）")

    results: List[Dict[str, Any]] = []

    for item in req.items:
        raw = (item.target or "").strip().strip('"').strip("'").replace("\\", "/")
        alias = (item.alias or "").strip() or None

        if not raw:
            results.append({"target": item.target, "error": "空路径"})
            continue

        try:
            p = Path(raw)
            if not p.is_absolute():
                results.append({"target": raw, "alias": alias, "error": "必须是绝对路径"})
                continue
            if not p.exists():
                results.append({"target": raw, "alias": alias, "error": "路径不存在"})
                continue

            path_b64 = b64url_encode(str(p))
            sig_ = sign(path_b64, action)
            full_url = f"http://{HOST}:{PORT}/open?path={path_b64}&action={action}&sig={sig_}"
            token = alias if (alias and alias.isalnum()) else gen_token()
            save_short_link(token, full_url, str(p), action)
            short_url = f"http://{HOST}:{PORT}/s/{token}"

            results.append({
                "target": str(p),
                "alias": alias,
                "token": token,
                "short_url": short_url,
                "full_url": full_url
            })
        except Exception as e:
            results.append({"target": raw, "alias": alias, "error": str(e)})

    return {"action": action, "items": results}


@app.get("/s/{token}", include_in_schema=False)
def short_redirect(token: str):
    url = get_link_url(token)
    if not url:
        raise HTTPException(status_code=404, detail="短链不存在")
    return RedirectResponse(url=url, status_code=302)


# ===== 历史列表 API（前端 links.html 调用）=====
@app.get("/api/links", response_class=JSONResponse)
def api_list_links(limit: int = Query(500, ge=1, le=5000)):
    return {"items": list_links(limit=limit)}


@app.delete("/api/links/{token}", response_class=JSONResponse)
def api_delete_link(token: str):
    ok = delete_link(token)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return {"deleted": True}


if __name__ == "__main__":
    print(f"服务已启动: http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
