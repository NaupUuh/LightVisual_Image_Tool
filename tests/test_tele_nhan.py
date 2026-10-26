# -*- coding: utf-8 -*-
"""Test v1.0.16: nhan bot + 409 khong bao gio tat luong.

Dung may chu Telegram gia, khong goi mang that, khong gui tin that.
Chay: python tests/test_tele_nhan.py
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

from core import tele  # noqa: E402

PORT = 8747
TOKEN = "123456789:NHAN_TEST"

DEM = {"tin": [], "updates": [], "loi_409": False, "n409": 0}
KQ = {"pass": 0, "fail": 0}


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

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai).decode("utf-8", "replace") if dai else "{}"
        duong = self.path.split("?")[0]
        phan = duong[4:].split("/") if duong.startswith("/bot") else []
        if len(phan) != 2:
            self._tra(404, {"ok": False, "description": "bad path"})
            return
        tok, method = phan
        if tok != TOKEN:
            self._tra(401, {"ok": False, "description": "Unauthorized"})
            return
        try:
            ts = json.loads(raw) if raw.strip() else {}
        except Exception:
            import urllib.parse
            ts = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

        if method == "getMe":
            self._tra(200, {"ok": True, "result": {
                "id": 123456789, "is_bot": True, "username": "may_a_bot",
                "first_name": "May A",
                "can_read_all_group_messages": False}})
            return
        if method == "getUpdates":
            if DEM["loi_409"]:
                DEM["n409"] += 1
                self._tra(409, {"ok": False, "description":
                                "Conflict: terminated by other getUpdates request"})
                return
            off = int(ts.get("offset") or 0)
            ra = [u for u in DEM["updates"] if int(u.get("update_id", 0)) >= off]
            self._tra(200, {"ok": True, "result": ra})
            return
        if method == "sendMessage":
            DEM["tin"].append({"chat_id": str(ts.get("chat_id") or ""),
                               "text": str(ts.get("text") or "")})
            self._tra(200, {"ok": True, "result": {"message_id": len(DEM["tin"])}})
            return
        if method == "setMyCommands":
            self._tra(200, {"ok": True, "result": True})
            return
        self._tra(404, {"ok": False, "description": "unknown"})

    do_GET = do_POST


def kiem(ten, dk, chi_tiet=""):
    if dk:
        KQ["pass"] += 1
        print("  PASS  %s" % ten)
    else:
        KQ["fail"] += 1
        print("  FAIL  %s  -> %s" % (ten, chi_tiet))


def up(uid, chat, text=""):
    return {"update_id": uid,
            "message": {"message_id": uid, "chat": chat, "text": text}}


NHOM = {"id": -1001234567890, "type": "supergroup", "title": "Nhóm Test"}


def main():
    tele.API = "http://127.0.0.1:%d/bot%%s/sendMessage" % PORT
    tele.API_GOC = "http://127.0.0.1:%d/bot%%s/%%s" % PORT
    srv = HTTPServer(("127.0.0.1", PORT), H)
    import threading
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("\n== 1. nhan_tin ==")
    kiem("nhan_tin rong -> nguyen van",
         tele.nhan_tin("abc", "") == "abc", tele.nhan_tin("abc", ""))
    kiem("nhan_tin co nhan -> chen len dau",
         tele.nhan_tin("abc", "May A") == "<b>🏷 May A</b>\nabc",
         tele.nhan_tin("abc", "May A"))
    kiem("nhan_tin escape HTML",
         "&lt;b&gt;" in tele.nhan_tin("abc", "<b>"),
         tele.nhan_tin("abc", "<b>"))

    print("\n== 2. BaoCao gan nhan ==")
    DEM["tin"] = []
    bc = tele.BaoCao(TOKEN, "", moi_giay=60, chat_ids=["-1001"], nhan="Máy A – ảnh")
    bc.bat_dau_worker()
    bc.bat_dau("noi dung")
    t0 = time.time()
    while time.time() - t0 < 8 and not DEM["tin"]:
        time.sleep(0.05)
    kiem("BaoCao gui 1 tin", len(DEM["tin"]) == 1, str(DEM["tin"]))
    if DEM["tin"]:
        kiem("tin co nhan bot", "Máy A – ảnh" in DEM["tin"][0]["text"],
             DEM["tin"][0]["text"][:80])
        kiem("nhan o dong dau", DEM["tin"][0]["text"].startswith("<b>🏷"),
             DEM["tin"][0]["text"][:40])
    bc.dung()

    print("\n== 3. BaoCao khong nhan ==")
    DEM["tin"] = []
    bc2 = tele.BaoCao(TOKEN, "", moi_giay=60, chat_ids=["-1001"])
    bc2.bat_dau_worker()
    bc2.bat_dau("noi dung")
    t0 = time.time()
    while time.time() - t0 < 8 and not DEM["tin"]:
        time.sleep(0.05)
    kiem("khong nhan -> khong chen nhan",
         DEM["tin"] and not DEM["tin"][0]["text"].startswith("<b>🏷"),
         DEM["tin"][0]["text"][:40] if DEM["tin"] else "khong gui")
    bc2.dung()

    print("\n== 4. 409 KHONG BAO GIO tat luong ==")
    DEM["updates"] = []
    DEM["loi_409"] = True
    DEM["n409"] = 0
    logs = []
    td = tele.TheoDoi(TOKEN, khi_lenh=lambda *a: None,
                      log=lambda s: logs.append(s), timeout=5)
    td.bat_dau()
    # 409 lien tuc 75s: code cu chet sau ~30s (5 lan thu voi backoff 3/6/9/12)
    t0 = time.time()
    while time.time() - t0 < 75:
        time.sleep(0.5)
    kiem("sau 75s 409 lien tuc luong VAN SONG", td.dang_chay() is True,
         "dang_chay=%s n409=%d logs=%s" % (td.dang_chay(), DEM["n409"], logs[-3:]))
    kiem("da gap 409 nhieu hon 5 lan (cu se chet)", DEM["n409"] > 5, str(DEM["n409"]))
    kiem("log noi ro luong van song",
         any("luồng vẫn sống" in s for s in logs), str(logs[-3:]))

    # het 409 -> phai tu phuc hoi va bat duoc lenh
    DEM["loi_409"] = False
    DEM["updates"] = [up(90, NHOM, "/baocao@may_a_bot")]
    da_nhan = []
    td.khi_lenh = lambda c, t: da_nhan.append((c, t))
    t0 = time.time()
    while time.time() - t0 < 40 and not da_nhan:
        time.sleep(0.1)
    kiem("het 409 -> tu phuc hoi, bat duoc /baocao", len(da_nhan) == 1, str(da_nhan))
    td.dung()

    print("\n== 5. 409 KHONG tu tat co _stop ==")
    DEM["loi_409"] = True
    DEM["n409"] = 0
    td2 = tele.TheoDoi(TOKEN, khi_lenh=lambda *a: None, log=lambda *a: None,
                       timeout=5)
    td2.bat_dau()
    t0 = time.time()
    while time.time() - t0 < 20:
        time.sleep(0.5)
    kiem("_stop KHONG bi set boi 409", td2._stop.is_set() is False,
         "_stop=%s n409=%d" % (td2._stop.is_set(), DEM["n409"]))
    td2.dung()

    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (KQ["pass"], KQ["fail"]))
    return 1 if KQ["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
