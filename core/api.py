# -*- coding: utf-8 -*-
"""Client API lightvisual.studio cho tool tạo ảnh hàng loạt.

Chỉ dùng thư viện chuẩn (urllib) — chạy được trên Python 3.9.
Không import tkinter, không import thư viện ngoài.
"""

import json
import mimetypes
import os
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.request
import uuid

BASE = "https://lightvisual.studio"
UA = "LightVisual_Image_Tool/1.0 (+windows)"

# ---------------------------------------------------------------- model
# public_id, nhãn hiển thị, giá 1 ảnh (đồng), có nhận quality không
DS_MODEL = [
    ("xai/grok-imagine-image-2.0", "Grok Imagine 2.0 — 30đ/ảnh", 30, True),
    ("xai/grok-imagine-image", "Grok Imagine — 10đ/ảnh", 10, False),
    ("google/nano-banana-pro", "Nano Banana Pro — 50đ/ảnh", 50, False),
    ("google/nano-banana-2", "Nano Banana 2.1 — 50đ/ảnh", 50, False),
    ("google/nano-banana-2-lite", "Nano Banana 2 Lite — 50đ/ảnh", 50, False),
]

ASPECT_GROK = ["1:1", "16:9", "9:16", "4:3", "3:4", "20:9", "9:19.5", "auto"]
ASPECT_NANO = ["16:9", "9:16", "1:1"]
DS_QUALITY = ["auto", "low", "medium"]
DS_RES = ["1k", "2k"]

# ---------------------------------------------------------------- video
# public_id, nhãn hiển thị
DS_VIDEO_MODEL = [
    ("xai/grok-imagine-video-1.5", "Grok Imagine Video 1.5"),
]
DS_VIDEO_RES = ["480p", "720p", "1080p"]
DS_VIDEO_ASPECT = ["9:16", "16:9"]
# Nguồn cảnh đầu cho tab video
DS_NGUON = [
    "Chỉ prompt video (không cần ảnh khung)",
    "Ảnh khung → video (giữ nguyên cảnh đầu)",
    "Prompt ảnh → tạo ảnh → video",
    "Folder ảnh tham chiếu → video (mỗi ảnh 1 video, dùng xong xoá)",
]
GIA_VIDEO = {"480p": 40, "720p": 70, "1080p": 125}
PHI_ANH_KHUNG = 15       # mỗi ảnh khung đầu cộng thêm, đồng

# Giới hạn ảnh gửi kèm khi sửa
MAX_ANH_GROK = 5
MAX_ANH_NANO = 3


class LoiAPI(Exception):
    """Lỗi gọi API. .ma = HTTP code (0 nếu lỗi mạng)."""

    def __init__(self, thong_bao, ma=0, loai="", request_id="", cho_lai=0):
        Exception.__init__(self, thong_bao)
        self.thong_bao = thong_bao
        self.ma = ma
        self.loai = loai
        self.request_id = request_id
        self.cho_lai = cho_lai


def la_grok(model):
    return "grok-imagine-image" in (model or "")


def la_nano(model):
    return "nano-banana" in (model or "")


def nhan_model(model):
    for pid, ten, gia, _q in DS_MODEL:
        if pid == model:
            return ten
    return model


def gia_model(model):
    for pid, _ten, gia, _q in DS_MODEL:
        if pid == model:
            return gia
    return 0


def co_quality(model):
    for pid, _ten, _gia, q in DS_MODEL:
        if pid == model:
            return q
    return False


def ds_aspect(model):
    return ASPECT_NANO if la_nano(model) else ASPECT_GROK


def max_anh(model):
    return MAX_ANH_NANO if la_nano(model) else MAX_ANH_GROK


# ---------------------------------------------------------------- http
def _ssl_ctx():
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def _doc_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None


