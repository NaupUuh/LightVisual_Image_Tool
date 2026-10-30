# -*- coding: utf-8 -*-
"""LightVisual Image Tool — tạo ảnh hàng loạt qua API lightvisual.studio.

GUI Tkinter. Logic mạng nằm ở core/api.py (thuần stdlib).
Chạy được trên Python 3.9 trở lên.
"""

import json
import hashlib
import os
import queue
import random
import re
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "1.0.22"
APP_TEN = "LightVisual Image Tool"

THU_MUC_GOC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THU_MUC_GOC)

from core import api  # noqa: E402
from core import tele  # noqa: E402

try:
    from PIL import Image, ImageTk
    CO_PIL = True
except Exception:
    CO_PIL = False

CFG_FILE = os.path.join(THU_MUC_GOC, "config.json")

DEFAULTS = {
    "api_key": "",
    "api_keys": [],
    "model": "xai/grok-imagine-image-2.0",
    "aspect": "1:1",
    "resolution": "1k",
    "quality": "auto",
    "so_anh": 1,
    "so_luong": 3,
    "thu_muc_ra": os.path.join(THU_MUC_GOC, "output"),
    "mo_khi_xong": False,
    "chia_folder": False,
    "giu_nhan_vat": True,
    # video
    "video_model": "xai/grok-imagine-video-1.5",
    "video_sec": 15,
    "video_res": "1080p",
    "video_aspect": "9:16",
    "video_nguon": "",
    "video_moi": 4,
    "video_luong": 2,
    "video_mc": "",
    "video_tham_chieu": "",
    "video_xoa_tham_chieu": True,
    "video_mo_khi_xong": False,
    "video_chia_folder": True,
    # báo cáo tiến độ lên Telegram
    "tele_bat": False,
    "tele_token": "",
    "tele_chat_id": "",
    "tele_chat_ids": [],
    "tele_nhom_ten": {},
    "tele_ten": "",
    "tele_bot_user": "",
    "tele_nghe": True,
    "tele_offset": 0,
    "tele_moi_phut": 30,
}

NEN = "#12141a"
NEN2 = "#191c24"
CHU = "#e6e8ee"
CHU_MO = "#8b93a7"
VIEN = "#2a2f3d"
XANH = "#3ddc97"
DO = "#ff5d6c"
VANG = "#ffc857"


def doc_cfg():
    d = dict(DEFAULTS)
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            d.update(json.load(f) or {})
    except Exception:
        pass
    return d


