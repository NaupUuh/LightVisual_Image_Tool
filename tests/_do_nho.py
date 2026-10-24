# -*- coding: utf-8 -*-
"""Do that: o kich thuoc nho nhat, thanh day + form tab video co bi cat khong."""
import os
import sys
import json

GOC = r"C:\Users\Admin\Desktop\LightVisual_Image_Tool"
sys.path.insert(0, GOC)
os.chdir(GOC)

import main as T

CFG = os.path.join(GOC, "tests", "_cfg_do.json")
with open(CFG, "w", encoding="utf-8") as f:
    json.dump({"api_key": "LV_x", "thu_muc_ra": os.path.join(GOC, "tests", "_tmp_do"),
               "plan": "grok-unlimited"}, f)
T.CFG_FILE = CFG

app = T.App()
app.geometry("1040x640")
app.update()
app.nb.select(1)
app.update()
app.update_idletasks()

print("geometry:", app.geometry())
print("min:", app.minsize())

# thanh day
day = app.btn_chay.master
print("thanh day: mapped=%s h=%d y=%d" % (day.winfo_ismapped(), day.winfo_height(),
                                          day.winfo_rooty() - app.winfo_rooty()))
for w, ten in ((app.btn_chay, "CHAY"), (app.btn_dung, "Dung"),
               (app.btn_tiep, "Tiep tuc"), (app.btn_nap, "Nap lai")):
    print("  nut %-9s mapped=%s w=%d h=%d" % (ten, w.winfo_ismapped(),
                                              w.winfo_width(), w.winfo_height()))

# cac widget trong tab video
f = app.tab_video
con = []


def quet(w, sau=""):
    for c in w.winfo_children():
        con.append((c, sau + "/" + c.winfo_class()))
        quet(c, sau + "/" + c.winfo_class())


quet(f)
cao_tab = f.winfo_height()
print("\ntab video cao:", cao_tab)
cat = []
for w, ten in con:
    try:
        if not w.winfo_ismapped():
            continue
        y = w.winfo_rooty() - f.winfo_rooty()
        h = w.winfo_height()
        if y + h > cao_tab + 1:
            cat.append((ten, w.winfo_class(), y, h, y + h - cao_tab))
    except Exception:
        pass
print("widget bi tran khoi tab:", len(cat))
for c in cat[:15]:
    print("  ", c)

# kiem tra panel phai hien du
p = app.cb_vmodel.master
print("\npanel phai: h=%d  (can %d)" % (p.winfo_height(), p.winfo_reqheight()))
for w, ten in ((app.sp_vmoi, "Video moi prompt"), (app.txt_mc, "Khung MC"),
               (app.lbl_phi_video, "Dong phi")):
    y = w.winfo_rooty() - app.winfo_rooty()
    print("  %-16s mapped=%s y=%d h=%d bottom=%d / cua so %d" %
          (ten, w.winfo_ismapped(), y, w.winfo_height(), y + w.winfo_height(),
           app.winfo_height()))

app.destroy()
try:
    os.remove(CFG)
except Exception:
    pass
