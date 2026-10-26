# -*- coding: utf-8 -*-
"""E2E: may chu Telegram GIA co long-poll; bom lenh /baocao -> app co tra loi khong?

Khong goi mang that, khong gui tin that.
Chay: python tests/test_baocao_ngay.py
"""
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

import main as T  # noqa: E402
from core import tele  # noqa: E402

PORT = 8761
TOKEN = "123456789:BAOCAO_TEST"
NHOM = "-5593791314"

TRANG = {"updates": [], "tin": [], "getupdates": 0, "uid": 5000}
OK = [0]
LOI = [0]


def kiem(ten, dk, ct=""):
    if dk:
        OK[0] += 1
        print("PASS  %s" % ten)
    else:
        LOI[0] += 1
        print("FAIL  %s  %s" % (ten, ct))


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _tra(self, ma, obj):
        body = json.dumps(obj).encode()
        self.send_response(ma)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _doc(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai).decode("utf-8", "replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def do_POST(self):
        d = self._doc()
        if "/sendMessage" in self.path:
            TRANG["tin"].append((str(d.get("chat_id")), str(d.get("text") or "")))
            return self._tra(200, {"ok": True, "result": {"message_id": len(TRANG["tin"])}})
        if "/getMe" in self.path:
            return self._tra(200, {"ok": True, "result": {
                "id": 8853760691, "username": "bao_cao_page_aq_bot",
                "can_read_all_group_messages": True}})
        if "/getUpdates" in self.path:
            TRANG["getupdates"] += 1
            off = int(d.get("offset") or 0)
            cho = min(2, int(d.get("timeout") or 0))
            het = time.time() + cho
            while time.time() < het:
                if any(int(u["update_id"]) >= off for u in TRANG["updates"]):
                    break
                time.sleep(0.05)
            ra = [u for u in TRANG["updates"] if int(u["update_id"]) >= off]
            return self._tra(200, {"ok": True, "result": ra})
        if "/setMyCommands" in self.path:
            return self._tra(200, {"ok": True, "result": True})
        return self._tra(404, {"ok": False, "description": "nf " + self.path})


def bom_lenh(text, chat_id=NHOM):
    TRANG["uid"] += 1
    TRANG["updates"].append({
        "update_id": TRANG["uid"],
        "message": {"message_id": TRANG["uid"], "text": text,
                    "chat": {"id": int(chat_id), "type": "supergroup", "title": "Test"},
                    "from": {"id": 8446833069, "first_name": "Meo"}}})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    tele.API_GOC = "http://127.0.0.1:%d/bot%%s/%%s" % PORT
    tele.API = "http://127.0.0.1:%d/bot%%s/sendMessage" % PORT

    goc = T.CFG_FILE
    T.CFG_FILE = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp",
                              "_cfg_baocao_ngay.json")
    with open(T.CFG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": "LV_ok",
                   "thu_muc_ra": os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                              "Temp", "_tmp_bcn"),
                   "tele_bat": True, "tele_token": TOKEN,
                   "tele_chat_id": NHOM, "tele_chat_ids": [NHOM],
                   "tele_nghe": True, "tele_moi_phut": 30, "tele_ten": "Máy A"}, f)

    app = T.App()
    for _ in range(60):
        app.update()
        time.sleep(0.01)

    # chờ luồng nghe bật (after 600ms) + long-poll đầu
    t0 = time.time()
    while time.time() - t0 < 8 and not (app.td and app.td.dang_chay()):
        app.update()
        time.sleep(0.03)
    kiem("luồng nghe bật", bool(app.td and app.td.dang_chay()),
         str(app.td))
    kiem("bot_username đọc được", getattr(app.td, "bot_username", "") == "bao_cao_page_aq_bot",
         getattr(app.td, "bot_username", ""))

    def gui_va_cho(text, nhan, giay=12):
        truoc = len(TRANG["tin"])
        bom_lenh(text)
        t = time.time()
        while time.time() - t < giay:
            app.update()
            time.sleep(0.03)
            if len(TRANG["tin"]) > truoc:
                return TRANG["tin"][truoc:]
        return []

    # 1) lenh co @bot
    ra = gui_va_cho("/baocao@bao_cao_page_aq_bot", "co @bot")
    kiem("nhận /baocao@bot -> có trả lời", len(ra) >= 1, "so tin: %d" % len(ra))
    if ra:
        kiem("  trả lời đúng nhóm", ra[0][0] == NHOM, ra[0][0])
        kiem("  có nhãn bot", "Máy A" in ra[0][1], ra[0][1][:120])
        kiem("  đúng nội dung báo cáo", "Báo cáo theo yêu cầu" in ra[0][1], ra[0][1][:200])
        print("---- tin tra loi ----")
        print(ra[0][1])
        print("---------------------")

    # 2) lenh tran
    ra = gui_va_cho("/baocao", "tran")
    kiem("nhận /baocao trần -> có trả lời", len(ra) >= 1, "so tin: %d" % len(ra))

    # 3) lenh cua bot khac -> phai im
    ra = gui_va_cho("/baocao@bot_khac", "bot khac")
    kiem("bỏ qua /baocao@bot_khac", len(ra) == 0, "so tin: %d" % len(ra))

    # 4) /trangthai
    ra = gui_va_cho("/trangthai@bao_cao_page_aq_bot", "trangthai")
    kiem("nhận /trangthai", len(ra) >= 1, "so tin: %d" % len(ra))

    print("\ngetUpdates goi: %d | tin da gui: %d" % (TRANG["getupdates"], len(TRANG["tin"])))
    app.destroy()
    T.CFG_FILE = goc
    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (OK[0], LOI[0]))
    return 0 if LOI[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