def luu_cfg(d):
    try:
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def mo_folder(p):
    try:
        if os.path.isdir(p):
            os.startfile(p)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.cfg = doc_cfg()
        self.ui_q = queue.Queue()
        self.job_q = queue.Queue()
        self.job_v_q = queue.Queue()
        self.dang_chay = False
        self._thoat = False        # đang đóng tool -> watchdog thôi bật lại luồng nghe
        self.dung_co = False
        self.ket_qua = []          # [(idx, prompt, duong_dan, loi)]
        self._aid = None
        self._anh_thu = []
        self._dem = {"ok": 0, "loi": 0, "dung": 0, "tong": 0}
        self._t0 = 0.0
        self._khoa_lock = threading.Lock()
        self._khoa_i = 0
        self._kq_khoa = {}
        self._khoa_dem = threading.Lock()

        # lượt chạy để dừng → tiếp tục / nạp lại
        self._lan_chay = None      # {"loai","cau_hinh","viec","so_luong"}
        self._da_xong = set()      # stt đã OK trong lượt này
        # nối thêm việc vào hàng chờ khi đang chạy
        self._hang_cho_khoa = set()   # khoá việc đã nằm trong lượt này
        self._stt_cuoi = 0
        self._q_luot = None
        self._so_worker = 0
        self._wk_lock = threading.Lock()
        self._the_he = 0           # mỗi lượt 1 thế hệ; worker cũ tự thoát
        self._dang_lam = 0         # số việc luồng đang thực sự chạy
        self._dem_lock = threading.Lock()
        self._tt_file = os.path.join(THU_MUC_GOC, "tiep_tuc.json")
        self.bc = None             # đối tượng báo cáo Telegram (core/tele.py)
        self.td = None             # theo dõi lệnh /baocao trong nhóm
        self._aid_moc = None       # id after() đang hẹn mốc báo cáo :00/:30
        self._aid_hen = None       # id after() hẹn _hen_moc lần đầu lúc mở tool
        self._moc_dem = []         # [(thời điểm, số việc đã xong)] — tính tốc độ trượt
        self._moc_dem_lock = threading.Lock()

        self.title("%s v%s" % (APP_TEN, APP_VERSION))
        self.geometry("1240x820")
        self.minsize(1040, 640)
        self.configure(bg=NEN)
        self._dung_style()
        self._dung_gui()
        self.protocol("WM_DELETE_WINDOW", self._thoat_app)
        self._aid = self.after(80, self._xu_ly_ui_q)
        # bật nghe lệnh /baocao ngay khi mở app (nếu đã cấu hình)
        if self.cfg.get("tele_bat") and self.cfg.get("tele_nghe", True) \
                and (self.cfg.get("tele_chat_ids") or self.cfg.get("tele_chat_id")):
            self.after(600, self._bat_theo_doi)
        # canh luồng nghe: nếu chết thì tự bật lại (30s/lần)
        self.after(30000, self._giam_sat_nghe)
        # hẹn báo cáo đúng mốc đồng hồ (:00 và :30) ngay từ lúc mở tool
        self._aid_hen = self.after(1500, self._hen_moc)

    # ------------------------------------------------------------ style
    def _dung_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=NEN, foreground=CHU, fieldbackground=NEN2,
                     bordercolor=VIEN, lightcolor=VIEN, darkcolor=VIEN)
        st.configure("TFrame", background=NEN)
        st.configure("Panel.TFrame", background=NEN2)
        st.configure("TLabel", background=NEN, foreground=CHU)
        st.configure("Panel.TLabel", background=NEN2, foreground=CHU)
        st.configure("Mo.TLabel", background=NEN, foreground=CHU_MO)
        st.configure("MoPanel.TLabel", background=NEN2, foreground=CHU_MO)
        st.configure("TieuDe.TLabel", background=NEN, foreground=CHU,
                     font=("Segoe UI", 10, "bold"))
        st.configure("Ten.TLabel", background=NEN, foreground=XANH,
                     font=("Segoe UI", 13, "bold"))
        st.configure("TButton", background=NEN2, foreground=CHU, padding=(10, 6),
                     borderwidth=1, focusthickness=0)
        st.map("TButton", background=[("active", "#232838")])
        st.configure("Chay.TButton", background=XANH, foreground="#06231a",
                     font=("Segoe UI", 10, "bold"), padding=(14, 8))
        st.map("Chay.TButton", background=[("active", "#33c485")])
        st.configure("Dung.TButton", background="#3a2029", foreground=DO,
                     padding=(14, 8))
        st.map("Dung.TButton", background=[("active", "#4b2634")])
        st.configure("TNotebook", background=NEN, borderwidth=0)
        st.configure("TNotebook.Tab", background=NEN2, foreground=CHU_MO,
                     padding=(18, 8))
        st.map("TNotebook.Tab", background=[("selected", "#242a38")],
               foreground=[("selected", CHU)])
        st.configure("Treeview", background=NEN2, fieldbackground=NEN2,
                     foreground=CHU, rowheight=26, borderwidth=0)
        st.configure("Treeview.Heading", background="#232838", foreground=CHU_MO,
                     relief="flat", padding=(6, 5))
        st.map("Treeview", background=[("selected", "#2f3a52")])
        st.configure("TEntry", fieldbackground=NEN2, foreground=CHU,
                     insertcolor=CHU, padding=5)
        st.configure("TCombobox", fieldbackground=NEN2, background=NEN2,
                     foreground=CHU, arrowcolor=CHU_MO, padding=5,
                     selectbackground=NEN2, selectforeground=CHU,
                     bordercolor=VIEN, lightcolor=VIEN, darkcolor=VIEN)
        # trạng thái readonly của clam không lấy fieldbackground ở trên → phải map riêng,
        # nếu không ô sẽ ra nền sáng + chữ sáng (trắng trên trắng, không đọc được)
        st.map("TCombobox",
               fieldbackground=[("readonly", NEN2), ("disabled", NEN2),
                                ("active", NEN2)],
               foreground=[("readonly", CHU), ("disabled", CHU_MO),
                           ("active", CHU)],
               background=[("readonly", NEN2), ("disabled", NEN2),
                           ("active", "#232838")],
               selectbackground=[("readonly", NEN2), ("disabled", NEN2)],
               selectforeground=[("readonly", CHU), ("disabled", CHU_MO)],
               arrowcolor=[("readonly", CHU_MO), ("disabled", CHU_MO)])
        # danh sách xổ xuống là Listbox Tk cổ điển, phải set qua option database
        self.option_add("*TCombobox*Listbox.background", NEN2)
        self.option_add("*TCombobox*Listbox.foreground", CHU)
        self.option_add("*TCombobox*Listbox.selectBackground", XANH)
        self.option_add("*TCombobox*Listbox.selectForeground", "#06231a")
        self.option_add("*TCombobox*Listbox.font", "{Segoe UI} 9")
        st.configure("TCheckbutton", background=NEN, foreground=CHU)
        st.map("TCheckbutton", background=[("active", NEN)])
        st.configure("Horizontal.TProgressbar", background=XANH,
                     troughcolor=NEN2, borderwidth=0, thickness=14)

    # ------------------------------------------------------------ gui
    def _dung_gui(self):
        top = ttk.Frame(self, padding=(14, 10, 14, 6))
        top.pack(fill="x")
        ttk.Label(top, text=APP_TEN, style="Ten.TLabel").pack(side="left")
        ttk.Label(top, text="  v%s" % APP_VERSION, style="Mo.TLabel").pack(side="left")
        self.lbl_plan = ttk.Label(top, text="", style="Mo.TLabel")
        self.lbl_plan.pack(side="right")
        ttk.Button(top, text="API key", command=self._doi_key).pack(side="right", padx=(0, 10))
        self.btn_tele = ttk.Button(top, text="📣 Telegram", command=self._hop_tele)
        self.btn_tele.pack(side="right", padx=(0, 8))
        self.upd_btn = ttk.Button(top, text="⬆ Cập nhật", command=self._check_update)
        self.upd_btn.pack(side="right", padx=(0, 8))
        ttk.Button(top, text="Tài liệu API", command=lambda: webbrowser.open(
            "https://lightvisual.studio/docs/api/images")).pack(side="right", padx=(0, 8))

        # thanh đáy phải pack TRƯỚC notebook: pack cấp chỗ theo thứ tự, nếu notebook
        # (expand=True) pack trước thì nó nuốt hết chỗ và thanh CHẠY/Dừng co về 1px.
        self._dung_day()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.tab_tao = ttk.Frame(self.nb, padding=12)
        self.tab_video = ttk.Frame(self.nb, padding=12)
        self.tab_sua = ttk.Frame(self.nb, padding=12)
        self.tab_kq = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_tao, text="1. Tạo ảnh hàng loạt")
        self.nb.add(self.tab_video, text="2. Ảnh → Video")
        self.nb.add(self.tab_sua, text="3. Sửa ảnh / giữ nhân vật")
        self.nb.add(self.tab_kq, text="4. Kết quả & nhật ký")

        self._dung_tab_tao()
        self._dung_tab_video()
        self._dung_tab_sua()
        self._dung_tab_kq()

        self._cap_nhat_plan_label()
        self._cap_nhat_uoc_tinh()
        self._cap_nhat_tele_label()

    # ------------------------------------------------ tab 1
    def _dung_tab_tao(self):
        f = self.tab_tao
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=0)
        f.rowconfigure(1, weight=1)

        ttk.Label(f, text="Mỗi dòng là một prompt. Dòng bắt đầu bằng # sẽ bị bỏ qua.",
                  style="Mo.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        khung = ttk.Frame(f)
        khung.grid(row=1, column=0, sticky="nsew")
        khung.rowconfigure(0, weight=1)
        khung.columnconfigure(0, weight=1)

        self.txt_prompt = tk.Text(khung, bg=NEN2, fg=CHU, insertbackground=CHU,
                                  relief="flat", font=("Consolas", 10), wrap="word",
                                  padx=10, pady=8, undo=True)
        self.txt_prompt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(khung, orient="vertical", command=self.txt_prompt.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.txt_prompt.configure(yscrollcommand=sb.set)
        self.txt_prompt.bind("<KeyRelease>", lambda e: self._cap_nhat_uoc_tinh())
        self.txt_prompt.bind("<<Paste>>", lambda e: self.after(50, self._cap_nhat_uoc_tinh))

        hang = ttk.Frame(f)
        hang.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(hang, text="Nhập từ file .txt", command=self._nap_file_prompt).pack(side="left")
        ttk.Button(hang, text="Dán mẫu", command=self._noi_dung_mau).pack(side="left", padx=6)
        ttk.Button(hang, text="Xoá hết", command=self._xoa_prompt).pack(side="left")
        self.lbl_dem_prompt = ttk.Label(hang, text="0 prompt", style="Mo.TLabel")
        self.lbl_dem_prompt.pack(side="left", padx=12)

        # cột phải: tuỳ chọn
        p = ttk.Frame(f, style="Panel.TFrame", padding=14)
        p.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(14, 0))
        p.columnconfigure(1, weight=1)

        def nhan(r, t):
            ttk.Label(p, text=t, style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)

        nhan(0, "Model")
        self.cb_model = ttk.Combobox(p, state="readonly", width=30,
                                     values=[x[1] for x in api.DS_MODEL])
        self.cb_model.grid(row=0, column=1, sticky="ew", pady=5)
        self.cb_model.bind("<<ComboboxSelected>>", self._doi_model)

        nhan(1, "Tỉ lệ")
        self.cb_aspect = ttk.Combobox(p, state="readonly", width=12)
        self.cb_aspect.grid(row=1, column=1, sticky="w", pady=5)
        self.cb_aspect.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon())

        nhan(2, "Độ phân giải")
        self.cb_res = ttk.Combobox(p, state="readonly", width=12, values=api.DS_RES)
        self.cb_res.grid(row=2, column=1, sticky="w", pady=5)
        self.cb_res.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon())

        nhan(3, "Chất lượng")
        self.cb_quality = ttk.Combobox(p, state="readonly", width=12, values=api.DS_QUALITY)
        self.cb_quality.grid(row=3, column=1, sticky="w", pady=5)
        self.cb_quality.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon())

        nhan(4, "Ảnh mỗi prompt")
        self.sp_n = tk.Spinbox(p, from_=1, to=4, width=6, bg=NEN2, fg=CHU,
                               buttonbackground=NEN2, relief="flat", justify="center",
                               command=self._cap_nhat_uoc_tinh)
        self.sp_n.grid(row=4, column=1, sticky="w", pady=5)
        self.sp_n.bind("<KeyRelease>", lambda e: self._cap_nhat_uoc_tinh())

        nhan(5, "Số luồng")
        self.sp_luong = tk.Spinbox(p, from_=1, to=8, width=6, bg=NEN2, fg=CHU,
                                   buttonbackground=NEN2, relief="flat", justify="center")
        self.sp_luong.grid(row=5, column=1, sticky="w", pady=5)

        ttk.Separator(p, orient="horizontal").grid(row=6, column=0, columnspan=2,
                                                   sticky="ew", pady=12)

        nhan(7, "Thư mục ra")
        o = ttk.Frame(p, style="Panel.TFrame")
        o.grid(row=7, column=1, sticky="ew", pady=5)
        o.columnconfigure(0, weight=1)
        self.e_ra = tk.Entry(o, bg=NEN2, fg=CHU, insertbackground=CHU, relief="flat")
        self.e_ra.grid(row=0, column=0, sticky="ew", ipady=4)
        ttk.Button(o, text="...", width=3, command=self._chon_ra).grid(row=0, column=1, padx=(6, 0))

        self.var_mo = tk.BooleanVar(value=bool(self.cfg.get("mo_khi_xong", False)))
        ttk.Checkbutton(p, text="Mở folder khi chạy xong", variable=self.var_mo,
                        command=self._luu_tuy_chon).grid(row=8, column=1, sticky="w", pady=(8, 0))

        self.var_chia_anh = tk.BooleanVar(value=bool(self.cfg.get("chia_folder", True)))
        ttk.Checkbutton(p, text="Mỗi prompt 1 thư mục con (bỏ tick = gộp chung)",
                        variable=self.var_chia_anh, command=self._luu_tuy_chon).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Separator(p, orient="horizontal").grid(row=10, column=0, columnspan=2,
                                                   sticky="ew", pady=12)
        self.lbl_chi_phi = ttk.Label(p, text="", style="Panel.TLabel",
                                     font=("Segoe UI", 10, "bold"))
        self.lbl_chi_phi.grid(row=11, column=0, columnspan=2, sticky="w")
        ttk.Label(p, text="Gói Grok Vô Hạn đang hạn thì ảnh Grok tính 0đ.",
                  style="MoPanel.TLabel", wraplength=250, justify="left").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # nạp lại tuỳ chọn đã lưu
        self._nap_tuy_chon()
        self._noi_dung_mau()

    def _nap_tuy_chon(self):
        c = self.cfg
        self.cb_model.set(api.nhan_model(c.get("model", DEFAULTS["model"])))
        self._cap_nhat_aspect()
        self.cb_aspect.set(c.get("aspect", DEFAULTS["aspect"]))
        if self.cb_aspect.get() not in self.cb_aspect["values"]:
            self.cb_aspect.set(api.ds_aspect(self._model_dang_chon())[0])
        self.cb_res.set(c.get("resolution", "1k"))
        self.cb_quality.set(c.get("quality", "auto"))
        self.sp_n.delete(0, "end")
        self.sp_n.insert(0, str(c.get("so_anh", 1)))
        self.sp_luong.delete(0, "end")
        self.sp_luong.insert(0, str(c.get("so_luong", 3)))
        self.e_ra.delete(0, "end")
        self.e_ra.insert(0, c.get("thu_muc_ra") or DEFAULTS["thu_muc_ra"])
        self._cap_nhat_quality_state()

    def _model_dang_chon(self):
        ten = self.cb_model.get()
        for pid, nhan, _gia, _q in api.DS_MODEL:
            if nhan == ten:
                return pid
        return api.DS_MODEL[0][0]

    def _cap_nhat_aspect(self):
        ds = api.ds_aspect(self._model_dang_chon())
        self.cb_aspect["values"] = ds
        if self.cb_aspect.get() not in ds:
            self.cb_aspect.set(ds[0])

    def _cap_nhat_quality_state(self):
        model = self._model_dang_chon()
        if api.la_nano(model):
            self.cb_res.configure(state="disabled")
            self.cb_quality.configure(state="disabled")
        else:
            self.cb_res.configure(state="readonly")
            self.cb_quality.configure(state="readonly" if api.co_quality(model) else "disabled")
            if not api.co_quality(model):
                self.cb_quality.set("auto")

    def _doi_model(self, _e=None):
        self._cap_nhat_aspect()
        self._cap_nhat_quality_state()
        self._luu_tuy_chon()

    def _luu_tuy_chon(self):
        self.cfg.update({
            "model": self._model_dang_chon(),
            "aspect": self.cb_aspect.get(),
            "resolution": self.cb_res.get(),
            "quality": self.cb_quality.get(),
            "thu_muc_ra": self.e_ra.get().strip(),
            "mo_khi_xong": bool(self.var_mo.get()),
        })
        if hasattr(self, "var_chia_anh"):
            self.cfg["chia_folder"] = bool(self.var_chia_anh.get())
        try:
            self.cfg["so_anh"] = max(1, min(4, int(self.sp_n.get())))
        except Exception:
            self.cfg["so_anh"] = 1
        try:
            self.cfg["so_luong"] = max(1, min(8, int(self.sp_luong.get())))
        except Exception:
            self.cfg["so_luong"] = 3
        luu_cfg(self.cfg)

    # ------------------------------------------------ nhiều API key
    def _ds_key(self):
        """Danh sách key đang dùng. Ưu tiên api_keys, không có thì lấy api_key."""
        ds = [k for k in (self.cfg.get("api_keys") or []) if k]
        if ds:
            return ds
        k = (self.cfg.get("api_key") or "").strip()
        return [k] if k else []

    def _lay_key(self):
        """Lấy key theo vòng tròn, an toàn giữa các luồng."""
        with self._khoa_lock:
            ds = self._ds_key()
            if not ds:
                return ""
            k = ds[self._khoa_i % len(ds)]
            self._khoa_i += 1
            return k

    def _khoa_chet(self, key):
        """Bỏ 1 key khỏi danh sách (key sai / hết hạn)."""
        with self._khoa_lock:
            ds = [k for k in (self.cfg.get("api_keys") or []) if k and k != key]
            self.cfg["api_keys"] = ds
            if self.cfg.get("api_key") == key:
                self.cfg["api_key"] = ds[0] if ds else ""
        self.ui_q.put(("key_chet", key))

    def _cap_nhat_key_label(self):
        ds = self._ds_key()
        if not ds:
            self.lbl_plan.configure(text="Chưa có API key", foreground=DO)
            return
        plan = self.cfg.get("plan_name") or ""
        vo_han = api.la_goi_vo_han(self.cfg.get("plan") or self.cfg.get("plan_name"))
        if not plan and vo_han:
            plan = "Gói Grok Vô Hạn"
        ten = "%d key" % len(ds) if len(ds) > 1 else "1 key"
        if vo_han:
            self.lbl_plan.configure(
                text="● %s · %s — ảnh Grok 0đ" % (ten, plan or "Gói Grok Vô Hạn"),
                foreground=XANH)
        else:
            self.lbl_plan.configure(text="● %s · %s" % (ten, plan or "đã có key"),
                                    foreground=CHU_MO)

    def _chon_ra(self):
        p = filedialog.askdirectory(initialdir=self.e_ra.get() or THU_MUC_GOC,
                                    title="Chọn thư mục lưu ảnh")
        if p:
            self.e_ra.delete(0, "end")
            self.e_ra.insert(0, p)
            self._luu_tuy_chon()

    def _noi_dung_mau(self):
        mau = (
            "# Mỗi dòng dưới đây là 1 ảnh. Sửa hoặc xoá rồi dán danh sách của bạn vào.\n"
            "Chân dung người đàn ông trung niên mặc vest xanh, nền phòng họp báo, "
            "ánh sáng studio, ống kính 85mm, chi tiết da thật\n"
            "Toàn cảnh sân khấu vận động tranh cử ban đêm, khán giả giơ cờ, "
            "đèn sân khấu ngược sáng, không khí căng thẳng\n"
            "Cận cảnh bàn làm việc trong Phòng Bầu dục, giấy tờ và bút ký, "
            "ánh nắng chiều qua cửa sổ, tông màu ấm\n"
        )
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", mau)
        self._cap_nhat_uoc_tinh()

    def _xoa_prompt(self):
        self.txt_prompt.delete("1.0", "end")
        self._cap_nhat_uoc_tinh()

    def _nap_file_prompt(self):
        p = filedialog.askopenfilename(initialdir=THU_MUC_GOC,
                                       filetypes=[("Text", "*.txt *.csv"), ("Tất cả", "*.*")])
        if not p:
            return
        try:
            ds = api.doc_prompt_tu_file(p)
        except Exception as e:
            messagebox.showerror(APP_TEN, "Không đọc được file:\n%s" % e)
            return
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", "\n".join(ds))
        self._cap_nhat_uoc_tinh()
        self._log("Đã nạp %d prompt từ %s" % (len(ds), os.path.basename(p)))

    def _ds_prompt(self):
        raw = self.txt_prompt.get("1.0", "end").splitlines()
        return [t.strip() for t in raw if t.strip() and not t.strip().startswith("#")]

    def _cap_nhat_uoc_tinh(self):
        n = len(self._ds_prompt())
        self.lbl_dem_prompt.configure(text="%d prompt" % n)
        try:
            moi = max(1, min(4, int(self.sp_n.get())))
        except Exception:
            moi = 1
        tong = n * moi
        model = self._model_dang_chon()
        so_gui = len(self._ds_anh_gui()) if api.la_nano(model) else 0
        tien = api.uoc_tinh_chi_phi(model, tong, so_gui, self.cfg.get("plan") or "")
        if tien == 0 and api.la_grok(model):
            chu = "0đ (gói vô hạn)"
        else:
            chu = "~%sđ" % format(tien, ",d").replace(",", ".")
        self.lbl_chi_phi.configure(
            text="%d prompt × %d ảnh = %d ảnh   ·   %s" % (n, moi, tong, chu))

    # ------------------------------------------------ tab 2: ảnh → video
    def _dung_tab_video(self):
        f = self.tab_video
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=2)
        f.rowconfigure(3, weight=3)
        f.rowconfigure(5, weight=2)
        f.rowconfigure(8, weight=3)

        ttk.Label(f, text="1. PROMPT ẢNH — chỉ dùng khi chọn nguồn 'Tạo ảnh từ prompt ảnh'",
                  style="TieuDe.TLabel").grid(row=0, column=0, sticky="w")
        k1 = ttk.Frame(f)
        k1.grid(row=1, column=0, sticky="nsew", pady=(6, 10))
        k1.rowconfigure(0, weight=1)
        k1.columnconfigure(0, weight=1)
        self.txt_prompt_anh = tk.Text(k1, bg=NEN2, fg=CHU, insertbackground=CHU,
                                      relief="flat", font=("Consolas", 10), wrap="word",
                                      padx=10, pady=8, height=3)
        self.txt_prompt_anh.grid(row=0, column=0, sticky="nsew")
        s1 = ttk.Scrollbar(k1, orient="vertical", command=self.txt_prompt_anh.yview)
        s1.grid(row=0, column=1, sticky="ns")
        self.txt_prompt_anh.configure(yscrollcommand=s1.set)
        self.txt_prompt_anh.insert(
            "1.0",
            "Người dẫn chương trình nam mặc vest xanh đứng trước màn hình "
            "BREAKING NEWS đỏ, tay chỉ về phía máy quay, ánh sáng studio\n")

        ttk.Label(f, text="2. PROMPT VIDEO — mỗi dòng 1 video (khi không dùng ảnh khung)",
                  style="TieuDe.TLabel").grid(row=2, column=0, sticky="w")
        k2 = ttk.Frame(f)
        k2.grid(row=3, column=0, sticky="nsew", pady=(6, 10))
        k2.rowconfigure(0, weight=1)
        k2.columnconfigure(0, weight=1)
        self.txt_prompt_video = tk.Text(k2, bg=NEN2, fg=CHU, insertbackground=CHU,
                                        relief="flat", font=("Consolas", 10), wrap="word",
                                        padx=10, pady=8, height=4)
        self.txt_prompt_video.grid(row=0, column=0, sticky="nsew")
        s2 = ttk.Scrollbar(k2, orient="vertical", command=self.txt_prompt_video.yview)
        s2.grid(row=0, column=1, sticky="ns")
        self.txt_prompt_video.configure(yscrollcommand=s2.set)
        self.txt_prompt_video.insert(
            "1.0",
            "9:16 vertical video, no logos. Photorealistic TV news style, "
            "natural expressions and lighting, slow push in\n")
        self.txt_prompt_video.bind("<<Paste>>", lambda e: self.after(50, self._cap_nhat_phi_video))

        # ngoại hình MC — random nối vào đầu prompt
        ttk.Label(f, text="3. NGOẠI HÌNH MC — mỗi dòng 1 ngoại hình, random nối vào đầu prompt video",
                  style="TieuDe.TLabel").grid(row=4, column=0, sticky="w")
        k4 = ttk.Frame(f)
        k4.grid(row=5, column=0, sticky="nsew", pady=(6, 10))
        k4.rowconfigure(0, weight=1)
        k4.columnconfigure(0, weight=1)
        self.txt_mc = tk.Text(k4, bg=NEN2, fg=CHU, insertbackground=CHU,
                              relief="flat", font=("Consolas", 10), wrap="word",
                              padx=10, pady=8, height=4)
        self.txt_mc.grid(row=0, column=0, sticky="nsew")
        s4 = ttk.Scrollbar(k4, orient="vertical", command=self.txt_mc.yview)
        s4.grid(row=0, column=1, sticky="ns")
        self.txt_mc.configure(yscrollcommand=s4.set)
        self.txt_mc.insert(
            "1.0",
            self.cfg.get("video_mc") or
            "22-year-old white female MC\n"
            "24-year-old black male MC\n"
            "30-year-old asian female MC\n")
        self.txt_mc.bind("<<Paste>>", lambda e: self.after(50, self._cap_nhat_phi_video))
        self.txt_mc.bind("<KeyRelease>", lambda e: self._cap_nhat_phi_video())

        # nguồn cảnh đầu
        nd = ttk.Frame(f)
        nd.grid(row=6, column=0, sticky="ew")
        ttk.Label(nd, text="Nguồn cảnh đầu", style="TieuDe.TLabel").pack(side="left")
        self.cb_vnguon = ttk.Combobox(nd, state="readonly", width=34, values=api.DS_NGUON)
        self.cb_vnguon.pack(side="left", padx=(8, 0))
        self.cb_vnguon.set(self.cfg.get("video_nguon") or api.DS_NGUON[0])
        if self.cb_vnguon.get() not in api.DS_NGUON:
            self.cb_vnguon.set(api.DS_NGUON[0])
        self.cb_vnguon.bind("<<ComboboxSelected>>", lambda e: self._doi_nguon())

        # ảnh khung
        kh = ttk.Frame(f)
        kh.grid(row=7, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(kh, text="Ảnh khung", style="TieuDe.TLabel").pack(side="left")
        ttk.Button(kh, text="Thêm ảnh...", command=self._them_khung).pack(side="left", padx=6)
        ttk.Button(kh, text="Thêm folder", command=self._them_folder_khung).pack(side="left")
        ttk.Button(kh, text="Bỏ ảnh chọn", command=self._bo_khung).pack(side="left", padx=6)
        ttk.Button(kh, text="Lấy ảnh vừa tạo", command=self._lay_anh_vua_tao).pack(side="left")
        self.lbl_khung = ttk.Label(kh, text="0 ảnh", style="Mo.TLabel")
        self.lbl_khung.pack(side="left", padx=10)

        k3 = ttk.Frame(f)
        k3.grid(row=8, column=0, sticky="nsew", pady=(6, 0))
        k3.rowconfigure(0, weight=1)
        k3.columnconfigure(0, weight=1)
        self.lst_khung = tk.Listbox(k3, bg=NEN2, fg=CHU, relief="flat",
                                    selectmode="extended", activestyle="none",
                                    highlightthickness=0, height=4)
        self.lst_khung.grid(row=0, column=0, sticky="nsew")
        self.lst_khung.bind("<Delete>", lambda e: self._bo_khung())
        s3 = ttk.Scrollbar(k3, orient="vertical", command=self.lst_khung.yview)
        s3.grid(row=0, column=1, sticky="ns")
        self.lst_khung.configure(yscrollcommand=s3.set)

        # folder ảnh tham chiếu — mỗi ảnh dùng 1 lần rồi xoá
        tc = ttk.Frame(f)
        tc.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(tc, text="Folder ảnh tham chiếu", style="TieuDe.TLabel").pack(side="left")
        self.e_thamchieu = tk.Entry(tc, bg=NEN2, fg=CHU, insertbackground=CHU,
                                    relief="flat", width=52)
        self.e_thamchieu.pack(side="left", padx=(8, 0), ipady=3)
        self.e_thamchieu.insert(0, self.cfg.get("video_tham_chieu") or "")
        self.e_thamchieu.bind("<FocusOut>", lambda e: self._cap_nhat_dem_tham_chieu())
        ttk.Button(tc, text="...", width=3, command=self._chon_tham_chieu).pack(side="left", padx=6)
        ttk.Button(tc, text="Xem", width=5, command=self._xem_tham_chieu).pack(side="left")
        ttk.Button(tc, text="Ghi prompt.txt", command=self._ghi_prompt_txt).pack(side="left", padx=(6, 0))
        self.var_xtc = tk.BooleanVar(value=bool(self.cfg.get("video_xoa_tham_chieu", True)))
        ttk.Checkbutton(tc, text="Xoá ảnh sau khi dùng", variable=self.var_xtc,
                        command=self._luu_tuy_chon_video).pack(side="left", padx=(10, 0))
        self.lbl_tc = ttk.Label(tc, text="", style="Mo.TLabel")
        self.lbl_tc.pack(side="left", padx=8)
        self._cap_nhat_dem_tham_chieu()

        # panel tuỳ chọn video
        p = ttk.Frame(f, style="Panel.TFrame", padding=14)
        p.grid(row=0, column=1, rowspan=10, sticky="nsew", padx=(14, 0))
        p.columnconfigure(1, weight=1)

        def nhan(r, t):
            ttk.Label(p, text=t, style="Panel.TLabel").grid(row=r, column=0, sticky="w", pady=5)

        nhan(0, "Model video")
        self.cb_vmodel = ttk.Combobox(p, state="readonly", width=26,
                                      values=[x[1] for x in api.DS_VIDEO_MODEL])
        self.cb_vmodel.grid(row=0, column=1, sticky="ew", pady=5)
        self.cb_vmodel.set(api.nhan_video(self.cfg.get("video_model", DEFAULTS["video_model"])))
        self.cb_vmodel.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon_video())

        nhan(1, "Số giây")
        self.sp_vsec = tk.Spinbox(p, from_=1, to=15, width=6, bg=NEN2, fg=CHU,
                                  buttonbackground=NEN2, relief="flat", justify="center",
                                  command=self._cap_nhat_phi_video)
        self.sp_vsec.grid(row=1, column=1, sticky="w", pady=5)
        self.sp_vsec.bind("<KeyRelease>", lambda e: self._cap_nhat_phi_video())
        self.sp_vsec.delete(0, "end")
        self.sp_vsec.insert(0, str(self.cfg.get("video_sec", DEFAULTS["video_sec"])))

        nhan(2, "Độ phân giải")
        self.cb_vres = ttk.Combobox(p, state="readonly", width=10, values=api.DS_VIDEO_RES)
        self.cb_vres.grid(row=2, column=1, sticky="w", pady=5)
        self.cb_vres.set(self.cfg.get("video_res", DEFAULTS["video_res"]))
        self.cb_vres.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon_video())

        nhan(3, "Khung hình")
        self.cb_vaspect = ttk.Combobox(p, state="readonly", width=10, values=api.DS_VIDEO_ASPECT)
        self.cb_vaspect.grid(row=3, column=1, sticky="w", pady=5)
        self.cb_vaspect.set(self.cfg.get("video_aspect", DEFAULTS["video_aspect"]))
        self.cb_vaspect.bind("<<ComboboxSelected>>", lambda e: self._luu_tuy_chon_video())

        nhan(4, "Video mỗi prompt")
        self.sp_vmoi = tk.Spinbox(p, from_=1, to=50, width=6, bg=NEN2, fg=CHU,
                                  buttonbackground=NEN2, relief="flat", justify="center",
                                  command=self._cap_nhat_phi_video)
        self.sp_vmoi.grid(row=4, column=1, sticky="w", pady=5)
        self.sp_vmoi.delete(0, "end")
        self.sp_vmoi.insert(0, str(self.cfg.get("video_moi", DEFAULTS["video_moi"]) or 4))
        self.sp_vmoi.bind("<KeyRelease>", lambda e: self._cap_nhat_phi_video())
        ttk.Label(p, text="mỗi video lấy 1 ngoại hình MC khác nhau", style="MoPanel.TLabel",
                  wraplength=190, justify="left").grid(row=5, column=1, sticky="w")

        ttk.Separator(p, orient="horizontal").grid(row=6, column=0, columnspan=2,
                                                   sticky="ew", pady=12)

        nhan(7, "Thư mục ra")
        o = ttk.Frame(p, style="Panel.TFrame")
        o.grid(row=7, column=1, sticky="ew", pady=5)
        o.columnconfigure(0, weight=1)
        self.e_vra = tk.Entry(o, bg=NEN2, fg=CHU, insertbackground=CHU, relief="flat")
        self.e_vra.grid(row=0, column=0, sticky="ew", ipady=4)
        self.e_vra.insert(0, self.cfg.get("thu_muc_ra") or DEFAULTS["thu_muc_ra"])
        ttk.Button(o, text="...", width=3, command=self._chon_vra).grid(row=0, column=1, padx=(6, 0))

        self.var_vmo = tk.BooleanVar(value=bool(self.cfg.get("video_mo_khi_xong", False)))
        ttk.Checkbutton(p, text="Mở folder khi chạy xong", variable=self.var_vmo).grid(
            row=8, column=1, sticky="w", pady=(8, 0))

        self.var_chia = tk.BooleanVar(value=bool(self.cfg.get("video_chia_folder", True)))
        ttk.Checkbutton(p, text="Mỗi prompt 1 thư mục con (bỏ tick = gộp chung)",
                        variable=self.var_chia, command=self._luu_tuy_chon_video).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Separator(p, orient="horizontal").grid(row=10, column=0, columnspan=2,
                                                   sticky="ew", pady=12)
        self.lbl_phi_video = ttk.Label(p, text="", style="Panel.TLabel",
                                       font=("Segoe UI", 10, "bold"))
        self.lbl_phi_video.grid(row=11, column=0, columnspan=2, sticky="w")
        ttk.Label(p, text="Gói Grok Vô Hạn đang hạn thì video Grok tính 0đ.",
                  style="MoPanel.TLabel", wraplength=250, justify="left").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self._doi_nguon()

    def _ds_anh_khung(self):
        return [self.lst_khung.get(i) for i in range(self.lst_khung.size())]

    # ------------------------------------------------ folder ảnh tham chiếu
    def _ds_tham_chieu(self):
        """Ảnh còn trong folder tham chiếu (mỗi ảnh chỉ dùng 1 lần)."""
        p = self.e_thamchieu.get().strip() if hasattr(self, "e_thamchieu") else ""
        return api.ds_anh_trong_folder(p) if p else []

    def _ds_don_vi_tham_chieu(self):
        """Mỗi folder con = 1 prompt riêng (prompt.txt trong folder)."""
        p = self.e_thamchieu.get().strip() if hasattr(self, "e_thamchieu") else ""
        return api.ds_don_vi_tham_chieu(p) if p else []

    def _cap_nhat_dem_tham_chieu(self):
        if not hasattr(self, "lbl_tc"):
            return
        p = self.e_thamchieu.get().strip()
        if not p:
            self.lbl_tc.configure(text="chưa chọn folder")
        elif not os.path.isdir(p):
            self.lbl_tc.configure(text="không thấy folder")
        else:
            don = api.ds_don_vi_tham_chieu(p)
            n = sum(len(d["anh"]) for d in don)
            thieu = [d["ten"] for d in don if not d["prompt"]]
            if len(don) <= 1:
                chu = "còn %d ảnh" % n
            else:
                chu = "%d folder · %d ảnh" % (len(don), n)
            if thieu:
                chu += " · %d folder thiếu prompt.txt" % len(thieu)
            self.lbl_tc.configure(text=chu)
        self._cap_nhat_phi_video()

    def _chon_tham_chieu(self):
        p = filedialog.askdirectory(initialdir=self.e_thamchieu.get() or THU_MUC_GOC,
                                    title="Chọn folder ảnh tham chiếu")
        if not p:
            return
        self.e_thamchieu.delete(0, "end")
        self.e_thamchieu.insert(0, p)
        self._luu_tuy_chon_video()
        self._cap_nhat_dem_tham_chieu()

    def _xem_tham_chieu(self):
        p = self.e_thamchieu.get().strip()
        if not p or not os.path.isdir(p):
            messagebox.showinfo(APP_TEN, "Chưa chọn folder ảnh tham chiếu.")
            return
        self._mo_thu_muc(p)

    def _ghi_prompt_txt(self):
        """Ghi prompt.txt vào từng folder con — mỗi folder 1 prompt, lấy theo thứ tự
        từ ô '2. PROMPT VIDEO' (hoặc giữ nguyên file đã có nếu không đủ prompt)."""
        goc = self.e_thamchieu.get().strip()
        if not goc or not os.path.isdir(goc):
            messagebox.showinfo(APP_TEN, "Chưa chọn folder ảnh tham chiếu.")
            return
        don = api.ds_don_vi_tham_chieu(goc)
        if not don:
            messagebox.showinfo(APP_TEN, "Folder này không có ảnh nào để ghi prompt.")
            return
        ds_pv = self._ds_prompt_video()
        if not ds_pv:
            messagebox.showwarning(APP_TEN, "Chưa có prompt video để ghi.\n"
                                            "Nhập prompt ở ô '2. PROMPT VIDEO' trước.")
            return
        da_co = sum(1 for d in don if d["prompt"])
        if da_co and not messagebox.askyesno(
                APP_TEN, "%d/%d folder đã có prompt.txt.\nGhi đè bằng prompt lấy theo "
                         "thứ tự từ ô PROMPT VIDEO?" % (da_co, len(don))):
            return
        n = 0
        for k, d in enumerate(don):
            noi_dung = ds_pv[k % len(ds_pv)]
            try:
                with open(os.path.join(d["folder"], "prompt.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(noi_dung + "\n")
                n += 1
            except Exception as e:
                self._log("Không ghi được prompt.txt vào %s (%s)" % (d["ten"], e))
        self._cap_nhat_dem_tham_chieu()
        self._log("Đã ghi prompt.txt cho %d/%d folder (%d prompt nguồn)." %
                  (n, len(don), len(ds_pv)))
        messagebox.showinfo(APP_TEN, "Đã ghi prompt.txt cho %d/%d folder.\n"
                                     "Mở folder kiểm tra/sửa lại từng prompt nếu cần." % (n, len(don)))

    def _mo_thu_muc(self, p):
        mo_folder(p)

    def _xoa_anh_tham_chieu(self, p):
        """Ảnh tham chiếu đã dùng xong → xoá khỏi folder để không bị dùng lại."""
        try:
            if os.path.isfile(p):
                os.remove(p)
                self.ui_q.put(("log", "Đã xoá ảnh tham chiếu: %s" % os.path.basename(p)))
        except Exception as e:
            self.ui_q.put(("log", "Không xoá được %s (%s)" % (os.path.basename(p), e)))
        self.ui_q.put(("dem_tc", None))

    @staticmethod
    def _slug_ten(nguon):
        """Vài từ đầu (cắt theo TỪ, không cắt giữa từ) của 1 chuỗi."""
        day_du = api.ten_an_toan(nguon, 400)
        tu = [t for t in day_du.split("_") if t]
        ten = ""
        for t in tu:
            ung = (ten + "_" + t) if ten else t
            if len(ung) > 48:
                break
            ten = ung
        if not ten:
            ten = (tu[0][:48] if tu else "prompt")
        return ten

    @classmethod
    def _ten_thu_muc(cls, prompt):
        """Tên thư mục ngắn (cắt theo TỪ) + mã băm 6 ký tự của prompt ĐẦY ĐỦ.

        Chỉ cắt 40 ký tự đầu là sai: nhiều prompt khác nhau dùng chung phần mở
        đầu (vd "photorealistic vertical breaking news broadcast studio…") nên
        bị coi là cùng 1 prompt và dồn chung 1 thư mục. Mã băm lấy trên toàn bộ
        prompt nên 2 prompt khác nhau luôn ra 2 thư mục khác nhau, và chạy lại
        đúng prompt cũ vẫn nhận ra thư mục cũ.
        """
        bam = hashlib.sha1((prompt or "").strip().encode("utf-8")).hexdigest()[:6]
        return "%s_%s" % (cls._slug_ten(prompt), bam)

    @classmethod
    def _ten_thu_muc_folder(cls, ten_folder):
        """Tên thư mục ra đặt theo ĐÚNG tên folder ảnh đầu vào (+ băm 6 ký tự).

        Băm lấy trên tên folder (không phải trên prompt) để chạy lại bao nhiêu
        lần cũng về đúng thư mục cũ, và 2 folder khác tên nhưng ra cùng slug
        vẫn không bị gộp.
        """
        ten = (ten_folder or "").strip() or "tham_chieu"
        bam = hashlib.sha1(("folder:" + ten).encode("utf-8")).hexdigest()[:6]
        return "%s_%s" % (cls._slug_ten(ten), bam)

    @classmethod
    def _cap_thu_muc(cls, goc, so, ten):
        """Tạo (hoặc dùng lại) thư mục con 'NN_<ten>' — đánh số tăng dần.

        Đánh số không nhảy số, không trùng: thư mục đã có (khớp mã băm cuối tên)
        thì dùng lại đúng thư mục đó để dồn video mới vào cùng chỗ.
        """
        bam = ten.rsplit("_", 1)[-1]
        os.makedirs(goc, exist_ok=True)
        try:
            co_san = sorted(d for d in os.listdir(goc)
                            if os.path.isdir(os.path.join(goc, d)) and
                            re.match(r"^\d{2,}_", d))
        except Exception:
            co_san = []
        for d in co_san:                      # đã có thư mục cho mục này → dùng lại
            if d.rsplit("_", 1)[-1] == bam:
                return os.path.join(goc, d)
        # mục mới → cấp số kế tiếp của dãy, không dùng lại số đã có
        so_moi = so
        for d in co_san:
            m = re.match(r"^(\d{2,})_", d)
            if m:
                so_moi = max(so_moi, int(m.group(1)) + 1)
        so = so_moi
        while True:
            p = os.path.join(goc, "%02d_%s" % (so, ten))
            if not os.path.exists(p):
                os.makedirs(p, exist_ok=True)
                return p
            so += 1                           # trùng tên khác nguồn → nhảy số

    @classmethod
    def _tao_thu_muc_prompt(cls, goc, so, prompt):
        """Tạo (hoặc dùng lại) thư mục con 'NN_<prompt>_<hash>' cho 1 prompt."""
        return cls._cap_thu_muc(goc, so, cls._ten_thu_muc(prompt))

    @classmethod
    def _tao_thu_muc_folder(cls, goc, so, ten_folder):
        """Tạo (hoặc dùng lại) thư mục con đặt theo tên folder ảnh đầu vào."""
        return cls._cap_thu_muc(goc, so, cls._ten_thu_muc_folder(ten_folder))

    def _cap_nhat_dem_khung(self):
        self.lbl_khung.configure(text="%d ảnh" % self.lst_khung.size())
        self._cap_nhat_phi_video()

    def _them_khung(self):
        ds = filedialog.askopenfilenames(
            initialdir=THU_MUC_GOC,
            filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.webp"), ("Tất cả", "*.*")])
        for p in ds:
            self.lst_khung.insert("end", p)
        self._cap_nhat_dem_khung()

    def _them_folder_khung(self):
        p = filedialog.askdirectory(initialdir=THU_MUC_GOC, title="Chọn folder ảnh khung")
        if not p:
            return
        for x in api.ds_anh_trong_folder(p):
            self.lst_khung.insert("end", x)
        self._cap_nhat_dem_khung()

    def _bo_khung(self):
        for i in reversed(self.lst_khung.curselection()):
            self.lst_khung.delete(i)
        self._cap_nhat_dem_khung()

    def _lay_anh_vua_tao(self):
        """Lấy ảnh vừa tạo ở tab 1 (hoặc ảnh đang chọn ở bảng kết quả) làm khung."""
        ds = [k[2] for k in self.ket_qua if k[2] and os.path.isfile(k[2])]
        if not ds:
            messagebox.showinfo(APP_TEN, "Chưa có ảnh nào được tạo trong phiên này.")
            return
        for p in ds:
            if p not in self._ds_anh_khung():
                self.lst_khung.insert("end", p)
        self._cap_nhat_dem_khung()

    def _dung_lam_khung(self):
        """Từ bảng kết quả → nạp ảnh đang chọn sang tab 2."""
        ds = []
        for it in self.tree.selection():
            f = self.tree.item(it, "values")[4]
            if f and os.path.isfile(f):
                ds.append(f)
        if not ds:
            messagebox.showinfo(APP_TEN, "Chọn một dòng có file ảnh trong bảng trước.")
            return
        for p in ds:
            if p not in self._ds_anh_khung():
                self.lst_khung.insert("end", p)
        self._cap_nhat_dem_khung()
        self.cb_vnguon.set(api.DS_NGUON[1])
        self._doi_nguon()
        self.nb.select(1)
        self._log("Đã nạp %d ảnh làm khung — nhập prompt video rồi bấm CHẠY." % len(ds))

    def _chon_vra(self):
        p = filedialog.askdirectory(initialdir=self.e_vra.get() or THU_MUC_GOC,
                                    title="Chọn thư mục lưu video")
        if p:
            self.e_vra.delete(0, "end")
            self.e_vra.insert(0, p)
            self._luu_tuy_chon_video()

    def _model_video_dang_chon(self):
        ten = self.cb_vmodel.get()
        for pid, nhan in api.DS_VIDEO_MODEL:
            if nhan == ten:
                return pid
        return api.DS_VIDEO_MODEL[0][0]

    def _luu_tuy_chon_video(self):
        try:
            self.cfg["video_sec"] = max(1, min(15, int(self.sp_vsec.get())))
        except Exception:
            self.cfg["video_sec"] = 6
        try:
            self.cfg["video_moi"] = max(1, min(50, int(self.sp_vmoi.get())))
        except Exception:
            self.cfg["video_moi"] = 1
        self.cfg["video_luong"] = len(self._ds_key()) or 1
        self.cfg["video_mc"] = self.txt_mc.get("1.0", "end").strip()
        self.cfg["video_mo_khi_xong"] = bool(self.var_vmo.get())
        if hasattr(self, "var_chia"):
            self.cfg["video_chia_folder"] = bool(self.var_chia.get())
        if hasattr(self, "e_thamchieu"):
            self.cfg["video_tham_chieu"] = self.e_thamchieu.get().strip()
            self.cfg["video_xoa_tham_chieu"] = bool(self.var_xtc.get())
        self.cfg.update({
            "video_model": self._model_video_dang_chon(),
            "video_res": self.cb_vres.get(),
            "video_aspect": self.cb_vaspect.get(),
            "video_nguon": self.cb_vnguon.get(),
        })
        luu_cfg(self.cfg)
        self._cap_nhat_phi_video()

    def _dang_chon_khung(self):
        return self.cb_vnguon.get() == api.DS_NGUON[1]

    def _dang_chon_prompt_anh(self):
        return self.cb_vnguon.get() == api.DS_NGUON[2]

    def _dang_chon_tham_chieu(self):
        return self.cb_vnguon.get() == api.DS_NGUON[3]

    def _doi_nguon(self):
        """Đổi nguồn cảnh đầu → bật/tắt ô nhập cho khớp.

        Danh sách ảnh khung luôn bật: Listbox ở state "disabled" nuốt luôn lệnh
        insert() của nút 'Thêm ảnh' / 'Lấy ảnh vừa tạo' (im lặng, không báo lỗi).
        """
        self._luu_tuy_chon_video()
        prompt_anh = self._dang_chon_prompt_anh()
        try:
            self.txt_prompt_anh.configure(state="normal" if prompt_anh else "disabled",
                                          bg=NEN2 if prompt_anh else "#0d0f14")
            self.lst_khung.configure(bg=NEN2 if self._dang_chon_khung() else "#0d0f14")
            self.e_thamchieu.configure(bg=NEN2 if self._dang_chon_tham_chieu() else "#0d0f14")
        except tk.TclError:
            pass
        self._cap_nhat_phi_video()

    def _ds_prompt_video(self):
        return [t.strip() for t in self.txt_prompt_video.get("1.0", "end").splitlines()
                if t.strip() and not t.strip().startswith("#")]

    def _ds_prompt_anh(self):
        return [t.strip() for t in self.txt_prompt_anh.get("1.0", "end").splitlines()
                if t.strip() and not t.strip().startswith("#")]

    def _ds_mc(self):
        """Danh sách ngoại hình MC (mỗi dòng 1 cái)."""
        return [t.strip() for t in self.txt_mc.get("1.0", "end").splitlines()
                if t.strip() and not t.strip().startswith("#")]

    @staticmethod
    def _ghep_mc(mc, prompt):
        """Nối ngoại hình MC vào đầu prompt; MC rỗng thì giữ nguyên prompt."""
        mc = (mc or "").strip().rstrip(",.")
        if not mc:
            return prompt
        return "%s, %s" % (mc, prompt.lstrip())

    def _cap_nhat_phi_video(self):
        if not hasattr(self, "lbl_phi_video"):
            return
        try:
            giay = max(1, min(15, int(self.sp_vsec.get())))
        except Exception:
            giay = 6
        try:
            moi = max(1, min(50, int(self.sp_vmoi.get())))
        except Exception:
            moi = 1
        n_anh = len(self._ds_anh_khung()) if hasattr(self, "lst_khung") else 0
        so_prompt = len(self._ds_prompt_video()) if hasattr(self, "txt_prompt_video") else 0
        so_mc = len(self._ds_mc()) if hasattr(self, "txt_mc") else 0

        if self._dang_chon_khung():
            so_video = max(1, n_anh) * moi
            mo_ta = "%d ảnh khung × %d" % (n_anh, moi)
            co_khung = n_anh > 0
        elif self._dang_chon_prompt_anh():
            n_ia = max(1, len(self._ds_prompt_anh()))
            so_video = n_ia * moi
            mo_ta = "%d prompt ảnh × %d" % (n_ia, moi)
            co_khung = True          # có phí ảnh khung phải tạo
        elif self._dang_chon_tham_chieu():
            don = self._ds_don_vi_tham_chieu()
            n_tc = sum(len(d["anh"]) for d in don)
            so_video = max(1, n_tc)
            if len(don) > 1:
                mo_ta = "%d folder × %d ảnh" % (len(don), n_tc)
            else:
                mo_ta = "%d ảnh tham chiếu × 1" % n_tc
            co_khung = n_tc > 0
        else:
            so_video = max(1, so_prompt) * moi
            mo_ta = "%d prompt × %d" % (max(1, so_prompt), moi)
            co_khung = False

        tien = api.uoc_tinh_phi_video(self.cb_vres.get(), giay, co_khung,
                                      self.cfg.get("plan") or "")
        tien = tien * so_video
        chu = "0đ (gói vô hạn)" if tien == 0 else "~%sđ" % format(tien, ",d").replace(",", ".")
        self.lbl_phi_video.configure(
            text="%s = %d video · %ds · %s\nMC: %d ngoại hình%s\n%s" %
                 (mo_ta, so_video, giay, self.cb_vres.get(), so_mc,
                  "" if so_mc else " (không nối)", chu))

    # ------------------------------------------------ tab 3
    def _dung_tab_sua(self):
        f = self.tab_sua
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)

        ttk.Label(f, text="Ảnh gửi kèm (giữ mặt / giữ bối cảnh). Trong prompt dùng "
                          "<IMAGE_0>, <IMAGE_1>… theo đúng thứ tự ảnh bên dưới.",
                  style="Mo.TLabel").grid(row=0, column=0, sticky="w")

        d = ttk.Frame(f)
        d.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        ttk.Button(d, text="Thêm ảnh...", command=self._them_anh).pack(side="left")
        ttk.Button(d, text="Thêm cả folder", command=self._them_folder_anh).pack(side="left", padx=6)
        ttk.Button(d, text="Bỏ ảnh chọn", command=self._bo_anh).pack(side="left")
        self.lbl_anh = ttk.Label(d, text="0 ảnh", style="Mo.TLabel")
        self.lbl_anh.pack(side="left", padx=12)

        giua = ttk.Frame(f)
        giua.grid(row=2, column=0, sticky="nsew")
        giua.columnconfigure(0, weight=0)
        giua.columnconfigure(1, weight=1)
        giua.rowconfigure(0, weight=1)

        self.lst_anh = tk.Listbox(giua, bg=NEN2, fg=CHU, relief="flat", width=42,
                                  selectmode="extended", activestyle="none",
                                  highlightthickness=0)
        self.lst_anh.grid(row=0, column=0, sticky="ns")
        self.lst_anh.bind("<Delete>", lambda e: self._bo_anh())

        k2 = ttk.Frame(giua)
        k2.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        k2.rowconfigure(1, weight=1)
        k2.columnconfigure(0, weight=1)
        ttk.Label(k2, text="Prompt cho mỗi ảnh (mỗi dòng 1 prompt):",
                  style="Mo.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.txt_prompt_sua = tk.Text(k2, bg=NEN2, fg=CHU, insertbackground=CHU,
                                      relief="flat", font=("Consolas", 10), wrap="word",
                                      padx=10, pady=8)
        self.txt_prompt_sua.grid(row=1, column=0, sticky="nsew")
        self.txt_prompt_sua.insert("1.0",
            "Đổi bối cảnh sang phòng họp báo, giữ nguyên khuôn mặt và biểu cảm <IMAGE_0>\n"
            "Đổi sang vest xám, ánh sáng ban ngày, giữ nguyên khuôn mặt <IMAGE_0>\n")

        ghi = ttk.Label(f, style="Mo.TLabel", text="Sửa ảnh chạy chung tuỳ chọn model / "
                        "tỉ lệ / độ phân giải ở tab 1.")
        ghi.grid(row=3, column=0, sticky="w", pady=(8, 0))

    def _them_anh(self):
        ds = filedialog.askopenfilenames(
            initialdir=THU_MUC_GOC,
            filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.webp"), ("Tất cả", "*.*")])
        for p in ds:
            if self.lst_anh.size() >= api.max_anh(self._model_dang_chon()):
                messagebox.showwarning(APP_TEN, "Model này chỉ nhận tối đa %d ảnh gửi kèm."
                                       % api.max_anh(self._model_dang_chon()))
                break
            self.lst_anh.insert("end", p)
        self._cap_nhat_dem_anh()

    def _them_folder_anh(self):
        p = filedialog.askdirectory(initialdir=THU_MUC_GOC, title="Chọn folder ảnh")
        if not p:
            return
        for x in api.ds_anh_trong_folder(p):
            if self.lst_anh.size() >= api.max_anh(self._model_dang_chon()):
                break
            self.lst_anh.insert("end", x)
        self._cap_nhat_dem_anh()

    def _bo_anh(self):
        for i in reversed(self.lst_anh.curselection()):
            self.lst_anh.delete(i)
        self._cap_nhat_dem_anh()

    def _cap_nhat_dem_anh(self):
        self.lbl_anh.configure(text="%d ảnh" % self.lst_anh.size())

    def _ds_anh_gui(self):
        return [self.lst_anh.get(i) for i in range(self.lst_anh.size())]

    # ------------------------------------------------ tab 3
    def _dung_tab_kq(self):
        f = self.tab_kq
        f.rowconfigure(1, weight=3)
        f.rowconfigure(3, weight=2)
        f.columnconfigure(0, weight=1)

        ttk.Label(f, text="Ảnh đã tạo", style="TieuDe.TLabel").grid(row=0, column=0, sticky="w")
        hang_kq = ttk.Frame(f)
        hang_kq.grid(row=0, column=0, sticky="e")
        ttk.Button(hang_kq, text="Làm khung → tab 2",
                   command=self._dung_lam_khung).pack(side="right")
        khung = ttk.Frame(f)
        khung.grid(row=1, column=0, sticky="nsew", pady=(6, 10))
        khung.rowconfigure(0, weight=1)
        khung.columnconfigure(0, weight=1)

        cot = ("stt", "prompt", "model", "trang_thai", "file", "giay")
        self.tree = ttk.Treeview(khung, columns=cot, show="headings", selectmode="browse")
        for k, ten, w, neo in (("stt", "#", 46, "center"), ("prompt", "Prompt", 420, "w"),
                               ("model", "Model", 190, "w"), ("trang_thai", "Trạng thái", 110, "center"),
                               ("file", "File", 260, "w"), ("giay", "Giây", 60, "center")):
            self.tree.heading(k, text=ten)
            self.tree.column(k, width=w, anchor=neo, stretch=(k == "prompt"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(khung, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("ok", foreground=XANH)
        self.tree.tag_configure("loi", foreground=DO)
        self.tree.tag_configure("dang", foreground=VANG)
        self.tree.bind("<Double-1>", self._mo_anh_chon)

        ttk.Label(f, text="Nhật ký", style="TieuDe.TLabel").grid(row=2, column=0, sticky="w")
        klog = ttk.Frame(f)
        klog.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        klog.rowconfigure(0, weight=1)
        klog.columnconfigure(0, weight=1)
        self.txt_log = tk.Text(klog, bg="#0d0f14", fg="#b9c2d4", relief="flat",
                               font=("Consolas", 9), wrap="word", padx=10, pady=8,
                               state="disabled")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        s2 = ttk.Scrollbar(klog, orient="vertical", command=self.txt_log.yview)
        s2.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=s2.set)

    def _mo_anh_chon(self, _e=None):
        it = self.tree.selection()
        if not it:
            return
        f = self.tree.item(it[0], "values")[4]
        if f and os.path.isfile(f):
            try:
                os.startfile(f)
            except Exception:
                pass

    # ------------------------------------------------ đáy
    def _dung_day(self):
        d = ttk.Frame(self, padding=(14, 6, 14, 10))
        d.pack(fill="x", side="bottom")
        d.columnconfigure(1, weight=1)

        self.btn_chay = ttk.Button(d, text="CHẠY", style="Chay.TButton",
                                   command=self._bam_chay, width=14)
        self.btn_chay.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.btn_dung = ttk.Button(d, text="Dừng", style="Dung.TButton",
                                   command=self._bam_dung, state="disabled", width=10)
        self.btn_dung.grid(row=0, column=2, rowspan=2, padx=(8, 0), sticky="ns")
        self.btn_tiep = ttk.Button(d, text="Tiếp tục", command=self._bam_tiep_tuc,
                                   state="disabled", width=13)
        self.btn_tiep.grid(row=0, column=3, rowspan=2, padx=(8, 0), sticky="ns")
        self.btn_nap = ttk.Button(d, text="Nạp lại", command=self._bam_nap_lai,
                                  state="disabled", width=10)
        self.btn_nap.grid(row=0, column=4, rowspan=2, padx=(6, 0), sticky="ns")
        self._ten_nut_noi = "➕ Nối vào hàng chờ (đang chạy)"
        self.btn_noi = ttk.Button(d, text=self._ten_nut_noi,
                                  command=self._noi_hang_cho, width=24)
        self.btn_noi.grid(row=0, column=5, rowspan=2, padx=(6, 0), sticky="ns")

        self.pb = ttk.Progressbar(d, style="Horizontal.TProgressbar", maximum=100, value=0)
        self.pb.grid(row=0, column=1, sticky="ew", padx=12)
        self.lbl_tien_do = ttk.Label(d, text="Sẵn sàng", style="Mo.TLabel")
        self.lbl_tien_do.grid(row=1, column=1, sticky="w", padx=12, pady=(4, 0))
        self._cap_nhat_nut_tiep()

    def _cap_nhat_plan_label(self):
        self._cap_nhat_key_label()

    def _doi_key(self):
        w = tk.Toplevel(self)
        w.title("Danh sách API key")
        w.configure(bg=NEN)
        w.geometry("720x460")
        w.transient(self)
        w.grab_set()

        ttk.Label(w, text="Mỗi dòng một API key — tool xoay vòng key cho từng luồng. "
                          "Dòng bắt đầu bằng # sẽ bỏ qua.",
                  style="TLabel", wraplength=680, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 6))

        khung = ttk.Frame(w)
        khung.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16)
        w.rowconfigure(1, weight=1)
        w.columnconfigure(0, weight=1)
        khung.rowconfigure(0, weight=1)
        khung.columnconfigure(0, weight=1)
        txt = tk.Text(khung, bg=NEN2, fg=CHU, insertbackground=CHU, relief="flat",
                      font=("Consolas", 10), wrap="none", padx=8, pady=6)
        txt.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(khung, orient="vertical", command=txt.yview)
        sb.grid(row=0, column=1, sticky="ns")
        txt.configure(yscrollcommand=sb.set)
        txt.insert("1.0", "\n".join(self._ds_key()))

        lbl = ttk.Label(w, text="", style="Mo.TLabel", wraplength=680, justify="left")
        lbl.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 0))

        def doc_keys():
            ra = []
            for dong in txt.get("1.0", "end").splitlines():
                t = dong.strip()
                if not t or t.startswith("#"):
                    continue
                if t not in ra:
                    ra.append(t)
            return ra

        def kiem():
            ds = doc_keys()
            if not ds:
                lbl.configure(text="Chưa nhập key nào.", foreground=DO)
                return
            lbl.configure(text="Đang kiểm tra %d key…" % len(ds), foreground=CHU_MO)
            w.update_idletasks()

            def chay():
                kq = []
                for k in ds:
                    try:
                        d = api.so_du(k)
                        kq.append((k, True, d))
                    except api.LoiAPI as ex:
                        kq.append((k, False, ex.thong_bao))
                self.ui_q.put(("kiem_key", kq))
            threading.Thread(target=chay, daemon=True).start()

        def luu():
            ds = doc_keys()
            self.cfg["api_keys"] = ds
            self.cfg["api_key"] = ds[0] if ds else ""
            luu_cfg(self.cfg)
            self._cap_nhat_key_label()
            self._cap_nhat_uoc_tinh()
            w.destroy()

        h = ttk.Frame(w)
        h.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=14)
        ttk.Button(h, text="Kiểm tra tất cả", command=kiem).pack(side="left")
        ttk.Button(h, text="Lưu", command=luu).pack(side="right")
        ttk.Button(h, text="Huỷ", command=w.destroy).pack(side="right", padx=(0, 8))
        self._hop_key = (w, lbl, txt)

    def _hien_kq_kiem_key(self, kq):
        hop = getattr(self, "_hop_key", None)
        if not hop:
            return
        _w, lbl, _txt = hop
        ok = [k for k in kq if k[1]]
        loi = [k for k in kq if not k[1]]
        dong = []
        for k, duoc, gt in kq:
            ngan = k[:10] + "…" + k[-4:] if len(k) > 18 else k
            if duoc:
                dong.append("%s OK (%s)" % (ngan, gt.get("plan_name") or gt.get("plan") or "?"))
            else:
                dong.append("%s LỖI (%s)" % (ngan, gt))
        lbl.configure(text="\n".join(dong[:8]), foreground=XANH if not loi else VANG)
        # dùng thông tin key đầu tiên còn sống để hiện gói
        if ok:
            k, _d, gt = ok[0]
            self.cfg["plan"] = gt.get("plan") or ""
            self.cfg["plan_name"] = gt.get("plan_name") or ""
            self.cfg["credits"] = gt.get("credits", 0)
            luu_cfg(self.cfg)
            self._cap_nhat_key_label()
            self._cap_nhat_uoc_tinh()
        self._log("Kiểm tra key: %d OK | %d lỗi" % (len(ok), len(loi)))

    # ------------------------------------------------ báo cáo Telegram
    # ------------------------------------------------ Telegram
    def _hop_tele(self):
        w = tk.Toplevel(self)
        w.title("Báo cáo tiến độ lên Telegram")
        w.configure(bg=NEN)
        w.geometry("700x530")
        w.minsize(640, 500)
        w.transient(self)
        w.grab_set()

        ttk.Label(w, text="Dán bot token và ID nhóm nhận báo cáo, đặt số phút, bấm Lưu.",
                  style="TLabel", wraplength=660, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 6))

        var_bat = tk.BooleanVar(value=bool(self.cfg.get("tele_bat")))
        var_nghe = tk.BooleanVar(value=bool(self.cfg.get("tele_nghe", True)))
        ttk.Checkbutton(w, text="Bật báo cáo Telegram", variable=var_bat).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

        ttk.Label(w, text="Bot token").grid(row=2, column=0, sticky="w", padx=16, pady=5)
        e_tok = ttk.Entry(w, width=52, show="•")
        e_tok.grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=5)

        ttk.Label(w, text="ID nhóm").grid(row=3, column=0, sticky="w", padx=16, pady=5)
        e_id = ttk.Entry(w, width=52)
        e_id.grid(row=3, column=1, sticky="ew", padx=(0, 16), pady=5)

        ttk.Label(w, text="Nhiều nhóm thì cách nhau dấu phẩy. Nhận: -1001234567890 · "
                          "@tenkenh · https://t.me/tenkenh\n"
                          "Chưa biết ID? Add bot vào nhóm rồi gõ /baocao trong nhóm — "
                          "tool ghi ID nhóm ra ô log.",
                  style="Mo.TLabel", wraplength=660, justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

        # Nhóm có nhiều bot: mỗi máy đặt 1 tên riêng -> tin báo cáo có nhãn,
        # nhìn là biết của máy/bot nào.
        ttk.Label(w, text="Tên gọi nhớ").grid(row=5, column=0, sticky="w",
                                              padx=16, pady=5)
        e_ten = ttk.Entry(w, width=52)
        e_ten.grid(row=5, column=1, sticky="ew", padx=(0, 16), pady=5)
        ttk.Label(w, text="Để trống = dùng @username của bot. Nhóm nhiều bot thì đặt "
                          "tên riêng (vd: Máy A – ảnh) để phân biệt tin báo cáo.",
                  style="Mo.TLabel", wraplength=660, justify="left").grid(
            row=6, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 6))

        # Lệnh đầy đủ để copy (bot bật privacy mode thì phải có @username)
        lbl_lenh = ttk.Label(w, text="", style="Mo.TLabel", wraplength=660,
                             justify="left")
        lbl_lenh.grid(row=7, column=0, columnspan=2, sticky="w", padx=16,
                      pady=(0, 4))

        f = ttk.Frame(w)
        f.grid(row=8, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 0))
        ttk.Label(f, text="Mốc báo cáo (phút: 30 = :00/:30)").pack(side="left")
        sp_phut = tk.Spinbox(f, from_=1, to=240, width=6, bg=NEN2, fg=CHU,
                             buttonbackground=NEN2, relief="flat", justify="center")
        sp_phut.pack(side="left", padx=(8, 20))
        sp_phut.delete(0, "end")
        try:
            phut_cu = int(self.cfg.get("tele_moi_phut") or 30)
        except Exception:
            phut_cu = 30
        sp_phut.insert(0, str(phut_cu))
        ttk.Checkbutton(f, text="Nghe lệnh /baocao trong nhóm",
                        variable=var_nghe).pack(side="left")

        lbl = ttk.Label(w, text="", style="Mo.TLabel", wraplength=660, justify="left")
        lbl.grid(row=9, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 0))

        h = ttk.Frame(w)
        h.grid(row=10, column=0, columnspan=2, sticky="ew", padx=16, pady=14)
        ttk.Button(h, text="Gửi thử", command=lambda: thu()).pack(side="left")
        ttk.Button(h, text="Kiểm tra quyền",
                   command=lambda: kiem_quyen()).pack(side="left", padx=(8, 0))
        ttk.Button(h, text="Lưu", command=lambda: luu()).pack(side="right")
        ttk.Button(h, text="Huỷ", command=w.destroy).pack(side="right", padx=(0, 8))
        w.columnconfigure(1, weight=1)

        tok_hien = (self.cfg.get("tele_token") or "").strip()
        if tok_hien:
            e_tok.insert(0, tok_hien)
        id_hien = ", ".join(self._ds_chat_nhan())
        if id_hien:
            e_id.insert(0, id_hien)
        e_ten.insert(0, str(self.cfg.get("tele_ten") or ""))

        def cap_nhat_lenh(*_a):
            u = self._ten_bot_that()
            if u:
                lbl_lenh.configure(
                    text="Lệnh dùng trong nhóm:\n/baocao@%s   ·   /tonghop@%s\n                         (privacy mode BẬT thì lệnh TRẦN không tới được bot)"
                         % (u, u), foreground=XANH)
            else:
                lbl_lenh.configure(
                    text="Dán bot token rồi Lưu để hiện lệnh đầy đủ dạng "
                         "/baocao@<tên_bot>.", foreground=CHU_MO)

        e_tok.bind("<FocusOut>", cap_nhat_lenh)
        w.after(400, cap_nhat_lenh)

        def lay_tok():
            # chỉ dùng token anh dán vào — KHÔNG rơi về token trong .env Hermes
            # (getUpdates 2 nơi cùng token sẽ tranh nhau, lỗi 409)
            return e_tok.get().strip()

        def doc_phut():
            try:
                return max(1, min(240, int(sp_phut.get() or 30)))
            except Exception:
                return 30

        def doc_ids():
            """Đọc ô ID -> (danh sách id hợp lệ, danh sách chuỗi sai)."""
            raw = (e_id.get() or "").replace(";", ",").replace("\n", ",")
            ds, sai = [], []
            for phan in raw.split(","):
                phan = phan.strip()
                if not phan:
                    continue
                cid, _ten = tele.tach_chat_id(phan)
                if cid:
                    if cid not in ds:
                        ds.append(cid)
                else:
                    sai.append(phan)
            return ds, sai

        def luu():
            tok = lay_tok()
            phut = doc_phut()
            ds, sai = doc_ids()
            if sai:
                lbl.configure(text="ID không đọc được: %s" % ", ".join(sai), foreground=DO)
                return
            if var_bat.get() and not tok:
                lbl.configure(text="Chưa có bot token.", foreground=DO)
                return
            if var_bat.get() and not ds:
                lbl.configure(text="Chưa có ID nhóm nhận báo cáo — tool sẽ chỉ nghe lệnh, "
                                    "chưa gửi báo cáo tự động.", foreground=VANG)
            self.cfg["tele_bat"] = bool(var_bat.get())
            self.cfg["tele_token"] = tok
            self.cfg["tele_ten"] = (e_ten.get() or "").strip()
            self.cfg["tele_nghe"] = bool(var_nghe.get())
            self.cfg["tele_moi_phut"] = phut
            self.cfg["tele_chat_ids"] = ds
            self.cfg["tele_chat_id"] = ds[0] if ds else ""
            ten = dict(self.cfg.get("tele_nhom_ten") or {})
            for c in list(ten):
                if c not in ds:
                    ten.pop(c, None)
            self.cfg["tele_nhom_ten"] = ten
            luu_cfg(self.cfg)
            self._dung_baocao()
            self._hen_moc()          # căn lại mốc :00/:30 theo nhịp vừa lưu
            self._cap_nhat_tele_label()
            if self.cfg["tele_bat"] and self.cfg.get("tele_nghe"):
                self._bat_theo_doi()
            else:
                self._dung_theo_doi()
            w.destroy()
            self._log("Telegram: đã lưu — bật=%s, %d nhóm, mỗi %d phút, nghe /baocao=%s."
                      % ("có" if self.cfg["tele_bat"] else "không", len(ds), phut,
                         "có" if self.cfg.get("tele_nghe") else "không"))

        def thu():
            tok = lay_tok()
            ds, sai = doc_ids()
            if not tok:
                lbl.configure(text="Thiếu bot token.", foreground=DO)
                return
            if sai:
                lbl.configure(text="ID không đọc được: %s" % ", ".join(sai), foreground=DO)
                return
            if not ds:
                lbl.configure(text="Nhập ít nhất 1 ID nhóm để gửi thử.", foreground=DO)
                return
            lbl.configure(text="Đang gửi thử tới %d nhóm…" % len(ds), foreground=CHU_MO)
            w.update_idletasks()

            def chay():
                loi = []
                for cid in ds:
                    ok, l = tele.gui(tok, cid, "<b>LightVisual Image Tool v%s</b>\n"
                                               "Kết nối Telegram OK." % APP_VERSION)
                    if not ok:
                        loi.append("%s: %s" % (cid, l))
                self.ui_q.put(("tele_thu", (not loi, "; ".join(loi), "%d nhóm" % len(ds))))
            threading.Thread(target=chay, daemon=True).start()

        def kiem_quyen():
            """Kiem tra bot co nhan duoc lenh TRAN trong tung nhom khong."""
            tok = lay_tok()
            ds, sai = doc_ids()
            if not tok:
                lbl.configure(text="Thiếu bot token.", foreground=DO)
                return
            if not ds:
                lbl.configure(text="Nhập ít nhất 1 ID nhóm để kiểm tra.", foreground=DO)
                return
            lbl.configure(text="Đang kiểm tra quyền bot trong nhóm…", foreground=CHU_MO)

            def chay():
                try:
                    kq, _pv = tele.kiem_tra_quyen(tok, ds)
                except Exception as e:
                    self.ui_q.put(("tele_quyen", (False, "Lỗi kiểm tra: %s" % e)))
                    return
                dong = []
                for d in kq:
                    u = d.get("bot_user") or ""
                    at = ("@" + u) if u else "<tên_bot>"
                    if d.get("loi"):
                        dong.append("• %s: không kiểm tra được (%s)"
                                    % (d.get("title"), d["loi"]))
                    elif d.get("doc_het"):
                        dong.append("• %s: OK — gõ /baocao trần được." % d.get("title"))
                    else:
                        dong.append("• %s: CHẶN lệnh trần — dùng /baocao%s hoặc "
                                    "/tonghop%s, hoặc thêm bot làm admin nhóm."
                                    % (d.get("title"), at, at))
                self.ui_q.put(("tele_quyen", (True, "\n".join(dong) or "Chưa có nhóm nào.")))
            threading.Thread(target=chay, daemon=True).start()

        self._hop_tele_ctl = {"lbl": lbl, "tok": e_tok, "id": e_id}

    def _hien_kq_tele_thu(self, ok, loi, chat):
        hop = getattr(self, "_hop_tele_ctl", None)
        if hop:
            lbl = hop["lbl"]
            try:
                if ok:
                    lbl.configure(text="Đã gửi thử tới %s — mở Telegram xem." % chat,
                                  foreground=XANH)
                else:
                    lbl.configure(text="Gửi lỗi: %s" % loi, foreground=DO)
            except tk.TclError:
                pass
        self._log("Telegram gửi thử: %s" % ("OK" if ok else "LỖI — %s" % loi))

    def _cap_nhat_tele_label(self):
        try:
            if self.cfg.get("tele_bat"):
                n = len(self.cfg.get("tele_chat_ids") or [])
                self.btn_tele.configure(text="📣 Telegram: BẬT" + (" (%d)" % n if n else ""))
            else:
                self.btn_tele.configure(text="📣 Telegram")
        except Exception:
            pass

    # -- đối tượng báo cáo
    def _ds_chat_nhan(self):
        ds = []
        for x in (self.cfg.get("tele_chat_ids") or []):
            x = str(x or "").strip()
            if x and x not in ds:
                ds.append(x)
        c = str(self.cfg.get("tele_chat_id") or "").strip()
        if c and c not in ds:
            ds.append(c)
        return ds

    def _dong_bo_migrate(self):
        """Nhóm nâng cấp lên supergroup -> thay ID cũ bằng ID mới trong config.

        Telegram đổi chat_id khi nhóm thường thành supergroup; nếu không cập
        nhật thì mọi tin gửi đi đều 400 "group chat was upgraded".
        """
        try:
            mg = tele.lay_migrate()
        except Exception:
            return
        if not mg:
            return
        doi = False
        ids = []
        for x in (self.cfg.get("tele_chat_ids") or []):
            x = str(x or "").strip()
            if not x:
                continue
            moi = mg.get(x, x)
            if moi != x:
                doi = True
            if moi not in ids:
                ids.append(moi)
        c = str(self.cfg.get("tele_chat_id") or "").strip()
        if c and mg.get(c):
            c = mg[c]
            doi = True
            if c not in ids:
                ids.append(c)
        if not doi:
            return
        self.cfg["tele_chat_ids"] = ids
        if c:
            self.cfg["tele_chat_id"] = c
        nhom_ten = self.cfg.get("tele_nhom_ten") or {}
        if isinstance(nhom_ten, dict):
            moi_ten = {}
            for k, v in nhom_ten.items():
                moi_ten[mg.get(str(k), str(k))] = v
            self.cfg["tele_nhom_ten"] = moi_ten
        luu_cfg(self.cfg)
        try:
            self._log("Telegram: nhóm đã lên supergroup — tự đổi ID sang %s."
                      % ", ".join(ids))
        except Exception:
            pass
        try:
            self._cap_nhat_tele_label()
        except Exception:
            pass

    def _dung_baocao(self, nhanh=False):
        """nhanh=True: báo dừng, không chờ gửi nốt (dùng khi đóng tool)."""
        if self.bc:
            try:
                if nhanh:
                    self.bc.dung_nhanh()
                else:
                    self.bc.dung()
            except Exception:
                pass
            self.bc = None

    def _bat_baocao(self):
        """Tạo đối tượng báo cáo cho lượt chạy mới (nếu đang bật)."""
        self._dung_baocao()
        if not self.cfg.get("tele_bat"):
            return
        tok = (self.cfg.get("tele_token") or "").strip()
        ds = self._ds_chat_nhan()
        if not tok or not ds:
            self._log("Telegram: bật nhưng thiếu token/nhóm — không gửi.")
            return
        try:
            phut = int(self.cfg.get("tele_moi_phut") or 30)
        except Exception:
            phut = 30
        # Báo cáo định kỳ do _hen_moc lo (rơi đúng mốc :00 / :30), nên ở đây
        # đặt nhịp rất lớn để BaoCao KHÔNG tự gửi thêm tin tiến độ nào.
        _ = phut        # giữ đọc cấu hình để phát hiện giá trị rác sớm
        self.bc = tele.BaoCao(tok, "", moi_giay=10 ** 8, chat_ids=ds,
                              log=lambda s: self.ui_q.put(("log", s)),
                              nhan=self._nhan_bot())
        self.bc.bat_dau_worker()

    # -- nhãn bot (1 nhóm nhiều bot vẫn phân biệt được tin của bot nào)
    def _nhan_bot(self):
        ten = str(self.cfg.get("tele_ten") or "").strip()
        if ten:
            return ten
        u = str(getattr(self.td, "bot_username", "") or "").strip()
        return ("@" + u) if u else ""

    def _ten_bot_that(self):
        """Username thật của bot (để hiện /baocao@<bot> cho anh copy)."""
        u = str(getattr(self.td, "bot_username", "") or "").strip()
        if u:
            return u
        u = str(self.cfg.get("tele_bot_user") or "").strip()
        if u:
            return u
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok:
            return ""
        try:
            ok, me = tele.get_me(tok)
            if ok:
                return str((me or {}).get("username") or "").strip()
        except Exception:
            pass
        return ""

    def _giam_sat_nghe(self):
        """Tự bật lại luồng nghe nếu nó đã chết (mạng rớt, lỗi lạ).

        Trước đây luồng nghe có thể chết mà không ai bật lại -> gõ /baocao
        không có ai trả lời cho tới khi đóng/mở tool.
        """
        try:
            if getattr(self, "_thoat", False):
                return
            if (self.cfg.get("tele_bat") and self.cfg.get("tele_nghe", True)
                    and (self.cfg.get("tele_token") or "").strip()):
                chet = (self.td is None) or (not self.td.dang_chay())
                if chet and not getattr(self, "_dang_doi_bat", False):
                    self._log("Telegram: luồng nghe lệnh đã dừng — tự bật lại.")
                    self._bat_theo_doi()
        except Exception:
            pass
        # báo cáo định kỳ do _hen_moc lo (rơi đúng mốc :00 / :30) — không lặp ở đây
        try:
            self.after(30000, self._giam_sat_nghe)
        except Exception:
            pass

    def _bao_quyen_nhom(self, chat_id, ten, at, la_admin):
        """Gửi 1 tin cảnh báo vào nhóm khi bot KHÔNG nhận được lệnh trần.

        Tin do bot GỬI ĐI luôn tới nhóm (privacy mode chỉ chặn chiều NHẬN),
        nên đây là cách duy nhất để anh đọc được cảnh báo ngay trên điện thoại.
        Mỗi nhóm chỉ gửi 1 lần trong 1 phiên để không spam.
        """
        da = getattr(self, "_da_bao_quyen", None)
        if da is None:
            da = self._da_bao_quyen = set()
        if str(chat_id) in da:
            return
        da.add(str(chat_id))
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok:
            return
        ly_do = ("bot đang là <b>admin</b> nhưng vẫn bị chặn" if la_admin
                 else "bot <b>CHƯA phải admin</b> + privacy mode đang <b>BẬT</b>")
        text = ("<b>⚠ Bot này chưa nhận được lệnh trần</b>\n"
                "Nhóm: <b>%s</b>\n"
                "Bot: %s — %s\n\n"
                "<b>Cách sửa (làm 1 lần, 30 giây):</b>\n"
                "1. Mở @BotFather → gõ <code>/setprivacy</code> → chọn bot này → "
                "<b>Disable</b>\n"
                "2. Xoá bot khỏi nhóm rồi thêm lại (bắt buộc — đổi privacy chỉ có "
                "hiệu lực sau khi thêm lại)\n"
                "3. Hoặc: nhóm → Manage → Administrators → Add Admin → chọn bot này\n\n"
                "<i>Sau đó gõ /tonghop trần là MỌI bot trong nhóm cùng báo cáo.</i>"
                % (tele.esc(ten or chat_id), tele.esc(at), ly_do))

        def chay():
            ok, loi = tele.gui(tok, str(chat_id), text)
            self.ui_q.put(("log", "Telegram: %s cảnh báo quyền tới \"%s\"."
                           % ("đã gửi" if ok else "KHÔNG gửi được", ten or chat_id)))
            if not ok:
                self.ui_q.put(("log", "Telegram: lỗi gửi cảnh báo — %s" % loi))
        threading.Thread(target=chay, daemon=True).start()

    def _kiem_tra_quyen_nghe(self):
        """Kiem tra bot co nhan duoc lenh TRAN trong nhom khong — chay o luong nen.

        Privacy mode BAT + bot KHONG phai admin => Telegram KHONG giao /baocao
        hay /tonghop tran cho bot. Nguoi dung go lenh tran se thay bot im lang va
        tuong tool hong. Phai noi ro cach xu ly ngay trong log.
        """
        tok = (self.cfg.get("tele_token") or "").strip()
        ds_chat = self._ds_chat_nhan()
        if not tok or not ds_chat:
            return

        def chay():
            try:
                ds, _pv = tele.kiem_tra_quyen(tok, ds_chat)
            except Exception as e:
                self.ui_q.put(("log", "Telegram: không kiểm tra được quyền bot — %s" % e))
                return
            for d in ds:
                u = d.get("bot_user") or ""
                at = ("@" + u) if u else "<tên_bot>"
                ten = d.get("title") or d.get("id")
                if d.get("loi"):
                    self.ui_q.put(("log", "Telegram: nhóm \"%s\" — không kiểm tra được "
                                          "quyền (%s)." % (ten, d["loi"])))
                elif d.get("doc_het"):
                    self.ui_q.put(("log", "Telegram: nhóm \"%s\" — bot %s nhận được MỌI tin "
                                          "(admin=%s). Gõ /baocao trần OK."
                                   % (ten, at, "có" if d.get("la_admin") else "không")))
                else:
                    self.ui_q.put(("log",
                        "⚠ Telegram: nhóm \"%s\" — bot %s CHƯA là admin và đang BẬT "
                        "privacy mode nên Telegram KHÔNG giao lệnh trần. Gõ /baocao hay "
                        "/tonghop trần SẼ KHÔNG AI TRẢ LỜI. Dùng /baocao%s hoặc "
                        "/tonghop%s — hoặc thêm bot làm admin nhóm (Manage → "
                        "Administrators → Add Admin) là gõ trần được."
                        % (ten, at, at, at)))
                    # báo thẳng vào nhóm để anh đọc được trên điện thoại
                    self._bao_quyen_nhom(d.get("id"), ten, at, bool(d.get("la_admin")))

        threading.Thread(target=chay, daemon=True).start()

    # -- nghe lệnh /baocao
    def _bat_theo_doi(self):
        # chỉ nghe lệnh bằng token anh tự nhập; KHÔNG dùng token .env Hermes
        # (2 nơi cùng getUpdates sẽ tranh nhau -> 409, và làm chết bot Hermes)
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok or not self.cfg.get("tele_nghe", True):
            self._dung_theo_doi()
            return
        # Dừng luồng cũ có thể phải chờ long-poll nhả kết nối (tới ~45s) -> phải
        # chạy ở luồng nền, KHÔNG được chặn luồng GUI (nút Lưu sẽ đứng hình).
        if getattr(self, "_dang_doi_bat", False):
            return
        self._dang_doi_bat = True
        offset = int(self.cfg.get("tele_offset") or 0)

        def chay():
            try:
                if not self._dung_theo_doi():
                    return
                td = tele.TheoDoi(tok, khi_lenh=self._co_lenh_baocao,
                                  khi_khac=self._co_lenh_khac,
                                  log=lambda s: self.ui_q.put(("log", s)))
                td.offset = offset
                if td.bat_dau():
                    self.td = td
                    # nhớ username để lần sau getMe lỗi vẫn phân biệt được
                    # /lenh@bot_khac (2-3 bot cùng nhóm không tranh nhau trả lời)
                    if td.bot_username and td.bot_username != self.cfg.get("tele_bot_user"):
                        self.cfg["tele_bot_user"] = td.bot_username
                        try:
                            luu_cfg(self.cfg)
                        except Exception:
                            pass
                    self.ui_q.put(("log", "Telegram: đang nghe lệnh /baocao trong nhóm."))
                    self._kiem_tra_quyen_nghe()
            finally:
                self._dang_doi_bat = False

        threading.Thread(target=chay, daemon=True).start()

    def _dung_theo_doi(self, nhanh=False):
        """Dừng nghe lệnh. Trả True nếu đã dừng hẳn (an toàn để bật lại).

        nhanh=True: chỉ báo dừng, KHÔNG chờ long-poll nhả kết nối — dùng khi đóng
        tool để cửa sổ không đứng hình tới 45s.
        """
        if not self.td:
            return True
        try:
            self.cfg["tele_offset"] = self.td.offset
            luu_cfg(self.cfg)
        except Exception:
            pass
        if nhanh:
            try:
                self.td.dung_nhanh()
            except Exception:
                pass
            self.td = None
            return True
        try:
            sach = self.td.dung()
        except Exception:
            sach = True
        if sach:
            self.td = None
        return sach

    def _co_lenh_baocao(self, chat_id, ten):
        """Chạy trong luồng polling -> trả lời NGAY, không chờ Tk xử lý hàng đợi.

        Trước đây chỉ đẩy vào ui_q: nếu cửa sổ đã đóng mà tiến trình còn sống
        (luồng gửi tin cũ không phải daemon) thì lệnh bị "nuốt" — bot im lặng
        dù vẫn nhận được lệnh.
        """
        try:
            self._gui_bao_cao(str(chat_id), ten or "")
        except Exception:
            traceback.print_exc()

    def _co_lenh_khac(self, chat_id, ten, lenh):
        """Lệnh khác (/trangthai, /giup) — chạy trong luồng polling -> đẩy vào UI."""
        self.ui_q.put(("tele_lenh_khac", (str(chat_id), ten or "", str(lenh))))

    # ------------------------------------------------ mốc đồng hồ + tốc độ
    def _moc_ghi(self, xong=None):
        """Ghi lại (thời điểm, số việc đã xong) mỗi lần có việc xong.

        Giữ tối đa ~2 giờ để tính tốc độ trượt "Đã thêm N video trong Mp"
        mà không phình bộ nhớ khi chạy 1000+ việc.
        """
        now = time.time()
        if xong is None:
            with self._dem_lock:
                d = dict(self._dem)
            xong = d["ok"] + d["loi"] + d.get("dung", 0)
        with self._moc_dem_lock:
            self._moc_dem.append((now, int(xong)))
            # cắt bớt mốc cũ hơn 2 giờ
            while len(self._moc_dem) > 2 and now - self._moc_dem[0][0] > 7200:
                self._moc_dem.pop(0)
            if len(self._moc_dem) > 4000:
                del self._moc_dem[:len(self._moc_dem) - 4000]

    def _toc_do_truot(self, cua_so=1800):
        """(số việc thêm được, số giây thực) trong `cua_so` giây gần nhất.

        Lấy dữ liệu HIỆN TẠI trừ dữ liệu `cua_so` giây trước — đúng cách anh
        muốn: không phải trung bình từ đầu lượt, nên thấy được máy đang chậm
        hay nhanh lên.
        """
        with self._dem_lock:
            d = dict(self._dem)
        xong_now = d["ok"] + d["loi"] + d.get("dung", 0)
        now = time.time()
        with self._moc_dem_lock:
            ds = list(self._moc_dem)
        if not ds:
            return 0, 0
        # mốc gần nhất cách đây >= cua_so giây; không có thì lấy mốc cũ nhất
        goc = None
        for t, x in ds:
            if now - t >= cua_so:
                goc = (t, x)
            else:
                break
        if goc is None:
            goc = ds[0]
        giay = now - goc[0]
        if giay < 30:            # chưa đủ dữ liệu để nói tốc độ
            return 0, 0
        return max(0, xong_now - goc[1]), giay

    def _dong_toc_do(self, don_vi="video"):
        """Dòng ' - Đã thêm 30 video trong 30p' (rỗng nếu chưa đủ dữ liệu).

        Cửa sổ = đúng nhịp báo cáo (tele_moi_phut, mặc định 30 phút): lấy số
        việc hiện tại trừ số việc ở mốc trước đó để ra tốc độ THẬT của 30p
        vừa rồi, không phải trung bình từ đầu lượt.
        """
        try:
            cua_so = max(60, int(self.cfg.get("tele_moi_phut") or 30) * 60)
        except Exception:
            cua_so = 1800
        them, giay = self._toc_do_truot(cua_so)
        if them <= 0 or giay < 30:
            return ""
        return " - Đã thêm %d %s trong %s" % (them, don_vi,
                                             tele.dinh_dang_phut(giay))

    def _don_vi(self):
        loai = (self._lan_chay or {}).get("loai") or "anh"
        return "video" if loai == "video" else "ảnh"

    def _hen_moc(self):
        """Hẹn lần báo cáo kế tiếp rơi ĐÚNG mốc đồng hồ (:00 và :30)."""
        try:
            if self._aid_moc:
                self.after_cancel(self._aid_moc)
        except Exception:
            pass
        try:
            if self._aid_hen:
                self.after_cancel(self._aid_hen)
        except Exception:
            pass
        self._aid_moc = None
        self._aid_hen = None
        if getattr(self, "_thoat", False):
            return
        try:
            phut = int(self.cfg.get("tele_moi_phut") or 30)
        except Exception:
            phut = 30
        con = tele.giay_toi_moc(phut)
        try:
            self._aid_moc = self.after(int(max(1, con) * 1000), self._chay_moc)
        except Exception:
            self._aid_moc = None

    def _chay_moc(self):
        """Đã tới mốc :00/:30 — gửi báo cáo rồi hẹn mốc kế tiếp.

        Giữ như bản cũ: báo cả khi đang rảnh (tin "Đang rảnh" + lượt gần nhất)
        để còn biết tool đang sống.
        """
        self._aid_moc = None
        try:
            if (not getattr(self, "_thoat", False) and self.cfg.get("tele_bat")
                    and self._ds_chat_nhan()):
                for cid in self._ds_chat_nhan():
                    self._gui_bao_cao(cid, "theo mốc", "📊 Báo cáo theo mốc")
        except Exception:
            traceback.print_exc()
        self._hen_moc()

    def _soan_bao_cao(self, tieu_de=""):
        """Soạn nội dung báo cáo hiện tại. Chỉ đọc dữ liệu thường (không đụng Tk)
        nên gọi được từ luồng polling — cửa sổ đã đóng bot vẫn trả lời được."""
        td = tieu_de or "<b>📊 Báo cáo theo yêu cầu</b>"
        with self._dem_lock:
            d = dict(self._dem)
        if self.dang_chay:
            giay = time.time() - self._t0 if self._t0 else 0
            xong = d["ok"] + d["loi"] + d.get("dung", 0)
            con = max(0, d["tong"] - xong)
            tb = (giay / xong) if xong else 0
            dong = [td,
                    "%s  %d/%d%s" % (tele.thanh_tien_do(d), xong, d["tong"],
                                     self._dong_toc_do(self._don_vi())),
                    "✅ OK %d   ❌ Lỗi %d   ⏸️ Dừng %d"
                    % (d["ok"], d["loi"], d.get("dung", 0)),
                    "⏱️ Đã chạy %s · còn khoảng %s"
                    % (tele.dinh_dang_giay(giay),
                       tele.dinh_dang_giay(tb * con) if con else "0s")]
            if xong:
                dong.append("⚡️ %.1fs/việc" % tb)
            return "\n".join(dong)
        cu = getattr(self, "_lan_cuoi", None) or {}
        dong = [td, "🟢 Đang rảnh — không có việc nào chạy."]
        if cu:
            dong.append("")
            dong.append("<b>Lượt gần nhất</b>")
            dong.append("%s  %d/%d" % (tele.thanh_tien_do(cu),
                                      cu.get("ok", 0) + cu.get("loi", 0) + cu.get("dung", 0),
                                      cu.get("tong", 0)))
            dong.append("✅ OK %d   ❌ Lỗi %d   ⏸️ Dừng %d"
                        % (cu.get("ok", 0), cu.get("loi", 0), cu.get("dung", 0)))
            if cu.get("giay"):
                dong.append("⏱ Tổng %s" % tele.dinh_dang_giay(cu["giay"]))
            if cu.get("thu_muc"):
                dong.append("📁 <code>%s</code>" % tele.esc(cu["thu_muc"]))
        dong.append("")
        dong.append("<i>Bấm CHẠY trong tool để bắt đầu, rồi gõ /baocao bất cứ lúc nào.</i>")
        return "\n".join(dong)

    def _gui_bao_cao(self, chat_id, ten="", tieu_de=""):
        """Gửi báo cáo tới 1 nhóm. Gọi được từ BẤT KỲ luồng nào."""
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok:
            self.ui_q.put(("log", "Telegram: chưa có bot token — không trả lời."))
            return False
        try:
            text = self._soan_bao_cao(("<b>%s</b>" % tieu_de) if tieu_de else "")
        except Exception:
            text = "<b>📊 Báo cáo</b>\n(không đọc được số liệu)"
        text = tele.nhan_tin(text, self._nhan_bot())
        self.ui_q.put(("log", "Telegram: %s — gửi báo cáo tới %s."
                       % (tieu_de or "theo yêu cầu", ten or chat_id)))

        def chay():
            ok, loi = tele.gui(tok, chat_id, text)
            self.ui_q.put(("tele_thu", (ok, loi, ten or chat_id)))
        threading.Thread(target=chay, daemon=True).start()
        return True

    def _tra_loi_baocao(self, chat_id, ten):
        """Soạn và gửi báo cáo ngay cho 1 nhóm (chạy ở luồng GUI)."""
        td = "<b>📊 Báo cáo theo yêu cầu</b>"
        if self.dang_chay:
            text = self._tin_tien_do(td)
        else:
            cu = getattr(self, "_lan_cuoi", None) or {}
            dong = [td, "Hiện không có việc nào đang chạy."]
            if cu:
                dong.append("")
                dong.append("<b>Lượt gần nhất</b>")
                dong.append("%s  %d/%d" % (tele.thanh_tien_do(cu),
                                          cu.get("ok", 0) + cu.get("loi", 0) + cu.get("dung", 0),
                                          cu.get("tong", 0)))
                dong.append("✅ OK %d   ❌ Lỗi %d   ⏸️ Dừng %d"
                            % (cu.get("ok", 0), cu.get("loi", 0), cu.get("dung", 0)))
                if cu.get("giay"):
                    dong.append("⏱ Tổng %s" % tele.dinh_dang_giay(cu["giay"]))
                if cu.get("thu_muc"):
                    dong.append("📁 <code>%s</code>" % tele.esc(cu["thu_muc"]))
            dong.append("")
            dong.append("<i>Bấm CHẠY trong tool để bắt đầu, rồi gõ /baocao bất cứ lúc nào.</i>")
            text = "\n".join(dong)
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok:
            self._log("Telegram: chưa có bot token — không trả lời /baocao.")
            return
        text = tele.nhan_tin(text, self._nhan_bot())
        self._log("Telegram: nhận lệnh /baocao từ %s — gửi báo cáo." % (ten or chat_id))

        def chay():
            ok, loi = tele.gui(tok, chat_id, text)
            self.ui_q.put(("tele_thu", (ok, loi, ten or chat_id)))
        threading.Thread(target=chay, daemon=True).start()

    def _tra_loi_lenh_khac(self, chat_id, ten, lenh):
        """Xử lý /trangthai, /giup (và lệnh lạ) — chạy ở luồng GUI."""
        tok = (self.cfg.get("tele_token") or "").strip()
        if not tok:
            return
        if lenh in ("trangthai", "status"):
            if self.dang_chay:
                dong = ["<b>🟢 Đang chạy</b>", self._tin_tien_do().split("\n", 1)[-1]]
            else:
                dong = ["<b>⚪ Đang rảnh</b>", "Không có việc nào đang chạy."]
                cu = getattr(self, "_lan_cuoi", None) or {}
                if cu:
                    dong.append("")
                    dong.append("Lượt gần nhất: %d/%d (OK %d · Lỗi %d)"
                                % (cu.get("ok", 0) + cu.get("loi", 0) + cu.get("dung", 0),
                                   cu.get("tong", 0), cu.get("ok", 0), cu.get("loi", 0)))
            dong.append("")
            dong.append("Nhóm nhận báo cáo: <b>%d</b> · báo theo mốc <b>%s</b> phút (:00/:30)"
                        % (len(self._ds_chat_nhan()), self.cfg.get("tele_moi_phut", 30)))
            text = "\n".join(dong)
        else:
            dong = ["<b>🤖 LightVisual v%s</b>" % APP_VERSION, "",
                    "<b>Các lệnh</b>",
                    "/baocao — báo cáo tiến độ ngay",
                    "/trangthai — đang chạy hay đang rảnh",
                    "/giup — hướng dẫn này"]
            if lenh not in ("giup", "help", "start"):
                dong.insert(1, "Không rõ lệnh <code>/%s</code>.\n" % tele.esc(lenh))
            text = "\n".join(dong)
        text = tele.nhan_tin(text, self._nhan_bot())
        self._log("Telegram: nhận lệnh /%s từ %s." % (lenh, ten or chat_id))

        def chay():
            ok, loi = tele.gui(tok, chat_id, text)
            if not ok:
                self.ui_q.put(("log", "Telegram: không trả lời được /%s — %s" % (lenh, loi)))
        threading.Thread(target=chay, daemon=True).start()

    def _tin_tien_do(self, tieu_de=None):
        """Soạn nội dung tin tiến độ hiện tại (dùng chung 1 nơi với _soan_bao_cao)."""
        td = tieu_de or "<b>LightVisual — đang chạy</b>"
        return self._soan_bao_cao(td)

    # ------------------------------------------------ log / ui queue
    def _log(self, s):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", "%s  %s\n" % (time.strftime("%H:%M:%S"), s))
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _xu_ly_ui_q(self):
        try:
            self._dong_bo_migrate()
        except Exception:
            pass
        try:
            while True:
                loai, gt = self.ui_q.get_nowait()
                if loai == "log":
                    self._log(gt)
                elif loai == "dong":
                    self._cap_nhat_dong(*gt)
                elif loai == "dung_dong":
                    self._danh_dau_dung(*gt)
                elif loai == "dem":
                    self._cap_nhat_dem(gt)
                elif loai == "xong":
                    self._ket_thuc(*gt)
                elif loai == "kiem_key":
                    self._hien_kq_kiem_key(gt)
                elif loai == "tele_thu":
                    self._hien_kq_tele_thu(*gt)
                elif loai == "tele_lenh":
                    self._tra_loi_baocao(*gt)
                elif loai == "tele_lenh_khac":
                    self._tra_loi_lenh_khac(*gt)
                elif loai == "tele_quyen":
                    hop = getattr(self, "_hop_tele_ctl", None)
                    if hop:
                        try:
                            hop["lbl"].configure(
                                text=gt[1], justify="left",
                                foreground=XANH if gt[0] else DO)
                        except tk.TclError:
                            pass
                    for dong in str(gt[1]).split("\n"):
                        if dong.strip():
                            self._log("Telegram: %s" % dong.strip())
                elif loai == "dem_tc":
                    self._cap_nhat_dem_tham_chieu()
                elif loai == "key_chet":
                    self._cap_nhat_key_label()
                    self._log("Đã loại 1 API key không dùng được.")
                elif loai == "upd_hoi":
                    self._update_hoi(gt)
                elif loai == "upd_xong":
                    self._update_xong(gt)
                elif loai == "upd_xong_restart":
                    self._update_xong_restart(gt)
                elif loai == "upd_loi":
                    self._update_loi(gt)
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()
        try:
            self._aid = self.after(80, self._xu_ly_ui_q)
        except (tk.TclError, RuntimeError):
            pass

    def _cap_nhat_dem(self, dem):
        self._dem = dem
        self.pb.configure(maximum=max(1, dem["tong"]),
                          value=dem["ok"] + dem["loi"] + dem.get("dung", 0))
        self.lbl_tien_do.configure(
            text="Tiến độ %d/%d  ·  OK %d  ·  Lỗi %d  ·  Dừng %d  ·  %.0fs" %
                 (dem["ok"] + dem["loi"] + dem.get("dung", 0), dem["tong"],
                  dem["ok"], dem["loi"], dem.get("dung", 0),
                  time.time() - self._t0))
        # KHÔNG đẩy tin tiến độ nữa: báo cáo định kỳ do _hen_moc lo, rơi đúng
        # mốc :00 / :30. Đẩy mỗi việc xong chỉ làm đầy hàng đợi rồi bị bỏ.

    def _dem_dung(self):
        with self._dem_lock:
            self._dem["dung"] += 1
        self._ket_thuc_viec()

    def _danh_dau_dung(self, loai, iid, v, ch):
        """Việc bị bỏ dở do bấm Dừng — chỉ cập nhật bảng, số đếm đã tăng ở luồng."""
        self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                      self._nhan(loai, ch), "đã dừng", "", ""), "dang")))
        self.ui_q.put(("log", "[%d] dừng — còn trong danh sách chờ" % v["stt"]))

    def _cap_nhat_dong(self, iid, gia_tri, tag):
        try:
            self.tree.item(iid, values=gia_tri, tags=(tag,))
            if tag == "ok":
                self.tree.see(iid)
        except tk.TclError:
            pass

    # ------------------------------------------------ chạy
    def _bam_chay(self):
        if self.dang_chay:
            return
        if not self._ds_key():
            messagebox.showwarning(APP_TEN, "Chưa có API key.\nBấm 'API key' ở góc phải để nhập.")
            return
        chi_so = self.nb.index(self.nb.select())
        if chi_so == 1:
            self._bam_chay_video()
            return
        self._luu_tuy_chon()
        model = self._model_dang_chon()
        che_do_sua = (chi_so == 2)

        if che_do_sua:
            ds_prompt = [t.strip() for t in self.txt_prompt_sua.get("1.0", "end").splitlines()
                         if t.strip() and not t.strip().startswith("#")]
            ds_anh = self._ds_anh_gui()
            if not ds_anh:
                messagebox.showwarning(APP_TEN, "Chưa thêm ảnh gửi kèm ở tab 3.")
                return
            if not ds_prompt:
                messagebox.showwarning(APP_TEN, "Chưa có prompt ở tab 2.")
                return
        else:
            ds_prompt = self._ds_prompt()
            ds_anh = []
            if not ds_prompt:
                messagebox.showwarning(APP_TEN, "Chưa có prompt nào ở tab 1.")
                return

        thu_muc = self.e_ra.get().strip() or DEFAULTS["thu_muc_ra"]
        try:
            os.makedirs(thu_muc, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_TEN, "Không tạo được thư mục ra:\n%s" % e)
            return

        moi = max(1, min(4, int(self.sp_n.get() or 1)))
        so_luong = max(1, min(8, int(self.sp_luong.get() or 1)))
        # gói -s1 chỉ cho 1 luồng: chạy nhiều hơn sẽ bị 429 liên tục, hạ xuống cho khớp gói
        toi_da = api.so_luong_toi_da(self.cfg.get("plan") or self.cfg.get("plan_name"))
        if toi_da and so_luong > toi_da:
            self._log("Gói hiện tại chỉ cho %d luồng — hạ từ %d xuống %d." %
                      (toi_da, so_luong, toi_da))
            so_luong = toi_da
        cau_hinh = {
            "model": model, "aspect": self.cb_aspect.get(),
            "resolution": self.cb_res.get(), "quality": self.cb_quality.get(),
            "moi": moi, "so_luong": so_luong, "thu_muc": thu_muc,
            "che_do_sua": che_do_sua, "ds_anh": ds_anh,
            "mo_khi_xong": bool(self.var_mo.get()),
        }

        # dọn bảng
        viec = []
        stt = 0
        for p in ds_prompt:
            for j in range(moi):
                stt += 1
                viec.append({"stt": stt, "prompt": p, "lan": j + 1, "moi": moi})

        chia = bool(self.var_chia_anh.get()) if hasattr(self, "var_chia_anh") else True
        cau_hinh["chia_folder"] = chia
        if chia and len(ds_prompt) > 1:
            ban_do = {}
            for k, g in enumerate(ds_prompt):
                ban_do[g] = self._tao_thu_muc_prompt(thu_muc, k + 1, g)
            for v in viec:
                v["thu_muc"] = ban_do[v["prompt"]]
            cau_hinh["thu_muc_prompt"] = ban_do
            self._log("Chia %d ảnh vào %d thư mục con (mỗi prompt 1 thư mục):" %
                      (len(viec), len(ban_do)))
            for g in ds_prompt:
                self._log("   %s" % os.path.basename(ban_do[g]))
        elif not chia and len(ds_prompt) > 1:
            self._log("Đang để 'gộp chung 1 folder' — %d prompt đều ghi vào %s" %
                      (len(ds_prompt), os.path.basename(thu_muc)))

        self.nb.select(2)
        self._chay_luot("anh", viec, cau_hinh)

        self._log("BẮT ĐẦU: %d ảnh | model %s | %d luồng | %s" %
                  (len(viec), api.nhan_model(model), so_luong,
                   "chế độ sửa ảnh" if che_do_sua else "chế độ tạo ảnh"))

    def _bam_chay_video(self):
        if self.dang_chay:
            return
        if not self._ds_key():
            messagebox.showwarning(APP_TEN, "Chưa có API key.\nBấm 'API key' ở góc phải để nhập.")
            return
        self._luu_tuy_chon_video()

        nguon = self.cb_vnguon.get()
        model = self._model_video_dang_chon()
        try:
            giay = max(1, min(15, int(self.sp_vsec.get())))
        except Exception:
            giay = 6
        try:
            moi = max(1, min(50, int(self.sp_vmoi.get())))
        except Exception:
            moi = 1
        res = self.cb_vres.get()
        aspect = self.cb_vaspect.get()

        ds_khung = self._ds_anh_khung()
        ds_pv = self._ds_prompt_video()
        ds_pa = self._ds_prompt_anh()
        ds_mc = self._ds_mc()
        ds_don_vi = self._ds_don_vi_tham_chieu() if self._dang_chon_tham_chieu() else []
        ds_goc = []

        # kiểm tra đầu vào theo nguồn
        if nguon == api.DS_NGUON[1]:
            if not ds_khung:
                messagebox.showwarning(APP_TEN, "Chưa có ảnh khung.\nBấm 'Thêm ảnh...' "
                                                "hoặc 'Lấy ảnh vừa tạo'.")
                return
            if not ds_pv:
                messagebox.showwarning(APP_TEN, "Chưa có prompt video.")
                return
        elif nguon == api.DS_NGUON[2]:
            if not ds_pa:
                messagebox.showwarning(APP_TEN, "Chưa có prompt ảnh.")
                return
            if not ds_pv:
                messagebox.showwarning(APP_TEN, "Chưa có prompt video.")
                return
        elif nguon == api.DS_NGUON[3]:
            if not self.e_thamchieu.get().strip():
                messagebox.showwarning(APP_TEN, "Chưa chọn folder ảnh tham chiếu.")
                return
            if not ds_don_vi:
                messagebox.showinfo(APP_TEN, "Folder ảnh tham chiếu đã hết ảnh.\n"
                                             "Chọn folder khác hoặc thêm ảnh vào folder.")
                return
            # prompt của mỗi folder: prompt.txt trong folder; thiếu thì lấy theo
            # thứ tự từ danh sách prompt video trên GUI
            if not any(d["prompt"] for d in ds_don_vi) and not ds_pv:
                messagebox.showwarning(
                    APP_TEN, "Chưa có prompt.\nMỗi folder cần 1 file prompt.txt, "
                             "hoặc nhập prompt video ở ô '2. PROMPT VIDEO'.")
                return
        else:
            if not ds_pv:
                messagebox.showwarning(APP_TEN, "Chưa có prompt video.")
                return

        thu_muc = self.e_vra.get().strip() or DEFAULTS["thu_muc_ra"]
        try:
            os.makedirs(thu_muc, exist_ok=True)
        except Exception as e:
            messagebox.showerror(APP_TEN, "Không tạo được thư mục ra:\n%s" % e)
            return

        # số luồng = số API key (mỗi key 1 luồng); gói giới hạn thì hạ theo gói
        so_luong = len(self._ds_key()) or 1
        toi_da = api.so_luong_toi_da(self.cfg.get("plan") or self.cfg.get("plan_name"))
        if toi_da and so_luong > toi_da:
            self._log("Gói hiện tại chỉ cho %d luồng — hạ từ %d xuống %d." %
                      (toi_da, so_luong, toi_da))
            so_luong = toi_da

        cau_hinh = {
            "model": model, "giay": giay, "res": res, "aspect": aspect,
            "thu_muc": thu_muc, "mo_khi_xong": bool(self.var_vmo.get()),
            "nguon": nguon,
        }

        viec = []
        stt = 0
        if nguon == api.DS_NGUON[1]:
            for p_anh in ds_khung:
                for j in range(moi):
                    stt += 1
                    viec.append({"stt": stt, "prompt": ds_pv[(stt - 1) % len(ds_pv)],
                                 "khung": p_anh, "prompt_anh": "",
                                 "lan": j + 1, "moi": moi,
                                 "nhan": os.path.basename(p_anh)})
        elif nguon == api.DS_NGUON[2]:
            for p_a in ds_pa:
                for j in range(moi):
                    stt += 1
                    viec.append({"stt": stt, "prompt": ds_pv[(stt - 1) % len(ds_pv)],
                                 "khung": "", "prompt_anh": p_a,
                                 "lan": j + 1, "moi": moi, "nhan": p_a[:40]})
        elif nguon == api.DS_NGUON[3]:
            # mỗi folder ảnh = 1 prompt riêng (prompt.txt); mỗi ảnh → 1 video;
            # ảnh dùng xong bị xoá khỏi folder. Thiếu prompt.txt thì lấy prompt
            # theo thứ tự từ danh sách prompt video trên GUI.
            k_folder = 0
            for d in ds_don_vi:
                prompt_dv = d["prompt"] or (ds_pv[k_folder % len(ds_pv)] if ds_pv else "")
                k_folder += 1
                for p_anh in d["anh"]:
                    stt += 1
                    viec.append({"stt": stt, "prompt": prompt_dv,
                                 "khung": p_anh, "prompt_anh": "",
                                 "lan": 1, "moi": 1,
                                 "nhan": os.path.basename(p_anh),
                                 "folder_vao": d["ten"],
                                 "xoa_sau": bool(self.var_xtc.get())})
        else:
            for p in ds_pv:
                for j in range(moi):
                    stt += 1
                    viec.append({"stt": stt, "prompt": p, "khung": "", "prompt_anh": "",
                                 "lan": j + 1, "moi": moi, "nhan": ""})

        # random ngoại hình MC: xáo trộn cả pool, dùng hết mới lặp lại
        if ds_mc:
            pool = []
            for v in viec:
                if not pool:
                    pool = list(ds_mc)
                    random.shuffle(pool)
                v["mc"] = pool.pop()
                v["prompt_goc"] = v["prompt"]
                v["prompt"] = self._ghep_mc(v["mc"], v["prompt"])
            self._log("Nối ngoại hình MC vào đầu %d prompt (%d MC trong pool)." %
                      (len(viec), len(ds_mc)))
        else:
            for v in viec:
                v["mc"] = ""

        for v in viec:
            g = v.get("prompt_goc") or v["prompt"]
            if g not in ds_goc:
                ds_goc.append(g)
        chia_folder = bool(self.var_chia.get()) if hasattr(self, "var_chia") else True
        cau_hinh["chia_folder"] = chia_folder
        if not chia_folder and len(ds_goc) > 1:
            self._log("Đang để 'gộp chung 1 folder' — %d prompt đều ghi vào %s" %
                      (len(ds_goc), os.path.basename(thu_muc)))
        if nguon == api.DS_NGUON[3] and ds_don_vi and chia_folder:
            # thư mục ra đặt theo ĐÚNG tên folder ảnh đầu vào (1 folder vào → 1 folder ra)
            ban_do = {}
            for k, d in enumerate(ds_don_vi):
                ban_do[d["ten"]] = self._tao_thu_muc_folder(thu_muc, k + 1, d["ten"])
            for v in viec:
                v["thu_muc"] = ban_do.get(v.get("folder_vao")) or thu_muc
            cau_hinh["thu_muc_folder"] = ban_do
            self._log("Chia %d video vào %d thư mục con (theo tên folder ảnh đầu vào):" %
                      (len(viec), len(ban_do)))
            for d in ds_don_vi:
                self._log("   %s  ←  %s (%d ảnh)" %
                          (os.path.basename(ban_do[d["ten"]]), d["ten"], len(d["anh"])))
        elif chia_folder and len(ds_goc) > 1:
            ban_do = {}
            for k, g in enumerate(ds_goc):
                ban_do[g] = self._tao_thu_muc_prompt(thu_muc, k + 1, g)
            for v in viec:
                v["thu_muc"] = ban_do[v.get("prompt_goc") or v["prompt"]]
            cau_hinh["thu_muc_prompt"] = ban_do
            self._log("Chia %d video vào %d thư mục con (mỗi prompt 1 thư mục):" %
                      (len(viec), len(ds_goc)))
            for g in ds_goc:
                self._log("   %s" % os.path.basename(ban_do[g]))

        for i in self.tree.get_children():
            self.tree.delete(i)
        self.ket_qua = []

        self.nb.select(3)
        self._chay_luot("video", viec, cau_hinh)

        self._log("BẮT ĐẦU VIDEO: %d video | %s | %ds | %s | %s | %d luồng" %
                  (len(viec), api.nhan_video(model), giay, res, aspect, so_luong))
        self._log("Nguồn cảnh đầu: %s" % nguon)

    # ------------------------------------------------ luồng chạy (mỗi API key 1 luồng)
    @staticmethod
    def _iid(loai, stt):
        return ("r%d" if loai == "anh" else "v%d") % stt

    @staticmethod
    def _nhan(loai, ch):
        return api.nhan_model(ch["model"]) if loai == "anh" else api.nhan_video(ch["model"])

    def _worker_key(self, loai, key, the_he, q):
        """1 luồng = 1 API key. Luồng cũ tự thoát khi sang lượt mới."""
        with self._wk_lock:
            self._so_worker += 1
        try:
            self._vong_worker(loai, key, the_he, q)
        finally:
            with self._wk_lock:
                self._so_worker -= 1

    def _vong_worker(self, loai, key, the_he, q):
        while True:
            if the_he != self._the_he:
                return
            try:
                iid, v, ch = q.get(timeout=0.5)
            except queue.Empty:
                if not self.dang_chay:
                    return
                continue
            if v is None:
                return
            lo = v.get("_loai") or loai        # việc nối chéo ảnh/video giữ đúng loại
            if self.dung_co or the_he != self._the_he:
                self._dem_dung()
                self.ui_q.put(("dung_dong", (lo, iid, v, ch)))
                continue
            try:
                if lo == "anh":
                    key = self._lam_mot(iid, v, ch, key, the_he)
                else:
                    key = self._lam_video(iid, v, ch, key, the_he)
            except Exception as e:          # luồng không được chết âm thầm
                self.ui_q.put(("log", "Luồng lỗi: %s" % e))
            if not self._ds_key():
                return

    def _tao_video_bang_key(self, key, v, ch):
        """Tạo + chờ + tải 1 video. Trả (đường dẫn, số byte)."""
        khung = v.get("khung") or ""
        if khung and not os.path.isfile(khung):
            raise api.LoiAPI("Không thấy ảnh khung: %s" % os.path.basename(khung), 0, "bad_input")
        if v.get("prompt_anh"):
            # bước 1: tạo ảnh khung từ prompt ảnh
            kq = api.tao_anh(key, self.cfg.get("model") or DEFAULTS["model"],
                             v["prompt_anh"], n=1,
                             aspect=self.cfg.get("aspect") or "9:16",
                             resolution=self.cfg.get("resolution") or "1k",
                             quality=self.cfg.get("quality") or "auto",
                             dung=lambda: self.dung_co)
            if not kq.get("anh"):
                raise api.LoiAPI("Không tạo được ảnh khung.", 0, "empty")
            url, b64 = kq["anh"][0]
            thu_khung = os.path.join(v.get("thu_muc") or ch["thu_muc"], "_khung")
            os.makedirs(thu_khung, exist_ok=True)
            khung = os.path.join(thu_khung, "%03d_%s.png" %
                                 (v["stt"], api.ten_an_toan(v["prompt_anh"])))
            api.tai_ve(url or b64, khung)
            if not self._la_anh(khung):
                raise api.LoiAPI("Ảnh khung tải về không hợp lệ.", 0, "empty")
            khung = self._doi_duoi(khung)

        r = api.tao_video(key, ch["model"], v["prompt"], giay=ch["giay"],
                          resolution=ch["res"], aspect=ch["aspect"],
                          anh_khung=khung or None, dung=lambda: self.dung_co)
        job_id = r["job_id"]
        self.ui_q.put(("log", "[%d] job %s — đang tạo…" % (v["stt"], job_id)))
        xong = api.cho_video_xong(key, job_id, dung=lambda: self.dung_co,
                                  bao=lambda s: self.ui_q.put(
                                      ("log", "[%d] %s" % (v["stt"], s))))
        ten = "%03d_%s_%d" % (v["stt"], api.ten_an_toan(v["prompt"]), v["lan"])
        thu_ra = v.get("thu_muc") or ch["thu_muc"]
        os.makedirs(thu_ra, exist_ok=True)
        duong_dan = os.path.join(thu_ra, ten + ".mp4")
        n = api.tai_video(key, job_id, xong.get("url"), duong_dan)
        return duong_dan, n

    def _lam_video(self, iid, v, ch, key="", the_he=None):
        t0 = time.time()
        key = key or self._lay_key()
        if the_he is not None and the_he != self._the_he:
            return key
        try:
            duong_dan, n = self._goi_co_xoay_key(
                key, lambda k: self._tao_video_bang_key(k, v, ch))[0]
            if n < 1024 or not self._la_video(duong_dan):
                raise api.LoiAPI("File tải về không phải video (%d byte)." % n, 0, "empty")
            if the_he is not None and the_he != self._the_he:
                return key      # lượt cũ: không ghi vào sổ của lượt mới
            giay = time.time() - t0
            with self._dem_lock:
                self._dem["ok"] += 1
            self._da_xong.add(v["stt"])
            self.ket_qua.append((v["stt"], v["prompt"], duong_dan, ""))
            self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                          api.nhan_video(ch["model"]), "OK",
                                          os.path.basename(duong_dan), "%.1f" % giay), "ok")))
            self.ui_q.put(("log", "[%d] OK  %s  (%.1fs, %.1f MB)" %
                           (v["stt"], os.path.basename(duong_dan), giay,
                            n / (1024.0 * 1024))))
            if v.get("xoa_sau") and v.get("khung"):
                self._xoa_anh_tham_chieu(v["khung"])
        except api.LoiAPI as e:
            if the_he is not None and the_he != self._the_he:
                return key
            if e.loai == "stopped":
                self._dem_dung()
                self.ui_q.put(("dung_dong", ("video", iid, v, ch)))
            else:
                with self._dem_lock:
                    self._dem["loi"] += 1
                self.ket_qua.append((v["stt"], v["prompt"], "", e.thong_bao))
                self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                              api.nhan_video(ch["model"]), "LỖI",
                                              e.thong_bao[:60], "%.1f" % (time.time() - t0)), "loi")))
                self.ui_q.put(("log", "[%d] LỖI %s" % (v["stt"], e.thong_bao)))
        except Exception as e:
            with self._dem_lock:
                self._dem["loi"] += 1
            self.ket_qua.append((v["stt"], v["prompt"], "", str(e)))
            self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                          api.nhan_video(ch["model"]), "LỖI",
                                          str(e)[:60], "%.1f" % (time.time() - t0)), "loi")))
            self.ui_q.put(("log", "[%d] LỖI %s" % (v["stt"], e)))
        finally:
            self._ket_thuc_viec()
        return key

    @staticmethod
    def _la_video(p):
        """Kiểm magic bytes: MP4 / MOV / WebM."""
        try:
            with open(p, "rb") as f:
                d = f.read(16)
        except Exception:
            return False
        if d[4:8] == b"ftyp":
            return True
        if d[:4] == b"\x1a\x45\xdf\xa3":
            return True
        return False

    def _goi_api(self, key, v, ch):
        """Gọi API với key hiện tại; key chết (401/403/hết credit) thì đổi key khác thử lại."""
        def goi(k):
            if ch["che_do_sua"]:
                return api.sua_anh(k, ch["model"], v["prompt"], ch["ds_anh"],
                                   aspect=ch["aspect"], resolution=ch["resolution"],
                                   quality=ch["quality"], dung=lambda: self.dung_co)
            return api.tao_anh(k, ch["model"], v["prompt"], n=1,
                               aspect=ch["aspect"], resolution=ch["resolution"],
                               quality=ch["quality"], dung=lambda: self.dung_co)

        kq, key2 = self._goi_co_xoay_key(key, goi)
        kq["_key"] = key2
        return kq

    def _goi_co_xoay_key(self, key, fn):
        """Chạy fn(key); gặp key chết thì xoay sang key khác. Trả (kết quả, key đã dùng)."""
        da_thu = set()
        while True:
            if key:
                da_thu.add(key)
            try:
                return fn(key), key
            except api.LoiAPI as e:
                if e.ma not in (401, 402, 403):
                    raise
                self._khoa_chet(key)
                con_lai = [k for k in self._ds_key() if k not in da_thu]
                if not con_lai:
                    raise api.LoiAPI("Hết key dùng được (%s)." % e.thong_bao, e.ma, e.loai)
                key = con_lai[0]
                self.ui_q.put(("log", "Key lỗi %s → chuyển key khác." % e.ma))

    def _lam_mot(self, iid, v, ch, key="", the_he=None):
        t0 = time.time()
        ten = "%03d_%s_%d" % (v["stt"], api.ten_an_toan(v["prompt"]), v["lan"])
        key = key or self._lay_key()
        if the_he is not None and the_he != self._the_he:
            return key
        try:
            kq = self._goi_api(key, v, ch)
            key = kq.get("_key") or key
            if not kq["anh"]:
                raise api.LoiAPI("Máy chủ không trả ảnh.", 0, "empty")
            url, b64 = kq["anh"][0]
            thu_ra_anh = v.get("thu_muc") or ch["thu_muc"]
            os.makedirs(thu_ra_anh, exist_ok=True)
            duong_dan = os.path.join(thu_ra_anh, ten + ".png")
            n = api.tai_ve(url or b64, duong_dan)
            if n < 16 or not self._la_anh(duong_dan):
                raise api.LoiAPI("File tải về không phải ảnh (%d byte)." % n, 0, "empty")
            duong_dan = self._doi_duoi(duong_dan)
            if the_he is not None and the_he != self._the_he:
                return key      # lượt cũ: không ghi vào sổ của lượt mới
            giay = time.time() - t0
            with self._dem_lock:
                self._dem["ok"] += 1
            self._da_xong.add(v["stt"])
            self.ket_qua.append((v["stt"], v["prompt"], duong_dan, ""))
            self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                          api.nhan_model(ch["model"]), "OK",
                                          os.path.basename(duong_dan), "%.1f" % giay), "ok")))
            self.ui_q.put(("log", "[%d] OK  %s  (%.1fs, %d KB)" %
                           (v["stt"], os.path.basename(duong_dan), giay, n // 1024)))
        except api.LoiAPI as e:
            if the_he is not None and the_he != self._the_he:
                return key
            if e.loai == "stopped":
                self._dem_dung()
                self.ui_q.put(("dung_dong", ("anh", iid, v, ch)))
            else:
                with self._dem_lock:
                    self._dem["loi"] += 1
                self.ket_qua.append((v["stt"], v["prompt"], "", e.thong_bao))
                self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                              api.nhan_model(ch["model"]), "LỖI", e.thong_bao[:60],
                                              "%.1f" % (time.time() - t0)), "loi")))
                self.ui_q.put(("log", "[%d] LỖI %s" % (v["stt"], e.thong_bao)))
        except Exception as e:
            with self._dem_lock:
                self._dem["loi"] += 1
            self.ket_qua.append((v["stt"], v["prompt"], "", str(e)))
            self.ui_q.put(("dong", (iid, (v["stt"], v["prompt"][:110],
                                          api.nhan_model(ch["model"]), "LỖI", str(e)[:60],
                                          "%.1f" % (time.time() - t0)), "loi")))
            self.ui_q.put(("log", "[%d] LỖI %s" % (v["stt"], e)))
        finally:
            self._ket_thuc_viec()
        return key

    @staticmethod
    def _la_anh(p):
        """Kiểm magic bytes: PNG / JPEG / WEBP / GIF."""
        try:
            with open(p, "rb") as f:
                d = f.read(12)
        except Exception:
            return False
        if d[:8] == b"\x89PNG\r\n\x1a\n":
            return True
        if d[:3] == b"\xff\xd8\xff":
            return True
        if d[:4] == b"RIFF" and d[8:12] == b"WEBP":
            return True
        if d[:6] in (b"GIF87a", b"GIF89a"):
            return True
        return False

    @staticmethod
    def _doi_duoi(p):
        """Đổi đuôi file theo nội dung thật (jpg/png/webp)."""
        try:
            with open(p, "rb") as f:
                dau = f.read(12)
        except Exception:
            return p
        duoi = None
        if dau[:3] == b"\xff\xd8\xff":
            duoi = ".jpg"
        elif dau[:8] == b"\x89PNG\r\n\x1a\n":
            duoi = ".png"
        elif dau[:4] == b"RIFF" and dau[8:12] == b"WEBP":
            duoi = ".webp"
        if not duoi or p.lower().endswith(duoi):
            return p
        moi = os.path.splitext(p)[0] + duoi
        try:
            if os.path.exists(moi):
                os.remove(moi)
            os.replace(p, moi)
            return moi
        except Exception:
            return p

    # ------------------------------------------------ dừng / tiếp tục / nạp lại
    def _luu_tt(self):
        """Ghi trạng thái lượt chạy ra tiep_tuc.json để mở lại app vẫn tiếp tục được."""
        if not self._lan_chay:
            try:
                os.remove(self._tt_file)
            except Exception:
                pass
            return
        d = {
            "loai": self._lan_chay["loai"],
            "cau_hinh": self._lan_chay["cau_hinh"],
            "viec": self._lan_chay["viec"],
            "da_xong": sorted(self._da_xong),
            "luc": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            with open(self._tt_file, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
        except Exception:
            pass

    def _doc_tt(self):
        try:
            with open(self._tt_file, "r", encoding="utf-8") as f:
                d = json.load(f) or {}
        except Exception:
            return
        if not d.get("viec"):
            return
        self._lan_chay = {"loai": d.get("loai") or "anh",
                          "viec": d["viec"],
                          "cau_hinh": d.get("cau_hinh") or {}}
        self._da_xong = set(d.get("da_xong") or [])

    def _cap_nhat_nut_tiep(self):
        co = bool(self._lan_chay) and not self.dang_chay
        con = False
        if co:
            con = any(v["stt"] not in self._da_xong for v in self._lan_chay["viec"])
        try:
            self.btn_tiep.configure(state="normal" if (co and con) else "disabled")
            self.btn_nap.configure(state="normal" if co else "disabled")
        except AttributeError:
            pass

    # ------------------------------------------------ nối thêm việc khi đang chạy
    def _bat_nut_noi(self):
        """Nút Nối LUÔN bấm được — bấm lúc chưa chạy sẽ được giải thích rõ."""
        try:
            self.btn_noi.configure(state="normal", text=self._ten_nut_noi)
        except AttributeError:
            pass

    def _tat_nut_noi(self):
        try:
            self.btn_noi.configure(state="normal", text=self._ten_nut_noi)
        except AttributeError:
            pass

    @staticmethod
    def _khoa_viec(v):
        """Khoá nhận diện 1 việc — dùng để không nối trùng."""
        return (str(v.get("prompt_goc") or v.get("prompt") or ""),
                str(v.get("khung") or ""),
                str(v.get("prompt_anh") or ""),
                int(v.get("lan") or 1),
                str(v.get("folder_vao") or ""))

    def _nguon_dang_chon(self):
        """Nguồn cảnh đầu đang chọn trên GUI (tab 2)."""
        try:
            return self.cb_vnguon.get() or api.DS_NGUON[0]
        except Exception:
            return api.DS_NGUON[0]

    def _che_do_chon_luc_bam(self, ch):
        """Chế độ tạo ảnh / sửa ảnh cho việc nối thêm — theo tab anh đang mở.

        Lưu ý: bấm CHẠY ở chế độ ảnh thì tool TỰ nhảy sang tab 3 (Sửa ảnh) —
        nên nếu lượt đang chạy là lượt ẢNH và tab đang mở là tab 3 thì giữ đúng
        chế độ của lượt (tránh đọc nhầm ô prompt sửa ảnh).
        """
        try:
            chi_so = self.nb.index(self.nb.select())
        except Exception:
            chi_so = -1
        if chi_so == 0:                     # tab 1: tạo ảnh hàng loạt
            return False
        if chi_so == 2:                     # tab 3: sửa ảnh / giữ nhân vật
            if (self._lan_chay or {}).get("loai") == "anh":
                return bool(ch.get("che_do_sua"))
            return True
        return bool(ch.get("che_do_sua"))   # tab khác -> giữ như lượt đang chạy

    def _ung_vien_noi(self, loai, ch, nguon=None, che_do_sua=None):
        """Đọc đầu vào HIỆN TẠI trên GUI -> danh sách việc (chưa có stt).

        Đọc theo CHẾ ĐỘ ANH ĐANG CHỌN lúc bấm nút, KHÔNG theo cấu hình của lượt
        đang chạy — nhờ vậy đang chạy nguồn này vẫn nối được việc của nguồn khác
        (vd: đang chạy prompt video, chọn folder ảnh tham chiếu khác rồi bấm nối).
        """
        ra = []
        if loai == "anh":
            # bấm CHẠY xong tool tự nhảy tab -> không dựa vào tab đang mở
            if che_do_sua is None:
                che_do_sua = bool(ch.get("che_do_sua"))
            if che_do_sua:
                ds_p = [t.strip() for t in
                        self.txt_prompt_sua.get("1.0", "end").splitlines()
                        if t.strip() and not t.strip().startswith("#")]
            else:
                ds_p = self._ds_prompt()
            try:
                moi = max(1, min(4, int(self.sp_n.get() or 1)))
            except Exception:
                moi = 1
            for p in ds_p:
                for j in range(1, moi + 1):
                    ra.append({"prompt": p, "khung": "", "prompt_anh": "",
                               "lan": j, "moi": moi, "nguon": ""})
            return ra

        nguon = nguon or self._nguon_dang_chon()
        try:
            moi = max(1, min(50, int(self.sp_vmoi.get() or 1)))
        except Exception:
            moi = 1
        if nguon == api.DS_NGUON[1]:                      # ảnh khung -> video
            for pk in self._ds_anh_khung():
                for j in range(1, moi + 1):
                    ra.append({"prompt": "", "khung": pk, "prompt_anh": "", "lan": j,
                               "moi": moi, "nhan": os.path.basename(pk), "nguon": nguon})
        elif nguon == api.DS_NGUON[2]:                    # prompt ảnh -> ảnh -> video
            for pa in self._ds_prompt_anh():
                for j in range(1, moi + 1):
                    ra.append({"prompt": "", "khung": "", "prompt_anh": pa, "lan": j,
                               "moi": moi, "nhan": pa[:40], "nguon": nguon})
        elif nguon == api.DS_NGUON[3]:                    # folder ảnh tham chiếu
            ds_pv = self._ds_prompt_video()
            k = 0
            for d in self._ds_don_vi_tham_chieu():
                p_dv = d["prompt"] or (ds_pv[k % len(ds_pv)] if ds_pv else "")
                k += 1
                for pk in d["anh"]:
                    ra.append({"prompt": p_dv, "khung": pk, "prompt_anh": "", "lan": 1,
                               "moi": 1, "nhan": os.path.basename(pk),
                               "folder_vao": d["ten"], "nguon": nguon,
                               "xoa_sau": bool(self.var_xtc.get())})
        else:                                             # chỉ prompt video
            for p in self._ds_prompt_video():
                for j in range(1, moi + 1):
                    ra.append({"prompt": p, "khung": "", "prompt_anh": "", "lan": j,
                               "moi": moi, "nhan": "", "nguon": nguon})
        return ra

    def _loai_theo_tab(self, ch):
        """Loại việc theo TAB đang mở lúc bấm nối: tab 2 = video, tab 1/3 = ảnh."""
        try:
            chi_so = self.nb.index(self.nb.select())
        except Exception:
            chi_so = -1
        if chi_so == 1:
            return "video"
        if chi_so in (0, 2):
            return "anh"
        return self._lan_chay.get("loai") or "anh"

    def _cau_hinh_noi(self, loai, ch):
        """Cấu hình cho việc nối thêm: lấy model/thông số ĐANG CHỌN trên GUI,
        giữ thư mục ra + bảng thư mục con + mở-folder-khi-xong của lượt đang chạy."""
        c = dict(ch)
        if loai == "video":
            try:
                c["giay"] = max(1, min(15, int(self.sp_vsec.get())))
            except Exception:
                pass
            c["model"] = self._model_video_dang_chon()
            c["res"] = self.cb_vres.get()
            c["aspect"] = self.cb_vaspect.get()
            c["nguon"] = self._nguon_dang_chon()
            if hasattr(self, "var_chia"):
                c["chia_folder"] = bool(self.var_chia.get())
        else:
            try:
                c["moi"] = max(1, min(4, int(self.sp_n.get() or 1)))
            except Exception:
                pass
            c["model"] = self._model_dang_chon()
            c["aspect"] = self.cb_aspect.get()
            c["resolution"] = self.cb_res.get()
            c["quality"] = self.cb_quality.get()
            c["che_do_sua"] = bool(self._che_do_chon_luc_bam(ch))
            c["ds_anh"] = self._ds_anh_gui() if c["che_do_sua"] else []
            if hasattr(self, "var_chia_anh"):
                c["chia_folder"] = bool(self.var_chia_anh.get())
        return c

    def _noi_hang_cho(self):
        """Nối prompt/ảnh MỚI vào hàng chờ của lượt đang chạy (tab 4)."""
        if not self.dang_chay or not self._lan_chay:
            messagebox.showinfo(APP_TEN, "Chưa có lượt nào đang chạy.\n"
                                         "Bấm CHẠY trước, rồi mới nối thêm.")
            return
        ch_goc = self._lan_chay.get("cau_hinh") or {}
        q = self._q_luot
        if q is None:
            messagebox.showinfo(APP_TEN, "Lượt chạy này không nhận thêm việc.")
            return

        # loại việc = theo tab đang mở (nối chéo ảnh <-> video vẫn đúng loại)
        loai = self._loai_theo_tab(ch_goc)
        nguon = None
        che_do_sua = None
        if loai == "video":
            nguon = self._nguon_dang_chon()
            if nguon == api.DS_NGUON[3]:
                p_tc = self.e_thamchieu.get().strip()
                if not p_tc or not os.path.isdir(p_tc):
                    messagebox.showwarning(APP_TEN, "Nguồn 'folder ảnh tham chiếu' "
                                                    "nhưng chưa chọn folder hợp lệ.")
                    return
            elif nguon == api.DS_NGUON[1] and not self._ds_anh_khung():
                messagebox.showwarning(APP_TEN, "Nguồn 'ảnh khung' nhưng danh sách ảnh khung "
                                                "đang trống.")
                return
            elif nguon == api.DS_NGUON[2] and not self._ds_prompt_anh():
                messagebox.showwarning(APP_TEN, "Nguồn 'prompt ảnh' nhưng ô '1. PROMPT ẢNH' "
                                                "đang trống.")
                return
        else:
            che_do_sua = self._che_do_chon_luc_bam(ch_goc)
            if che_do_sua and not self._ds_anh_gui():
                messagebox.showwarning(APP_TEN, "Chế độ sửa ảnh nhưng chưa có ảnh gửi kèm (tab 3).")
                return

        them = []
        trong = 0
        for v in self._ung_vien_noi(loai, ch_goc, nguon=nguon, che_do_sua=che_do_sua):
            if loai == "video" and not (v.get("prompt") or "").strip():
                trong += 1
                continue
            k = self._khoa_viec(v)
            if k in self._hang_cho_khoa:
                continue
            self._hang_cho_khoa.add(k)
            v["_loai"] = loai
            them.append(v)
        if trong:
            self._log("Bỏ qua %d việc không có prompt." % trong)
        if not them:
            self._log("Nối hàng chờ: không có prompt/ảnh nào mới (đều đã nằm trong lượt này).")
            return

        # cấu hình riêng cho các việc nối thêm (theo GUI lúc bấm), giữ nguyên
        # thư mục ra + bảng thư mục con của lượt đang chạy
        ch = self._cau_hinh_noi(loai, ch_goc)

        if loai == "video":
            ds_mc = self._ds_mc()
            pool = []
            for v in them:
                if ds_mc:
                    if not pool:
                        pool = list(ds_mc)
                        random.shuffle(pool)
                    v["mc"] = pool.pop()
                else:
                    v["mc"] = ""
                g = v.get("prompt") or ""
                v["prompt_goc"] = g
                if v["mc"]:
                    v["prompt"] = self._ghep_mc(v["mc"], g)

            co_folder = any(v.get("folder_vao") for v in them)
            chia = ch.get("chia_folder", True)
            bdo_f = ch.get("thu_muc_folder")
            bdo_p = ch.get("thu_muc_prompt")
            if co_folder and chia:
                if bdo_f is None:                 # lượt đang chạy chưa chia theo folder
                    bdo_f = {}
                    ch["thu_muc_folder"] = bdo_f
                    ch_goc["thu_muc_folder"] = bdo_f
                for v in them:
                    t = v.get("folder_vao") or ""
                    if t and t not in bdo_f:
                        bdo_f[t] = self._tao_thu_muc_folder(ch["thu_muc"], len(bdo_f) + 1, t)
                        self._log("   thư mục mới: %s" % os.path.basename(bdo_f[t]))
                    v["thu_muc"] = bdo_f.get(t) or ch["thu_muc"]
            else:
                ds_goc = []
                for v in them:
                    g = v.get("prompt_goc") or ""
                    if g not in ds_goc:
                        ds_goc.append(g)
                if chia and (bdo_p is not None or len(ds_goc) > 1):
                    if bdo_p is None:
                        bdo_p = {}
                        ch["thu_muc_prompt"] = bdo_p
                        ch_goc["thu_muc_prompt"] = bdo_p
                    for v in them:
                        g = v.get("prompt_goc") or ""
                        if g not in bdo_p:
                            bdo_p[g] = self._tao_thu_muc_prompt(ch["thu_muc"], len(bdo_p) + 1, g)
                            self._log("   thư mục mới: %s" % os.path.basename(bdo_p[g]))
                        v["thu_muc"] = bdo_p[g]
                else:
                    for v in them:            # gộp chung: tất cả vào thư mục ra
                        v["thu_muc"] = ch["thu_muc"]
        else:
            chia_a = ch.get("chia_folder", True)
            bdo_a = ch.get("thu_muc_prompt")
            for v in them:
                v["mc"] = ""
                g = v.get("prompt") or ""
                if chia_a and (bdo_a is not None or len({x.get("prompt") for x in them}) > 1):
                    if bdo_a is None:
                        bdo_a = {}
                        ch["thu_muc_prompt"] = bdo_a
                        ch_goc["thu_muc_prompt"] = bdo_a
                    if g not in bdo_a:
                        bdo_a[g] = self._tao_thu_muc_prompt(ch["thu_muc"], len(bdo_a) + 1, g)
                        self._log("   thư mục mới: %s" % os.path.basename(bdo_a[g]))
                    v["thu_muc"] = bdo_a[g]
                else:
                    v["thu_muc"] = ch["thu_muc"]

        nhan = self._nhan(loai, ch)
        for v in them:
            self._stt_cuoi += 1
            v["stt"] = self._stt_cuoi
            iid = self._iid(loai, v["stt"])
            try:
                self.tree.delete(iid)
            except tk.TclError:
                pass
            self.tree.insert("", "end", iid=iid,
                             values=(v["stt"], (v.get("prompt") or "")[:110],
                                     nhan, "chờ", "", ""),
                             tags=("dang",))
            try:
                self.tree.see(iid)
            except tk.TclError:
                pass
            q.put((iid, v, ch))
        self._lan_chay["viec"].extend(them)

        with self._dem_lock:
            self._dem["tong"] += len(them)
            d = dict(self._dem)
        self._cap_nhat_dem(d)

        # lỡ tất cả luồng đã thoát (hàng chờ vừa cạn) -> mở lại luồng
        with self._wk_lock:
            song = self._so_worker
        if song <= 0:
            keys = self._ds_key() or [""]
            for k in keys:
                threading.Thread(target=self._worker_key,
                                 args=(loai, k, self._the_he, q), daemon=True).start()
            self._log("Hàng chờ cạn nên luồng đã thoát — mở lại %d luồng." % len(keys))

        try:                                # phản hồi ngay trên nút, khỏi mò sang tab 4
            self.btn_noi.configure(text="✔ Đã nối " + str(len(them)) + " việc")
            self.after(4000, lambda: self.btn_noi.configure(
                text=self._ten_nut_noi, state="normal"))
        except Exception:
            pass
        if loai == "video":
            nhan_nguon = nguon or api.DS_NGUON[0]
        else:
            nhan_nguon = "sửa ảnh" if che_do_sua else "tạo ảnh"
        self._log("➕ Nối %d việc (%s) vào hàng chờ — tổng %d. Luồng đang chạy nhận ngay."
                  % (len(them), nhan_nguon, d["tong"]))

    def _chay_luot(self, loai, viec, cau_hinh, da_xong=None):
        """1 lượt chạy: mỗi API key = 1 luồng chạy song song."""
        da_xong = set(da_xong or ())
        keys = self._ds_key() or [""]
        self._the_he += 1
        the_he = self._the_he

        self._lan_chay = {"loai": loai, "viec": viec, "cau_hinh": cau_hinh}
        self._da_xong = set(da_xong)
        self.dang_chay = True
        self.dung_co = False
        self._t0 = time.time()
        with self._moc_dem_lock:
            self._moc_dem = [(self._t0, len(self._da_xong))]
        self.btn_chay.configure(state="disabled")
        self.btn_dung.configure(state="normal")
        self.btn_tiep.configure(state="disabled")
        self.btn_nap.configure(state="disabled")
        self._bat_nut_noi()

        q = queue.Queue()      # queue riêng mỗi lượt: luồng lượt cũ không giành được việc mới
        self._q_luot = q
        self._hang_cho_khoa = set()
        with self._wk_lock:
            self._so_worker = 0
        with self._dem_lock:
            self._dem = {"ok": len(da_xong), "loi": 0, "dung": 0, "tong": len(viec)}
        nhan = self._nhan(loai, cau_hinh)

        self._stt_cuoi = max([v["stt"] for v in viec] or [0])
        for v in viec:
            self._hang_cho_khoa.add(self._khoa_viec(v))
            iid = self._iid(loai, v["stt"])
            try:
                self.tree.delete(iid)
            except tk.TclError:
                pass
            if v["stt"] in da_xong:
                self.tree.insert("", "end", iid=iid,
                                 values=(v["stt"], v["prompt"][:110], nhan,
                                         "đã xong", "", ""), tags=("ok",))
                continue
            self.tree.insert("", "end", iid=iid,
                             values=(v["stt"], v["prompt"][:110], nhan, "chờ", "", ""),
                             tags=("dang",))
            q.put((iid, v, cau_hinh))

        for k in keys:
            threading.Thread(target=self._worker_key,
                             args=(loai, k, the_he, q), daemon=True).start()

        self._log("Chạy %d việc (%d đã xong trước đó) · %d luồng = %d API key" %
                  (len(viec), len(da_xong), len(keys), len(keys)))
        self._cap_nhat_dem(dict(self._dem))

        # báo cáo Telegram
        self._bat_baocao()
        if self.bc and self.bc.enabled:
            ten_loai = "tạo ảnh" if loai == "anh" else "ảnh → video"
            mo_ta = api.nhan_model(cau_hinh.get("model", "")) if loai == "anh" \
                else api.nhan_video(cau_hinh.get("model", ""))
            self.bc.bat_dau(
                "<b>LightVisual v%s — bắt đầu</b>\n"
                "Loại: %s · Model: %s\n"
                "Tổng: <b>%d</b> việc (%d đã xong trước đó)\n"
                "Luồng: %d (mỗi API key 1 luồng)\n"
                "Thư mục ra: <code>%s</code>\n"
                "Nhóm nhận báo cáo: <b>%d</b>\n"
                "Sẽ báo đúng mốc :00 và :30 (nhịp %d phút). Gõ /baocao trong nhóm để xem ngay."
                % (APP_VERSION, ten_loai, mo_ta, len(viec), len(da_xong),
                   len(keys), tele.esc(cau_hinh.get("thu_muc", "")),
                   len(self._ds_chat_nhan()),
                   int(self.cfg.get("tele_moi_phut") or 30)))

    def _ket_thuc_viec(self):
        with self._dem_lock:
            d = dict(self._dem)
        self._moc_ghi()                 # ghi mốc để tính "Đã thêm N trong Mp"
        self.ui_q.put(("dem", d))
        if d["ok"] + d["loi"] + d["dung"] >= d["tong"]:
            ch = (self._lan_chay or {}).get("cau_hinh") or {}
            self.ui_q.put(("xong", (ch,)))

    def _bam_dung(self):
        if not self.dang_chay:
            return
        self.dung_co = True
        self._luu_tt()
        self._tat_nut_noi()
        self._log("Đang dừng… các luồng sẽ nhả việc đang chạy. "
                  "Bấm 'Tiếp tục' để chạy tiếp phần còn lại.")
        self.btn_dung.configure(state="disabled")
        if self.bc and self.bc.enabled:
            with self._dem_lock:
                d = dict(self._dem)
            self.bc.bat_dau(
                "<b>LightVisual — đã bấm DỪNG</b>\n"
                "%s  %d/%d\n"
                "✅ OK %d   ❌ Lỗi %d\n"
                "Các luồng đang nhả việc — sẽ có tin kết thúc ngay sau đây."
                % (tele.thanh_tien_do(d), d["ok"] + d["loi"] + d.get("dung", 0),
                   d["tong"], d["ok"], d["loi"]))

    def _bam_tiep_tuc(self):
        """Chạy tiếp phần chưa xong của lượt trước (không làm lại việc đã OK)."""
        if self.dang_chay:
            return
        if not self._lan_chay:
            self._doc_tt()
        if not self._lan_chay:
            messagebox.showinfo(APP_TEN, "Không có lượt chạy nào để tiếp tục.")
            return
        con = [v for v in self._lan_chay["viec"] if v["stt"] not in self._da_xong]
        if not con:
            messagebox.showinfo(APP_TEN, "Lượt trước đã xong hết — không còn việc.")
            return
        self.nb.select(2 if self._lan_chay["loai"] == "anh" else 3)
        self._chay_luot(self._lan_chay["loai"], self._lan_chay["viec"],
                        self._lan_chay["cau_hinh"], da_xong=self._da_xong)

    def _bam_nap_lai(self):
        """Chạy lại từ đầu đúng danh sách + tuỳ chọn của lượt trước."""
        if self.dang_chay:
            return
        if not self._lan_chay:
            self._doc_tt()
        if not self._lan_chay:
            messagebox.showinfo(APP_TEN, "Không có lượt chạy nào để nạp lại.")
            return
        thieu = [v for v in self._lan_chay["viec"]
                 if v.get("khung") and not os.path.isfile(v["khung"])]
        if thieu:
            messagebox.showinfo(
                APP_TEN, "Lượt trước dùng folder ảnh tham chiếu — %d ảnh đã bị xoá "
                         "sau khi dùng nên không nạp lại được.\n"
                         "Hãy thêm ảnh mới vào folder rồi bấm CHẠY." % len(thieu))
            return
        self.nb.select(2 if self._lan_chay["loai"] == "anh" else 3)
        self._chay_luot(self._lan_chay["loai"], self._lan_chay["viec"],
                        self._lan_chay["cau_hinh"], da_xong=())

    def _ket_thuc(self, ch):
        if not self.dang_chay:
            return
        self.dang_chay = False
        self.btn_chay.configure(state="normal")
        self.btn_dung.configure(state="disabled")
        self._tat_nut_noi()
        d = self._dem
        giay = time.time() - self._t0
        con = len(self._lan_chay["viec"]) - len(self._da_xong) if self._lan_chay else 0
        self.lbl_tien_do.configure(
            text="XONG  %d/%d  ·  OK %d  ·  Lỗi %d  ·  Dừng %d  ·  %.0fs" %
                 (d["ok"] + d["loi"] + d["dung"], d["tong"], d["ok"], d["loi"],
                  d.get("dung", 0), giay))
        self._log("KẾT THÚC: OK %d | Lỗi %d | Dừng %d | Tổng %d | %.1fs" %
                  (d["ok"], d["loi"], d.get("dung", 0), d["tong"], giay))
        if con:
            self._log("Còn %d việc chưa xong — bấm 'Tiếp tục' để chạy tiếp "
                      "hoặc 'Nạp lại' để làm lại từ đầu." % con)
        if ch.get("mo_khi_xong") and d["ok"]:
            mo_folder(ch.get("thu_muc") or "")
        for q in (self.job_q, self.job_v_q):
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
        self._luu_tt()
        self._cap_nhat_nut_tiep()
        self._cap_nhat_plan_label()
        # nhớ lượt vừa xong để /baocao trả lời được khi không chạy
        self._lan_cuoi = {
            "ok": d["ok"], "loi": d["loi"], "dung": d.get("dung", 0),
            "tong": d["tong"], "giay": giay,
            "thu_muc": (ch or {}).get("thu_muc", ""),
        }
        # báo cáo kết thúc
        if self.bc and self.bc.enabled:
            tb = (giay / max(1, d["ok"] + d["loi"] + d.get("dung", 0)))
            dong = [
                "<b>LightVisual v%s — KẾT THÚC</b>" % APP_VERSION,
                "%s  %d/%d" % (tele.thanh_tien_do(d),
                               d["ok"] + d["loi"] + d.get("dung", 0), d["tong"]),
                "✅ OK %d   ❌ Lỗi %d   ⏸️ Dừng %d" % (d["ok"], d["loi"], d.get("dung", 0)),
                "⏱ Tổng %s · %.1fs/việc" % (tele.dinh_dang_giay(giay), tb),
            ]
            if con:
                dong.append("Còn <b>%d</b> việc — bấm “Tiếp tục” để chạy tiếp." % con)
            if d["loi"]:
                dong.append("\n<i>Mở tab “Kết quả & nhật ký” để xem lỗi từng dòng.</i>")
            dong.append("📁 <code>%s</code>" % tele.esc((ch or {}).get("thu_muc", "")))
            self.bc.ket_thuc("\n".join(dong))
            self._dung_baocao()

    # ------------------------------------------------ cập nhật từ GitHub

    def _check_update(self):
        """Kiểm tra GitHub rồi (nếu có bản mới) hỏi trước khi cập nhật."""
        if self.dang_chay:
            messagebox.showwarning("Đang chạy",
                                   "Tool đang chạy — đợi xong rồi cập nhật.")
            return
        self.upd_btn.configure(state="disabled", text="⬆ Đang kiểm tra...")
        threading.Thread(target=self._update_work, daemon=True).start()

    def _update_work(self):
        try:
            import updater as U
        except Exception as e:
            self.ui_q.put(("upd_loi", "Thiếu updater.py: %s" % e))
            return
        self.ui_q.put(("log", "Bản đang dùng: v%s" % U.read_local_version()))
        r = U.check_update()
        if not r.get("ok"):
            self.ui_q.put(("upd_loi", r.get("error", "?")))
            return
        if not r.get("has_update"):
            self.ui_q.put(("upd_xong",
                           "Bạn đang dùng bản mới nhất (v%s)." % r["local"]))
            return
        self.ui_q.put(("upd_hoi", r))

    def _update_hoi(self, r):
        notes = (r.get("notes") or "").strip()
        msg = ("Có bản mới v%s (bạn đang dùng v%s).\n\n" % (r["remote"], r["local"])
               + (notes + "\n\n" if notes else "")
               + "Cập nhật NGAY bây giờ?\n"
                 "(Cài đặt + API key + ảnh/video cũ được giữ nguyên.)")
        if not messagebox.askyesno("Có bản cập nhật", msg):
            self._update_xong("Đã bỏ qua cập nhật.")
            return
        self.upd_btn.configure(text="⬆ Đang tải...")
        threading.Thread(target=self._update_apply, args=(r,), daemon=True).start()

    def _update_apply(self, r):
        try:
            import updater as U
            res = U.apply_update(r.get("zip", ""),
                                 log=lambda s: self.ui_q.put(("log", s)))
        except Exception as e:
            self.ui_q.put(("upd_loi", "Lỗi cập nhật: %s" % e))
            return
        if not res.get("ok"):
            self.ui_q.put(("upd_loi", res.get("error", "?")))
            return
        self.ui_q.put(("upd_xong_restart", res))

    def _update_xong_restart(self, res):
        v = res.get("version", "?")
        self._log("Đã cập nhật lên v%s. Đang khởi động lại tool..." % v)
        if not messagebox.askyesno(
                "Đã cập nhật",
                "Đã cập nhật lên v%s.\n\n"
                "Bản cũ được sao lưu ở:\n%s\n\n"
                "Khởi động lại tool ngay bây giờ?" % (v, res.get("backup", ""))):
            self._update_xong("Đã cập nhật v%s — mở lại tool để dùng bản mới." % v)
            return
        self._khoi_dong_lai()

    def _khoi_dong_lai(self):
        """Mở lại chính tool này rồi thoát tiến trình hiện tại."""
        try:
            import subprocess
            py = sys.executable or "python"
            me = os.path.join(THU_MUC_GOC, "main.py")
            subprocess.Popen([py, me], cwd=THU_MUC_GOC)
            self.after(300, self.destroy)
        except Exception as e:
            self._update_xong("Đã cập nhật — không tự mở lại được (%s). "
                              "Mở tool bằng tay." % e)

    def _update_xong(self, msg):
        try:
            self.upd_btn.configure(state="normal", text="⬆ Cập nhật")
        except Exception:
            pass
        self._log(msg)

    def _update_loi(self, err):
        self._update_xong("LỖI cập nhật: %s" % err)
        msg = "Không cập nhật được:\n%s" % err
        low = str(err).lower()
        if "certificate" in low or "ssl" in low:
            msg += ("\n\nMáy này thiếu kho chứng chỉ CA.\n"
                    "Cách sửa: chép file cacert.pem vào thư mục tool rồi thử lại.")
        messagebox.showerror("Cập nhật", msg)

    def _thoat_app(self):
        if self.dang_chay:
            if not messagebox.askyesno(APP_TEN, "Đang chạy. Dừng và thoát?"):
                return
            self.dung_co = True
        # chặn watchdog bật lại luồng nghe trong lúc đang đóng
        self._thoat = True
        try:
            if self._aid_moc:
                self.after_cancel(self._aid_moc)
                self._aid_moc = None
            if getattr(self, "_aid_hen", None):
                self.after_cancel(self._aid_hen)
                self._aid_hen = None
        except Exception:
            pass
        try:
            if self._aid:
                self.after_cancel(self._aid)
                self._aid = None
        except Exception:
            pass
        # Gửi nốt báo cáo: chờ TỐI ĐA 2s (mỗi tin thường <1s). Không chờ 45s nữa.
        try:
            if self.bc:
                self.bc.dung(cho=2.0)
        except Exception:
            pass
        self.bc = None
        # Nghe lệnh: chỉ báo dừng, KHÔNG join long-poll (giữ kết nối tới 40s).
        self._dung_theo_doi(nhanh=True)
        try:
            self.destroy()
        except Exception:
            pass


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
