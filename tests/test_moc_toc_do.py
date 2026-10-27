# -*- coding: utf-8 -*-
"""Test v1.0.19: bao cao dung MOC DONG HO (:00 / :30) + dong toc do
" - Da them 30 video trong 30p" + dinh dang tien do moi.

Khong gui gi len Telegram that: chi test ham thuan trong core/tele.py va
ham tinh toan cua App (khong khoi tao cua so).

Chay: python tests/test_moc_toc_do.py
"""
import os
import sys
import time

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

from core import tele  # noqa: E402

OK = [0]
LOI = [0]


def kiem(ten, dk, ct=""):
    if dk:
        OK[0] += 1
        print("PASS  %s" % ten)
    else:
        LOI[0] += 1
        print("FAIL  %s  %s" % (ten, ct))


def lt(h, m, s):
    return time.struct_time((2026, 10, 27, h, m, s, 1, 300, 0))


def main():
    print("\n== 1. giay_toi_moc — moc :00 va :30 ==")
    kiem("12:00:00 -> 1800s (moc :30)", tele.giay_toi_moc(30, lt(12, 0, 0)) == 1800,
         str(tele.giay_toi_moc(30, lt(12, 0, 0))))
    kiem("12:29:30 -> 30s", tele.giay_toi_moc(30, lt(12, 29, 30)) == 30,
         str(tele.giay_toi_moc(30, lt(12, 29, 30))))
    kiem("12:30:00 -> 1800s (moc :00)", tele.giay_toi_moc(30, lt(12, 30, 0)) == 1800,
         str(tele.giay_toi_moc(30, lt(12, 30, 0))))
    kiem("12:45:10 -> 890s", tele.giay_toi_moc(30, lt(12, 45, 10)) == 890,
         str(tele.giay_toi_moc(30, lt(12, 45, 10))))
    kiem("23:59:59 -> 1s", tele.giay_toi_moc(30, lt(23, 59, 59)) == 1,
         str(tele.giay_toi_moc(30, lt(23, 59, 59))))
    kiem("moc 60 -> chi :00", tele.giay_toi_moc(60, lt(12, 30, 0)) == 1800,
         str(tele.giay_toi_moc(60, lt(12, 30, 0))))
    kiem("moc 15 -> :00/:15/:30/:45", tele.giay_toi_moc(15, lt(12, 14, 0)) == 60,
         str(tele.giay_toi_moc(15, lt(12, 14, 0))))
    kiem("khong bao gio tra 0", tele.giay_toi_moc(30, lt(12, 30, 0)) > 0)
    kiem("luon <= buoc", tele.giay_toi_moc(30, lt(9, 7, 7)) <= 1800,
         str(tele.giay_toi_moc(30, lt(9, 7, 7))))
    kiem("gia tri rac -> 30 phut", tele.giay_toi_moc("xx", lt(12, 0, 0)) == 1800,
         str(tele.giay_toi_moc("xx", lt(12, 0, 0))))

    print("\n== 2. dinh_dang_phut — cau 'trong 30p' ==")
    kiem("45s", tele.dinh_dang_phut(45) == "45s", tele.dinh_dang_phut(45))
    kiem("59s", tele.dinh_dang_phut(59) == "59s", tele.dinh_dang_phut(59))
    kiem("60s -> 1p", tele.dinh_dang_phut(60) == "1p", tele.dinh_dang_phut(60))
    kiem("1800s -> 30p", tele.dinh_dang_phut(1800) == "30p", tele.dinh_dang_phut(1800))
    kiem("1790s -> 30p (lam tron)", tele.dinh_dang_phut(1790) == "30p",
         tele.dinh_dang_phut(1790))
    kiem("5460s -> 1h31p", tele.dinh_dang_phut(5460) == "1h31p",
         tele.dinh_dang_phut(5460))
    kiem("am -> 0s", tele.dinh_dang_phut(-5) == "0s", tele.dinh_dang_phut(-5))

    print("\n== 3. thanh_tien_do — 10 o ==")
    kiem("0/10 -> 10 o trang", tele.thanh_tien_do(
        {"ok": 0, "loi": 0, "dung": 0, "tong": 10}) == "▱" * 10,
        tele.thanh_tien_do({"ok": 0, "loi": 0, "dung": 0, "tong": 10}))
    kiem("5/10 -> 5 day 5 trang", tele.thanh_tien_do(
        {"ok": 5, "loi": 0, "dung": 0, "tong": 10}) == "▰" * 5 + "▱" * 5,
        tele.thanh_tien_do({"ok": 5, "loi": 0, "dung": 0, "tong": 10}))
    kiem("10/10 -> day", tele.thanh_tien_do(
        {"ok": 10, "loi": 0, "dung": 0, "tong": 10}) == "▰" * 10,
        tele.thanh_tien_do({"ok": 10, "loi": 0, "dung": 0, "tong": 10}))
    kiem("137/240 -> 6 o", tele.thanh_tien_do(
        {"ok": 133, "loi": 4, "dung": 0, "tong": 240}).count("▰") == 6,
        tele.thanh_tien_do({"ok": 133, "loi": 4, "dung": 0, "tong": 240}))
    kiem("luon du 10 o", all(
        len(tele.thanh_tien_do({"ok": i, "loi": 0, "dung": 0, "tong": 7})) == 10
        for i in range(0, 8)))
    kiem("tong 0 khong chia 0", len(tele.thanh_tien_do(
        {"ok": 0, "loi": 0, "dung": 0, "tong": 0})) == 10)

    print("\n== 4. toc do truot — ham cua App (khong mo cua so) ==")
    import main as T
    app = T.App.__new__(T.App)
    import threading
    app._dem_lock = threading.Lock()
    app._moc_dem_lock = threading.Lock()
    app.cfg = {"tele_moi_phut": 30}
    app._lan_chay = {"loai": "video"}
    now = time.time()
    app._dem = {"ok": 30, "loi": 0, "dung": 0, "tong": 240}
    # moc 30 phut truoc: 0 viec -> 30 viec trong 30p
    app._moc_dem = [(now - 1800, 0), (now - 900, 15), (now, 30)]
    them, giay = app._toc_do_truot(1800)
    kiem("toc do: 30 viec / 1800s", them == 30 and abs(giay - 1800) < 2,
         "them=%s giay=%.0f" % (them, giay))
    kiem("dong toc do dung cau",
         app._dong_toc_do("video") == " - Đã thêm 30 video trong 30p",
         app._dong_toc_do("video"))
    app._lan_chay = {"loai": "anh"}
    kiem("don vi anh", app._dong_toc_do(app._don_vi()) == " - Đã thêm 30 ảnh trong 30p",
         app._dong_toc_do(app._don_vi()))
    app._lan_chay = {"loai": "video"}

    # chua du 30s du lieu -> khong in dong toc do
    app._moc_dem = [(time.time() - 5, 28)]
    kiem("chua du du lieu -> rong", app._dong_toc_do("video") == "",
         app._dong_toc_do("video"))

    # khong co viec moi trong cua so -> rong (khong in "0 video")
    app._moc_dem = [(time.time() - 1800, 30)]
    kiem("khong them duoc viec nao -> rong", app._dong_toc_do("video") == "",
         app._dong_toc_do("video"))

    # moc dem ghi lai dung so viec
    app._moc_dem = []
    app._dem = {"ok": 3, "loi": 1, "dung": 0, "tong": 10}
    app._moc_ghi()
    kiem("_moc_ghi ghi (thoi diem, so viec)",
         len(app._moc_dem) == 1 and app._moc_dem[0][1] == 4,
         str(app._moc_dem))

    # cat bot moc cu hon 2 gio
    app._moc_dem = [(time.time() - 8000, 0), (time.time() - 10, 5)]
    app._moc_ghi(6)
    kiem("cat moc cu hon 2 gio", all(time.time() - t < 7300 for t, x in app._moc_dem),
         str(app._moc_dem))

    print("\n== 5. noi dung bao cao day du (dang chay) ==")
    app.dang_chay = True
    app._t0 = time.time() - 5460          # 1h31p
    app._dem = {"ok": 133, "loi": 4, "dung": 0, "tong": 240}
    app._moc_dem = [(time.time() - 1800, 103), (time.time(), 137)]
    txt = app._soan_bao_cao()
    dong = txt.split("\n")
    kiem("co 5 dong", len(dong) == 5, str(len(dong)) + " | " + txt)
    kiem("dong 1 tieu de", dong[0] == "<b>📊 Báo cáo theo yêu cầu</b>", dong[0])
    kiem("dong 2 thanh + so + toc do",
         dong[1].startswith("▰▰▰▰▰▰▱▱▱▱  137/240") and "Đã thêm 34 video trong 30p" in dong[1],
         dong[1])
    kiem("dong 3 OK/Loi/Dung",
         dong[2] == "✅ OK 133   ❌ Lỗi 4   ⏸️ Dừng 0", dong[2])
    kiem("dong 4 da chay + con lai", dong[3].startswith("⏱️ Đã chạy 1h31p · còn khoảng"),
         dong[3])
    kiem("dong 5 toc do trung binh", dong[4].startswith("⚡️ ") and dong[4].endswith("s/việc"),
         dong[4])
    print("\n--- tin that se gui ---\n" + txt + "\n-----------------------")

    print("\nKET QUA: PASS %d | FAIL %d" % (OK[0], LOI[0]))
    return 0 if LOI[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
