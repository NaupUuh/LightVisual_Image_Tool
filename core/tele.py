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

# Nhóm thường (-5593791314) khi được nâng cấp lên supergroup sẽ đổi ID thành
# -1004471871974. Telegram trả 400 kèm parameters.migrate_to_chat_id ⇒ ghi lại
# ánh xạ ở đây để main.py lưu vào config.json (người dùng không phải sửa tay).
_MIGRATE = {}


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
    if "upgraded to a supergroup" in low or "migrate_to_chat_id" in low:
        moi = _migrate_tu(d)
        if moi:
            return ("HTTP %s: nhóm đã nâng cấp lên supergroup — ID mới %s "
                    "(tool tự chuyển)." % (ma, moi))
        return "HTTP %s: nhóm đã nâng cấp lên supergroup, cần ID mới." % ma
    if "chat not found" in low:
        return "HTTP %s: không thấy chat — bot chưa được add vào nhóm?" % ma
    if "bot was blocked" in low:
        return "HTTP %s: bot bị chặn." % ma
    if "not enough rights" in low:
        return "HTTP %s: bot thiếu quyền gửi tin trong nhóm." % ma
    return "HTTP %s: %s" % (ma, mo_ta[:200])


def _migrate_tu(d):
    """Lấy chat_id mới trong parameters.migrate_to_chat_id (nếu có)."""
    try:
        p = (d or {}).get("parameters") or {}
        moi = p.get("migrate_to_chat_id")
        if moi:
            return str(moi)
    except Exception:
        pass
    return ""


def lay_migrate():
    """Trả dict {id_cu: id_moi} đã gặp trong phiên này (main.py lưu vào config)."""
    return dict(_MIGRATE)


def _ghi_migrate(tham_so, d):
    """Ghi lại cặp (chat_id cũ -> mới) khi Telegram báo nhóm lên supergroup."""
    try:
        moi = _migrate_tu(d)
        if not moi:
            return
        cu = ""
        if isinstance(tham_so, dict):
            cu = str(tham_so.get("chat_id") or "").strip()
        if cu and cu != moi:
            _MIGRATE[cu] = moi
    except Exception:
        pass




def goi(token, method, tham_so=None, timeout=25):
    """Gọi Bot API. Trả (ok, kết_quả | mô_tả_lỗi)."""
    token = lay_token(token)
    if not token:
        return False, "chưa có bot token"
    url = API_GOC % (token, method)
    data = None
    # tham_so=None -> GET; tham_so={} (dict rỗng) vẫn phải POST, nếu không
    # máy chủ/proxy có thể trả 501 Unsupported method.
    if tham_so is not None:
        data = json.dumps(tham_so).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    if data is not None:
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
        d = _doc_json(raw) or {}
        _ghi_migrate(tham_so, d)
        return False, _mo_ta_loi(e.code, d)
    except Exception as e:
        return False, str(e)[:200]


def dat_lenh(token, ds=None):
    """Đăng ký menu lệnh -> gõ '/' trong nhóm là hiện danh sách để bấm.

    ds: [{"command": "baocao", "description": "..."}, ...]
    Trả (ok, lỗi).
    """
    ds = ds or [
        {"command": "baocao", "description": "Báo cáo tiến độ ngay"},
        {"command": "trangthai", "description": "Đang chạy hay đang rảnh"},
        {"command": "tonghop", "description": "Cả nhóm cùng báo cáo (mọi máy)"},
        {"command": "giup", "description": "Hướng dẫn dùng bot"},
    ]
    sach = []
    for c in ds:
        ten = str((c or {}).get("command") or "").strip().lstrip("/")
        mo = str((c or {}).get("description") or "").strip()
        if not ten or not mo:
            continue
        sach.append({"command": ten[:32], "description": mo[:256]})
    if not sach:
        return False, "không có lệnh nào để đăng ký"
    return goi(token, "setMyCommands", {"commands": sach,
                                        "scope": {"type": "all_group_chats"}},
               timeout=20)


