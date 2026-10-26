# TIẾP TỤC — LightVisual Image Tool

Cập nhật: 2026-10-26 · **v1.0.8** · trạng thái: chạy thật OK với key thật (gói Grok Vô Hạn 1 ngày)

## 1. Tool này làm gì
Tạo ảnh hàng loạt qua API lightvisual.studio (`POST /v1/images/generations`),
sửa ảnh / giữ nhân vật qua `POST /v1/images/edits`,
và tạo **video** qua `POST /v1/videos` (Grok Imagine Video 1.5).
Gói **Grok Vô Hạn** → ảnh Grok tính **0đ**, kể cả ảnh gửi kèm.

## 2. Trạng thái code
- `main.py` — GUI Tkinter 4 tab, chạy được Python 3.9+.
- `core/api.py` — client thuần stdlib (`urllib`), không cần pip.
- `run.bat` — chạy ẩn qua VBS; `run.bat debug` để thấy lỗi.
- `config.json` — lưu key thật + gói. **Không commit, không chia sẻ.**
- `tiep_tuc.json` — trạng thái lượt chạy dở (tự sinh, đừng commit).
- `output/` — thư mục ra mặc định.

## 3. Tab video (v1.0.2 → v1.0.5)
- 3 nguồn vào: **chỉ prompt (T2V)** / **ảnh khung (I2V)** / **prompt ảnh → ảnh → video**.
- Bỏ hẳn "Số lượng" ở tab video — số luồng tự suy từ **số API key** (1 key = 1 luồng).
- **Video mỗi prompt** (1–50): 1 prompt × N = N video.
- **Ngoại hình MC**: mỗi dòng 1 ngoại hình, random **không lặp trong 1 vòng**, nối vào **TRƯỚC** prompt bằng `", "`.
  Ví dụ prompt `9:16 vertical video, no logos. …` → `22-year-old white female MC, 9:16 vertical video, no logos. …`
  1 prompt + 30 dòng MC + Video mỗi prompt 30 → 30 video với 30 MC khác nhau.
- **Dừng / Tiếp tục / Nạp lại**: mỗi lượt dùng queue riêng nên luồng của lượt cũ không giành mất việc của lượt mới;
  việc bị cắt giữa chừng được chạy lại, việc đã OK thì giữ nguyên (`tiep_tuc.json`).
- "Mở folder khi chạy xong" mặc định **TẮT** (cả tab ảnh và tab video).

## 4. Đã kiểm chứng (chạy thật, không phải suy đoán)

### 4a. Test tự động (máy chủ giả, 0đ) — cập nhật v1.0.7
| Test | Kết quả |
|---|---|
| `tests/test_mock.py` | **19/0 PASS** |
| `tests/test_gui.py` | **90/0 PASS** |
| `tests/test_key_dialog.py` | **7/0 PASS** |
| `tests/test_tele.py` | **26/0 PASS** (máy chủ Telegram giả, 0 tin thật) |
| `tests/test_tele_gui.py` | **9/0 PASS** (GUI thật → bắt đầu/tiến độ/kết thúc đều bắn tin) |
| `tests/_test_update_btn.py` | **PASS** (nút Cập nhật hiện, bấm chạy được) |
| `tests/_do_tab_tc.py` | **PASS** (tab video không cắt khung tham chiếu ở 1040x640) |
| `py_compile` main.py + core/api.py + updater.py | OK (3.14.2 + 3.13) |

Test cho "1 folder ảnh = 1 prompt" (v1.0.7) nằm trong `tests/test_gui.py`:
`prompt.txt: tách đúng 2 folder`, `... đọc đúng prompt từng folder`, `... nhãn hiện số folder + số ảnh`,
`... ra đúng 2 thư mục`, `... tên thư mục ra = tên folder vào`, `... số video khớp số ảnh từng folder`,
`... mỗi folder dùng đúng prompt của mình`, `... ảnh đã dùng bị xoá khỏi folder con`,
`thiếu prompt.txt: vẫn nhận folder / nhãn báo thiếu prompt / dùng prompt dự phòng`,
`không prompt nào: cảnh báo, không chạy`, `ghi prompt.txt: 2 file được tạo / nội dung theo thứ tự folder`.

