# -*- coding: utf-8 -*-
"""Test: nhom Telegram nang cap len supergroup -> tool tu doi chat_id.

Chay: python tests/test_migrate.py
"""
import io
import json
import os
import sys
import urllib.error

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

from core import tele  # noqa: E402

PASS = [0]
FAIL = [0]


def kiem(ten, dieu):
    if dieu:
        PASS[0] += 1
        print("PASS  %s" % ten)
    else:
        FAIL[0] += 1
        print("FAIL  %s" % ten)


class FakeResp(object):
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_loi(ma, payload):
    return urllib.error.HTTPError(
        "https://x", ma, "Bad Request", {},
        io.BytesIO(json.dumps(payload).encode("utf-8")))


# ---------------------------------------------------------------- 1. helper
d = {"ok": False, "error_code": 400,
     "description": "Bad Request: group chat was upgraded to a supergroup chat",
     "parameters": {"migrate_to_chat_id": -1004471871974}}
kiem("_migrate_tu lay dung id moi",
     tele._migrate_tu(d) == "-1004471871974")
kiem("_migrate_tu rong khi khong co parameters", tele._migrate_tu({}) == "")
kiem("_migrate_tu rong khi parameters None",
     tele._migrate_tu({"parameters": None}) == "")

# ---------------------------------------------------------------- 2. mo ta loi
mo = tele._mo_ta_loi(400, d)
kiem("mo ta loi co id moi", "-1004471871974" in mo)
kiem("mo ta loi noi ro tu chuyen", "tự chuyển" in mo)
mo2 = tele._mo_ta_loi(400, {"description":
                            "Bad Request: group chat was upgraded to a supergroup chat"})
kiem("mo ta loi khong co id van de doc", "supergroup" in mo2)

# ---------------------------------------------------------------- 3. gui tu thu lai
goi_da = []
loi_lan = {"n": 0}


def urlopen_gia(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    body = req.data or b""
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    goi_da.append(body)
    if "-5593791314" in body:
        loi_lan["n"] += 1
        raise http_loi(400, d)
    return FakeResp({"ok": True, "result": {"message_id": 7}})


cu = urllib.request.urlopen
urllib.request.urlopen = urlopen_gia
try:
    tele._MIGRATE.clear()
    ok, loi = tele.gui("123456:AAA", "-5593791314", "xin chao")
    kiem("gui tu thu lai thanh cong", ok is True and loi == "")
    kiem("goi 2 lan (id cu roi id moi)", len(goi_da) == 2)
    kiem("lan 2 dung id moi", "-1004471871974" in goi_da[-1])
    kiem("_MIGRATE ghi cap id", tele.lay_migrate().get("-5593791314")
         == "-1004471871974")

    # id moi cung loi -> khong lap vo han
    goi_da[:] = []

    def luon_loi(req, timeout=None):
        body = (req.data or b"").decode("utf-8", "replace")
        goi_da.append(body)
        raise http_loi(400, d)

    urllib.request.urlopen = luon_loi
    tele._MIGRATE.clear()
    ok, loi = tele.gui("123456:AAA", "-5593791314", "x")
    kiem("id moi cung loi -> tra False", ok is False)
    kiem("chi goi 2 lan, khong lap vo han", len(goi_da) == 2)
    kiem("loi co nhac supergroup", "supergroup" in loi)
finally:
    urllib.request.urlopen = cu

# ---------------------------------------------------------------- 4. goi() ghi migrate
goi_da[:] = []


def urlopen_goi(req, timeout=None):
    body = (req.data or b"").decode("utf-8", "replace")
    goi_da.append(body)
    raise http_loi(400, d)


cu = urllib.request.urlopen
urllib.request.urlopen = urlopen_goi
try:
    tele._MIGRATE.clear()
    ok, loi = tele.goi("123456:AAA", "sendMessage", {"chat_id": "-5593791314",
                                                     "text": "hi"})
    kiem("goi() tra False", ok is False)
    kiem("goi() ghi _MIGRATE", tele.lay_migrate().get("-5593791314")
         == "-1004471871974")
finally:
    urllib.request.urlopen = cu

# ---------------------------------------------------------------- 5. _dong_bo_migrate
sys.path.insert(0, GOC)


class AppGia(object):
    """Chi mo phong phan _dong_bo_migrate can."""

    def __init__(self):
        self.cfg = {"tele_chat_ids": ["-5593791314", "-999"],
                    "tele_chat_id": "-5593791314",
                    "tele_nhom_ten": {"-5593791314": "Test"}}
        self.da_luu = []
        self.log = []
        self.label = 0

    def _log(self, s):
        self.log.append(s)

    def _cap_nhat_tele_label(self):
        self.label += 1


import main as M  # noqa: E402

# gan nguyen ham cua class App vao object gia
AppGia._dong_bo_migrate = M.App._dong_bo_migrate

cu_luu = M.luu_cfg
_da_luu = []
M.luu_cfg = lambda c: _da_luu.append(dict(c))
try:
    tele._MIGRATE.clear()
    tele._MIGRATE["-5593791314"] = "-1004471871974"
    a = AppGia()
    a._dong_bo_migrate()
    kiem("thay id cu bang id moi trong tele_chat_ids",
         a.cfg["tele_chat_ids"] == ["-1004471871974", "-999"])
    kiem("cap nhat tele_chat_id", a.cfg["tele_chat_id"] == "-1004471871974")
    kiem("doi khoa tele_nhom_ten",
         a.cfg["tele_nhom_ten"] == {"-1004471871974": "Test"})
    kiem("co ghi config.json", len(_da_luu) == 1)
    kiem("co log thong bao", any("supergroup" in s for s in a.log))

    # chay lai lan 2 -> khong ghi lai
    _da_luu[:] = []
    a._dong_bo_migrate()
    kiem("lan 2 khong ghi lai config", len(_da_luu) == 0)

    # khong co migrate -> khong lam gi
    tele._MIGRATE.clear()
    _da_luu[:] = []
    b = AppGia()
    b._dong_bo_migrate()
    kiem("khong co migrate -> khong ghi", len(_da_luu) == 0)
    kiem("khong co migrate -> giu id cu",
         b.cfg["tele_chat_ids"] == ["-5593791314", "-999"])
finally:
    M.luu_cfg = cu_luu
    tele._MIGRATE.clear()

# ---------------------------------------------------------------- ket qua
print("\nKET QUA: PASS %d | FAIL %d" % (PASS[0], FAIL[0]))
sys.exit(1 if FAIL[0] else 0)
