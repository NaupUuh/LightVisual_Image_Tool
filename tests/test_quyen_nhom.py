# -*- coding: utf-8 -*-
"""Test kiem_tra_quyen bang may chu Telegram GIA (khong goi API that)."""
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = r"C:\Users\Admin\Desktop\LightVisual_Image_Tool"
sys.path.insert(0, GOC)
import core.tele as tele  # noqa: E402

TOKEN = "111:AAA"
tele.API = "http://127.0.0.1:%d/bot%%s/%%s"
tele.API_GOC = "http://127.0.0.1:%d/bot%%s/%%s"

CAU_HINH = {"status": "member", "privacy": False}
HITS = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _tra(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode() if n else ""
        p = self.path.split("/")
        method = p[-1]
        HITS.append(method)
        try:
            ts = json.loads(raw) if raw else {}
        except Exception:
            ts = {}
        if method == "getMe":
            self._tra({"ok": True, "result": {
                "id": 8853760691, "username": "bao_cao_page_aq_bot",
                "can_read_all_group_messages": CAU_HINH["privacy"]}})
        elif method == "getChat":
            self._tra({"ok": True, "result": {"id": int(ts.get("chat_id", 0)),
                                              "title": "Test", "type": "group"}})
        elif method == "getChatMember":
            self._tra({"ok": True, "result": {
                "user": {"id": 8853760691, "is_bot": True,
                         "username": "bao_cao_page_aq_bot"},
                "status": CAU_HINH["status"]}})
        else:
            self._tra({"ok": True, "result": True})


srv = HTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
tele.API = "http://127.0.0.1:%d/bot%%s/%%s" % port
tele.API_GOC = tele.API
threading.Thread(target=srv.serve_forever, daemon=True).start()

PASS = FAIL = 0


def kiem(ten, dieu):
    global PASS, FAIL
    if dieu:
        PASS += 1
        print("  PASS", ten)
    else:
        FAIL += 1
        print("  FAIL", ten)


print("== ca 1: bot la member + privacy BAT ==")
CAU_HINH.update({"status": "member", "privacy": False})
ds, pv = tele.kiem_tra_quyen(TOKEN, ["-5593791314"])
kiem("tra ve 1 nhom", len(ds) == 1)
d = ds[0] if ds else {}
kiem("privacy_off=False", pv is False)
kiem("la_admin=False", d.get("la_admin") is False)
kiem("doc_het=False (bi chan lenh tran)", d.get("doc_het") is False)
kiem("status=member", d.get("status") == "member")
kiem("doc duoc ten nhom", d.get("title") == "Test")
kiem("co bot_user", d.get("bot_user") == "bao_cao_page_aq_bot")

print("== ca 2: bot la admin ==")
CAU_HINH.update({"status": "administrator", "privacy": False})
ds, pv = tele.kiem_tra_quyen(TOKEN, ["-5593791314"])
d = ds[0] if ds else {}
kiem("la_admin=True", d.get("la_admin") is True)
kiem("doc_het=True", d.get("doc_het") is True)

print("== ca 3: privacy TAT, bot la member ==")
CAU_HINH.update({"status": "member", "privacy": True})
ds, pv = tele.kiem_tra_quyen(TOKEN, ["-5593791314"])
d = ds[0] if ds else {}
kiem("privacy_off=True", pv is True)
kiem("doc_het=True (privacy tat la du)", d.get("doc_het") is True)

print("== ca 4: khong co token ==")
ds, pv = tele.kiem_tra_quyen("", ["-5593791314"])
kiem("tra rong", ds == [] and pv is False)

print("== ca 5: nhieu nhom ==")
CAU_HINH.update({"status": "member", "privacy": False})
ds, pv = tele.kiem_tra_quyen(TOKEN, ["-5593791314", "-1001234567890"])
kiem("2 nhom", len(ds) == 2)

print("== ca 6: goi dung method ==")
kiem("co goi getMe", "getMe" in HITS)
kiem("co goi getChatMember", "getChatMember" in HITS)
kiem("co goi getChat", "getChat" in HITS)

srv.shutdown()
print("\nKET QUA: PASS %d | FAIL %d" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