def lay_lenh(token):
    """Đọc menu lệnh đã đăng ký. Trả (ok, list | lỗi)."""
    ok, kq = goi(token, "getMyCommands",
                 {"scope": {"type": "all_group_chats"}}, timeout=15)
    if not ok:
        return False, kq
    return True, kq or []


def get_me(token):
    """Trả (ok, {'username':..., 'id':...} | lỗi)."""
    # gửi POST ({} = có body) để chắc chắn qua được mọi cấu hình mạng/proxy
    ok, kq = goi(token, "getMe", {}, timeout=15)
    if not ok:
        return False, kq
    if not isinstance(kq, dict):
        return False, "getMe trả dữ liệu lạ"
    return True, kq


def gui(token, chat_id, text, timeout=20):
    """Gửi 1 tin nhắn. Trả (ok, mô_tả_lỗi).

    Nếu nhóm đã nâng cấp lên supergroup, Telegram trả 400 kèm
    parameters.migrate_to_chat_id ⇒ gửi lại ngay bằng ID mới.
    """
    token = lay_token(token)
    chat_id = str(chat_id or "").strip()
    if not token:
        return False, "chưa có bot token"
    if not chat_id:
        return False, "chưa có chat_id"
    # đã biết nhóm lên supergroup trước đó -> gửi thẳng bằng ID mới
    chat_id = _MIGRATE.get(chat_id, chat_id)
    return _gui1(token, chat_id, text, timeout, thu_lai=True)


def _gui1(token, chat_id, text, timeout, thu_lai):
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
        moi = _migrate_tu(d)
        if moi and thu_lai:
            _MIGRATE[chat_id] = moi
            ok, loi = _gui1(token, moi, text, timeout, thu_lai=False)
            if ok:
                return True, ""
            return False, "nhóm đã lên supergroup (%s) nhưng gửi vẫn lỗi: %s" % (
                moi, loi)
        return False, _mo_ta_loi(e.code, d)
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


