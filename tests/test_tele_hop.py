# -*- coding: utf-8 -*-
"""Kiểm hộp thoại Telegram mới: nhập token -> Cập nhật -> tick nhóm -> Lưu,
và lệnh /baocao trả báo cáo ngay. Dùng máy chủ Telegram giả, không gửi tin thật.

Chạy: python tests/test_tele_hop.py
"""

import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

import tkinter as tk  # noqa: E402

import main as T  # noqa: E402
from core import tele  # noqa: E402

PORT = 8745
TOKEN = "123456789:HOP_TEST"

DEM = {"tin": [], "updates": []}

NHOM_A = {"id": -1001234567890, "type": "supergroup", "title": "Nhóm Test A"}
NHOM_B = {"id": -1009876543210, "type": "group", "title": "Nhóm Test B"}


def up(uid, chat, text=""):
    return {"update_id": uid, "message": {"message_id": uid, "chat": chat, "text": text}}


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
                "id": 123456789, "is_bot": True, "username": "test_bot"}})
            return
        if method == "getUpdates":
            off = int(ts.get("offset") or 0)
            self._tra(200, {"ok": True,
                            "result": [u for u in DEM["updates"]
                                       if int(u.get("update_id", 0)) >= off]})
            return
        if method == "sendMessage":
            DEM["tin"].append({"chat_id": str(ts.get("chat_id") or ""),
                               "text": str(ts.get("text") or "")})
            self._tra(200, {"ok": True, "result": {"message_id": len(DEM["tin"])}})
            return
        self._tra(404, {"ok": False, "description": "unknown"})

    do_GET = do_POST


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

    temp = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp")
    goc_cfg = T.CFG_FILE
    T.CFG_FILE = os.path.join(temp, "_cfg_hop.json")
    if os.path.exists(T.CFG_FILE):
        os.remove(T.CFG_FILE)
    with open(T.CFG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": "LV_test", "tele_bat": False, "tele_nghe": False}, f)

    app = T.App()
    for _ in range(30):
        app.update()

    kiem("mặc định 30 phút", int(app.cfg.get("tele_moi_phut")) == 30,
         str(app.cfg.get("tele_moi_phut")))

    # ---- mở hộp thoại
    app._hop_tele()
    for _ in range(20):
        app.update()
    ctl = getattr(app, "_hop_tele_ctl", None)
    kiem("hộp thoại mở", ctl is not None)
    if not ctl:
        app.destroy()
        return 1
    tree, lbl = ctl["tree"], ctl["lbl"]

    # ---- token + bấm Cập nhật
    DEM["updates"] = [up(1, NHOM_A, "chào"), up(2, NHOM_B, "hi"),
                      up(3, {"id": 999, "type": "private", "first_name": "X"}, "/baocao")]
    ctl["tok"].delete(0, "end")
    ctl["tok"].insert(0, TOKEN)
    ctl["btn"].invoke()
    t0 = time.time()
    while time.time() - t0 < 20:
        app.update()
        time.sleep(0.05)
        if tree.get_children():
            break
    for _ in range(20):
        app.update()
        time.sleep(0.02)

    dong = list(tree.get_children())
    kiem("Cập nhật -> hiện 2 nhóm", len(dong) == 2, str(dong))
    kiem("hiện đúng chat id âm", set(dong) == {"-1001234567890", "-1009876543210"}, str(dong))
    kiem("hiện tên nhóm",
         any("Nhóm Test A" in str(tree.item(d, "values")) for d in dong),
         str([tree.item(d, "values") for d in dong]))
    kiem("mặc định chưa tick", all(tree.item(d, "values")[0] == "☐" for d in dong),
         str([tree.item(d, "values")[0] for d in dong]))
    kiem("báo đã thấy nhóm", "2 nhóm" in lbl.cget("text"), lbl.cget("text"))

    # ---- tick 1 nhóm (giả lập bấm chuột vào dòng)
    bb = tree.bbox("-1001234567890", "#1")
    tree.event_generate("<Button-1>", x=int(bb[0]) + 6, y=int(bb[1]) + 6)
    tree.event_generate("<ButtonRelease-1>", x=int(bb[0]) + 6, y=int(bb[1]) + 6)
    for _ in range(5):
        app.update()
    kiem("tick nhóm A", tree.item("-1001234567890", "values")[0] == "☑",
         str(tree.item("-1001234567890", "values")))

    # ---- lưu
    win = tree.winfo_toplevel()
    nut_luu = []
    for w in win.winfo_children():
        try:
            con = w.winfo_children()
        except Exception:
            continue
        for b in con:
            try:
                if isinstance(b, tk.ttk.Button) and b.cget("text") == "Lưu":
                    nut_luu.append(b)
            except Exception:
                pass
    kiem("thấy nút Lưu", len(nut_luu) == 1, str(nut_luu))
    if nut_luu:
        nut_luu[0].invoke()
    for _ in range(20):
        app.update()
        time.sleep(0.02)

    kiem("lưu tele_chat_ids", app.cfg.get("tele_chat_ids") == ["-1001234567890"],
         str(app.cfg.get("tele_chat_ids")))
    kiem("lưu tele_chat_id đầu", app.cfg.get("tele_chat_id") == "-1001234567890",
         str(app.cfg.get("tele_chat_id")))
    kiem("lưu tên nhóm", (app.cfg.get("tele_nhom_ten") or {}).get(
        "-1001234567890") == "Nhóm Test A", str(app.cfg.get("tele_nhom_ten")))
    kiem("lưu 30 phút", int(app.cfg.get("tele_moi_phut")) == 30,
         str(app.cfg.get("tele_moi_phut")))
    kiem("cfg ghi ra file", os.path.exists(T.CFG_FILE))
    with open(T.CFG_FILE, encoding="utf-8") as f:
        d = json.load(f)
    kiem("file có tele_chat_ids", d.get("tele_chat_ids") == ["-1001234567890"], str(d))

    # ---- BaoCao gửi tới nhóm đã chọn
    DEM["tin"] = []
    app.cfg["tele_bat"] = True
    app._bat_baocao()
    kiem("BaoCao dùng nhóm đã chọn",
         app.bc is not None and app.bc.chat_ids == ["-1001234567890"],
         str(app.bc.chat_ids if app.bc else None))
    app._dung_baocao()

    # ---- lệnh /baocao -> trả báo cáo ngay
    DEM["tin"] = []
    app._lan_cuoi = {"ok": 7, "loi": 1, "dung": 0, "tong": 8, "giay": 95,
                     "thu_muc": "D:\\anh\\test"}
    app._tra_loi_baocao("-1001234567890", "Nhóm Test A")
    t0 = time.time()
    while time.time() - t0 < 10 and not DEM["tin"]:
        app.update()
        time.sleep(0.05)
    kiem("/baocao gửi ngay 1 tin", len(DEM["tin"]) == 1, str(len(DEM["tin"])))
    if DEM["tin"]:
        txt = DEM["tin"][0]["text"]
        kiem("/baocao đúng nhóm", DEM["tin"][0]["chat_id"] == "-1001234567890",
             DEM["tin"][0]["chat_id"])
        kiem("/baocao có tiêu đề", "Báo cáo theo yêu cầu" in txt, txt[:120])
        kiem("/baocao nêu lượt gần nhất", "OK 7" in txt, txt[:200])

    # ---- /baocao khi đang chạy -> dùng số liệu hiện tại
    DEM["tin"] = []
    app.dang_chay = True
    app._dem = {"ok": 3, "loi": 0, "dung": 0, "tong": 10}
    app._t0 = time.time() - 42
    app._lan_chay = {"loai": "anh"}
    app._tra_loi_baocao("-1001234567890", "Nhóm Test A")
    t0 = time.time()
    while time.time() - t0 < 10 and not DEM["tin"]:
        app.update()
        time.sleep(0.05)
    kiem("/baocao khi đang chạy -> có tiến độ",
         DEM["tin"] and "3/10" in DEM["tin"][0]["text"],
         DEM["tin"][0]["text"][:200] if DEM["tin"] else "khong gui")
    app.dang_chay = False

    # ---- TheoDoi bắt lệnh trong nhóm -> đẩy vào ui_q
    DEM["updates"] = [up(50, NHOM_B, "/baocao@test_bot")]
    app.cfg["tele_nghe"] = True
    app._bat_theo_doi()
    kiem("bật theo dõi", app.td is not None and app.td.dang_chay(),
         str(app.td))
    DEM["tin"] = []
    t0 = time.time()
    while time.time() - t0 < 12 and not DEM["tin"]:
        app.update()
        time.sleep(0.05)
    kiem("lệnh /baocao trong nhóm -> tool tự trả lời",
         len(DEM["tin"]) >= 1, str(DEM["tin"]))
    if DEM["tin"]:
        kiem("trả lời vào đúng nhóm B", DEM["tin"][0]["chat_id"] == "-1009876543210",
             DEM["tin"][0]["chat_id"])
    app._dung_theo_doi()
    kiem("dừng theo dõi", app.td is None)

    app.destroy()
    T.CFG_FILE = goc_cfg
    for p in ("_cfg_hop.json",):
        try:
            os.remove(os.path.join(temp, p))
        except Exception:
            pass
    srv.shutdown()
    print("\nKET QUA: PASS %d | FAIL %d" % (ok[0], loi[0]))
    return 0 if loi[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