def goi_api(duong_dan, key="", method="GET", body=None, headers=None, timeout=240):
    """Gọi 1 endpoint, trả dict JSON. Ném LoiAPI khi lỗi."""
    url = duong_dan if duong_dan.startswith("http") else BASE + duong_dan
    h = {"User-Agent": UA, "Accept": "application/json"}
    if key:
        h["Authorization"] = "Bearer " + key.strip()
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    ctx = _ssl_ctx()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read()
            ma = r.status
            cho_lai = r.headers.get("Retry-After") or ""
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        ma = e.code
        cho_lai = e.headers.get("Retry-After") if e.headers else ""
        d = _doc_json(raw)
        msg = ""
        loai = ""
        rid = ""
        if isinstance(d, dict) and isinstance(d.get("error"), dict):
            err = d["error"]
            msg = err.get("message") or ""
            loai = err.get("type") or ""
            rid = err.get("request_id") or err.get("id") or ""
        if not msg:
            msg = "HTTP %s" % ma
        giay = 0
        try:
            giay = int(float(cho_lai)) if cho_lai else 0
        except Exception:
            giay = 0
        if ma == 401:
            msg = "API key không hợp lệ hoặc đã hết hạn."
        elif ma == 402:
            msg = "Ví không đủ số dư. " + msg
        elif ma == 429:
            msg = "Hàng đợi máy chủ đang đầy, chờ %ds." % (giay or 10)
        raise LoiAPI(msg, ma, loai, rid, giay)
    except urllib.error.URLError as e:
        raise LoiAPI("Không kết nối được máy chủ: %s" % (e.reason,), 0, "network")
    except Exception as e:
        raise LoiAPI("Lỗi mạng: %s" % (e,), 0, "network")

    d = _doc_json(raw)
    if d is None:
        raise LoiAPI("Máy chủ trả dữ liệu không phải JSON.", ma, "bad_response")
    return d


def _goi_co_thu(duong_dan, key="", method="GET", body=None, headers=None,
                timeout=240, so_lan=6, dung=None):
    """Gọi có thử lại khi 429 / lỗi mạng."""
    lan = 0
    while True:
        lan += 1
        if dung is not None and dung():
            raise LoiAPI("Đã dừng theo yêu cầu.", 0, "stopped")
        try:
            return goi_api(duong_dan, key, method, body, headers, timeout)
        except LoiAPI as e:
            het = lan >= so_lan
            if e.ma == 429 and not het:
                # hàng đợi đầy: chờ theo Retry-After, không có thì 10s rồi thử lại
                time.sleep(min(180, e.cho_lai or 10))
                continue
            if e.ma == 0 and not het:
                time.sleep(3 * lan)
                continue
            raise


# ---------------------------------------------------------------- phần thân
def _json_body(d):
    return json.dumps(d, ensure_ascii=False).encode("utf-8")


def _tach_ds_anh(d):
    """Trả danh sách [(url, b64)] từ response tạo ảnh."""
    ds = []
    if not isinstance(d, dict):
        return ds
    for item in (d.get("data") or []):
        if not isinstance(item, dict):
            continue
        u = (item.get("url") or "").strip()
        b = (item.get("b64_json") or "").strip()
        if u:
            ds.append((u, ""))
        elif b:
            ds.append((b, b) if b.startswith("data:image/") else ("", b))
    if not ds:
        u = (d.get("url") or "").strip()
        if u:
            ds.append((u, ""))
    return ds


def _tach_anh(d):
    """Lấy url hoặc b64 từ response tạo ảnh. Trả (url, b64, job_id)."""
    job = ""
    if isinstance(d, dict):
        job = (d.get("job_id") or d.get("id") or d.get("request_id") or "") or ""
        url = (d.get("url") or "").strip()
        if url:
            return url, "", job
        for item in (d.get("data") or []):
            if not isinstance(item, dict):
                continue
            u = (item.get("url") or "").strip()
            if u:
                return u, "", job
            b = (item.get("b64_json") or "").strip()
            if b:
                if b.startswith("data:image/"):
                    return b, b, job
                return "", b, job
    return "", "", job


def so_du(key, dung=None):
    """GET /v1/balance → {'credits': int, 'plan': str, 'plan_name': str}"""
    d = _goi_co_thu("/v1/balance", key, dung=dung)
    return {
        "credits": d.get("credits", 0),
        "plan": d.get("plan") or "",
        "plan_name": d.get("plan_name") or "",
    }


