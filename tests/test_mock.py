# -*- coding: utf-8 -*-
"""Test core/api.py với máy chủ giả — không tốn credit, không cần key thật.

Chạy: python tests/test_mock.py
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import api  # noqa: E402

TRANG_THAI = {"job_da_hoi": 0, "lan_429": 0, "lan_edit": 0, "body_edit": None}
ANH_1PX = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
           b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _gui(self, ma, obj=None, raw=None, headers=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(ma)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/balance":
            if self.headers.get("Authorization") != "Bearer LV_ok":
                return self._gui(401, {"error": {"message": "invalid api key",
                                                 "type": "authentication_error"}})
            return self._gui(200, {"credits": 5000, "plan": "grok-unlimited",
                                   "plan_name": "Gói Grok Vô Hạn"})
        if self.path.startswith("/v1/images/lv_job_"):
            TRANG_THAI["job_da_hoi"] += 1
            if TRANG_THAI["job_da_hoi"] < 3:
                return self._gui(200, {"status": "running"})
            return self._gui(200, {"status": "completed",
                                   "data": [{"url": "http://127.0.0.1:%d/v1/media/abc.png"
                                             % PORT}]})
        if self.path.startswith("/v1/media/"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(ANH_1PX)))
            self.end_headers()
            self.wfile.write(ANH_1PX)
            return
        return self._gui(404, {"error": {"message": "not found"}})

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai)
        if self.headers.get("Authorization") != "Bearer LV_ok":
            return self._gui(401, {"error": {"message": "API key không hợp lệ",
                                             "type": "authentication_error",
                                             "request_id": "lv_req_x"}})
        if self.path == "/v1/images/generations":
            d = json.loads(raw.decode())
            if d.get("prompt") == "429":
                TRANG_THAI["lan_429"] += 1
                if TRANG_THAI["lan_429"] == 1:
                    return self._gui(429, {"error": {"message": "queue full"}},
                                     headers={"Retry-After": "1"})
            if d.get("prompt") == "job":
                return self._gui(200, {"job_id": "lv_job_1", "status": "queued"})
            return self._gui(200, {"created": 1, "model": d.get("model"),
                                   "data": [{"url": "http://127.0.0.1:%d/v1/media/a.png" % PORT},
                                            {"b64_json": "iVBORw0KGgo="}]})
        if self.path == "/v1/images/edits":
            TRANG_THAI["lan_edit"] += 1
            TRANG_THAI["body_edit"] = raw
            return self._gui(200, {"data": [{"url": "http://127.0.0.1:%d/v1/media/e.png" % PORT}]})
        return self._gui(404, {"error": {"message": "not found"}})


PORT = 8731


def chay_server():
    s = HTTPServer(("127.0.0.1", PORT), H)
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    return s


def main():
    s = chay_server()
    api.BASE = "http://127.0.0.1:%d" % PORT
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_test")
    if not os.path.isdir(out):
        os.makedirs(out)
    ok = 0
    loi = 0

    def kiem(ten, dieu_kien, chi_tiet=""):
        nonlocal ok, loi
        if dieu_kien:
            ok += 1
            print("PASS  %s" % ten)
        else:
            loi += 1
            print("FAIL  %s  %s" % (ten, chi_tiet))

    # 1. sai key
    try:
        api.so_du("LV_sai")
        kiem("key sai phải ném lỗi", False)
    except api.LoiAPI as e:
        kiem("key sai → LoiAPI 401", e.ma == 401 and "hợp lệ" in e.thong_bao, e.thong_bao)

    # 2. số dư
    try:
        d = api.so_du("LV_ok")
        kiem("so_du", d["credits"] == 5000 and "Vô Hạn" in d["plan_name"], str(d))
    except api.LoiAPI as e:
        kiem("so_du", False, e.thong_bao)

    # 3. tạo ảnh đồng bộ (2 ảnh: url + b64)
    try:
        r = api.tao_anh("LV_ok", "xai/grok-imagine-image-2.0", "mot con meo", n=2,
                        aspect="16:9", resolution="2k", quality="low")
        kiem("tao_anh đồng bộ trả 2 ảnh", len(r["anh"]) == 2, str(r["anh"]))
        p = os.path.join(out, "a.png")
        n = api.tai_ve(r["anh"][0][0], p)
        kiem("tai_ve url", n == len(ANH_1PX) and os.path.isfile(p), "n=%s" % n)
        p2 = os.path.join(out, "b.png")
        n2 = api.tai_ve("data:image/png;base64,iVBORw0KGgo=", p2)
        kiem("tai_ve data:base64", n2 > 0, "n=%s" % n2)
    except api.LoiAPI as e:
        kiem("tao_anh đồng bộ", False, e.thong_bao)

    # 4. tạo ảnh bất đồng bộ (job) — phải poll 3 lần rồi tải được
    TRANG_THAI["job_da_hoi"] = 0
    try:
        r = api.tao_anh("LV_ok", "xai/grok-imagine-image-2.0", "job")
        kiem("tao_anh job → chờ xong", r["job_id"] == "lv_job_1" and len(r["anh"]) == 1
             and TRANG_THAI["job_da_hoi"] >= 3, "hoi=%s" % TRANG_THAI["job_da_hoi"])
    except api.LoiAPI as e:
        kiem("tao_anh job", False, e.thong_bao)

    # 5. 429 có Retry-After → thử lại thành công
    TRANG_THAI["lan_429"] = 0
    t0 = time.time()
    try:
        r = api.tao_anh("LV_ok", "xai/grok-imagine-image", "429")
        kiem("429 thử lại", TRANG_THAI["lan_429"] == 2 and len(r["anh"]) == 2,
             "lan=%s" % TRANG_THAI["lan_429"])
        kiem("429 có chờ Retry-After", time.time() - t0 >= 0.9, "%.2fs" % (time.time() - t0))
    except api.LoiAPI as e:
        kiem("429 thử lại", False, e.thong_bao)

    # 6. sửa ảnh multipart
    f1 = os.path.join(out, "x1.jpg")
    f2 = os.path.join(out, "x2.png")
    open(f1, "wb").write(b"\xff\xd8\xff\xe0JFIF")
    open(f2, "wb").write(ANH_1PX)
    try:
        r = api.sua_anh("LV_ok", "xai/grok-imagine-image-2.0",
                        "Ghép <IMAGE_0> và <IMAGE_1>", [f1, f2], aspect="1:1")
        body = TRANG_THAI["body_edit"] or b""
        kiem("sua_anh trả ảnh", len(r["anh"]) == 1, str(r["anh"]))
        kiem("sua_anh gửi 2 file", body.count(b'name="image"; filename=') == 2,
             "count=%d" % body.count(b'name="image"; filename='))
        kiem("sua_anh gửi model+prompt+aspect", b"xai/grok-imagine-image-2.0" in body
             and b"<IMAGE_0>" in body and b"1:1" in body)
        kiem("sua_anh gửi quality cho 2.0", b'name="quality"' in body)
    except api.LoiAPI as e:
        kiem("sua_anh", False, e.thong_bao)

    # 7. Nano Banana không gửi resolution/quality
    TRANG_THAI["body_edit"] = None
    try:
        api.sua_anh("LV_ok", "google/nano-banana-pro", "doi mau ao", [f1])
        body = TRANG_THAI["body_edit"] or b""
        kiem("nano: không gửi resolution", b'name="resolution"' not in body)
        kiem("nano: không gửi quality", b'name="quality"' not in body)
    except api.LoiAPI as e:
        kiem("nano multipart", False, e.thong_bao)

    # 8. cắt ảnh theo giới hạn model
    kiem("max_anh grok=5 nano=3",
         api.max_anh("xai/grok-imagine-image-2.0") == 5
         and api.max_anh("google/nano-banana-pro") == 3)

    # 9. dừng giữa đường
    try:
        api.tao_anh("LV_ok", "xai/grok-imagine-image", "job", dung=lambda: True)
        kiem("dừng theo yêu cầu", False)
    except api.LoiAPI as e:
        kiem("dừng theo yêu cầu", e.loai == "stopped", e.loai)

    # 10. tiện ích
    kiem("ten_an_toan", api.ten_an_toan("Tổng thống Mỹ!") == "tong_thong_my",
         api.ten_an_toan("Tổng thống Mỹ!"))
    kiem("gia_model", api.gia_model("xai/grok-imagine-image-2.0") == 30
         and api.gia_model("xai/grok-imagine-image") == 10)
    kiem("uoc_tinh_chi_phi", api.uoc_tinh_chi_phi("xai/grok-imagine-image-2.0", 100) == 3000)

    s.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (ok, loi))
    return 0 if loi == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
