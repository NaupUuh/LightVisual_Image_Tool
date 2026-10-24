# -*- coding: utf-8 -*-
"""Cập nhật LightVisual Image Tool từ GitHub.

Cách dùng:
    python updater.py            # chỉ kiểm tra, in ra bản mới nếu có
    python updater.py --apply    # kiểm tra rồi cập nhật luôn

Cơ chế: đọc version.json trên repo (qua GitHub API để không bị CDN cache),
so với APP_VERSION trong main.py. Nếu repo mới hơn -> tải zip của nhánh
-> ghi đè mã nguồn.

AN TOÀN: KHÔNG bao giờ ghi đè
    - config.json    (cài đặt + API key của người dùng)
    - tiep_tuc.json  (trạng thái lượt chạy dở)
    - output/        (ảnh/video đã tạo)
    - __pycache__/   (rác)
Trước khi ghi đè, tự sao lưu toàn bộ file sắp thay vào _backup_update/.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = "NaupUuh/LightVisual_Image_Tool"
BRANCH = "master"
BASE = Path(__file__).resolve().parent

# Đọc version.json qua API (KHÔNG bị CDN cache như raw.githubusercontent) —
# raw giữ cache ~5 phút nên máy khác bấm ngay sau khi push sẽ thấy bản CŨ.
VERSION_API = (f"https://api.github.com/repos/{REPO}/contents/version.json"
               f"?ref={BRANCH}")
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
# API zipball, KHÔNG dùng codeload (archive/refs/heads/...zip) vì bị cache.
ZIP_URL = f"https://api.github.com/repos/{REPO}/zipball/{BRANCH}"
COMMITS_URL = (f"https://api.github.com/repos/{REPO}/commits?"
               f"sha={BRANCH}&per_page=20")

# Không bao giờ ghi đè / không copy từ repo về
KEEP_NAMES = {"config.json", "config.json.bak", "tiep_tuc.json"}
KEEP_DIRS = {"output", "__pycache__", "_backup_update", ".git",
             "tests/_tmp_test", "tests/_tmp_do"}
KEEP_SUFFIX = {".log", ".bak", ".part"}

TIMEOUT = 25

# File chứng chỉ CA đóng gói kèm tool. Máy Windows cũ / Python không có
# certifi sẽ báo "CERTIFICATE_VERIFY_FAILED" khi gọi HTTPS.
CA_FILE = BASE / "cacert.pem"


def _ssl_context() -> ssl.SSLContext:
    """SSL context bám chắc, thử lần lượt 4 nguồn chứng chỉ."""
    for cafile in (CA_FILE,
                   _certifi_path(),
                   ssl.get_default_verify_paths().cafile):
        if cafile and Path(cafile).is_file():
            try:
                return ssl.create_default_context(cafile=str(cafile))
            except Exception:
                continue
    ctx = _windows_store_context()
    if ctx is not None:
        return ctx
    return ssl.create_default_context()


def _windows_store_context():
    """Gom chứng chỉ từ kho ROOT/CA của Windows thành 1 context."""
    try:
        pems = []
        for store in ("ROOT", "CA"):
            try:
                for cert, enc, trust in ssl.enum_certificates(store):
                    if enc == "x509_asn":
                        pems.append(
                            "-----BEGIN CERTIFICATE-----\n"
                            + base64.encodebytes(cert).decode("ascii").strip()
                            + "\n-----END CERTIFICATE-----\n")
            except Exception:
                continue
        if not pems:
            return None
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cadata="".join(pems))
        return ctx
    except Exception:
        return None


def _certifi_path():
    try:
        import certifi
        return certifi.where()
    except Exception:
        return None


def _urlopen(req, timeout: int = TIMEOUT):
    """urlopen có tự chữa lỗi chứng chỉ."""
    ctxs = [_ssl_context()]
    try:
        ctxs.append(ssl.create_default_context())
    except Exception:
        pass
    last = None
    for ctx in ctxs:
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), ssl.SSLError) or \
                    "CERTIFICATE_VERIFY_FAILED" in str(e):
                last = e
                continue
            raise
    raise last


# ---------------------------------------------------------------- tiện ích

def read_local_version() -> str:
    """Đọc APP_VERSION trong main.py (không import để tránh mở GUI)."""
    f = BASE / "main.py"
    try:
        m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']',
                      f.read_text(encoding="utf-8", errors="replace"),
                      re.MULTILINE)
        return m.group(1) if m else "0.0.0"
    except Exception:
        return "0.0.0"


def _vtuple(v: str) -> tuple:
    """'1.0.2' -> (1, 0, 2). Chịu được hậu tố như '1.0.2-beta'."""
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in parts[:4]) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return _vtuple(remote) > _vtuple(local)


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "LightVisualImageTool-Updater",
                      "Accept": "application/vnd.github+json"})
    with _urlopen(req, timeout=timeout) as r:
        return r.read()


def _read_version_json() -> dict:
    """Đọc version.json từ repo. Ưu tiên API (tươi), lỗi thì dùng raw."""
    last = None
    try:
        j = json.loads(_get(VERSION_API).decode("utf-8", "replace"))
        raw = base64.b64decode(j.get("content", "")).decode("utf-8", "replace")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        last = e
        if e.code == 404:
            raise
    except Exception as e:
        last = e
    try:
        return json.loads(_get(VERSION_URL).decode("utf-8", "replace"))
    except Exception:
        raise last if last is not None else RuntimeError("không đọc được version.json")


# ---------------------------------------------------------------- kiểm tra

def check_update(use_api: bool = True) -> dict:
    """Trả {"ok","has_update","local","remote","notes","zip","commits"}."""
    local = read_local_version()
    out = {"ok": True, "has_update": False, "local": local,
           "remote": local, "notes": "", "zip": ZIP_URL, "commits": []}

    try:
        data = _read_version_json()
        out["remote"] = str(data.get("version") or "").strip()
        out["notes"] = str(data.get("notes") or "").strip()
        out["zip"] = str(data.get("zip") or "").strip() or ZIP_URL
    except urllib.error.HTTPError as e:
        if e.code == 404:
            out.update(ok=False,
                       error="Repo chưa có version.json (hoặc chưa tạo repo).")
            return out
        out.update(ok=False, error="HTTP %d khi đọc version.json" % e.code)
        return out
    except Exception as e:
        out.update(ok=False, error="Không kết nối được GitHub: %s" % e)
        return out

    if not out["remote"]:
        out.update(ok=False, error="version.json thiếu trường 'version'.")
        return out

    out["has_update"] = is_newer(out["remote"], local)

    if use_api and out["has_update"]:
        try:
            cs = json.loads(_get(COMMITS_URL).decode("utf-8", "replace"))
            out["commits"] = [
                (c.get("commit", {}).get("message", "") or "").split("\n")[0]
                for c in cs[:8] if isinstance(c, dict)
            ]
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- cập nhật

def _target_ok(rel: Path) -> bool:
    """True nếu được phép ghi file này (rel = đường dẫn tương đối)."""
    parts = rel.parts
    if not parts:
        return False
    if parts[0] in KEEP_DIRS or parts[0] in KEEP_NAMES:
        return False
    if any("/".join(parts[:i]) in KEEP_DIRS for i in range(1, len(parts))):
        return False
    if rel.name in KEEP_NAMES:
        return False
    if rel.suffix.lower() in KEEP_SUFFIX:
        return False
    return True


def apply_update(zip_url: str = "", log=print) -> dict:
    """Tải zip nhánh và ghi đè mã nguồn. Trả {"ok":bool, ...}."""
    url = zip_url or ZIP_URL
    log("Đang tải %s ..." % url)
    try:
        blob = _get(url, timeout=120)
    except Exception as e:
        return {"ok": False, "error": "Tải thất bại: %s" % e}
    log("Đã tải %.0f KB. Đang giải nén..." % (len(blob) / 1024.0))

    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except Exception as e:
        return {"ok": False, "error": "File zip hỏng: %s" % e}

    names = zf.namelist()
    if not names:
        return {"ok": False, "error": "Zip rỗng."}

    root = names[0].split("/")[0] + "/"
    backup_dir = BASE / "_backup_update" / time.strftime("%Y%m%d_%H%M%S")
    written, skipped, failed = [], [], []

    for info in zf.infolist():
        if info.is_dir():
            continue
        rel = Path(info.filename[len(root):]) if info.filename.startswith(root) \
            else Path(info.filename)
        if not _target_ok(rel):
            skipped.append(str(rel))
            continue
        dst = BASE / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_file():
                b = backup_dir / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b)
            dst.write_bytes(zf.read(info))
            written.append(str(rel))
        except Exception as e:
            failed.append("%s: %s" % (rel, e))

    log("Ghi đè %d file, giữ nguyên %d file." % (len(written), len(skipped)))
    if failed:
        for f in failed[:5]:
            log("  LỖI %s" % f)
        return {"ok": False, "error": "%d file lỗi" % len(failed),
                "written": written, "failed": failed,
                "backup": str(backup_dir)}

    # xoá cache .pyc để Python dùng code mới
    for pc in (BASE / "__pycache__", BASE / "core" / "__pycache__"):
        if pc.is_dir():
            shutil.rmtree(pc, ignore_errors=True)

    new_v = read_local_version()
    return {"ok": True, "written": written, "skipped": skipped,
            "version": new_v, "backup": str(backup_dir)}


def rollback(backup_path: str, log=print) -> dict:
    """Khôi phục từ thư mục _backup_update/<timestamp>."""
    src = Path(backup_path)
    if not src.is_dir():
        return {"ok": False, "error": "Không thấy %s" % src}
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(src)
            dst = BASE / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            n += 1
    log("Đã khôi phục %d file từ %s" % (n, src))
    return {"ok": True, "restored": n}


# ---------------------------------------------------------------- CLI

def main() -> int:
    apply_it = "--apply" in sys.argv or "-y" in sys.argv
    local = read_local_version()
    print("Bản đang dùng : v%s" % local)

    r = check_update()
    if not r["ok"]:
        print("LỖI: %s" % r["error"])
        return 1

    print("Bản trên GitHub: v%s" % r["remote"])
    if not r["has_update"]:
        print("Bạn đang dùng bản mới nhất.")
        return 0

    print("\n>>> CÓ BẢN MỚI v%s" % r["remote"])
    if r["notes"]:
        print("    %s" % r["notes"])
    for c in r["commits"]:
        print("    - %s" % c)

    if not apply_it:
        print("\nThêm --apply để cập nhật.")
        return 0

    res = apply_update(r["zip"], log=print)
    if not res["ok"]:
        print("\nCẬP NHẬT THẤT BẠI: %s" % res["error"])
        return 1
    print("\nĐÃ CẬP NHẬT lên v%s. Mở lại tool để dùng." % res["version"])
    print("(Bản cũ sao lưu ở %s)" % res["backup"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