def _tao_hoac_sua(key, endpoint, body, headers, timeout, dung, model):
    """Gửi request tạo/sửa ảnh rồi trả list ảnh (chờ job nếu cần)."""
    d = _goi_co_thu(endpoint, key, "POST", body, headers, timeout, dung=dung)
    ds = _tach_ds_anh(d)
    job = ""
    if isinstance(d, dict):
        job = (d.get("job_id") or d.get("id") or d.get("request_id") or "") or ""
    if ds:
        return {"anh": ds, "job_id": job, "raw": d}
    if not job:
        msg = ""
        if isinstance(d.get("error"), dict):
            msg = d["error"].get("message") or ""
        raise LoiAPI(msg or "Máy chủ không trả về ảnh.", 0, "empty")
    # job chạy nền — hỏi cho tới khi xong
    kq = cho_xong(key, job, giay_toi_da=max(180, timeout), dung=dung)
    return {"anh": [(kq["url"], kq["b64"])], "job_id": job, "raw": d}


def tao_anh(key, model, prompt, n=1, aspect="1:1", resolution="1k",
            quality="auto", timeout=240, dung=None):
    """POST /v1/images/generations → {'anh': [(url,b64)], 'job_id'}

    Tài liệu không ghi tham số `n`, nên mỗi lần gọi tạo đúng 1 ảnh;
    muốn nhiều ảnh thì gọi nhiều lần (tool tự xếp hàng).
    """
    body = {"model": model, "prompt": prompt, "aspect_ratio": aspect}
    if not la_nano(model):
        body["resolution"] = resolution
        if co_quality(model):
            body["quality"] = quality
    return _tao_hoac_sua(key, "/v1/images/generations", _json_body(body),
                         {"Content-Type": "application/json"}, timeout, dung, model)


def _multipart(fields, files):
    """files: list[(ten_field, duong_dan, ten_file, mime)]"""
    bd = "----LVBoundary" + uuid.uuid4().hex
    out = []
    for k, v in fields:
        out.append(("--" + bd + "\r\n").encode())
        out.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % k).encode("utf-8"))
        out.append(str(v).encode("utf-8"))
        out.append(b"\r\n")
    for field, path, fname, mime in files:
        out.append(("--" + bd + "\r\n").encode())
        out.append(('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
                    % (field, fname)).encode("utf-8"))
        out.append(("Content-Type: %s\r\n\r\n" % mime).encode())
        with open(path, "rb") as f:
            out.append(f.read())
        out.append(b"\r\n")
    out.append(("--" + bd + "--\r\n").encode())
    return b"".join(out), "multipart/form-data; boundary=" + bd


def _mime(path):
    m = mimetypes.guess_type(path)[0] or ""
    if m in ("image/jpeg", "image/png", "image/webp"):
        return m
    return "image/jpeg"


def sua_anh(key, model, prompt, ds_file, aspect="1:1", resolution="1k",
            quality="auto", timeout=300, dung=None):
    """POST /v1/images/edits (multipart) → {'anh': [(url,b64)], 'job_id'}"""
    files = []
    for p in ds_file[:max_anh(model)]:
        files.append(("image", p, os.path.basename(p), _mime(p)))
    fields = [("model", model), ("prompt", prompt), ("aspect_ratio", aspect)]
    if not la_nano(model):
        fields.append(("resolution", resolution))
        if co_quality(model):
            fields.append(("quality", quality))
    body, ctype = _multipart(fields, files)
    return _tao_hoac_sua(key, "/v1/images/edits", body,
                         {"Content-Type": ctype}, timeout, dung, model)


def hoi_job(key, job_id, timeout=60, dung=None):
    """GET /v1/images/{id} → {'status','url','b64'}"""
    d = _goi_co_thu("/v1/images/" + urllib.request.quote(job_id, safe=""), key,
                    timeout=timeout, dung=dung)
    trang_thai = (d.get("status") or "").lower()
    url, b64, _job = _tach_anh(d)
    return {"status": trang_thai, "url": url, "b64": b64, "raw": d}


def cho_xong(key, job_id, giay_toi_da=300, dung=None, bao=None):
    """Hỏi job tới khi xong. Trả {'url','b64'}."""
    t0 = time.time()
    while time.time() - t0 < giay_toi_da:
        if dung is not None and dung():
            raise LoiAPI("Đã dừng theo yêu cầu.", 0, "stopped")
        r = hoi_job(key, job_id, dung=dung)
        st = r["status"]
        if st in ("completed", "done", "succeeded", "success"):
            if r["url"] or r["b64"]:
                return {"url": r["url"], "b64": r["b64"]}
            raise LoiAPI("Job xong nhưng không có ảnh.", 0, "empty")
        if st in ("failed", "error", "canceled", "cancelled", "rejected",
                  "moderated", "content_filtered", "blocked"):
            err = ""
            raw = r.get("raw") or {}
            if isinstance(raw.get("error"), dict):
                err = raw["error"].get("message") or ""
            raise LoiAPI("Tạo ảnh thất bại%s" % (": " + err if err else "."), 0, "failed")
        if bao:
            bao("job %s — %s" % (job_id, st or "chờ"))
        time.sleep(2.0)
    raise LoiAPI("Hết thời gian chờ tạo ảnh.", 0, "timeout")


