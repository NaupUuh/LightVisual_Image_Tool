# -*- coding: utf-8 -*-
"""Kiểm hộp thoại Telegram (nhập token + ID nhóm, không có nút Cập nhật)
và lệnh /baocao trả báo cáo ngay. Dùng máy chủ Telegram giả, không gửi tin thật.

Chạy: python tests/test_tele_hop.py
"""

import json
import os
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


def tim_nut(win, nhan):
    """Tìm nút theo nhãn trong toàn bộ cây widget."""
    thay = []

    def duyet(w):
        for c in w.winfo_children():
            try:
                if isinstance(c, tk.ttk.Button) and c.cget("text") == nhan:
                    thay.append(c)
            except Exception:
                pass
            duyet(c)
    duyet(win)
    return thay


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
    lbl = ctl["lbl"]
    win = lbl.winfo_toplevel()

    kiem("không còn nút Cập nhật", len(tim_nut(win, "Cập nhật")) == 0,
         str(len(tim_nut(win, "Cập nhật"))))
    kiem("có ô token", ctl.get("tok") is not None)
    kiem("có ô ID nhóm", ctl.get("id") is not None)
    kiem("token bị che", str(ctl["tok"].cget("show")) == "•", str(ctl["tok"].cget("show")))

    # ---- nhập token + ID nhóm
    ctl["tok"].delete(0, "end")
    ctl["tok"].insert(0, TOKEN)
    ctl["id"].delete(0, "end")
    ctl["id"].insert(0, "-1001234567890, -1009876543210")
    nut_luu = tim_nut(win, "Lưu")
    kiem("thấy nút Lưu", len(nut_luu) == 1, str(nut_luu))
    if nut_luu:
        nut_luu[0].invoke()
    for _ in range(20):
        app.update()
        time.sleep(0.02)

    kiem("lưu 2 nhóm", app.cfg.get("tele_chat_ids") == ["-1001234567890", "-1009876543210"],
         str(app.cfg.get("tele_chat_ids")))
    kiem("lưu tele_chat_id đầu", app.cfg.get("tele_chat_id") == "-1001234567890",
         str(app.cfg.get("tele_chat_id")))
    kiem("lưu 30 phút", int(app.cfg.get("tele_moi_phut")) == 30,
         str(app.cfg.get("tele_moi_phut")))
    with open(T.CFG_FILE, encoding="utf-8") as f:
        d = json.load(f)
    kiem("cfg ghi ra file", d.get("tele_chat_ids") == ["-1001234567890", "-1009876543210"],
         str(d.get("tele_chat_ids")))

    # ---- nhập link + @kenh
    app._hop_tele()
    for _ in range(20):
        app.update()
    ctl2 = app._hop_tele_ctl
    win2 = ctl2["lbl"].winfo_toplevel()
    ctl2["id"].delete(0, "end")
    ctl2["id"].insert(0, "https://t.me/nhomabc, @kenhxyz, 1001234567890")
    n2 = tim_nut(win2, "Lưu")
    if n2:
        n2[0].invoke()
    for _ in range(20):
        app.update()
        time.sleep(0.02)
    kiem("đọc được link + @kenh + id dương",
         app.cfg.get("tele_chat_ids") == ["@nhomabc", "@kenhxyz", "-1001234567890"],
         str(app.cfg.get("tele_chat_ids")))

    # ---- ID sai -> không lưu, báo lỗi
    app._hop_tele()
    for _ in range(20):
        app.update()
    ctl3 = app._hop_tele_ctl
    win3 = ctl3["lbl"].winfo_toplevel()
    ctl3["id"].delete(0, "end")
    ctl3["id"].insert(0, "linh tinh")
    n3 = tim_nut(win3, "Lưu")
    if n3:
        n3[0].invoke()
    for _ in range(20):
        app.update()
    kiem("ID sai -> báo lỗi, không lưu",
         "không đọc được" in ctl3["lbl"].cget("text")
         and app.cfg.get("tele_chat_ids") == ["@nhomabc", "@kenhxyz", "-1001234567890"],
         ctl3["lbl"].cget("text"))
    win3.destroy()
    for _ in range(5):
        app.update()

    # ---- đưa cfg về 1 nhóm để test gửi
    app.cfg["tele_chat_ids"] = ["-1001234567890"]
    app.cfg["tele_chat_id"] = "-1001234567890"
    app.cfg["tele_token"] = TOKEN
    app.cfg["tele_bat"] = True
    app.cfg["tele_nghe"] = False

    # ---- BaoCao gửi tới nhóm đã chọn
    DEM["tin"] = []
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
    app.cfg["tele_offset"] = 0
    DEM["tin"] = []          # xoá TRƯỚC khi bật: luồng nền có thể trả lời ngay
    app._bat_theo_doi()
    # _bat_theo_doi chạy ở luồng nền (dừng long-poll cũ có thể lâu) -> phải chờ
    t0 = time.time()
    while time.time() - t0 < 20 and not (app.td and app.td.dang_chay()):
        app.update()
        time.sleep(0.05)
    kiem("bật theo dõi", app.td is not None and app.td.dang_chay(), str(app.td))
    t0 = time.time()
    while time.time() - t0 < 12 and not DEM["tin"]:
        app.update()
        time.sleep(0.05)
    kiem("lệnh /baocao trong nhóm -> tool tự trả lời",
         len(DEM["tin"]) >= 1, str(DEM["tin"]))
    if DEM["tin"]:
        kiem("trả lời vào đúng nhóm B", DEM["tin"][0]["chat_id"] == "-1009876543210",
             DEM["tin"][0]["chat_id"])
    log_txt = app.txt_log.get("1.0", "end")
    kiem("log ghi ID nhóm mới thấy", "-1009876543210" in log_txt,
         log_txt[-200:])
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
