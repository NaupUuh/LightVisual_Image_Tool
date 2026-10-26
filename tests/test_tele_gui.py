# -*- coding: utf-8 -*-
"""Chạy GUI thật với máy chủ ảnh giả + máy chủ Telegram giả.

Mục tiêu: chứng minh báo cáo Telegram thật sự được bắn ra trong 1 lượt chạy
(bắt đầu → kết thúc), không chỉ kiểm hàm lẻ.

Chạy: python tests/test_tele_gui.py
"""

import json
import os
import shutil
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

import main as T  # noqa: E402
from core import tele  # noqa: E402

PORT_API = 8751
PORT_TG = 8752
TOKEN = "123456789:AAIntegrationFakeToken"
ANH = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
TIN = []


class ApiH(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _gui(self, ma, obj=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(ma)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/balance":
            return self._gui(200, {"credits": 99999, "plan": "grok-unlimited",
                                   "plan_name": "Gói Grok Vô Hạn 30 ngày"})
        if self.path.startswith("/v1/media/"):
            return self._gui(200, None, ANH, "image/png")
        return self._gui(404, {"error": {"message": "nf"}})

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(dai)
        if self.path == "/v1/images/generations":
            time.sleep(0.15)
            return self._gui(200, {"data": [{"url": "http://127.0.0.1:%d/v1/media/a.png"
                                                    % PORT_API}]})
        return self._gui(404, {"error": {"message": "nf"}})


class TgH(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai).decode("utf-8", "replace")
        d = urllib.parse.parse_qs(raw)
        TIN.append(((d.get("chat_id") or [""])[0], (d.get("text") or [""])[0]))
        body = json.dumps({"ok": True, "result": {"message_id": len(TIN)}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    ok = [0]
    loi = [0]

    def kiem(ten, dk, ct=""):
        if dk:
            ok[0] += 1
            print("PASS  %s" % ten)
        else:
            loi[0] += 1
            print("FAIL  %s  %s" % (ten, ct))

    srv_api = HTTPServer(("127.0.0.1", PORT_API), ApiH)
    srv_tg = HTTPServer(("127.0.0.1", PORT_TG), TgH)
    threading.Thread(target=srv_api.serve_forever, daemon=True).start()
    threading.Thread(target=srv_tg.serve_forever, daemon=True).start()

    T.api.BASE = "http://127.0.0.1:%d" % PORT_API
    tele.API = "http://127.0.0.1:%d/bot%%s/sendMessage" % PORT_TG

    goc_cfg = T.CFG_FILE
    T.CFG_FILE = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp", "_cfg_tg_gui.json")
    out = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp", "_tmp_tg_gui")
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    with open(T.CFG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": "LV_ok", "thu_muc_ra": out, "mo_khi_xong": False,
                   "tele_bat": True, "tele_token": TOKEN, "tele_chat_id": "8446",
                   "tele_chat_ids": ["8446"], "tele_nghe": False,
                   "tele_moi_phut": 1}, f)

    app = T.App()
    for _ in range(30):
        app.update()

    kiem("nút Telegram hiện BẬT", "BẬT" in app.btn_tele.cget("text"),
         app.btn_tele.cget("text"))

    app.txt_prompt.delete("1.0", "end")
    app.txt_prompt.insert("1.0", "prompt mot\nprompt hai\n")
    app.sp_luong.delete(0, "end")
    app.sp_luong.insert(0, "1")
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 60:
        app.update()
        time.sleep(0.03)
    for _ in range(60):
        app.update()
        time.sleep(0.02)

    # chờ luồng gửi nốt tin trong hàng đợi
    time.sleep(1.5)
    for _ in range(30):
        app.update()
        time.sleep(0.02)

    dong = app.tree.get_children()
    kiem("chạy xong 2 việc", len(dong) == 2, str(len(dong)))
    kiem("có gửi tin Telegram", len(TIN) >= 2, str(len(TIN)))
    if TIN:
        kiem("tin đầu là BẮT ĐẦU", "bắt đầu" in TIN[0][1], TIN[0][1][:120])
        kiem("tin cuối là KẾT THÚC", "KẾT THÚC" in TIN[-1][1], TIN[-1][1][:160])
        kiem("gửi đúng chat_id", all(t[0] == "8446" for t in TIN), str(set(t[0] for t in TIN)))
        kiem("tin kết thúc có số OK", "OK 2" in TIN[-1][1], TIN[-1][1][:160])
        kiem("tin kết thúc có thư mục ra", out.split("\\")[-1] in TIN[-1][1],
             TIN[-1][1][:200])
    kiem("đã đóng báo cáo sau khi xong", app.bc is None, str(app.bc))

    app.destroy()
    T.CFG_FILE = goc_cfg
    srv_api.shutdown()
    srv_tg.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (ok[0], loi[0]))
    return 0 if loi[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
