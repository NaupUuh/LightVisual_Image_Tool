# -*- coding: utf-8 -*-
"""Test v1.0.17: dong tool KHONG treo + bao cao dinh ky 30 phut.

1) Long-poll gia giu ket noi 8s -> bam X (dong tool) phai xong < 3s.
2) Sau khi dong cua so, go /baocao van phai duoc tra loi (tien trinh con song).
3) Nhip bao cao dinh ky: qua `tele_moi_phut` phut -> tu gui tin co nhan bot.
4) Luong gui tin la daemon -> tien trinh thoat duoc ngay.

Chay: python tests/test_dong_app.py
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

PORT = 8763
TOKEN = "123456789:DONG_TEST"
NHOM = "-5593791314"
TRANG = {"tin": [], "updates": [], "uid": 7000, "giu": 8.0}
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
        b = json.dumps(obj).encode()
        self.send_response(ma)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai).decode("utf-8", "replace")
        try:
            d = json.loads(raw) if raw else {}
        except Exception:
            d = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        if "/sendMessage" in self.path:
            TRANG["tin"].append((str(d.get("chat_id")), str(d.get("text") or "")))
            return self._tra(200, {"ok": True, "result": {"message_id": len(TRANG["tin"])}})
        if "/getMe" in self.path:
            return self._tra(200, {"ok": True, "result": {
                "id": 8853760691, "username": "bao_cao_page_aq_bot",
                "can_read_all_group_messages": False}})
        if "/getUpdates" in self.path:
            # giu ket noi lau nhu long-poll that
            off = int(d.get("offset") or 0)
            het = time.time() + TRANG["giu"]
            while time.time() < het:
                if any(int(u["update_id"]) >= off for u in TRANG["updates"]):
                    break
                time.sleep(0.05)
            return self._tra(200, {"ok": True,
                                   "result": [u for u in TRANG["updates"]
                                              if int(u["update_id"]) >= off]})
        if "/setMyCommands" in self.path:
            return self._tra(200, {"ok": True, "result": True})
        return self._tra(404, {"ok": False, "description": "nf"})


def bom(text):
    TRANG["uid"] += 1
    TRANG["updates"].append({
        "update_id": TRANG["uid"],
        "message": {"message_id": TRANG["uid"], "text": text,
                    "chat": {"id": int(NHOM), "type": "supergroup", "title": "Test"},
                    "from": {"id": 1, "first_name": "Meo"}}})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tele.API_GOC = "http://127.0.0.1:%d/bot%%s/%%s" % PORT
    tele.API = "http://127.0.0.1:%d/bot%%s/sendMessage" % PORT

    goc = T.CFG_FILE
    T.CFG_FILE = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp",
                              "_cfg_dong_app.json")
    with open(T.CFG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": "LV_ok",
                   "thu_muc_ra": os.path.join(os.environ.get("LOCALAPPDATA", "."),
                                              "Temp", "_tmp_dong"),
                   "tele_bat": True, "tele_token": TOKEN,
                   "tele_chat_id": NHOM, "tele_chat_ids": [NHOM],
                   "tele_nghe": True, "tele_moi_phut": 30, "tele_ten": "Máy A"}, f)

    app = T.App()
    t0 = time.time()
    while time.time() - t0 < 10 and not (app.td and app.td.dang_chay()):
        app.update()
        time.sleep(0.02)
    kiem("luồng nghe đang chạy", bool(app.td and app.td.dang_chay()))
    kiem("đọc được username bot", getattr(app.td, "bot_username", "") == "bao_cao_page_aq_bot",
         getattr(app.td, "bot_username", ""))
    kiem("nhớ username vào config", app.cfg.get("tele_bot_user") == "bao_cao_page_aq_bot",
         str(app.cfg.get("tele_bot_user")))

    # ---- bao cao dinh ky (gia lap da qua 30 phut)
    truoc = len(TRANG["tin"])
    app._lan_hb = time.time() - 31 * 60
    app._giam_sat_nghe()
    t = time.time()
    while time.time() - t < 6 and len(TRANG["tin"]) == truoc:
        app.update()
        time.sleep(0.02)
    kiem("báo cáo định kỳ tự gửi", len(TRANG["tin"]) > truoc,
         "so tin: %d" % (len(TRANG["tin"]) - truoc))
    if len(TRANG["tin"]) > truoc:
        kiem("  tin định kỳ có nhãn bot", "Máy A" in TRANG["tin"][-1][1],
             TRANG["tin"][-1][1][:120])
        kiem("  tin định kỳ ghi 'định kỳ'", "định kỳ" in TRANG["tin"][-1][1],
             TRANG["tin"][-1][1][:120])
        kiem("  gửi đúng nhóm", TRANG["tin"][-1][0] == NHOM, TRANG["tin"][-1][0])

    # ---- dong tool khi long-poll dang giu ket noi 8s
    app._bam_dung() if app.dang_chay else None
    t0 = time.time()
    app._thoat_app()
    mat = time.time() - t0
    kiem("đóng tool KHÔNG treo (<3s)", mat < 3.0, "mất %.2fs" % mat)
    print("   thoi gian dong: %.2fs" % mat)
    try:
        con_song = bool(app.winfo_exists())
    except Exception:
        con_song = False
    kiem("cửa sổ đã đóng", not con_song)

    # ---- sau khi dong cua so: lenh /baocao van phai duoc tra loi
    truoc = len(TRANG["tin"])
    bom("/baocao@bao_cao_page_aq_bot")
    t = time.time()
    while time.time() - t < 10 and len(TRANG["tin"]) == truoc:
        time.sleep(0.05)
    kiem("sau khi đóng cửa sổ vẫn trả lời /baocao", len(TRANG["tin"]) > truoc,
         "so tin: %d" % (len(TRANG["tin"]) - truoc))

    # ---- luong gui tin phai la daemon
    bc = tele.BaoCao(TOKEN, NHOM, moi_giay=60, chat_ids=[NHOM])
    bc.bat_dau_worker()
    kiem("luồng gửi tin là daemon", bool(bc._t and bc._t.daemon), str(bc._t))
    bc.dung_nhanh()

    # ---- CA CUA ANH: dang chay viec -> bam Dung -> tat app
    app2 = T.App()
    t0 = time.time()
    while time.time() - t0 < 10 and not (app2.td and app2.td.dang_chay()):
        app2.update()
        time.sleep(0.02)
    # gia lap dang chay 1 luot: 10 viec, 3 xong, con 7
    app2.dang_chay = True
    app2._t0 = time.time() - 120
    with app2._dem_lock:
        app2._dem.update({"tong": 10, "ok": 3, "loi": 1, "dung": 0})
    app2._lan_chay = {"loai": "anh", "viec": [{"stt": i} for i in range(10)],
                      "cau_hinh": {"thu_muc": os.environ.get("TEMP", ".")}}
    app2._da_xong = {0, 1, 2, 3}
    app2._bat_baocao()          # như khi bấm CHẠY: tạo đối tượng báo cáo
    # khong cho hop thoai chan: tra loi "Dung va thoat?"
    goc_ask = T.messagebox.askyesno
    T.messagebox.askyesno = lambda *a, **k: True
    try:
        t1 = time.time()
        app2._bam_dung()
        t2 = time.time()
        kiem("bấm DỪNG phản hồi ngay (<1s)", t2 - t1 < 1.0, "%.2fs" % (t2 - t1))
        t = time.time()
        while time.time() - t < 5 and not any("DỪNG" in x[1] for x in TRANG["tin"]):
            app2.update()
            time.sleep(0.05)
        kiem("DỪNG có gửi tin báo Telegram", any("DỪNG" in x[1] for x in TRANG["tin"]),
             "so tin: %d" % len(TRANG["tin"]))
        t3 = time.time()
        app2._thoat_app()
        mat2 = time.time() - t3
        kiem("đang chạy -> DỪNG -> tắt KHÔNG treo (<3s)", mat2 < 3.0,
             "mất %.2fs" % mat2)
        print("   thoi gian tat (dang chay): %.2fs" % mat2)
    finally:
        T.messagebox.askyesno = goc_ask
        try:
            app2.destroy()
        except Exception:
            pass

    T.CFG_FILE = goc
    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (OK[0], LOI[0]))
    return 0 if LOI[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