def tai_ve(url_or_b64, duong_dan, timeout=180):
    """Tải ảnh về file. Nhận http(s) hoặc data:base64."""
    import base64
    if url_or_b64.startswith("data:image/"):
        phan = url_or_b64.split(",", 1)
        raw = base64.b64decode(phan[1]) if len(phan) > 1 else b""
        with open(duong_dan, "wb") as f:
            f.write(raw)
        return len(raw)
    req = urllib.request.Request(url_or_b64, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        raw = r.read()
    with open(duong_dan, "wb") as f:
        f.write(raw)
    return len(raw)


# ---------------------------------------------------------------- tiện ích
def bo_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D")
    return s


def ten_an_toan(s, toi_da=48):
    s = bo_dau(s).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return (s[:toi_da] or "anh").strip("_")


def doc_prompt_tu_file(path):
    """Đọc .txt / .csv: mỗi dòng 1 prompt, bỏ dòng trống và dòng bắt đầu bằng #."""
    ds = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for dong in f:
            t = dong.strip()
            if not t or t.startswith("#"):
                continue
            ds.append(t)
    return ds


def ds_anh_trong_folder(folder):
    duoi = (".jpg", ".jpeg", ".png", ".webp")
    if not folder or not os.path.isdir(folder):
        return []
    ds = []
    for ten in sorted(os.listdir(folder)):
        p = os.path.join(folder, ten)
        if os.path.isfile(p) and ten.lower().endswith(duoi):
            ds.append(p)
    return ds


def la_goi_vo_han(plan):
    """Gói Grok Vô Hạn: plan dạng 'grok-unlimited-d<ngày>-s<luồng>'."""
    return str(plan or "").strip().lower().startswith("grok-unlimited")


def so_luong_toi_da(plan):
    """Số luồng song song gói cho phép, đọc từ đuôi '-s<luồng>'. 0 = không rõ."""
    p = str(plan or "").strip().lower()
    i = p.rfind("-s")
    if i < 0:
        return 0
    so = p[i + 2:]
    if not so.isdigit():
        return 0
    return max(0, int(so))


def uoc_tinh_chi_phi(model, so_anh, so_anh_gui=0, plan=""):
    """Ước tính đồng. Gói vô hạn thì ảnh Grok 0đ (kể cả phí ảnh gửi kèm)."""
    so_anh = max(0, int(so_anh))
    if la_goi_vo_han(plan) and la_grok(model):
        return 0
    tong = gia_model(model) * so_anh
    if la_nano(model):
        # tài liệu: mỗi ảnh gửi kèm khi sửa tính thêm 60đ
        tong += 60 * max(0, int(so_anh_gui)) * so_anh
    return tong


def phi_anh_gui_kem(model):
    """Phí mỗi ảnh gửi kèm (đồng). Grok: tài liệu không ghi số cụ thể."""
    return 60 if la_nano(model) else None


# ---------------------------------------------------------------- video
def la_video(model):
    return "imagine-video" in (model or "") or "grok-video" in (model or "")


def nhan_video(model):
    for pid, ten in DS_VIDEO_MODEL:
        if pid == model:
            return ten
    return model


def gia_video_giay(resolution):
    return GIA_VIDEO.get(str(resolution or "720p").lower(), GIA_VIDEO["720p"])


def uoc_tinh_phi_video(resolution, giay, co_anh_khung=False, plan=""):
    """Đồng. Gói Grok Vô Hạn đang hạn → 0đ cho cả video Grok lẫn phí ảnh khung."""
    if la_goi_vo_han(plan):
        return 0
    tong = gia_video_giay(resolution) * max(1, int(giay or 6))
    if co_anh_khung:
        tong += PHI_ANH_KHUNG
    return tong


def _anh_sang_url(path, toi_da_byte=8 * 1024 * 1024):
    """Ảnh local → data URI base64 (API nhận https hoặc data:image)."""
    import base64
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) > toi_da_byte:
        raise LoiAPI("Ảnh khung quá lớn (%d MB). Dùng ảnh nhỏ hơn 8 MB."
                     % (len(raw) // (1024 * 1024)), 0, "bad_input")
    mime = _mime(path)
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))


