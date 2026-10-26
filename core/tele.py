# -*- coding: utf-8 -*-
"""Báo cáo tiến độ lên Telegram — thuần stdlib, không cần pip.

Dùng:
    bc = BaoCao(token, chat_id, moi_giay=300)
    bc.bat_dau("...")      # luôn gửi
    bc.tien_do("...")      # chỉ gửi nếu đã qua moi_giay
    bc.ket_thuc("...")     # luôn gửi
    bc.dung()

Token lấy theo thứ tự: tham số truyền vào -> biến môi trường TELEGRAM_BOT_TOKEN
-> %LOCALAPPDATA%\\hermes\\.env (dòng TELEGRAM_BOT_TOKEN=...).
Không bao giờ ghi token ra log; hàm che() chỉ trả 10 ký tự đầu.
"""

from __future__ import annotations

import html
import json
import os
import queue
import threading
import time
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot%s/sendMessage"
GIOI_HAN_KY_TU = 3800          # Telegram cắt ở 4096, chừa chỗ cho phần đuôi


# ---------------------------------------------------------------- tiện ích
def thu_muc_hermes():
    la = os.environ.get("LOCALAPPDATA")
    if la:
        return os.path.join(la, "hermes")
    return os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes")


def doc_token_hermes():
    """Đọc TELEGRAM_BOT_TOKEN trong .env của Hermes (nếu có)."""
    p = os.path.join(thu_muc_hermes(), ".env")
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for dong in f:
                t = dong.strip()
                if t.startswith("TELEGRAM_BOT_TOKEN="):
                    v = t.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    except Exception:
        pass
    return ""


def lay_token(token=""):
    """token truyền vào -> biến môi trường -> .env của Hermes."""
    t = (token or "").strip()
    if t:
        return t
    t = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if t:
        return t
    return doc_token_hermes()


def che(token):
    """Rút gọn token để in ra log/màn hình."""
    t = (token or "").strip()
    if not t:
        return "(chưa có)"
    if len(t) <= 14:
        return t[:4] + "…"
    return t[:10] + "…"


def esc(s):
    return html.escape(str(s or ""), quote=False)


def _doc_json(raw):
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return None


def gui(token, chat_id, text, timeout=20):
    """Gửi 1 tin nhắn. Trả (ok, mô_tả_lỗi)."""
    token = lay_token(token)
    chat_id = str(chat_id or "").strip()
    if not token:
        return False, "chưa có bot token"
    if not chat_id:
        return False, "chưa có chat_id"
    body = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": str(text or "")[:GIOI_HAN_KY_TU],
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(API % token, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = _doc_json(r.read())
        if isinstance(d, dict) and d.get("ok"):
            return True, ""
        return False, str((d or {}).get("description") or "Telegram từ chối")[:200]
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        d = _doc_json(raw) or {}
        return False, "HTTP %s: %s" % (e.code, str(d.get("description") or "")[:160])
    except Exception as e:
        return False, str(e)[:200]


def dinh_dang_giay(giay):
    giay = max(0, int(giay))
    if giay < 60:
        return "%ds" % giay
    if giay < 3600:
        return "%dp%02ds" % (giay // 60, giay % 60)
    return "%dh%02dp" % (giay // 3600, (giay % 3600) // 60)


def thanh_tien_do(dem):
    """Vẽ thanh tiến độ bằng ký tự (10 ô)."""
    tong = max(1, int(dem.get("tong") or 1))
    xong = int(dem.get("ok", 0)) + int(dem.get("loi", 0)) + int(dem.get("dung", 0))
    xong = min(xong, tong)
    day = int(round(xong * 10.0 / tong))
    return "%s%s" % ("▰" * day, "▱" * (10 - day))


# ---------------------------------------------------------------- lớp báo cáo
class BaoCao(object):
    """Hàng đợi gửi Telegram chạy nền, có chặn tần suất cho tin tiến độ."""

    def __init__(self, token="", chat_id="", moi_giay=300, log=None):
        self.token = lay_token(token)
        self.chat_id = str(chat_id or "").strip()
        self.moi_giay = max(15, int(moi_giay or 300))
        self.log = log or (lambda *a, **k: None)
        self.q = queue.Queue(maxsize=200)
        self._stop = threading.Event()
        self._t = None
        self._lan_gui = 0.0
        self._khoa = threading.Lock()
        self.loi_cuoi = ""
        self.da_gui = 0

    @property
    def enabled(self):
        return bool(self.token and self.chat_id)

    # -- vòng đời
    def bat_dau_worker(self):
        if not self.enabled or self._t:
            return
        self._lan_gui = time.time()     # tin tiến độ đầu tiên phải chờ đủ moi_giay
        # không daemon: khi thoát app, tiến trình chờ gửi nốt tin kết thúc trong hàng đợi
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = False
        self._t.start()

    def dung(self, cho=5.0):
        """Dừng luồng gửi; chờ tối đa `cho` giây để gửi nốt tin còn trong hàng đợi."""
        self._stop.set()
        t = self._t
        if t and t.is_alive():
            t.join(timeout=cho)

    # -- đưa tin vào hàng đợi
    def _dat(self, text, ngay):
        if not self.enabled:
            return False
        try:
            self.q.put_nowait((text, bool(ngay)))
            return True
        except queue.Full:
            return False

    def bat_dau(self, text):
        return self._dat(text, True)

    def tien_do(self, text):
        return self._dat(text, False)

    def ket_thuc(self, text):
        return self._dat(text, True)

    # -- gửi
    def _loop(self):
        while True:
            if self._stop.is_set() and self.q.empty():
                break
            try:
                text, ngay = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            if not ngay:
                with self._khoa:
                    if time.time() - self._lan_gui < self.moi_giay:
                        continue        # chưa tới nhịp -> bỏ tin này
            ok, loi = gui(self.token, self.chat_id, text)
            with self._khoa:
                self._lan_gui = time.time()
            if ok:
                self.da_gui += 1
            else:
                self.loi_cuoi = loi
                self.log("Tele: gửi lỗi — %s" % loi)

    # -- gửi đồng bộ (dùng cho nút "Gửi thử")
    def thu(self, text="LightVisual: kết nối Telegram OK"):
        return gui(self.token, self.chat_id, text)
