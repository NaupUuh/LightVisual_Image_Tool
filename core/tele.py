# -*- coding: utf-8 -*-
"""Telegram cho LightVisual — thuần stdlib, không cần pip.

Gồm 3 phần:
  * gui()/goi()  — gửi tin, gọi Bot API
  * BaoCao       — hàng đợi gửi nền, chặn tần suất, gửi nhiều nhóm
  * TheoDoi      — long-poll getUpdates để bắt lệnh /baocao trong nhóm
  * lay_nhom()   — quét getUpdates một lượt, gom danh sách nhóm/kênh

Token lấy theo thứ tự: tham số -> TELEGRAM_BOT_TOKEN -> .env của Hermes.
Không bao giờ ghi token ra log; che() chỉ trả 10 ký tự đầu.
"""

from __future__ import annotations

import html
import json
import os
import queue
import re
import threading
import time
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot%s/sendMessage"          # giữ để test cũ dùng
API_GOC = "https://api.telegram.org/bot%s/%s"
GIOI_HAN_KY_TU = 3800          # Telegram cắt ở 4096, chừa chỗ cho phần đuôi

LOAI_NHOM = ("group", "supergroup", "channel")
LOAI_GOI = ("message", "edited_message", "channel_post", "edited_channel_post",
            "my_chat_member", "chat_member", "chat_join_request")


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


def _mo_ta_loi(ma, d, mac_dinh="Telegram từ chối"):
    """Chuyển lỗi Bot API thành câu dễ hiểu."""
    mo_ta = str((d or {}).get("description") or mac_dinh)
    low = mo_ta.lower()
    if "terminated by other getupdates" in low or "conflict" in low:
        return ("HTTP %s: token này đang bị chương trình khác đọc getUpdates "
                "(409 Conflict). Tắt bot đó hoặc dùng token bot riêng." % ma)
    if "chat not found" in low:
        return "HTTP %s: không thấy chat — bot chưa được add vào nhóm?" % ma
    if "bot was blocked" in low:
        return "HTTP %s: bot bị chặn." % ma
    if "not enough rights" in low:
        return "HTTP %s: bot thiếu quyền gửi tin trong nhóm." % ma
    return "HTTP %s: %s" % (ma, mo_ta[:200])


def goi(token, method, tham_so=None, timeout=25):
    """Gọi Bot API. Trả (ok, kết_quả | mô_tả_lỗi)."""
    token = lay_token(token)
    if not token:
        return False, "chưa có bot token"
    url = API_GOC % (token, method)
    data = None
    if tham_so:
        data = json.dumps(tham_so).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = _doc_json(r.read())
        if isinstance(d, dict) and d.get("ok"):
            return True, d.get("result")
        return False, str((d or {}).get("description") or "Telegram từ chối")[:200]
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            raw = e.read()
        except Exception:
            pass
        return False, _mo_ta_loi(e.code, _doc_json(raw) or {})
    except Exception as e:
        return False, str(e)[:200]


def get_me(token):
    """Trả (ok, {'username':..., 'id':...} | lỗi)."""
    ok, kq = goi(token, "getMe", None, timeout=15)
    if not ok:
        return False, kq
    if not isinstance(kq, dict):
        return False, "getMe trả dữ liệu lạ"
    return True, kq


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
        return False, _mo_ta_loi(e.code, _doc_json(raw) or {})
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


# ---------------------------------------------------------------- nhóm / lệnh
def chat_cua_update(up):
    """Lấy dict chat từ 1 update (message, channel_post, my_chat_member…)."""
    if not isinstance(up, dict):
        return None
    for k in LOAI_GOI:
        o = up.get(k)
        if isinstance(o, dict) and isinstance(o.get("chat"), dict):
            return o["chat"]
    return None


def text_cua_update(up):
    if not isinstance(up, dict):
        return ""
    for k in ("message", "channel_post", "edited_message", "edited_channel_post"):
        o = up.get(k)
        if isinstance(o, dict) and isinstance(o.get("text"), str):
            return o["text"]
    return ""


def ten_nhom(chat):
    """Tên hiển thị của 1 chat."""
    if not isinstance(chat, dict):
        return ""
    return (chat.get("title") or chat.get("username")
            or chat.get("first_name") or str(chat.get("id") or ""))


def tach_chat_id(raw):
    """Đọc Chat ID hoặc link nhóm -> (chat_id, tên_gợi_ý).

    Nhận: "-1001234567890", "1001234567890" (tự thêm -100), "@tenkenh",
    "https://t.me/tenkenh", "https://t.me/+AbCdEf", "t.me/joinchat/AbCdEf".
    Link mời riêng tư không suy ra được số -> trả ("", "").
    """
    s = (raw or "").strip()
    if not s:
        return "", ""
    if s.startswith("@"):
        ten = s[1:].strip()
        return (("@" + ten) if ten else ""), ten
    m = re.match(r"^(?:https?://)?(?:www\.)?t(?:elegram)?\.me/(.+)$", s, re.I)
    if m:
        duong = m.group(1).strip().strip("/")
        if duong.lower().startswith("joinchat/") or duong.startswith("+"):
            return "", ""
        duong = duong.split("?")[0].split("/")[0]
        if not duong:
            return "", ""
        return "@" + duong, duong
    so = re.sub(r"[\s.]", "", s)
    if re.match(r"^-?\d+$", so):
        if so.startswith("-"):
            return so, ""
        if so.startswith("100"):
            return "-" + so, ""
        return so, ""
    return "", ""