def tao_video(key, model, prompt, giay=6, resolution="720p", aspect="9:16",
              anh_khung=None, timeout=180, dung=None):
    """POST /v1/videos → {'job_id','status','raw'}

    anh_khung: đường dẫn ảnh local làm khung đầu (I2V), None = tạo từ mô tả.
    """
    body = {
        "model": model,
        "prompt": prompt or "",
        "seconds": max(1, min(15, int(giay or 6))),
        "resolution": resolution,
        "aspect_ratio": aspect,
    }
    if anh_khung:
        if not os.path.isfile(anh_khung):
            raise LoiAPI("Không thấy ảnh khung: %s" % anh_khung, 0, "bad_input")
        body["image"] = {"url": _anh_sang_url(anh_khung)}
    d = _goi_co_thu("/v1/videos", key, "POST", _json_body(body),
                    {"Content-Type": "application/json"}, timeout, dung=dung)
    job = ""
    if isinstance(d, dict):
        job = (d.get("id") or d.get("job_id") or "") or ""
    if not job:
        msg = ""
        if isinstance(d, dict) and isinstance(d.get("error"), dict):
            msg = d["error"].get("message") or ""
        raise LoiAPI(msg or "Máy chủ không trả mã job video.", 0, "empty")
    return {"job_id": job, "status": (d.get("status") or "").lower(), "raw": d}


def hoi_video(key, job_id, timeout=60, dung=None):
    """GET /v1/videos/{id} → {'status','url','raw'}"""
    d = _goi_co_thu("/v1/videos/" + urllib.request.quote(job_id, safe=""), key,
                    timeout=timeout, dung=dung)
    url = ""
    if isinstance(d, dict):
        url = (d.get("url") or d.get("video_url") or "").strip()
        if not url:
            v = d.get("video")
            if isinstance(v, dict):
                url = (v.get("url") or "").strip()
        if not url:
            data = d.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                url = (data[0].get("url") or "").strip()
    return {"status": (d.get("status") or "").lower(), "url": url, "raw": d}


def cho_video_xong(key, job_id, giay_toi_da=900, dung=None, bao=None):
    """Hỏi job video tới khi xong. Trả {'url'}."""
    t0 = time.time()
    while time.time() - t0 < giay_toi_da:
        if dung is not None and dung():
            raise LoiAPI("Đã dừng theo yêu cầu.", 0, "stopped")
        r = hoi_video(key, job_id, dung=dung)
        st = r["status"]
        if st in ("completed", "done", "succeeded", "success"):
            if r["url"]:
                return {"url": r["url"]}
            raise LoiAPI("Job video xong nhưng không có link.", 0, "empty")
        if st in ("failed", "error", "canceled", "cancelled", "rejected",
                  "moderated", "content_filtered", "blocked", "expired"):
            err = ""
            raw = r.get("raw") or {}
            if isinstance(raw.get("error"), dict):
                err = raw["error"].get("message") or ""
            raise LoiAPI("Tạo video thất bại%s" % (": " + err if err else "."), 0, "failed")
        if bao:
            bao("video %s — %s" % (job_id, st or "chờ"))
        time.sleep(3.0)
    raise LoiAPI("Hết thời gian chờ tạo video.", 0, "timeout")


def tai_video(key, job_id, url, duong_dan, timeout=600):
    """Tải MP4 về file. Ưu tiên link công khai, fallback /v1/videos/{id}/content."""
    if url:
        try:
            return tai_ve(url, duong_dan, timeout=timeout)
        except Exception:
            pass
    req = urllib.request.Request(
        BASE + "/v1/videos/" + urllib.request.quote(job_id, safe="") + "/content",
        headers={"User-Agent": UA, "Authorization": "Bearer " + key.strip()})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        raw = r.read()
    with open(duong_dan, "wb") as f:
        f.write(raw)
    return len(raw)