### 4b. Test với key thật + gói `grok-unlimited-d1-s1`
| Việc | Kết quả đo được |
|---|---|
| `GET /v1/balance` | `credits 0`, plan `grok-unlimited-d1-s1`, tên "Grok Vô Hạn 1 ngày" |
| Tạo 3 ảnh Grok 2.0 | **12,8 s**, 1024×1024 JPEG ~168 KB/ảnh, credits vẫn 0 |
| Sửa ảnh (1 ảnh gửi kèm, tag `<IMAGE_0>`) | **10,7 s**, nội dung đổi đúng, credits 0 |
| Tạo video T2V (1 s / 480p) | job `lv_job_75b5a33…`, xong ~**22 s**, MP4 285 KB, `mvhd dur 1042 → 1.04 s`, `avc1 @24` |
| Xoay key (1 key hỏng 401 + 1 key thật) | tự loại key hỏng, chuyển key sống, không dừng lô |

## 5. Nút "⬆ Cập nhật" (v1.0.3)
Góc phải trên, cạnh nút `API key`. Máy nào cũng chỉ cần bấm 1 lần:
1. Kiểm tra `version.json` trên GitHub (qua API, không bị CDN cache) → so với `APP_VERSION`.
2. Có bản mới → hỏi, rồi tải zip nhánh `master` và ghi đè mã nguồn.
3. Tự khởi động lại tool.
- **Giữ nguyên**: `config.json` (API key + cài đặt), `tiep_tuc.json`, `output/`.
- Bản cũ sao lưu vào `_backup_update/<timestamp>/` (khôi phục bằng `updater.rollback()`).
- Chạy tay: `python updater.py` (chỉ kiểm tra) · `python updater.py --apply` (cập nhật).
- `cacert.pem` đóng gói kèm để máy thiếu chứng chỉ CA vẫn gọi HTTPS được.

## 5b. Folder ảnh tham chiếu (v1.0.4 → mở rộng ở v1.0.7)
Nguồn thứ 4 trong "Nguồn cảnh đầu": **Folder ảnh tham chiếu → video**.
- Chọn **folder gốc**; tool quét các **folder con**, mỗi folder con là **1 đơn vị công việc**.
- **Mỗi folder con mang prompt riêng** trong file `prompt.txt` (cũng nhận `prompt.md`, `_prompt.txt`, `prompt`).
  Đọc cả file, bỏ dòng trắng và dòng bắt đầu bằng `#`.
- Mỗi ảnh trong folder con = **đúng 1 video** (không nhân `Video mỗi prompt`), dùng prompt của folder đó.
- Ảnh dùng làm khung đầu (I2V), **dùng xong bị xoá khỏi folder**; folder hết ảnh thì dừng riêng folder đó,
  các folder khác vẫn chạy tiếp. Ô tích **"Xoá ảnh sau khi dùng"** mặc định BẬT.
- **Thư mục ra đặt theo tên folder ảnh đầu vào**: `output/<NN>_<tên folder vào>/`. Chạy lại cùng folder
  → dùng lại đúng thư mục đó (không tạo trùng).
- **Folder thiếu `prompt.txt`** → lấy prompt theo **thứ tự** từ ô "2. PROMPT VIDEO" (không bị chặn);
  nhãn sẽ báo `· N folder thiếu prompt.txt`. Nếu **không có prompt nào cả** → cảnh báo rồi dừng.
- Nút **"Ghi prompt.txt"**: lấy danh sách prompt trên ô PROMPT VIDEO ghi lần lượt vào từng folder con
  (bỏ qua folder đã có file) → khỏi tạo file bằng tay cho hàng chục folder.
- Nhãn cạnh ô nhập: `<N> folder · <M> ảnh` (1 folder thì hiện `còn M ảnh`).
- MC vẫn nối trước prompt của folder như cũ.
- Nếu ảnh bị xoá/mất giữa lúc chạy → job đó báo LỖI "Không thấy ảnh khung", các job khác chạy tiếp.
- "Nạp lại" lượt cũ có ảnh tham chiếu đã xoá → báo rõ, không chạy lại được (đúng thiết kế).

### Lỗi đã sửa ở v1.0.7 (2026-10-25)
Trước v1.0.7, nguồn tham chiếu chỉ có **1 folder** và prompt **xoay vòng** theo số ảnh
(`ds_pv[(stt-1) % len(ds_pv)]`) → 10 ảnh + 2 prompt thì ảnh 1 dùng P1, ảnh 2 dùng P2, ảnh 3 lại P1…
không gán được prompt theo từng nhóm ảnh. Nay đổi sang: **1 folder con = 1 prompt**, thư mục ra theo
tên folder vào. Code cũ (1 folder ảnh nằm trực tiếp trong folder gốc, không có folder con) vẫn chạy được
như trước — lúc đó đơn vị duy nhất chính là folder gốc.