def la_lenh_baocao(text, bot_username=""):
    """True nếu text là /baocao hoặc /baocao@<bot>."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return False
    phan = t.split()[0][1:]
    if not phan:
        return False
    if "@" in phan:
        ten, _, ai = phan.partition("@")
        if bot_username and ai.strip().lower() != bot_username.strip().lower():
            return False
        phan = ten
    return phan.strip().lower() in ("baocao", "bc", "report")


def lay_nhom(token, giay=10.0, offset=0, log=None):
    """Quét getUpdates trong `giay` giây, gom nhóm/kênh bot đang ở.

    Trả (danh_sách_nhóm, offset_mới, mô_tả_lỗi).
    Mỗi nhóm: {"id": "-100…", "type": "supergroup", "title": "Tên nhóm"}
    """
    log = log or (lambda *a, **k: None)
    token = lay_token(token)
    ds = {}
    if not token:
        return [], int(offset or 0), "chưa có bot token"
    off = int(offset or 0)
    het = time.time() + max(1.0, float(giay))
    while time.time() < het:
        con = max(1, int(het - time.time()))
        cho = min(20, con)
        ok, kq = goi(token, "getUpdates",
                     {"offset": off, "timeout": cho, "limit": 100}, timeout=cho + 15)
        if not ok:
            return list(ds.values()), off, kq
        for up in (kq or []):
            try:
                off = max(off, int(up.get("update_id", 0)) + 1)
            except Exception:
                pass
            c = chat_cua_update(up)
            if c and str(c.get("type")) in LOAI_NHOM:
                ds[str(c.get("id"))] = {"id": str(c.get("id")),
                                        "type": str(c.get("type")),
                                        "title": ten_nhom(c)}
    dsac = sorted(ds.values(), key=lambda x: (x.get("title") or "").lower())
    log("Tele: quét thấy %d nhóm." % len(dsac))
    return dsac, off, ""


# ---------------------------------------------------------------- lớp báo cáo
class BaoCao(object):
    """Hàng đợi gửi Telegram chạy nền, chặn tần suất, gửi được nhiều nhóm."""

    def __init__(self, token="", chat_id="", moi_giay=300, log=None, chat_ids=None):
        self.token = lay_token(token)
        ds = []
        for x in (chat_ids or []):
            x = str(x or "").strip()
            if x and x not in ds:
                ds.append(x)
        c = str(chat_id or "").strip()
        if c and c not in ds:
            ds.insert(0, c)
        self.chat_ids = ds
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
    def chat_id(self):
        return self.chat_ids[0] if self.chat_ids else ""

    @property
    def enabled(self):
        return bool(self.token and self.chat_ids)

    # -- vòng đời
    def bat_dau_worker(self):
        if not self.enabled or self._t:
            return False
        self._lan_gui = time.time()     # tin tiến độ đầu tiên phải chờ đủ moi_giay
        # không daemon: khi thoát app, tiến trình chờ gửi nốt tin kết thúc trong hàng đợi
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = False
        self._t.start()
        return True

    def dung(self, cho=5.0):
        """Dừng luồng gửi; chờ tối đa `cho` giây để gửi nốt tin còn trong hàng đợi."""
        self._stop.set()
        t = self._t
        if t and t.is_alive():
            t.join(timeout=cho)

    # -- đưa tin vào hàng đợi
    def _dat(self, text, ngay, chat_ids=None):
        if not self.token:
            return False
        ds = self.chat_ids
        if chat_ids:
            ds = [str(x) for x in chat_ids if str(x or "").strip()]
        if not ds:
            return False
        try:
            self.q.put_nowait((text, bool(ngay), list(ds)))
            return True
        except queue.Full:
            return False

    def bat_dau(self, text):
        return self._dat(text, True)

    def tien_do(self, text):
        return self._dat(text, False)

    def ket_thuc(self, text):
        return self._dat(text, True)

    def gui_ngay(self, text, chat_ids=None):
        """Gửi ngay, không chờ nhịp (dùng cho lệnh /baocao)."""
        return self._dat(text, True, chat_ids)

    # -- gửi
    def _loop(self):
        while True:
            if self._stop.is_set() and self.q.empty():
                break
            try:
                text, ngay, ds = self.q.get(timeout=1.0)
            except queue.Empty:
                continue
            if not ngay:
                with self._khoa:
                    if time.time() - self._lan_gui < self.moi_giay:
                        continue        # chưa tới nhịp -> bỏ tin này
            ok_het = True
            for cid in ds:
                ok, loi = gui(self.token, cid, text)
                if ok:
                    self.da_gui += 1
                else:
                    ok_het = False
                    self.loi_cuoi = loi
                    self.log("Tele: gửi lỗi (%s) — %s" % (cid, loi))
            with self._khoa:
                self._lan_gui = time.time()
            if not ok_het:
                continue

    # -- gửi đồng bộ (dùng cho nút "Gửi thử")
    def thu(self, text="LightVisual: kết nối Telegram OK", chat_id=None):
        return gui(self.token, chat_id or self.chat_id, text)


# ---------------------------------------------------------------- theo dõi lệnh
class TheoDoi(object):
    """Long-poll getUpdates để bắt /baocao trong nhóm.

    Gọi khi_lenh(chat_id, ten_nhom) mỗi lần có lệnh. Tự lưu offset.
    """

    def __init__(self, token="", khi_lenh=None, log=None, timeout=25):
        self.token = lay_token(token)
        self.khi_lenh = khi_lenh
        self.log = log or (lambda *a, **k: None)
        self.timeout = max(5, int(timeout))
        self.nhom = {}
        self.offset = 0
        self.bot_username = ""
        self.loi_cuoi = ""
        self._stop = threading.Event()
        self._t = None

    @property
    def enabled(self):
        return bool(self.token)

    def dang_chay(self):
        return bool(self._t and self._t.is_alive())

    def bat_dau(self):
        if not self.enabled or self.dang_chay():
            return False
        ok, me = get_me(self.token)
        if ok:
            self.bot_username = str(me.get("username") or "")
            # Privacy mode BẬT -> Telegram chỉ gửi lệnh dạng /baocao@<bot>, lệnh
            # trần "/baocao" bị chặn. Phải nói rõ để anh không tưởng tool hỏng.
            if not me.get("can_read_all_group_messages"):
                self.log("Telegram: bot đang BẬT chế độ riêng tư nên chỉ nhận lệnh "
                         "dạng /baocao@%s. Muốn gõ /baocao trần: BotFather -> "
                         "/setprivacy -> chọn bot -> Disable." % self.bot_username)
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = True
        self._t.start()
        return True

    def dung(self, cho=45.0):
        """Dừng long-poll. Phải chờ đủ lâu: Telegram giữ request tới `timeout` giây,
        nếu bật lại trước khi luồng cũ nhả kết nối thì 2 luồng cùng getUpdates
        -> 409 Conflict và tool tự tắt nghe lệnh."""
        self._stop.set()
        t = self._t
        if t and t.is_alive():
            t.join(timeout=cho)
        if t and t.is_alive():
            # luồng cũ vẫn treo -> không cho bật luồng mới (tránh 409)
            self.log("Tele: luồng nghe cũ chưa dừng hẳn — chờ thêm rồi bật lại.")
            return False
        self._t = None
        return True

    def _loop(self):
        dem_loi = 0
        while not self._stop.is_set():
            ok, kq = goi(self.token, "getUpdates",
                         {"offset": self.offset, "timeout": self.timeout,
                          "limit": 100,
                          "allowed_updates": ["message", "channel_post",
                                              "my_chat_member"]},
                         timeout=self.timeout + 15)
            if not ok:
                self.loi_cuoi = kq
                dem_loi += 1
                if "409" in str(kq) or "Conflict" in str(kq):
                    # token này đang bị nơi khác getUpdates (vd bot Hermes) —
                    # dừng ngay, không tranh chấp làm chết cả 2 bên
                    self.log("Tele: token đang được nơi khác dùng để nghe lệnh (409). "
                             "Hãy tạo bot riêng cho tool bằng @BotFather rồi dán token mới.")
                    self._stop.set()
                    break
                if dem_loi == 1:
                    self.log("Tele: không đọc được lệnh trong nhóm — %s" % kq)
                if dem_loi >= 3:
                    break
                self._stop.wait(3.0)
                continue
            dem_loi = 0
            for up in (kq or []):
                try:
                    self.offset = max(self.offset, int(up.get("update_id", 0)) + 1)
                except Exception:
                    pass
                c = chat_cua_update(up)
                if c and str(c.get("type")) in LOAI_NHOM:
                    cid = str(c.get("id"))
                    moi = cid not in self.nhom
                    self.nhom[cid] = {"id": cid,
                                      "type": str(c.get("type")),
                                      "title": ten_nhom(c)}
                    if moi:
                        # ghi ID ra log để anh copy dán vào ô "ID nhóm"
                        self.log("Telegram: thấy nhóm \"%s\" — ID %s"
                                 % (ten_nhom(c), cid))
                if not self.khi_lenh:
                    continue
                txt = text_cua_update(up)
                if la_lenh_baocao(txt, self.bot_username):
                    cid = str((c or {}).get("id") or "")
                    # chỉ nhận lệnh trong nhóm/kênh, bỏ qua chat riêng
                    if cid and str((c or {}).get("type")) in LOAI_NHOM:
                        try:
                            self.khi_lenh(cid, ten_nhom(c))
                        except Exception:
                            pass
