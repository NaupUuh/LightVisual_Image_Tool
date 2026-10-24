# -*- coding: utf-8 -*-
"""Đo thật: nút 'Cập nhật' có hiện trên GUI và luồng kiểm tra chạy được."""
import os
import sys
import tempfile
import time

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
os.chdir(GOC)

import tkinter as tk
import main as T

tmp = tempfile.mkdtemp(prefix="lv_upd_gui_")
T.CFG_FILE = os.path.join(tmp, "config.json")

root = tk.Tk()
app = T.App()
root.update()

b = app.upd_btn
print("nut Cap nhat: text=%r mapped=%s state=%s w=%d h=%d x=%d y=%d" % (
    b.cget("text"), b.winfo_ismapped(), str(b.cget("state")),
    b.winfo_width(), b.winfo_height(), b.winfo_rootx(), b.winfo_rooty()))

# bấm nút thật (không có bản mới) -> phải trả về "bản mới nhất"
b.invoke()
t0 = time.time()
while time.time() - t0 < 25:
    root.update()
    time.sleep(0.05)
    if str(b.cget("state")) == "normal" and "Đang kiểm tra" not in b.cget("text"):
        break

print("sau khi bam: text=%r state=%s" % (b.cget("text"), str(b.cget("state"))))
log = app.txt_log.get("1.0", "end") if hasattr(app, "txt_log") else ""
tail = [l for l in log.strip().splitlines() if l.strip()][-4:]
for l in tail:
    print("LOG:", l)

ok = (b.winfo_ismapped() and b.winfo_height() > 10
      and "mới nhất" in log)
print("KET QUA:", "PASS" if ok else "FAIL")
root.destroy()
sys.exit(0 if ok else 1)