## 5c. Thư mục con theo prompt (v1.0.5 → sửa lỗi ở v1.0.6)
Khi tab video có **nhiều hơn 1 prompt** (sau khi đã nối MC), tool tự tạo thư mục con
trong thư mục ra và dồn video của từng prompt vào đó:
```
output/01_<tu dau cua prompt>_<hash6>/001_...mp4
output/02_<tu dau cua prompt>_<hash6>/...
```
- Tên thư mục = `_ten_thu_muc(prompt)`:
  - phần chữ: các **từ đầu** của `ten_an_toan(prompt, 400)`, cắt theo ranh giới từ, tối đa 48 ký tự;
  - phần đuôi: **6 ký tự sha1 của prompt ĐẦY ĐỦ** → 2 prompt khác nhau **luôn** ra 2 thư mục khác nhau.
- **Chạy lại cùng prompt** → dùng lại đúng thư mục cũ (so khớp hash 6 ký tự ở đuôi tên).
- Số thư mục = số **kế tiếp** của dãy hiện có (không trùng số kể cả khi chèn prompt mới vào giữa).
- **Chỉ 1 prompt thì giữ nguyên như cũ** — video nằm thẳng trong thư mục ra, không tạo
  thư mục con.
- Ảnh khung tạo từ prompt ảnh (`_khung/`) cũng nằm trong thư mục của prompt đó.
- Danh sách thư mục được in ra log ngay khi bắt đầu chạy.

### Lỗi đã sửa ở v1.0.6 (2026-10-25)
**Triệu chứng**: nhiều prompt khác nhau nhưng video bị dồn chung 1 thư mục con
(vd `01_photorealistic_vertical_breaking_news_br/` chứa cả prompt "story one" lẫn "story two").

