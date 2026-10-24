# -*- coding: utf-8 -*-
"""Kiem tra hop thoai nhieu API key (mo/dong, doc dong trong, bo comment, trung lap)."""
import json
import os
import sys

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
import main as T

T.CFG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cfg_keydlg.json")
with open(T.CFG_FILE, "w", encoding="utf-8") as f:
    json.dump({"api_key": "k1", "api_keys": ["k1", "k2"]}, f)

app = T.App()
for _ in range(20):
    app.update()

ok = loi = 0


def kiem(ten, dk, ct=""):
    global ok, loi
    if dk:
        ok += 1
        print("PASS  %s" % ten)
    else:
        loi += 1
        print("FAIL  %s  %s" % (ten, ct))


kiem("nut API key ton tai", app.lbl_plan.cget("text").find("2 key") >= 0,
     app.lbl_plan.cget("text"))

app._doi_key()
for _ in range(10):
    app.update()
w, lbl, txt = app._hop_key
kiem("hop thoai mo", w.winfo_exists() == 1)
noi_dung = txt.get("1.0", "end").strip().splitlines()
kiem("nap san 2 key", noi_dung == ["k1", "k2"], str(noi_dung))

# nhap lai: co comment, dong trong, trung lap
txt.delete("1.0", "end")
txt.insert("1.0", "# ghi chu\nkA\n\n  kB  \nkA\n")
w.update()
app._doi_key.__self__  # noop
# bam Luu qua nut that
nut = [c for c in w.winfo_children() if c.winfo_class() == "TFrame"]
def tim_luu(wg):
    for c in wg.winfo_children():
        if c.winfo_class() == "TButton" and c.cget("text") == "Lưu":
            return c
        r = tim_luu(c)
        if r:
            return r
    return None
b = tim_luu(w)
b.invoke()
for _ in range(10):
    app.update()
kiem("luu: bo comment/dong trong/trung lap", app.cfg["api_keys"] == ["kA", "kB"],
     str(app.cfg["api_keys"]))
kiem("api_key = key dau", app.cfg["api_key"] == "kA", app.cfg["api_key"])
kiem("label cap nhat 2 key", "2 key" in app.lbl_plan.cget("text"), app.lbl_plan.cget("text"))
cfg = json.load(open(T.CFG_FILE, encoding="utf-8"))
kiem("ghi ra file config", cfg.get("api_keys") == ["kA", "kB"], str(cfg.get("api_keys")))

app._thoat_app()
os.remove(T.CFG_FILE)
print("\nKET QUA: PASS %d | FAIL %d" % (ok, loi))
sys.exit(0 if loi == 0 else 1)
