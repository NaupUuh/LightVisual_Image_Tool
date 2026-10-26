# -*- coding: utf-8 -*-
"""Kiểm core/tele.py bằng máy chủ Telegram giả (không gọi mạng thật).

Chạy: python tests/test_tele.py
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

from core import tele  # noqa: E402

PORT = 8741
TOKEN = "123456789:AAFakeTokenForTestOnly_do_not_use"
DEM = {"tin": [], "loi": 0}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai).decode("utf-8", "replace")
        # đường dẫn dạng /bot<TOKEN>/sendMessage
        duong = self.path.split("?")[0]
        if not duong.startswith("/bot") or not duong.endswith("/sendMessage"):
            self._tra(404, {"ok": False, "description": "bad path"})
            return
        tok = duong[4:-len("/sendMessage")]
        if tok != TOKEN:
            self._tra(401, {"ok": False, "description": "Unauthorized"})
            return
        import urllib.parse
        d = urllib.parse.parse_qs(raw)
        DEM["tin"].append({
            "chat_id": (d.get("chat_id") or [""])[0],
            "text": (d.get("text") or [""])[0],
            "parse_mode": (d.get("parse_mode") or [""])[0],
        })
        if "FAIL" in (d.get("text") or [""])[0]:
            self._tra(400, {"ok": False, "description": "Bad Request: chat not found"})
            return
        self._tra(200, {"ok": True, "result": {"message_id": len(DEM["tin"])}})

    def _tra(self, ma, obj):
        body = json.dumps(obj).encode()
        self.send_response(ma)
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

    srv = HTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tele.API = "http://127.0.0.1:%d/bot%%s/sendMessage" % PORT

    # ---- hàm tiện ích
    kiem("che() không lộ token", tele.che(TOKEN) == TOKEN[:10] + "…", tele.che(TOKEN))
    kiem("che() token rỗng", tele.che("") == "(chưa có)", tele.che(""))
    kiem("giây 0", tele.dinh_dang_giay(0) == "0s", tele.dinh_dang_giay(0))
    kiem("giây 75", tele.dinh_dang_giay(75) == "1p15s", tele.dinh_dang_giay(75))
    kiem("giây 3725", tele.dinh_dang_giay(3725) == "1h02p", tele.dinh_dang_giay(3725))
    kiem("thanh 4/10", tele.thanh_tien_do(
        {"ok": 3, "loi": 1, "dung": 0, "tong": 10}) == "▰▰▰▰▱▱▱▱▱▱",
        tele.thanh_tien_do({"ok": 3, "loi": 1, "dung": 0, "tong": 10}))
    kiem("thanh đầy", tele.thanh_tien_do(
        {"ok": 5, "loi": 0, "dung": 0, "tong": 5}) == "▰" * 10)
    kiem("thanh vượt tổng không tràn", len(tele.thanh_tien_do(
        {"ok": 9, "loi": 9, "dung": 0, "tong": 5})) == 10)

    # ---- gui()
    o, l = tele.gui(TOKEN, "999", "<b>xin chào</b>")
    kiem("gui() OK", o is True, l)
    kiem("gui() đúng chat_id", DEM["tin"] and DEM["tin"][-1]["chat_id"] == "999",
         str(DEM["tin"][-1] if DEM["tin"] else None))
    kiem("gui() parse_mode HTML",
         DEM["tin"] and DEM["tin"][-1]["parse_mode"] == "HTML")

    o, l = tele.gui("999999:WRONG", "999", "x")
    kiem("gui() sai token -> lỗi", o is False and "401" in l, l)

    o, l = tele.gui(TOKEN, "999", "FAIL")
    kiem("gui() lỗi 400 trả mô tả dễ hiểu",
         o is False and "400" in l and "chưa được add" in l, l)

    # gui("") rơi về lay_token() (có thể đọc .env Hermes) nên phải chặn fallback
    # để kiểm đúng nhánh thiếu token
    _lay = tele.lay_token
    tele.lay_token = lambda t="": ""
    o, l = tele.gui("", "999", "x")
    tele.lay_token = _lay
    kiem("gui() thiếu token (không fallback) -> không gọi mạng",
         o is False and "token" in l, l)

    o, l = tele.gui(TOKEN, "", "x")
    kiem("gui() thiếu chat_id", o is False and "chat_id" in l, l)

    # ---- chặn tần suất
    DEM["tin"] = []
    bc = tele.BaoCao(TOKEN, "999", moi_giay=60)
    kiem("BaoCao.enabled", bc.enabled is True)
    bc.bat_dau_worker()
    bc.bat_dau("bắt đầu")
    time.sleep(0.8)
    kiem("tin bắt đầu được gửi ngay", len(DEM["tin"]) == 1, str(len(DEM["tin"])))

    bc.tien_do("tiến độ 1")
    bc.tien_do("tiến độ 2")
    time.sleep(0.8)
    kiem("tiến độ bị chặn trong moi_giay", len(DEM["tin"]) == 1, str(len(DEM["tin"])))

    bc.ket_thuc("kết thúc")
    bc.dung()
    kiem("tin kết thúc luôn gửi", len(DEM["tin"]) == 2, str(len(DEM["tin"])))
    kiem("nội dung tin kết thúc", DEM["tin"][-1]["text"] == "kết thúc",
         DEM["tin"][-1]["text"] if DEM["tin"] else "")

    # ---- tiến độ được gửi khi đã qua nhịp
    DEM["tin"] = []
    bc2 = tele.BaoCao(TOKEN, "999", moi_giay=60)
    bc2.moi_giay = 1        # hạ sàn 15s của lớp để test nhanh
    bc2.bat_dau_worker()
    time.sleep(1.2)
    bc2.tien_do("tiến độ sau 1s")
    time.sleep(0.8)
    kiem("tiến độ gửi khi qua nhịp", len(DEM["tin"]) == 1, str(len(DEM["tin"])))
    bc2.dung()

    # ---- tắt: không gửi gì
    DEM["tin"] = []
    bc3 = tele.BaoCao("", "", moi_giay=1)
    kiem("không token/chat -> enabled False", bc3.enabled is False)
    bc3.bat_dau_worker()
    bc3.bat_dau("x")
    bc3.ket_thuc("y")
    time.sleep(0.3)
    kiem("không bật -> không gửi", len(DEM["tin"]) == 0, str(len(DEM["tin"])))

    # ---- lay_token
    os.environ["TELEGRAM_BOT_TOKEN"] = "ENV_TOKEN_ABC"
    kiem("lay_token đọc biến môi trường",
         tele.lay_token("") == "ENV_TOKEN_ABC", tele.lay_token(""))
    kiem("lay_token ưu tiên tham số",
         tele.lay_token("THAM_SO") == "THAM_SO")
    del os.environ["TELEGRAM_BOT_TOKEN"]

    # ---- HTML escape
    kiem("esc() chặn thẻ HTML",
         tele.esc("<b>&x</b>") == "&lt;b&gt;&amp;x&lt;/b&gt;", tele.esc("<b>&x</b>"))

    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (ok[0], loi[0]))
    return 0 if loi[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
