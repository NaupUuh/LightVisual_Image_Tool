# TIẾP TỤC — LightVisual Image Tool

Cập nhật: 2026-10-24 · **v1.0.2** · trạng thái: chạy thật OK với key thật (gói Grok Vô Hạn 1 ngày)

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

## 3. Tab video (v1.0.2)
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
| `tests/test_gui.py` | **56/0 PASS** |
| `tests/test_key_dialog.py` | **7/0 PASS** |
| `py_compile` main.py + core/api.py | OK (3.13 và 3.9.9) |

### 4b. Test với key thật + gói `grok-unlimited-d1-s1`
| Việc | Kết quả đo được |
|---|---|
| `GET /v1/balance` | `credits 0`, plan `grok-unlimited-d1-s1`, tên "Grok Vô Hạn 1 ngày" |
| Tạo 3 ảnh Grok 2.0 | **12,8 s**, 1024×1024 JPEG ~168 KB/ảnh, credits vẫn 0 |
| Sửa ảnh (1 ảnh gửi kèm, tag `<IMAGE_0>`) | **10,7 s**, nội dung đổi đúng, credits 0 |
| Tạo video T2V (1 s / 480p) | job `lv_job_75b5a33…`, xong ~**22 s**, MP4 285 KB, `mvhd dur 1042 → 1.04 s`, `avc1 @24` |
| Xoay key (1 key hỏng 401 + 1 key thật) | tự loại key hỏng, chuyển key sống, không dừng lô |

## 5. Việc còn lại
1. Gói hiện tại chỉ **1 ngày / 1 luồng** → muốn nhiều luồng song song thật thì nâng gói hoặc thêm nhiều key.
2. Bắn 2 job video liên tiếp trên gói 1 luồng dễ gặp `"Model đang bị giới hạn tốc độ"` — chờ vài giây rồi chạy lại.
3. Gói hết hạn thì `/v1/balance` vẫn trả 200 nhưng sẽ bị trừ credit — kiểm tra số dư định kỳ.
4. Chưa test video 15 s / 1080p thật (tốn credit); preset đã set sẵn 15 s / 1080p / 9:16 / 4 video mỗi prompt.

## 6. Lệnh hay dùng
```
cd C:\Users\Admin\Desktop\LightVisual_Image_Tool
run.bat                       :: chạy ẩn
run.bat debug                 :: chạy có cửa sổ cmd
python tests\test_mock.py     :: test API (0đ)
python tests\test_gui.py      :: test GUI + chạy thử
python tests\test_key_dialog.py
```

## 7. Bản sao lưu
- `Z:\HQData-2\TOOLS TỔNG HỢP\TOOLS UPDATE CUỐI\LightVisual_Image_Tool\` — bản sync, **không kèm key**.
- GitHub: `https://github.com/NaupUuh/LightVisual_Image_Tool` — `config.json` + `tiep_tuc.json` + `output/` nằm trong `.gitignore`.