def dinh_dang_phut(giay):
    """Độ dài cửa sổ thời gian dạng ngắn: 45s / 30p / 1h31p.

    Khác `dinh_dang_giay` ở chỗ bỏ phần giây khi đã ≥ 1 phút — dùng cho câu
    "Đã thêm N video trong 30p" nên không cần chính xác tới giây.
    """
    giay = max(0, int(giay))
    if giay < 60:
        return "%ds" % giay
    phut = int(round(giay / 60.0))
    if phut < 60:
        return "%dp" % phut
    return "%dh%02dp" % (phut // 60, phut % 60)


def giay_toi_moc(buoc_phut=30, now=None):
    """Số giây còn lại tới MỐC ĐỒNG HỒ kế tiếp chia hết cho `buoc_phut`.

    buoc_phut=30 -> mốc :00 và :30; 60 -> :00; 15 -> :00/:15/:30/:45.
    Khác hẳn kiểu "mỗi N phút kể từ lúc bật": kiểu đó trôi theo giờ mở tool,
    còn kiểu này luôn rơi đúng mốc để nhiều máy cùng báo 1 lúc.
    """
    try:
        buoc = max(1, int(buoc_phut)) * 60
    except Exception:
        buoc = 1800
    t = now or time.localtime()
    trong_ngay = t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec
    con = buoc - (trong_ngay % buoc)
    if con <= 0:
        con += buoc
    return con


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
    phan = phan.strip().lower()
    return phan in ("baocao", "bc", "report")


def la_lenh_tonghop(text, bot_username=""):
    """True nếu text là /tonghop@<bot> — nhờ CẢ NHÓM báo cáo (mỗi máy tự trả lời).

    Giữ riêng khỏi `lenh_nao` để không đổi hợp đồng của hàm cũ (test cũ đang
    khẳng định lenh_nao('/bc') == 'bc').
    """
    t = (text or "").strip()
    if not t.startswith("/"):
        return False
    phan = t.split()[0][1:]
    if "@" in phan:
        ten, _, ai = phan.partition("@")
        if bot_username and ai.strip().lower() != bot_username.strip().lower():
            return False
        phan = ten
    return phan.strip().lower() in ("tonghop", "tổng hợp", "tong_hop")


def lenh_nao(text, bot_username=""):
    """Trả tên lệnh (không dấu /, không @bot) nếu text là lệnh gửi cho bot này."""
    t = (text or "").strip()
    if not t.startswith("/"):
        return ""
    phan = t.split()[0][1:]
    if not phan:
        return ""
    if "@" in phan:
        ten, _, ai = phan.partition("@")
        if bot_username and ai.strip().lower() != bot_username.strip().lower():
            return ""
        phan = ten
    return phan.strip().lower()


def kiem_tra_quyen(token, chat_ids):
    """Kiem tra bot co nhan duoc lenh TRAN (/baocao, /tonghop) trong tung nhom khong.

    Telegram chi giao lenh tran khi bot LA ADMIN nhom, hoac da TAT privacy mode.
    Bot thuong + privacy BAT => chi nhan dang /lenh@<bot_username>.

    Tra (danh_sach, privacy_off). Moi nhom:
        {"id","title","status","la_admin","doc_het","loi","bot_user"}
    """
    token = (token or "").strip()
    ds = []
    privacy_off = False
    bot_user = ""
    bot_id = 0
    if not token:
        return ds, privacy_off
    ok, me = get_me(token)
    if ok and isinstance(me, dict):
        privacy_off = bool(me.get("can_read_all_group_messages"))
        bot_user = str(me.get("username") or "")
        try:
            bot_id = int(me.get("id") or 0)
        except Exception:
            bot_id = 0
    for cid in (chat_ids or []):
        cid = str(cid or "").strip()
        if not cid:
            continue
        d = {"id": cid, "title": cid, "status": "", "la_admin": False,
             "doc_het": False, "loi": "", "bot_user": bot_user}
        okc, ch = goi(token, "getChat", {"chat_id": cid}, timeout=15)
        if okc and isinstance(ch, dict):
            d["title"] = str(ch.get("title") or ch.get("username") or cid)
        okm, cm = goi(token, "getChatMember",
                      {"chat_id": cid, "user_id": bot_id}, timeout=15)
        if okm and isinstance(cm, dict):
            d["status"] = str(cm.get("status") or "")
            d["la_admin"] = d["status"] in ("administrator", "creator")
        else:
            d["loi"] = str(cm if not isinstance(cm, dict)
                           else (cm.get("description") or cm))[:160]
        d["doc_het"] = bool(d["la_admin"] or privacy_off)
        ds.append(d)
    return ds, privacy_off


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


def nhan_tin(text, nhan=""):
    """Gan nhan bot len dau tin.

    Trong 1 nhom co nhieu bot cung chay LightVisual, tin bao cao phai noi ro
    cua bot nao. Khong co nhan -> tra nguyen van.
    """
    nhan = str(nhan or "").strip()
    if not nhan:
        return text
    return "<b>🏷 %s</b>\n%s" % (esc(nhan), text)


# ---------------------------------------------------------------- lớp báo cáo
class BaoCao(object):
    """Hàng đợi gửi Telegram chạy nền, chặn tần suất, gửi được nhiều nhóm."""

    def __init__(self, token="", chat_id="", moi_giay=300, log=None, chat_ids=None,
                 nhan=""):
        self.token = lay_token(token)
        self.nhan = str(nhan or "").strip()
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
        # PHẢI daemon: nếu không, khi đóng tool tiến trình Python vẫn chờ luồng này
        # gửi xong (mỗi lần gửi timeout 20s) -> cửa sổ đóng mà tool còn treo.
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = True
        self._t.start()
        return True

    def dung(self, cho=5.0):
        """Dừng luồng gửi; chờ tối đa `cho` giây để gửi nốt tin còn trong hàng đợi."""
        self._stop.set()
        t = self._t
        if t and t.is_alive():
            t.join(timeout=cho)

    def dung_nhanh(self):
        """Báo dừng nhưng KHÔNG chờ. Dùng khi đóng tool để GUI không đứng hình."""
        self._stop.set()

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
            text = nhan_tin(text, self.nhan)
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

    def __init__(self, token="", khi_lenh=None, log=None, timeout=25, khi_khac=None):
        self.token = lay_token(token)
        self.khi_lenh = khi_lenh
        self.khi_khac = khi_khac        # (chat_id, ten_nhom, ten_lenh) cho lệnh khác
        self.log = log or (lambda *a, **k: None)
        self.timeout = max(5, int(timeout))
        self.nhom = {}
        self.offset = 0
        self.bot_username = ""
        self.loi_cuoi = ""
        self.lan_cuoi_ok = 0.0      # moc lan cuoi getUpdates tra ve OK
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
        # đăng ký menu lệnh để gõ "/" trong nhóm là hiện sẵn để bấm
        ok_lenh, loi_lenh = dat_lenh(self.token)
        if not ok_lenh:
            self.log("Telegram: không đăng ký được menu lệnh — %s" % loi_lenh)
        self._t = threading.Thread(target=self._loop)
        self._t.daemon = True
        self._t.start()
        return True

    def dung_nhanh(self):
        """Báo dừng nhưng KHÔNG join — gọi trên luồng GUI lúc đóng tool.

        Long-poll getUpdates có thể đang giữ kết nối tới 40s; join trên luồng GUI
        sẽ làm cửa sổ đứng hình. Luồng là daemon nên tiến trình vẫn thoát được.
        """
        self._stop.set()

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
                    # 409 = có request getUpdates khác đang giữ kết nối (mở 2 cửa sổ
                    # tool, hoặc 1 lần gọi thử từ ngoài). PHẢI thử lại MÃI, tuyệt đối
                    # KHÔNG tắt luồng: tắt là bot im lặng vĩnh viễn cho tới khi anh
                    # đóng/mở lại tool — đúng lỗi "ấn /baocao không chạy".
                    cho = min(30.0, 3.0 * min(dem_loi, 10))
                    if dem_loi == 1 or dem_loi % 5 == 0:
                        self.log("Tele: tranh chấp getUpdates (409) lần %d — thử lại "
                                 "sau %.0fs (luồng vẫn sống)." % (dem_loi, cho))
                    self._stop.wait(cho)
                    continue
                if dem_loi == 1:
                    self.log("Tele: không đọc được lệnh trong nhóm — %s" % kq)
                # lỗi khác (mạng rớt, DNS, timeout...): nghỉ rồi thử lại, không bỏ
                if dem_loi >= 8:
                    self.log("Tele: lỗi liên tục %d lần — nghỉ 30s rồi thử lại."
                             % dem_loi)
                    self._stop.wait(30.0)
                    dem_loi = 0
                    continue
                self._stop.wait(min(30.0, 3.0 * dem_loi))
                continue
            dem_loi = 0
            self.lan_cuoi_ok = time.time()
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
                # /tonghop -> mọi bot trong nhóm cùng báo cáo (ai có mặt thì trả lời)
                if la_lenh_tonghop(txt, self.bot_username):
                    cid = str((c or {}).get("id") or "")
                    if cid and str((c or {}).get("type")) in LOAI_NHOM and self.khi_lenh:
                        try:
                            self.khi_lenh(cid, ten_nhom(c))
                        except Exception:
                            pass
                    continue
                lenh = lenh_nao(txt, self.bot_username)
                if not lenh:
                    continue
                cid = str((c or {}).get("id") or "")
                # chỉ nhận lệnh trong nhóm/kênh, bỏ qua chat riêng
                if not cid or str((c or {}).get("type")) not in LOAI_NHOM:
                    continue
                if lenh in ("baocao", "bc", "report"):
                    if self.khi_lenh:
                        try:
                            self.khi_lenh(cid, ten_nhom(c))
                        except Exception:
                            pass
                elif self.khi_khac:
                    try:
                        self.khi_khac(cid, ten_nhom(c), lenh)
                    except Exception:
                        pass
