# -*- coding: utf-8 -*-
"""Đo thật tab video sau khi thêm khung folder ảnh tham chiếu."""
import os
import sys
import tempfile

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
os.chdir(GOC)

import tkinter as tk
import main as T

tmp = tempfile.mkdtemp(prefix="lv_do_tc_")
T.CFG_FILE = os.path.join(tmp, "config.json")

root = tk.Tk()
root.withdraw()
app = T.App()
root.deiconify()
root.geometry("1040x640")
root.update()
app.nb.select(1)
root.update()
root.update_idletasks()

f = app.tab_video
print("tab video: w=%d h=%d reqh=%d" % (f.winfo_width(), f.winfo_height(), f.winfo_reqheight()))
for w in f.winfo_children():
    if w.winfo_ismapped():
        print("  %-22s y=%4d h=%4d w=%4d  %s" % (
            w.winfo_name(), w.winfo_y(), w.winfo_height(), w.winfo_width(),
            (w.cget("text")[:38] if "text" in w.keys() else "")))
print("entry tham chieu: mapped=%s w=%d h=%d y=%d" % (
    app.e_thamchieu.winfo_ismapped(), app.e_thamchieu.winfo_width(),
    app.e_thamchieu.winfo_height(), app.e_thamchieu.winfo_rooty()))
print("lbl_tc: %r" % app.lbl_tc.cget("text"))
print("panel phai: h=%d" % [w for w in f.winfo_children()
                            if w.winfo_name() == "!frame"][0].winfo_height())

# tab video có nằm gọn trong notebook không
nb = app.nb
print("notebook: h=%d  tab video h=%d" % (nb.winfo_height(), f.winfo_height()))
ok = (app.e_thamchieu.winfo_ismapped() and app.e_thamchieu.winfo_height() > 12
      and f.winfo_reqheight() <= f.winfo_height() + 2)
print("KET QUA:", "PASS" if ok else "FAIL")
root.destroy()
sys.exit(0 if ok else 1)
