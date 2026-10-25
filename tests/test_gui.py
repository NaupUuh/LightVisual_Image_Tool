# -*- coding: utf-8 -*-
"""Dựng GUI thật + chạy thử luồng với máy chủ giả (không tốn credit).

Kiểm: cửa sổ mở, tab, combobox, uoc tinh chi phi, chạy 3 prompt x 1 ảnh
qua mock -> bảng có 3 dòng OK, file tải về đúng, log có KẾT THÚC.
"""

import json
import os
import re
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
def dem_mp4(goc):
    """Đếm mp4 trong cả thư mục con (video được chia theo prompt)."""
    n = 0
    for thu, _, fs in os.walk(goc):
        n += len([f for f in fs if f.endswith(".mp4")])
    return n


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
    mp4s = [os.path.join(t, f) for t, _, fs in os.walk(out)
            for f in fs if f.endswith(".mp4")]
    kiem("video: 2 file mp4", len(mp4s) == 2, str(mp4s))
    kiem("video: file đúng dung lượng", all(os.path.getsize(f) == len(MP4) for f in mp4s),
         str([os.path.getsize(f) for f in mp4s]))

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
    kiem("video I2V: 3 mp4", dem_mp4(out) == 3,
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

    # ---- Nhiều prompt: mỗi prompt 1 thư mục con đánh số tăng dần
    app.cb_vnguon.set(T.api.DS_NGUON[0])
    app._doi_nguon()
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "FOLDER A" + chr(10) + "FOLDER B" + chr(10) + "FOLDER C" + chr(10))
    app.txt_mc.delete("1.0", "end")
    app.sp_vmoi.delete(0, "end")
    app.sp_vmoi.insert(0, "1")
    DEM["video"] = 0
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
    subs = sorted(d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d))
                  and d[:2].isdigit() and "folder_" in d)
    kiem("nhiều prompt: 3 thư mục con", len(subs) == 3, str(subs))
    so_thu_muc = [int(d.split("_", 1)[0]) for d in subs]
    kiem("nhiều prompt: đánh số tăng dần, không trùng số",
         so_thu_muc == sorted(set(so_thu_muc)) and len(so_thu_muc) == 3, str(subs))
    kiem("nhiều prompt: mỗi thư mục 1 mp4",
         all(len([f for f in os.listdir(os.path.join(out, d)) if f.endswith(".mp4")]) == 1
             for d in subs), str(subs))
    kiem("nhiều prompt: tên thư mục theo prompt",
         all(w in " ".join(subs).lower() for w in ("folder_a", "folder_b", "folder_c")), str(subs))
    # chạy lại cùng prompt → dùng lại thư mục cũ, không tạo thêm
    lai = T.App._tao_thu_muc_prompt(out, 1, "FOLDER A")
    kiem("chạy lại: dùng lại thư mục cũ", os.path.basename(lai) == subs[0], os.path.basename(lai))

    # ---- Bug 2026-10-25: prompt khác nhau nhưng 40 ký tự đầu giống nhau
    #      → trước đây bị cắt tên còn 40 ký tự nên gộp chung 1 thư mục
    b_dir = os.path.join(out, "_bug40")
    os.makedirs(b_dir, exist_ok=True)
    dau = "photorealistic vertical breaking news broadcast studio anchor desk red banner "
    p_a = dau + "story about the senate vote"
    p_b = dau + "story about the hurricane relief fund"
    f_a = T.App._tao_thu_muc_prompt(b_dir, 1, p_a)
    f_b = T.App._tao_thu_muc_prompt(b_dir, 2, p_b)
    kiem("40 ký tự giống nhau: 2 prompt ra 2 thư mục", f_a != f_b,
         "%s | %s" % (os.path.basename(f_a), os.path.basename(f_b)))
    kiem("40 ký tự giống nhau: chạy lại đúng prompt cũ → đúng thư mục cũ",
         T.App._tao_thu_muc_prompt(b_dir, 1, p_a) == f_a and
         T.App._tao_thu_muc_prompt(b_dir, 2, p_b) == f_b,
         str(os.listdir(b_dir)))
    kiem("40 ký tự giống nhau: tên thư mục có mã băm phân biệt",
         len({os.path.basename(f_a), os.path.basename(f_b)}) == 2 and
         all(re.search(r"_[0-9a-f]{6}$", os.path.basename(f)) for f in (f_a, f_b)),
         "%s | %s" % (os.path.basename(f_a), os.path.basename(f_b)))

    # ---- Nhiều prompt + nhiều MC: mỗi prompt 1 thư mục (MC khác nhau không làm tách thư mục)
    m_dir = os.path.join(out, "_mc_nhieu")
    os.makedirs(m_dir, exist_ok=True)
    app.cb_vnguon.set(T.api.DS_NGUON[0])
    app._doi_nguon()
    app.e_vra.delete(0, "end")
    app.e_vra.insert(0, m_dir)
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "PROMPT ONE" + chr(10) + "PROMPT TWO" + chr(10))
    app.txt_mc.delete("1.0", "end")
    app.txt_mc.insert("1.0", "MC_A" + chr(10) + "MC_B" + chr(10) + "MC_C" + chr(10))
    app.sp_vmoi.delete(0, "end")
    app.sp_vmoi.insert(0, "2")
    DEM["video"] = 0
    app.cfg["api_key"] = "LV_ok"
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 60:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    subs_m = sorted(d for d in os.listdir(m_dir) if os.path.isdir(os.path.join(m_dir, d)))
    kiem("MC + nhiều prompt: đúng 2 thư mục (không tách theo MC)",
         len(subs_m) == 2, str(subs_m))
    mp4_m = {d: len([f for f in os.listdir(os.path.join(m_dir, d)) if f.endswith(".mp4")])
             for d in subs_m}
    kiem("MC + nhiều prompt: mỗi thư mục 2 mp4 (2 video/prompt)",
         sorted(mp4_m.values()) == [2, 2], str(mp4_m))
    ten_m = " ".join(subs_m).lower()
    kiem("MC + nhiều prompt: thư mục khớp prompt (one/two)",
         "prompt_one" in ten_m and "prompt_two" in ten_m, str(subs_m))

    # ---- Folder ảnh tham chiếu: mỗi ảnh 1 video, dùng xong xoá khỏi folder
    tc_dir = os.path.join(out, "_thamchieu")
    os.makedirs(tc_dir, exist_ok=True)
    for k in range(3):
        with open(os.path.join(tc_dir, "ref%d.png" % k), "wb") as fh:
            fh.write(ANH)
    app.cb_vnguon.set(T.api.DS_NGUON[3])
    app.e_thamchieu.delete(0, "end")
    app.e_thamchieu.insert(0, tc_dir)
    app._doi_nguon()
    app._cap_nhat_dem_tham_chieu()
    kiem("tham chieu: đếm đúng 3 ảnh", "còn 3 ảnh" in app.lbl_tc.cget("text"),
         app.lbl_tc.cget("text"))
    kiem("tham chieu: ước tính 3 video",
         "3 ảnh tham chiếu" in app.lbl_phi_video.cget("text"),
         app.lbl_phi_video.cget("text"))
    app.var_xtc.set(True)
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "REF PROMPT" + chr(10))
    app.txt_mc.delete("1.0", "end")
    DEM["video"] = 0
    app.cfg["api_key"] = "LV_ok"
    n_mp4_truoc = dem_mp4(out)
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 40:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    gt3 = [app.tree.item(i, "values") for i in app.tree.get_children()]
    kiem("tham chieu: 3 dòng OK", len(gt3) == 3 and all(g[3] == "OK" for g in gt3), str(gt3))
    kiem("tham chieu: 3 job", DEM.get("video") == 3, str(DEM.get("video")))
    kiem("tham chieu: thêm 3 mp4",
         dem_mp4(out) == n_mp4_truoc + 3,
         str(os.listdir(out)))
    con_lai = [f for f in os.listdir(tc_dir)]
    kiem("tham chieu: folder rỗng sau khi chạy", con_lai == [], str(con_lai))
    kiem("tham chieu: nhãn về 0 ảnh", "còn 0 ảnh" in app.lbl_tc.cget("text"),
         app.lbl_tc.cget("text"))

    # ---- Mỗi folder ảnh 1 prompt riêng (prompt.txt) + thư mục ra theo tên folder vào
    tc2 = os.path.join(out, "_tc_nhieu")
    os.makedirs(tc2, exist_ok=True)
    bo = {"senate_vote": ("PROMPT SENATE", 2), "hurricane": ("PROMPT HURRICANE", 3)}
    for ten_f, (prompt_f, n_f) in bo.items():
        d_f = os.path.join(tc2, ten_f)
        os.makedirs(d_f, exist_ok=True)
        with open(os.path.join(d_f, "prompt.txt"), "w", encoding="utf-8") as fh:
            fh.write(prompt_f + chr(10))
        for k in range(n_f):
            with open(os.path.join(d_f, "a%d.png" % k), "wb") as fh:
                fh.write(ANH)
    don = T.api.ds_don_vi_tham_chieu(tc2)
    kiem("prompt.txt: tách đúng 2 folder", len(don) == 2, str([d["ten"] for d in don]))
    kiem("prompt.txt: đọc đúng prompt từng folder",
         {d["ten"]: d["prompt"] for d in don} == {k: v[0] for k, v in bo.items()},
         str({d["ten"]: d["prompt"] for d in don}))
    kiem("prompt.txt: đếm ảnh từng folder",
         {d["ten"]: len(d["anh"]) for d in don} == {k: v[1] for k, v in bo.items()},
         str({d["ten"]: len(d["anh"]) for d in don}))

    tc3 = os.path.join(out, "_tc_nhieu_ra")
    os.makedirs(tc3, exist_ok=True)
    app.cb_vnguon.set(T.api.DS_NGUON[3])
    app.e_thamchieu.delete(0, "end")
    app.e_thamchieu.insert(0, tc2)
    app.e_vra.delete(0, "end")
    app.e_vra.insert(0, tc3)
    app._doi_nguon()
    app._cap_nhat_dem_tham_chieu()
    kiem("prompt.txt: nhãn hiện số folder + số ảnh",
         "2 folder" in app.lbl_tc.cget("text") and "5 ảnh" in app.lbl_tc.cget("text"),
         app.lbl_tc.cget("text"))
    kiem("prompt.txt: ước tính 5 video", "5 video" in app.lbl_phi_video.cget("text"),
         app.lbl_phi_video.cget("text"))
    app.var_xtc.set(True)
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "KHONG DUNG" + chr(10))
    app.txt_mc.delete("1.0", "end")
    DEM["video"] = 0
    DEM.pop("prompts", None)
    app.cfg["api_key"] = "LV_ok"
    app.nb.select(1)
    app._bam_chay()
    t0 = time.time()
    while app.dang_chay and time.time() - t0 < 60:
        app.update()
        time.sleep(0.03)
    for _ in range(30):
        app.update()
        time.sleep(0.02)
    subs_tc = sorted(d for d in os.listdir(tc3) if os.path.isdir(os.path.join(tc3, d)))
    kiem("prompt.txt: ra đúng 2 thư mục", len(subs_tc) == 2, str(subs_tc))
    kiem("prompt.txt: tên thư mục ra = tên folder vào",
         all(any(t in d for d in subs_tc) for t in bo), str(subs_tc))
    mp4_tc = {d: len([f for f in os.listdir(os.path.join(tc3, d)) if f.endswith(".mp4")])
              for d in subs_tc}
    kiem("prompt.txt: số video khớp số ảnh từng folder",
         sorted(mp4_tc.values()) == [2, 3], str(mp4_tc))
    gui_tc = DEM.get("prompts") or []
    kiem("prompt.txt: mỗi folder dùng đúng prompt của mình",
         sorted(gui_tc) == ["PROMPT HURRICANE", "PROMPT HURRICANE", "PROMPT HURRICANE",
                            "PROMPT SENATE", "PROMPT SENATE"], str(gui_tc))
    kiem("prompt.txt: ảnh đã dùng bị xoá khỏi folder con",
         all(os.listdir(os.path.join(tc2, t)) in ([], ["prompt.txt"]) for t in bo),
         str({t: os.listdir(os.path.join(tc2, t)) for t in bo}))

    # ---- Folder thiếu prompt.txt → lấy prompt theo thứ tự từ ô PROMPT VIDEO
    tc4 = os.path.join(out, "_tc_thieu_prompt")
    os.makedirs(tc4, exist_ok=True)
    for ten_f in ("khong_co_prompt",):
        d_f = os.path.join(tc4, ten_f)
        os.makedirs(d_f, exist_ok=True)
        for k in range(2):
            with open(os.path.join(d_f, "b%d.png" % k), "wb") as fh:
                fh.write(ANH)
    don4 = T.api.ds_don_vi_tham_chieu(tc4)
    kiem("thiếu prompt.txt: vẫn nhận folder",
         len(don4) == 1 and don4[0]["prompt"] == "" and len(don4[0]["anh"]) == 2, str(don4))
    app.cb_vnguon.set(T.api.DS_NGUON[3])
    app.e_thamchieu.delete(0, "end")
    app.e_thamchieu.insert(0, tc4)
    app._doi_nguon()
    app._cap_nhat_dem_tham_chieu()
    kiem("thiếu prompt.txt: nhãn báo thiếu prompt",
         "thiếu prompt.txt" in app.lbl_tc.cget("text"), app.lbl_tc.cget("text"))
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "DU PHONG" + chr(10))
    DEM["video"] = 0
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
    kiem("thiếu prompt.txt: dùng prompt dự phòng",
         (DEM.get("prompts") or []) == ["DU PHONG", "DU PHONG"], str(DEM.get("prompts")))

    # ---- Không có prompt nào (folder thiếu prompt.txt + ô PROMPT VIDEO trống) → cảnh báo
    cu_w = T.messagebox.showwarning
    dem_w = [0]
    T.messagebox.showwarning = lambda *a, **k: dem_w.__setitem__(0, dem_w[0] + 1)
    try:
        tc5 = os.path.join(out, "_tc_khong_prompt")
        os.makedirs(os.path.join(tc5, "f1"), exist_ok=True)
        with open(os.path.join(tc5, "f1", "c.png"), "wb") as fh:
            fh.write(ANH)
        app.e_thamchieu.delete(0, "end")
        app.e_thamchieu.insert(0, tc5)
        app.txt_prompt_video.delete("1.0", "end")
        app.nb.select(1)          # lượt chạy trước tự nhảy sang tab Kết quả
        app._bam_chay()
    finally:
        T.messagebox.showwarning = cu_w
    kiem("không prompt nào: cảnh báo, không chạy", dem_w[0] >= 1 and not app.dang_chay,
         str(dem_w[0]))

    # ---- Nút 'Ghi prompt.txt' tạo file cho từng folder con
    tc6 = os.path.join(out, "_tc_ghi")
    for ten_f in ("alpha", "beta"):
        d_f = os.path.join(tc6, ten_f)
        os.makedirs(d_f, exist_ok=True)
        with open(os.path.join(d_f, "d.png"), "wb") as fh:
            fh.write(ANH)
    app.e_thamchieu.delete(0, "end")
    app.e_thamchieu.insert(0, tc6)
    app.txt_prompt_video.delete("1.0", "end")
    app.txt_prompt_video.insert("1.0", "GHI MOT" + chr(10) + "GHI HAI" + chr(10))
    cu_i = T.messagebox.showinfo
    T.messagebox.showinfo = lambda *a, **k: None
    try:
        app._ghi_prompt_txt()
    finally:
        T.messagebox.showinfo = cu_i
    kiem("ghi prompt.txt: 2 file được tạo",
         all(os.path.isfile(os.path.join(tc6, t, "prompt.txt")) for t in ("alpha", "beta")),
         str({t: os.listdir(os.path.join(tc6, t)) for t in ("alpha", "beta")}))
    kiem("ghi prompt.txt: nội dung theo thứ tự folder",
         T.api.doc_prompt_folder(os.path.join(tc6, "alpha")) == "GHI MOT" and
         T.api.doc_prompt_folder(os.path.join(tc6, "beta")) == "GHI HAI",
         "%s | %s" % (T.api.doc_prompt_folder(os.path.join(tc6, "alpha")),
                      T.api.doc_prompt_folder(os.path.join(tc6, "beta"))))

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