**Nguyên nhân**: `_tao_thu_muc_prompt()` gọi `ten_an_toan(prompt, 40)` → tên thư mục chỉ còn
40 ký tự đầu. Các prompt tin tức dùng chung phần mở ("photorealistic vertical breaking news
broadcast studio…") nên 40 ký tự đầu giống nhau → bị coi là cùng 1 prompt, gộp chung thư mục.
Test cũ chỉ đếm **tổng số MP4** nên không bắt được.

**Cách sửa**: thêm `_ten_thu_muc()` cắt theo **từ** + gắn hash 6 ký tự của prompt đầy đủ;
`_tao_thu_muc_prompt()` so khớp theo hash và cấp số kế tiếp của dãy.

**Cách kiểm tra**: `python tests/test_gui.py` → 71 PASS / 0 FAIL, trong đó 3 test mới:
`40 ký tự giống nhau: 2 prompt ra 2 thư mục`, `... chạy lại đúng prompt cũ → đúng thư mục cũ`,
`... tên thư mục có mã băm phân biệt`.

**Điều tránh**: đừng cắt tên thư mục theo **số ký tự** của prompt; luôn có thành phần phân biệt
lấy từ toàn bộ nội dung (hash). Đừng assert test bằng tổng số file — phải assert **file nào nằm
trong thư mục nào**.

## 5d. Báo cáo tiến độ lên Telegram (v1.0.8)
Nút **📣 Telegram** ở góc phải trên, cạnh `API key`. Mở hộp thoại:
- **Bật báo cáo Telegram** — mặc định TẮT.
- **Bot token** — để trống thì tool tự đọc `TELEGRAM_BOT_TOKEN` trong `.env` của Hermes.
- **Chat ID** — chat nhận tin (user: `8446833069`).
- **Gửi tiến độ mỗi (phút)** — 1…60, mặc định 5.
- Nút **Gửi thử** kiểm tra token/chat ngay, **Lưu** ghi vào `config.json`.

3 loại tin được gửi:
1. **BẮT ĐẦU** — loại việc, model, tổng số việc (kèm số đã xong trước đó), số luồng, thư mục ra.
2. **TIẾN ĐỘ** — mỗi N phút: thanh tiến độ, `OK/Lỗi/Dừng`, đã chạy, còn khoảng bao lâu, giây/việc.
3. **KẾT THÚC** — tổng kết + đường dẫn thư mục ra; nếu còn việc thì nhắc bấm "Tiếp tục".
   Bấm **DỪNG** cũng gửi 1 tin báo ngay.

Ghi chú kỹ thuật:
- `core/tele.py` — thuần stdlib (`urllib`), không cần pip; chạy được Python 3.9+.
- Luồng gửi là **thread riêng có hàng đợi**, nên gọi mạng không làm treo GUI; khi app đóng vẫn gửi nốt tin kết thúc.
- **Token luôn bị che** trong log (`123456789:…`), không ghi vào log hay file.
- Mạng lỗi / token sai → chỉ ghi log, **không ảnh hưởng lượt chạy**.
- Token lưu trong `config.json` (đã nằm trong `.gitignore`).

## 6. Việc còn lại
1. Gói hiện tại chỉ **1 ngày / 1 luồng** → muốn nhiều luồng song song thật thì nâng gói hoặc thêm nhiều key.
2. Bắn 2 job video liên tiếp trên gói 1 luồng dễ gặp `"Model đang bị giới hạn tốc độ"` — chờ vài giây rồi chạy lại.
3. Gói hết hạn thì `/v1/balance` vẫn trả 200 nhưng sẽ bị trừ credit — kiểm tra số dư định kỳ.
4. Chưa test video 15 s / 1080p thật (tốn credit); preset đã set sẵn 15 s / 1080p / 9:16 / 4 video mỗi prompt.
5. Chưa chạy thật "1 folder ảnh = 1 prompt" với ảnh thật (test mới chỉ dùng máy chủ giả) — anh chạy
   thử 1 folder nhỏ (2–3 ảnh) rồi xem lại tên thư mục ra có đúng tên folder vào không.
6. `output/` còn 2 thư mục cũ (`01_photorealistic_vertical_breaking_news_br`,
   `02_9_16_vertical_no_logos_photorealistic_tv`) bị **gộp sai prompt** từ trước bản 1.0.6 — dữ liệu
   lịch sử, chưa dọn; code mới không ghi vào 2 thư mục đó nữa.


## 7. Lệnh hay dùng
```
cd C:\Users\Admin\Desktop\LightVisual_Image_Tool
run.bat                       :: chạy ẩn
run.bat debug                 :: chạy có cửa sổ cmd
python tests\test_mock.py     :: test API (0đ)
python tests\test_gui.py      :: test GUI + chạy thử
python tests\test_key_dialog.py
```

## 8. Bản sao lưu
- `Z:\HQData-2\TOOLS TỔNG HỢP\TOOLS UPDATE CUỐI\LightVisual_Image_Tool\` — bản sync, **không kèm key**.
- GitHub: `https://github.com/NaupUuh/LightVisual_Image_Tool` — `config.json` + `tiep_tuc.json` + `output/` + `Image/` nằm trong `.gitignore`.

## 9. Sang máy khác (đóng gói bản sạch) — v1.0.8
```
cd C:\Users\Admin\Desktop\LightVisual_Image_Tool
python _sang.py
```
→ tạo `Desktop\LightVisual_Image_Tool_v<ver>.zip` (~196 KB, 18 file) **và** thư mục rời cùng tên.

- **Copy**: `main.py`, `updater.py`, `core/api.py`, `core/tele.py`, `run.bat`, `version.json`,
  `cacert.pem`, `HUONG_DAN.txt`, `TIEP_TUC.md`, `tests/*`, `config.mau.json`.
- **KHÔNG copy**: `config.json` (API key), `tiep_tuc.json` (trạng thái lượt chạy), `output/`,
  `Image/`, `_backup_update/`, `__pycache__`, `.git`.
- `config.mau.json` có **mọi key rỗng**; máy mới chỉ cần đổi tên thành `config.json`
  (hoặc cứ chạy `run.bat`, tool tự sinh `config.json` rỗng) rồi bấm **API key** dán key.
- Script tự kiểm: thiếu file bắt buộc → báo `THIEU FILE`; quét regex `LV_…`, `sk-…`, `<id>:<token>`
  → nếu thấy key thật thì in `CANH BAO — có thể lộ key`.
- Đã kiểm: giải nén zip ra thư mục trống → `python main.py` chạy được, `APP_VERSION = 1.0.8`,
  nút Telegram hiện, hộp thoại mở OK, 4 bộ test 19/90/26/9 đều PASS.
