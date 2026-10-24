# -*- coding: utf-8 -*-
"""Dựng GUI thật + chạy thử luồng với máy chủ giả (không tốn credit).

Kiểm: cửa sổ mở, tab, combobox, uoc tinh chi phi, chạy 3 prompt x 1 ảnh
qua mock -> bảng có 3 dòng OK, file tải về đúng, log có KẾT THÚC.
"""

import json
import os
import shutil
import sys
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, HTTPServer

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

import main as T  # noqa: E402

MP4 = (b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
       b"\x00\x00\x00\x08free" + b"x" * 4096)

ANH = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
PORT = 8733
DEM = {"tao": 0, "sua": 0}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _gui(self, ma, obj=None, raw=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(ma)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/balance":
            return self._gui(200, {"credits": 43000, "plan": "grok-unlimited",
                                   "plan_name": "Gói Grok Vô Hạn 30 ngày"})
        if self.path.startswith("/v1/videos/"):
            jid = self.path.rsplit("/", 1)[-1]
            return self._gui(200, {"id": jid, "status": "completed",
                                   "url": "http://127.0.0.1:%d/v1/media/v.mp4" % PORT})
        if self.path.startswith("/v1/media/"):
            self.send_response(200)
            mp4 = self.path.endswith(".mp4")
            body = MP4 if mp4 else ANH
            self.send_header("Content-Type", "video/mp4" if mp4 else "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return self._gui(404, {"error": {"message": "nf"}})

    def do_POST(self):
        dai = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(dai)
        if (self.headers.get("Authorization") or "").endswith("LV_bad"):
            return self._gui(401, {"error": {"message": "invalid api key"}})
        if self.path == "/v1/images/generations":
            DEM["tao"] += 1
            time.sleep(0.25)
            return self._gui(200, {"data": [{"url": "http://127.0.0.1:%d/v1/media/a.png" % PORT}]})
        if self.path == "/v1/videos":
            DEM["video"] = DEM.get("video", 0) + 1
            try:
                DEM.setdefault("prompts", []).append(json.loads(raw.decode()).get("prompt", ""))
            except Exception:
                pass
            time.sleep(DEM.get("delay", 0.2))
            return self._gui(200, {"id": "lv_job_v%d" % DEM["video"], "status": "queued"})
        if self.path == "/v1/images/edits":
            DEM["sua"] += 1
            return self._gui(200, {"data": [{"url": "http://127.0.0.1:%d/v1/media/b.png" % PORT}]})
        return self._gui(404, {"error": {"message": "nf"}})


def main():
    srv = HTTPServer(("127.0.0.1", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    T.api.BASE = "http://127.0.0.1:%d" % PORT

    # config riêng cho test
    goc_cfg = T.CFG_FILE
    T.CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cfg_test.json")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_gui")
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    with open(T.CFG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": "LV_ok", "thu_muc_ra": out, "mo_khi_xong": False,
                   "plan": "grok-unlimited", "plan_name": "Gói Grok Vô Hạn 30 ngày"}, f)

    ok = [0]
    loi = [0]

    def kiem(ten, dk, ct=""):
        if dk:
            ok[0] += 1
            print("PASS  %s" % ten)
        else:
            loi[0] += 1
            print("FAIL  %s  %s" % (ten, ct))

    app = T.App()
    for _ in range(30):
        app.update()

    kiem("cửa sổ mở", app.winfo_ismapped(), str(app.winfo_ismapped()))
    kiem("tiêu đề có version", T.APP_VERSION in app.title(), app.title())
    kiem("4 tab", app.nb.index("end") == 4, str(app.nb.index("end")))
    kiem("model mặc định = Grok 2.0",
         app._model_dang_chon() == "xai/grok-imagine-image-2.0", app._model_dang_chon())
    kiem("aspect Grok 8 lựa chọn", len(app.cb_aspect["values"]) == 8,
         str(len(app.cb_aspect["values"])))
    kiem("quality bật cho 2.0", str(app.cb_quality.cget("state")) == "readonly",
         str(app.cb_quality.cget("state")))
    kiem("lbl plan = vô hạn", "0đ" in app.lbl_plan.cget("text"), app.lbl_plan.cget("text"))

    # đổi sang model cũ -> quality tắt
    app.cb_model.set("Grok Imagine — 10đ/ảnh")
    app._doi_model()
    kiem("quality tắt cho grok-imagine cũ", str(app.cb_quality.cget("state")) == "disabled",
         str(app.cb_quality.cget("state")))
    app.cb_model.set("Nano Banana Pro — 50đ/ảnh")
    app._doi_model()
    kiem("nano: resolution tắt", str(app.cb_res.cget("state")) == "disabled")
    kiem("nano: 3 tỉ lệ", list(app.cb_aspect["values"]) == ["16:9", "9:16", "1:1"],
         str(app.cb_aspect["values"]))
    app.cb_model.set("Grok Imagine 2.0 — 30đ/ảnh")
    app._doi_model()

    # ước tính chi phí
    app.txt_prompt.delete("1.0", "end")
    app.txt_prompt.insert("1.0", "prompt A\nprompt B\n# bo qua\n\nprompt C\n")
    app._cap_nhat_uoc_tinh()
    kiem("đếm prompt bỏ comment/dòng trống", app.lbl_dem_prompt.cget("text") == "3 prompt",
         app.lbl_dem_prompt.cget("text"))
    kiem("ước tính 0đ với gói vô hạn", "0đ" in app.lbl_chi_phi.cget("text"),
         app.lbl_chi_phi.cget("text"))

    # chạy thật qua mock
    app.sp_luong.delete(0, "end")
    app.sp_luong.insert(0, "2")
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(40):
        app.update()
        time.sleep(0.02)

    dong = app.tree.get_children()
    gt = [app.tree.item(i, "values") for i in dong]
    kiem("bảng có 3 dòng", len(dong) == 3, str(len(dong)))
    kiem("cả 3 dòng OK", all(g[3] == "OK" for g in gt), str([g[3] for g in gt]))
    kiem("mock nhận 3 request", DEM["tao"] == 3, str(DEM))
    files = sorted(os.listdir(out))
    kiem("3 file tải về", len(files) == 3, str(files))
    kiem("file đúng đuôi png", all(f.endswith(".png") for f in files), str(files))
    kiem("file có nội dung", all(os.path.getsize(os.path.join(out, f)) == len(ANH) for f in files))
    kiem("progress đầy", app.pb.cget("value") == 3, str(app.pb.cget("value")))
    log = app.txt_log.get("1.0", "end")
    kiem("log có KẾT THÚC", "KẾT THÚC" in log, log[-200:])
    kiem("log OK 3", "OK 3" in log)
    kiem("nút CHẠY bật lại", str(app.btn_chay.cget("state")) == "normal")

    # nhiều API key: key hỏng bị loại, tự chuyển key còn sống
    app.nb.select(0)
    app.cfg["api_keys"] = ["LV_bad", "LV_ok"]
    app.cfg["api_key"] = "LV_bad"
    app.txt_prompt.delete("1.0", "end")
    app.txt_prompt.insert("1.0", "key test 1\nkey test 2\n")
    app._cap_nhat_uoc_tinh()
    app._cap_nhat_key_label()
    kiem("lbl hiện 2 key", "2 key" in app.lbl_plan.cget("text"), app.lbl_plan.cget("text"))
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(40):
        app.update()
        time.sleep(0.02)
    gt2 = [app.tree.item(i, "values") for i in app.tree.get_children()]
    kiem("2 dòng OK dù key đầu hỏng", all(g[3] == "OK" for g in gt2), str([g[3] for g in gt2]))
    kiem("key hỏng bị loại khỏi danh sách", app.cfg["api_keys"] == ["LV_ok"], str(app.cfg["api_keys"]))
    kiem("log có chuyển key", "chuyển key khác" in app.txt_log.get("1.0", "end"))
    kiem("lbl còn 1 key", "1 key" in app.lbl_plan.cget("text"), app.lbl_plan.cget("text"))
    files = sorted(os.listdir(out))

    # chế độ sửa ảnh
    f1 = os.path.join(out, files[0])
    app.nb.select(2)
    app.lst_anh.insert("end", f1)
    app._cap_nhat_dem_anh()
    app.txt_prompt_sua.delete("1.0", "end")
    app.txt_prompt_sua.insert("1.0", "doi bối cảnh <IMAGE_0>\n")
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 30:
        app.update()
        time.sleep(0.03)
    for _ in range(20):
        app.update()
    kiem("chế độ sửa gọi /images/edits", DEM["sua"] == 1, str(DEM))
    kiem("sửa xong có file mới", len(os.listdir(out)) >= 4, str(len(os.listdir(out))))

    # ---- tab video: T2V thuần (không cần ảnh khung)
    app.nb.select(1)
    app.cb_vnguon.set(T.api.DS_NGUON[0])
    app._doi_nguon()
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "vid A" + chr(10) + "vid B" + chr(10))
    app.sp_vmoi.delete(0, "end")
    app.sp_vmoi.insert(0, "1")
    app.cb_vres.set("480p")
    app._cap_nhat_phi_video()
    kiem("video: ước tính theo prompt", "2 prompt" in app.lbl_phi_video.cget("text"),
         app.lbl_phi_video.cget("text"))
    app.cfg["api_key"] = "LV_ok"
    app.cfg["api_keys"] = []
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    gtv = [app.tree.item(i, "values") for i in app.tree.get_children()]
    kiem("video: 2 dòng", len(gtv) == 2, str(len(gtv)))
    kiem("video: cả 2 OK", all(g[3] == "OK" for g in gtv), str(gtv))
    kiem("video: mock nhận 2 job", DEM.get("video") == 2, str(DEM))
    mp4s = [f for f in os.listdir(out) if f.endswith(".mp4")]
    kiem("video: 2 file mp4", len(mp4s) == 2, str(mp4s))
    kiem("video: file đúng dung lượng", all(os.path.getsize(os.path.join(out, f)) == len(MP4)
                                            for f in mp4s), str([os.path.getsize(os.path.join(out, f)) for f in mp4s]))

    # ---- tab video: có ảnh khung (I2V)
    f_png = [f for f in os.listdir(out) if f.endswith(".png")][0]
    app.lst_khung.delete(0, "end")
    app.lst_khung.insert("end", os.path.join(out, f_png))
    app.cb_vnguon.set(T.api.DS_NGUON[1])
    app._doi_nguon()
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "vid I2V" + chr(10))
    app._cap_nhat_phi_video()
    kiem("video: ước tính theo ảnh khung", "1 ảnh khung" in app.lbl_phi_video.cget("text"),
         app.lbl_phi_video.cget("text"))
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    gtv2 = [app.tree.item(i, "values") for i in app.tree.get_children()]
    kiem("video I2V: 1 dòng OK", len(gtv2) == 1 and gtv2[0][3] == "OK", str(gtv2))
    kiem("video I2V: thêm 1 job", DEM.get("video") == 3, str(DEM))
    kiem("video I2V: 3 mp4", len([f for f in os.listdir(out) if f.endswith(".mp4")]) == 3,
         str(os.listdir(out)))

    # ---- MC: nối ngoại hình vào đầu prompt, random không lặp trong 1 vòng
    kiem("ghep MC rỗng giữ nguyên prompt", T.App._ghep_mc("", "abc") == "abc")
    kiem("ghep MC có dấu phẩy",
         T.App._ghep_mc("22-year-old white female MC,", "abc") ==
         "22-year-old white female MC, abc")

    app.cb_vnguon.set(T.api.DS_NGUON[0])
    app._doi_nguon()
    app.lst_khung.delete(0, "end")
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "BASE PROMPT" + chr(10))
    app.txt_mc.delete("1.0", "end")
    app.txt_mc.insert("1.0", "MC_A" + chr(10) + "MC_B" + chr(10) + "MC_C" + chr(10))
    app.sp_vmoi.delete(0, "end")
    app.sp_vmoi.insert(0, "3")
    app._cap_nhat_phi_video()
    kiem("ước tính hiện số MC", "MC: 3 ngoại hình" in app.lbl_phi_video.cget("text"),
         app.lbl_phi_video.cget("text"))
    DEM.pop("prompts", None)
    app.cfg["api_key"] = "LV_ok"
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    gui = DEM.get("prompts") or []
    kiem("MC: 3 video", len(gui) == 3, str(len(gui)))
    kiem("MC: mọi prompt có tiền tố MC + prompt gốc",
         all(p.endswith("BASE PROMPT") and p.split(",")[0] in ("MC_A", "MC_B", "MC_C")
             for p in gui), str(gui))
    kiem("MC: 3 lần random không trùng nhau",
         len({p.split(",")[0] for p in gui}) == 3, str(gui))

    # ---- Dừng → Tiếp tục: không làm lại việc đã OK, không mất việc
    app.cb_vnguon.set(T.api.DS_NGUON[0])
    app._doi_nguon()
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "".join("S%d%s" % (i, chr(10)) for i in range(1, 7)))
    app.txt_mc.delete("1.0", "end")
    app.sp_vmoi.delete(0, "end")
    app.sp_vmoi.insert(0, "1")
    DEM["delay"] = 0.7
    DEM["video"] = 0
    DEM.pop("prompts", None)
    app.cfg["api_key"] = "LV_ok"
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while time.time() - t0 < 1.4:
        app.update()
        time.sleep(0.03)
    app._bam_dung()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 20:
        app.update()
        time.sleep(0.03)
    for _ in range(20):
        app.update()
    so_xong = len(app._da_xong)
    kiem("dừng: có việc đã xong nhưng chưa hết", 0 < so_xong < 6, str(so_xong))
    kiem("dừng: nút Tiếp tục bật", str(app.btn_tiep.cget("state")) == "normal",
         str(app.btn_tiep.cget("state")))
    kiem("dừng: nút Nạp lại bật", str(app.btn_nap.cget("state")) == "normal")
    kiem("dừng: đếm Dừng > 0", app._dem.get("dung", 0) > 0, str(app._dem))
    kiem("dừng: có file tiep_tuc.json", os.path.exists(app._tt_file))

    DEM["delay"] = 0.2
    DEM["video"] = 0          # đếm riêng job của lượt "Tiếp tục"
    app._bam_tiep_tuc()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    gtv3 = [app.tree.item(i, "values") for i in app.tree.get_children()]
    kiem("tiếp tục: đủ 6 dòng", len(gtv3) == 6, str(len(gtv3)))
    kiem("tiếp tục: cả 6 xong (OK hoặc đã xong trước đó)",
         all(g[3] in ("OK", "đã xong") for g in gtv3), str([g[3] for g in gtv3]))
    stt3 = [g[0] for g in gtv3]
    kiem("tiếp tục: không trùng stt", len(set(stt3)) == 6, str(stt3))
    # việc bị cắt giữa chừng khi bấm Dừng phải chạy lại → tối đa +1 job mỗi luồng
    kiem("tiếp tục: không chạy lại việc đã xong",
         6 - so_xong <= DEM["video"] <= 6 - so_xong + 1,
         "%d job / %d xong trước khi dừng" % (DEM["video"], so_xong))

    # chặn khi thiếu key
    app.cfg["api_key"] = ""
    app.cfg["api_keys"] = []
    cu = T.messagebox.showwarning
    T.messagebox.showwarning = lambda *a, **k: ok.__setitem__(0, ok[0] + 1)
    app.txt_prompt.delete("1.0", "end")
    app.txt_prompt.insert("1.0", "x\n")
    app._bam_chay()
    kiem("thiếu key -> cảnh báo, không chạy", not app.dang_chay)
    T.messagebox.showwarning = cu

    app._thoat_app()
    srv.shutdown()
    try:
        os.remove(T.CFG_FILE)
    except Exception:
        pass
    shutil.rmtree(out, ignore_errors=True)
    T.CFG_FILE = goc_cfg
    print("\nKET QUA: PASS %d | FAIL %d" % (ok[0], loi[0]))
    return 0 if loi[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
