# -*- coding: utf-8 -*-
"""Kiểm phần nhóm + lệnh /baocao của core/tele.py bằng máy chủ Telegram giả.

Không gọi mạng thật, không gửi tin thật.
Chạy: python tests/test_tele_nhom.py
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

PORT = 8743
TOKEN = "123456789:NHOM_TEST"

DEM = {"tin": [], "updates": [], "goi": []}


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
        if not duong.startswith("/bot"):
            self._tra(404, {"ok": False, "description": "bad path"})
            return
        phan = duong[4:].split("/")
        if len(phan) != 2:
            self._tra(404, {"ok": False, "description": "bad path"})
            return
        tok, method = phan
        DEM["goi"].append(method)
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
                "id": 123456789, "is_bot": True, "username": "test_bot",
                "first_name": "Test"}})
            return

        if method == "getUpdates":
            if DEM.get("loi_409"):
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

        self._tra(404, {"ok": False, "description": "unknown method"})

    do_GET = do_POST


def up(uid, chat, text=""):
    return {"update_id": uid,
            "message": {"message_id": uid, "chat": chat, "text": text}}


NHOM_A = {"id": -1001234567890, "type": "supergroup", "title": "Nhóm A"}
NHOM_B = {"id": -1009876543210, "type": "group", "title": "Nhóm B"}
KENH_C = {"id": -1005555555555, "type": "channel", "title": "Kênh C"}
RIENG = {"id": 8446833069, "type": "private", "first_name": "Mèo"}


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
    tele.API_GOC = "http://127.0.0.1:%d/bot%%s/%%s" % PORT

    # ---- lệnh
    kiem("la_lenh_baocao /baocao", tele.la_lenh_baocao("/baocao") is True)
    kiem("la_lenh_baocao /baocao có tham số",
         tele.la_lenh_baocao("/baocao xin chao") is True)
    kiem("la_lenh_baocao /bc", tele.la_lenh_baocao("/bc") is True)
    kiem("la_lenh_baocao đúng @bot",
         tele.la_lenh_baocao("/baocao@test_bot", "test_bot") is True)
    kiem("la_lenh_baocao @bot khác -> bỏ",
         tele.la_lenh_baocao("/baocao@bot_khac", "test_bot") is False)
    kiem("la_lenh_baocao không phải lệnh",
         tele.la_lenh_baocao("baocao") is False)
    kiem("la_lenh_baocao lệnh khác",
         tele.la_lenh_baocao("/start") is False)

    # ---- getMe
    o, me = tele.get_me(TOKEN)
    kiem("get_me OK", o is True and me.get("username") == "test_bot", str(me))
    o, l = tele.get_me("999999:WRONG")
    kiem("get_me sai token -> lỗi", o is False and "401" in str(l), str(l))

    # ---- lay_nhom
    DEM["updates"] = [up(1, NHOM_A, "chào"), up(2, RIENG, "/baocao"),
                      up(3, NHOM_B, "hi"), up(4, NHOM_A, "lặp nhóm A")]
    ds, off, l = tele.lay_nhom(TOKEN, giay=1.0, offset=0)
    kiem("lay_nhom trả 2 nhóm (bỏ private, gộp trùng)", len(ds) == 2,
         str([d.get("title") for d in ds]))
    kiem("lay_nhom có title + id âm",
         any(d["id"] == "-1001234567890" and d["title"] == "Nhóm A" for d in ds),
         str(ds))
    kiem("lay_nhom sắp theo tên", [d["title"] for d in ds] == ["Nhóm A", "Nhóm B"],
         str([d["title"] for d in ds]))
    kiem("lay_nhom offset = last+1", off == 5, str(off))
    kiem("lay_nhom không lỗi", l == "", str(l))

    # kênh cũng được tính
    DEM["updates"] = [up(10, KENH_C, "bài mới")]
    ds2, off2, _ = tele.lay_nhom(TOKEN, giay=0.6, offset=10)
    kiem("lay_nhom nhận cả channel", len(ds2) == 1 and ds2[0]["type"] == "channel",
         str(ds2))

    # thiếu token
    _lay = tele.lay_token
    tele.lay_token = lambda t="": ""
    ds3, off3, l3 = tele.lay_nhom("", giay=0.5, offset=0)
    tele.lay_token = _lay
    kiem("lay_nhom thiếu token -> lỗi rõ", ds3 == [] and "token" in l3, l3)

    # ---- TheoDoi bắt lệnh
    DEM["updates"] = []
    da_nhan = []
    td = tele.TheoDoi(TOKEN, khi_lenh=lambda cid, ten: da_nhan.append((cid, ten)),
                      log=lambda *a: None, timeout=5)
    td.offset = 0
    kiem("TheoDoi bật được", td.bat_dau() is True)
    kiem("TheoDoi biết username bot", td.bot_username == "test_bot", td.bot_username)
    DEM["updates"] = [up(20, NHOM_B, "/baocao")]
    t0 = time.time()
    while not da_nhan and time.time() - t0 < 8:
        time.sleep(0.1)
    td.dung()
    kiem("TheoDoi gọi khi_lenh khi thấy /baocao",
         len(da_nhan) == 1, str(da_nhan))
    kiem("TheoDoi trả đúng chat_id + tên nhóm",
         da_nhan and da_nhan[0][0] == "-1009876543210" and da_nhan[0][1] == "Nhóm B",
         str(da_nhan))
    kiem("TheoDoi lưu offset", td.offset == 21, str(td.offset))

    # lệnh trong chat riêng không kích hoạt
    DEM["updates"] = []
    da_nhan2 = []
    td2 = tele.TheoDoi(TOKEN, khi_lenh=lambda cid, ten: da_nhan2.append(cid),
                       log=lambda *a: None, timeout=5)
    td2.offset = 0
    td2.bat_dau()
    DEM["updates"] = [up(30, RIENG, "/baocao")]
    time.sleep(1.6)
    td2.dung()
    kiem("TheoDoi bỏ qua chat riêng", len(da_nhan2) == 0, str(da_nhan2))

    # 409 Conflict: tranh chấp TẠM THỜI -> phải thử lại, KHÔNG tắt luồng.
    # (bug cũ: gặp 1 lần 409 là chết luôn -> "bot không chạy")
    DEM["updates"] = []
    DEM["loi_409"] = True
    logs = []
    td3 = tele.TheoDoi(TOKEN, khi_lenh=lambda *a: None, log=lambda s: logs.append(s),
                       timeout=5)
    td3.bat_dau()
    t0 = time.time()
    while time.time() - t0 < 6:
        time.sleep(0.1)
    kiem("TheoDoi gặp 409 -> vẫn sống để thử lại", td3.dang_chay() is True,
         "dang_chay=%s logs=%s" % (td3.dang_chay(), logs))
    kiem("TheoDoi 409 -> log nói đang thử lại",
         any("thử lại" in s for s in logs), str(logs))
    # hết tranh chấp -> phải tự phục hồi và bắt được lệnh trở lại
    DEM["loi_409"] = False
    DEM["updates"] = [up(70, NHOM_A, "/baocao@test_bot")]
    da_nhan3 = []
    td3.khi_lenh = lambda c, t: da_nhan3.append((c, t))
    t0 = time.time()
    while time.time() - t0 < 25 and not da_nhan3:
        time.sleep(0.1)
    kiem("TheoDoi tự phục hồi sau 409", len(da_nhan3) == 1, str(da_nhan3))
    td3.dung()

    # ---- BaoCao nhiều nhóm
    DEM["tin"] = []
    bc = tele.BaoCao(TOKEN, "", moi_giay=60, chat_ids=["-1001", "-1002"])
    kiem("BaoCao nhận nhiều nhóm", bc.chat_ids == ["-1001", "-1002"], str(bc.chat_ids))
    kiem("BaoCao.enabled khi có nhóm", bc.enabled is True)
    bc.bat_dau_worker()
    bc.bat_dau("bắt đầu")
    time.sleep(1.0)
    kiem("gửi bắt đầu tới cả 2 nhóm", len(DEM["tin"]) == 2, str(len(DEM["tin"])))
    kiem("đúng 2 chat_id", sorted(t["chat_id"] for t in DEM["tin"]) == ["-1001", "-1002"],
         str(DEM["tin"]))
    bc.tien_do("tiến độ")
    time.sleep(0.5)
    kiem("tiến độ bị chặn trong 60s", len(DEM["tin"]) == 2, str(len(DEM["tin"])))
    bc.gui_ngay("báo cáo ngay")
    time.sleep(0.6)
    kiem("gui_ngay không bị chặn nhịp", len(DEM["tin"]) == 4, str(len(DEM["tin"])))
    bc.dung()

    # 1 chat_id truyền qua tham số cũ vẫn chạy
    DEM["tin"] = []
    bc2 = tele.BaoCao(TOKEN, "8446", moi_giay=60)
    kiem("BaoCao chat_id cũ -> danh sách 1", bc2.chat_ids == ["8446"], str(bc2.chat_ids))
    kiem("BaoCao.chat_id trả phần tử đầu", bc2.chat_id == "8446", bc2.chat_id)

    # không token/nhóm -> không gửi
    DEM["tin"] = []
    bc3 = tele.BaoCao("", "", moi_giay=1, chat_ids=[])
    kiem("không nhóm -> enabled False", bc3.enabled is False)
    bc3.bat_dau("x")
    kiem("không nhóm -> không đưa vào hàng đợi", bc3.q.empty() is True)

    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (ok[0], loi[0]))
    return 0 if loi[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
