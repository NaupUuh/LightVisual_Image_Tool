# TIẾP TỤC — LightVisual Image Tool

Cập nhật: 2026-10-25 · **v1.0.6** · trạng thái: chạy thật OK với key thật (gói Grok Vô Hạn 1 ngày)

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

### 4a. Test tự động (máy chủ giả, 0đ) — v1.0.2
| Test | Kết quả |
|---|---|
| `tests/test_mock.py` | **19/0 PASS** |
| `tests/test_gui.py` | **68/0 PASS** |
| `tests/test_key_dialog.py` | **7/0 PASS** |
| `tests/_test_update_btn.py` | **PASS** (nút Cập nhật hiện, bấm chạy được) |
| `tests/_do_tab_tc.py` | **PASS** (tab video không cắt khung tham chiếu ở 1040x640) |
| `py_compile` main.py + core/api.py + updater.py | OK (3.13) |

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

## 5b. Folder ảnh tham chiếu (v1.0.4)
Nguồn thứ 4 trong "Nguồn cảnh đầu": **Folder ảnh tham chiếu → video**.
- Chọn folder chứa ảnh; mỗi ảnh trong folder = **đúng 1 video** (không nhân `Video mỗi prompt`).
- Ảnh dùng làm khung đầu (I2V) như nguồn "Ảnh khung", nhưng **dùng xong bị xoá khỏi folder** → lần sau không bao giờ lặp lại ảnh cũ.
- Ô tích **"Xoá ảnh sau khi dùng"** mặc định BẬT; tắt đi thì ảnh giữ nguyên (dùng lại được).
- Prompt video xoay vòng theo số ảnh; MC vẫn nối trước prompt như cũ.
- Nhãn cạnh ô nhập hiện **"còn N ảnh"** và tự cập nhật sau mỗi ảnh xong.
- Nếu ảnh bị xoá/mất giữa lúc chạy → job đó báo LỖI "Không thấy ảnh khung", các job khác chạy tiếp.
- "Nạp lại" lượt cũ có ảnh tham chiếu đã xoá → báo rõ, không chạy lại được (đúng thiết kế).

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

## 6. Việc còn lại
1. Gói hiện tại chỉ **1 ngày / 1 luồng** → muốn nhiều luồng song song thật thì nâng gói hoặc thêm nhiều key.
2. Bắn 2 job video liên tiếp trên gói 1 luồng dễ gặp `"Model đang bị giới hạn tốc độ"` — chờ vài giây rồi chạy lại.
3. Gói hết hạn thì `/v1/balance` vẫn trả 200 nhưng sẽ bị trừ credit — kiểm tra số dư định kỳ.
4. Chưa test video 15 s / 1080p thật (tốn credit); preset đã set sẵn 15 s / 1080p / 9:16 / 4 video mỗi prompt.

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
- GitHub: `https://github.com/NaupUuh/LightVisual_Image_Tool` — `config.json` + `tiep_tuc.json` + `output/` nằm trong `.gitignore`.
