# TIẾP TỤC — LightVisual Image Tool

Cập nhật: 2026-10-26 · **v1.0.13** · trạng thái: chạy thật OK với key thật (gói Grok Vô Hạn 1 ngày)

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

## 5d. Báo cáo tiến độ lên Telegram (v1.0.14)
Nút **📣 Telegram** ở góc phải trên, cạnh `API key`. Mở hộp thoại — **chỉ 2 ô nhập, không quét nhóm**:

1. **Bật báo cáo Telegram** — mặc định TẮT.
2. **Bot token** — dán token bot (dạng `123456789:AA…`), hiện che (`•`).
3. **ID nhóm** — dán ID nhóm/kênh nhận báo cáo. Nhận các dạng:
   - `-1001234567890` (ID nhóm, luôn âm)
   - `1001234567890` → tự thêm dấu `-` đầu
   - `@tenkenh` (kênh công khai, bot phải là admin)
   - `https://t.me/tenkenh` → đổi thành `@tenkenh`
   - Nhiều nhóm: cách nhau **dấu phẩy** (hoặc `;`, hoặc xuống dòng).
   - ID sai → báo đỏ, **không lưu**.
4. **Gửi tiến độ mỗi (phút)** — mặc định **30**, cho 1…240.
5. **Nghe lệnh /baocao trong nhóm** — mặc định BẬT.
6. **Gửi thử** kiểm tra, **Lưu** ghi `config.json`.

**Chưa biết ID nhóm?** Add bot vào nhóm → gõ `/baocao` trong nhóm → tool ghi ra ô log:
`Telegram: thấy nhóm "Tên nhóm" — ID -1001234567890` → copy ID đó dán vào ô.

3 loại tin tự động:
1. **BẮT ĐẦU** — loại việc, model, tổng số việc (kèm số đã xong trước đó), số luồng, thư mục ra.
2. **TIẾN ĐỘ** — mỗi N phút (mặc định 30): thanh tiến độ, `OK/Lỗi/Dừng`, đã chạy, còn bao lâu, giây/việc.
3. **KẾT THÚC** — tổng kết + đường dẫn thư mục ra; nếu còn việc thì nhắc bấm "Tiếp tục".
   Bấm **DỪNG** cũng gửi 1 tin báo ngay.

`/baocao` trả gì:
- **Đang chạy** → tiến độ hiện tại (đọc từ cache số đếm, không đụng widget Tk).
- **Không chạy** → tổng kết lượt gần nhất (OK/Lỗi/Dừng, thời gian, thư mục ra).

Ghi chú kỹ thuật:
- `core/tele.py` — thuần stdlib (`urllib`), không cần pip; chạy được Python 3.9+.
- Luồng gửi là **thread riêng có hàng đợi**, nên gọi mạng không làm treo GUI.
- **Token luôn bị che** trong log, không ghi ra file log.
- Mạng lỗi / token sai → chỉ ghi log, **không ảnh hưởng lượt chạy**.
- **`getUpdates` chỉ được chạy 1 nơi cho mỗi token.** Tool chỉ nghe lệnh bằng token anh dán
  vào hộp thoại; **không** tự dùng token trong `.env` của Hermes — nếu dùng, bot Hermes và tool
  sẽ tranh nhau và trả `409 Conflict`. Gặp 409 → tool tự dừng + nhắc tạo bot riêng.
- **Menu lệnh:** tool tự gọi `setMyCommands` (scope `all_group_chats`) lúc bật nghe lệnh →
  gõ `/` trong nhóm là hiện sẵn 3 lệnh để bấm, không phải nhớ cú pháp:
  `/baocao` (báo cáo ngay), `/trangthai` (đang chạy/rảnh), `/giup` (hướng dẫn).
  Lệnh gắn `@bot_khac` thì bot này bỏ qua → 1 nhóm nhiều bot không tranh nhau.
  Xem lại menu: `tele.lay_lenh(token)`; đăng ký lại: `tele.dat_lenh(token)`.
- Group privacy ON thì chỉ thấy lệnh dạng `/baocao@<username_bot>` — tool xử lý cả 2 dạng.
- **409 Conflict** → tool **thử lại 5 lần** (chờ 3/6/9/12s), chỉ bỏ khi tranh chấp liên tục;
  trước v1.0.13 gặp 1 lần là tắt luồng vĩnh viễn → bot im lặng dù app vẫn mở.
- **Nhiều bot / nhiều máy:** mỗi máy 1 token riêng + cùng ID nhóm = OK, không 409.
  Mỗi token chỉ 1 chương trình `getUpdates`; 2 tool cùng token (dù khác máy) → 409.
- `tele_offset` (update_id cuối) lưu trong `config.json` để mở lại app không xử lý lặp lệnh cũ.
- Test: `tests/test_tele_nhom.py` (35) + `tests/test_tele_hop.py` (24: hộp thoại token + ID nhóm,
  đọc link/@kenh/ID dương, ID sai không lưu, `/baocao` trả lời).

## 5e. Nối thêm việc khi tool ĐANG CHẠY (v1.0.15)
Nút **➕ Nối vào hàng chờ (đang chạy)** ở đáy cửa sổ (cạnh `Nạp lại`). Nút **luôn bấm được** —
bấm lúc chưa chạy thì tool nhắc *"Chưa có lượt nào đang chạy"*. Khi đang chạy, tool đọc **đúng
phần đang chọn trên màn hình lúc bấm** rồi **nối vào hàng chờ của lượt đang chạy** (tab 4);
các luồng đang chạy nhận việc mới **ngay**, không cần dừng tool.

Hai cách dùng chính (đang ở tab 2):
1. **Chỉ prompt video** — thêm dòng vào ô `2. PROMPT VIDEO` → bấm nút → prompt MỚI được nối
   vào hàng chờ và chạy tiếp ngay sau việc đang làm.
2. **Folder ảnh tham chiếu** — chọn **folder khác** ở ô folder → bấm nút → mọi ảnh trong folder
   đó thành việc mới; **mỗi tên folder vào = 1 thư mục con** ở thư mục ra; ảnh dùng xong vẫn bị xoá.

Quy tắc (đã kiểm chứng):
- **Chống nạp trùng**: khoá = prompt gốc + ảnh khung + prompt ảnh + lần + tên folder. Bấm 2 lần
  cùng dữ liệu → lần 2 báo *"không có prompt/ảnh nào mới"*.
- **Theo tab đang mở**: tab 2 = việc video, tab 1 = việc tạo ảnh, tab 3 = việc sửa ảnh.
  **Nối chéo được** (đang chạy lượt ảnh vẫn nối được việc video vào cùng hàng chờ) vì mỗi việc
  tự nhớ loại của nó ở khoá `_loai`, worker dispatch theo từng việc.
- Việc nối thêm dùng **model/giây/res/tỉ lệ đang chọn trên GUI lúc bấm**; thư mục ra + bảng
  thư mục con (`thu_muc_folder` / `thu_muc_prompt`) thì **dùng chung với lượt đang chạy**.
- Nguồn `ảnh khung` / `prompt ảnh` cũng nối được; thiếu đầu vào → báo rõ, không chạy sai.
- Nút hiện **✔ Đã nối N việc** trong 4 giây rồi trở lại bình thường.
- Nếu **tất cả luồng đã thoát** (hàng chờ vừa cạn) mà anh nối thêm → tool **tự mở lại luồng**.
- **Cẩn thận đã gặp**: bấm CHẠY ở chế độ ảnh thì tool **tự nhảy sang tab 3** → nếu lượt đang chạy
  là lượt ẢNH mà tab đang mở là tab 3 thì giữ đúng chế độ của lượt (tránh đọc nhầm ô prompt sửa ảnh).
- Test: `_test_tab2.py` (đúng 2 tình huống trên), `_test_cross.py` (nối chéo ảnh↔video),
  `_test_vnoi.py`, `_test_fnoi.py`, `_test_uv.py`, `_test_noi4.py`, `_test_nut_idle.py`.

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

## 9. Sang máy khác (đóng gói bản sạch) — v1.0.11
```
cd C:\Users\Admin\Desktop\LightVisual_Image_Tool
python _sang.py
```
→ tạo `Desktop\LightVisual_Image_Tool_v<ver>.zip` (~215 KB, 20 file) **và** thư mục rời cùng tên.

- **Copy**: `main.py`, `updater.py`, `core/api.py`, `core/tele.py`, `run.bat`, `version.json`,
  `cacert.pem`, `HUONG_DAN.txt`, `TIEP_TUC.md`, `tests/*`, `config.mau.json`.
- **KHÔNG copy**: `config.json` (API key), `tiep_tuc.json` (trạng thái lượt chạy), `output/`,
  `Image/`, `_backup_update/`, `__pycache__`, `.git`.
- `config.mau.json` có **mọi key rỗng**; máy mới chỉ cần đổi tên thành `config.json`
  (hoặc cứ chạy `run.bat`, tool tự sinh `config.json` rỗng) rồi bấm **API key** dán key.
- Script tự kiểm: thiếu file bắt buộc → báo `THIEU FILE`; quét regex `LV_…`, `sk-…`, `<id>:<token>`
  → nếu thấy key thật thì in `CANH BAO — có thể lộ key`.
- Đã kiểm: giải nén zip ra thư mục trống → `python main.py` chạy được, `APP_VERSION = 1.0.13`,
  nút Telegram hiện, hộp thoại mở OK, 4 bộ test 19/90/26/9 đều PASS.

## 5f. v1.0.17 — tắt tool không treo + báo cáo định kỳ

### Nguyên nhân treo khi tắt (đã đo, không đoán)
1. `BaoCao._t.daemon = False` → tiến trình Python **chờ luồng gửi tin** (mỗi tin
   timeout 20s, hàng đợi tới 200 tin) → cửa sổ đóng nhưng tool còn sống.
2. `_thoat_app` gọi `bc.dung(cho=...)` **join trên luồng GUI** → cửa sổ đứng hình.
3. `TheoDoi.dung(cho=45)` join long-poll 25–40s trên luồng GUI → treo tới 45s.

### Cách sửa
- `BaoCao.bat_dau_worker()`: `self._t.daemon = True`.
- `_thoat_app`: `after_cancel(self._aid)` (huỷ watchdog) → `bc.dung(cho=2.0)` →
  `_dung_theo_doi(nhanh=True)` (**chỉ báo dừng, KHÔNG join**) → `destroy()`.
- `TheoDoi.dung_nhanh()`: chỉ `_stop.set()`; luồng là daemon nên tiến trình thoát được.

### Đo thật (app thật, cửa sổ thật, bấm X thật)
| Trường hợp | Trước | Sau |
|---|---|---|
| Đang rảnh, bấm X | tới 45s (join long-poll) | **0.06s** |
| Đang chạy việc → Dừng → X | treo / phải kill | **0.98s** |

### Báo cáo định kỳ (mới)
- Watchdog `_giam_sat_nghe` (30s) kiểm tra mốc `_lan_hb`; quá `tele_moi_phut`
  phút thì gửi `⏱ Báo cáo định kỳ` tới **mọi nhóm** — **kể cả khi tool đang rảnh**.
- Nếu trong kỳ vừa rồi đã có tin báo cáo nào gửi đi (`bc.da_gui` tăng) thì **bỏ**
  tin định kỳ → không spam.
- Mỗi máy chạy 1 bot riêng ⇒ nhóm có N máy thì nhận N tin, mỗi tin có nhãn riêng.

### Lệnh mới
- `/tonghop` (hoặc `/tonghop@<bot>`): nhờ **cả nhóm** báo cáo — bot nào đang chạy
  thì bot đó trả lời, không cần biết tên từng bot.
- `/baocao@<bot>` vẫn như cũ; `/bc`, `/report` là alias.

### Trả lời lệnh khi cửa sổ đã đóng
`_co_lenh_baocao` gọi thẳng `_gui_bao_cao()` (dữ liệu thuần, không đụng Tk) thay vì
chỉ đẩy vào `ui_q` — cửa sổ đóng mà tiến trình còn sống vẫn trả lời được.

### Kiểm chứng
- `tests/test_baocao_ngay.py` — **9 PASS / 0 FAIL** (máy chủ Telegram giả, long-poll thật).
- `tests/test_dong_app.py` — **14 PASS / 0 FAIL** (đo thời gian tắt, báo cáo định kỳ,
  ca đang chạy → Dừng → tắt).
- 8 bộ test cũ: **222 PASS / 0 FAIL**.
- App thật: mở → 409 từ ngoài (đang long-poll) → bấm X → thoát **0.06s**, cửa sổ biến
  mất, getUpdates từ ngoài trả `ok` (đã nhả kết nối).

### Cần tránh
- **KHÔNG** `join()` luồng long-poll trên luồng GUI (Tk sẽ đứng hình tới 45s).
- **KHÔNG** để luồng gửi tin là non-daemon.
- **KHÔNG** quên `after_cancel(self._aid)` trước `destroy()` — watchdog sẽ gọi
  `after()` trên cửa sổ đã huỷ.
- `goi()` phân biệt `tham_so=None` (GET) và `tham_so={}` (POST) — đừng dùng
  `if tham_so:` vì `{}` là falsy, `getMe` sẽ thành GET.

## 5g — v1.0.18: bot im lang khi go /tonghop tran (2026-10-27)

**Trieu chung:** 3 bot cung chay trong 1 nhom, go `/tonghop` tran -> khong bot nao tra loi.
Go `/tonghop@bot` rieng tung con thi duoc.

**Nguyen nhan da xac minh (khong phai loi code):**
- `getMe()` -> `can_read_all_group_messages = False` (privacy mode BAT)
- `getChatMember()` -> `status = member` (bot KHONG phai admin)
- Tai lieu Telegram: *"Privacy mode is enabled by default for all bots, except bots that
  were added to a group as admins (bot admins always receive all messages)"*
  => Bot thuong + privacy BAT CHI nhan `/lenh@<bot_username>`, khong nhan lenh tran.

**Cach sua (lam 1 lan, phia Telegram cua anh):**
1. Nhom -> Manage -> Administrators -> Add Admin -> chon bot (CACH CHAC NHAT, khong can tat privacy)
2. Hoac: @BotFather -> `/setprivacy` -> chon bot -> **Disable** -> **xoa bot khoi nhom roi them lai**
   (doi privacy chi co hieu luc sau khi them lai)

**Tool lam gi (v1.0.18):**
- `tele.kiem_tra_quyen(token, chat_ids)` -> `(ds, privacy_off)`; moi nhom: status, la_admin, doc_het, loi
- `_kiem_tra_quyen_nghe()` chay sau khi bat nghe -> log ro + gui 1 tin canh bao vao nhom (1 lan/nhom/phien)
- Nut **"Kiem tra quyen"** trong hop thoai Telegram de kiem tra lai bat cu luc nao

**Cach kiem tra:** `python tests/test_quyen_nhom.py` -> PASS 16 | FAIL 0

## 5h — v1.0.19: bao cao theo MOC DONG HO :00/:30 + dong toc do (2026-10-27)

**Yeu cau:** "vao moc phut :00 va phut :30 thi se bao cao"; dong tien do them
" - Da them 30 video trong 30p" (lay hien tai tru du lieu 30p truoc).

**Da lam:**
- `tele.giay_toi_moc(buoc_phut)` — so giay toi moc dong ho ke tiep. `30` -> :00/:30,
  `60` -> :00, `15` -> :00/:15/:30/:45.
- `_hen_moc()` hen `after()` dung moc; `_chay_moc()` gui xong tu hen moc ke.
  Hen lai khi luu hop thoai Telegram. Go bo phan bao dinh ky cu trong `_giam_sat_nghe`.
- `BaoCao(moi_giay=10**8)` — tat tu dong gui tin tien do cua `core/tele.py`, chi con
  nhanh moc dong ho lo viec bao cao (tranh 2 nguon bao trung nhau).
- `_moc_ghi()` luu moc `(gio, so viec xong)` moi lan 1 viec ket thuc, giu ~2 gio.
- `_toc_do_truot(cua_so)` + `_dong_toc_do(don_vi)` — chen ` - Da them N video trong Mp`
  vao dong thanh tien do. Don vi tu doi anh/video; chua du 30s du lieu thi bo dong.
- Doi nhan o nhap: "Moc bao cao (phut: 30 = :00/:30)".
- Emoji thong nhat `⏸️` o ca 3 cho (dang chay / ket thuc / luot gan nhat).
- `after_cancel` ca `_aid_moc` va `_aid_hen` khi tat tool.

**Format bao cao moi (dang chay):**
```
🏷 @adungg_bot
📊 Báo cáo theo yêu cầu
▰▰▰▰▰▰▱▱▱▱  137/240 - Đã thêm 30 video trong 30p
✅ OK 133   ❌ Lỗi 4   ⏸️ Dừng 0
⏱️ Đã chạy 1h31p · còn khoảng 1h08p
⚡️ 40.1s/việc
```

**Kiem chung:** 12 bo test — **300 PASS / 0 FAIL** (them `tests/test_moc_toc_do.py` 36 case:
moc :00/:30, gioi han cua so, don vi anh/video, thanh 10 o, ca rong).
`test_dong_app.py` len 17 case (do thoi gian tat + bao theo moc).

**Can tranh:**
- KHONG de 2 nguon cung gui bao cao dinh ky (BaoCao.moi_giay + `_hen_moc`) -> tin trung.
- `_moc_dem` phai reset khi bat dau luot chay moi (da lam trong `_bam_chay`), khong thi
  dong "Da them" se tinh lan ca luot truoc.
- Moc dung dong ho that: doi `tele_moi_phut` = 60 thi chi bao :00, khong phai :30.


## 5i — v1.0.20: nhóm lên supergroup thì tự đổi chat_id (2026-10-27)

**Triệu chứng**: log tool hiện `Tele: gửi lỗi (-5593791314) — HTTP 400: Bad Request:
group chat was upgraded to a supergroup chat` ⇒ mọi báo cáo/tiến độ đều mất.

**Nguyên nhân**: Telegram đổi `chat_id` của nhóm thường thành dạng `-100...` khi
nhóm được nâng cấp (bật Topics, đổi loại nhóm, đủ điều kiện...). ID cũ trả
`getChat` vẫn "ok" nhưng mọi thao tác gửi đều 400 kèm
`parameters.migrate_to_chat_id`. `config.json` vẫn giữ ID cũ nên tool gửi mãi vào
địa chỉ đã chết.

**Cách sửa**:
- `core/tele.py`: thêm `_MIGRATE` + `_migrate_tu(d)` + `_ghi_migrate()` + `lay_migrate()`.
  `gui()` gặp 400 có `migrate_to_chat_id` ⇒ **gửi lại ngay** bằng ID mới (chỉ 1 lần,
  không lặp vô hạn). Lần sau `gui()` tự dùng ID mới luôn.
- `main.py`: `_dong_bo_migrate()` chạy trong `_xu_ly_ui_q` — thay ID cũ bằng ID mới
  trong `tele_chat_id`, `tele_chat_ids`, khoá `tele_nhom_ten`, rồi `luu_cfg()`.

**Cách kiểm tra**: `tests/test_migrate.py` — 23 case (helper, mô tả lỗi, gửi lại,
không lặp vô hạn, đồng bộ config, chạy 2 lần không ghi lại).
Kiểm tra thật: `sendChatAction` vào ID mới trả `{"ok":true}`.

**Tránh**: đừng chỉ sửa `config.json` bằng tay rồi thôi — lần sau nhóm đổi tiếp
thì lại mất báo cáo. Đừng bắt user tự điền ID mới.


## 5j — v1.0.21: chọn lưu mỗi prompt 1 folder hay gộp chung 1 folder (2026-10-30)

**Yêu cầu**: "option lưu từng prompt theo 1 folder hoặc tất cả prompt vào chung 1 folder".

**Đã làm**:
- 2 khoá config mới: `chia_folder` (tab 1 ảnh, mặc định `False` = gộp chung — đúng
  hành vi 1.0.20) và `video_chia_folder` (tab 2 video, mặc định `True` = chia theo
  prompt — đúng hành vi 1.0.20). Mặc định giữ y nguyên nên máy đang chạy không đổi gì.
- Tab 1 (ảnh): `var_chia_anh`; tab 2 (video): `var_chia` — checkbox
  "Mỗi prompt 1 thư mục con (bỏ tick = gộp chung)" nằm dưới ô "Mở folder khi chạy xong".
- `_bam_chay`: khi bật và có >1 prompt → tạo thư mục con `NN_<prompt>_<hash>` và gán
  `v["thu_muc"]` cho từng việc; tắt → tất cả ghi thẳng vào thư mục ra.
- `_bam_chay_video`: thêm `cau_hinh["chia_folder"]`; điều kiện chia theo folder ảnh
  vào và theo prompt đều phải qua `chia_folder`.
- `_noi_hang_cho`: nối thêm việc giữa lượt chạy cũng tôn trọng `chia_folder`
  (cả nhánh ảnh và nhánh video) — nếu không, việc nối sẽ ghi lạc chỗ.
- `_lam_mot` ghi ảnh vào `v["thu_muc"]` (trước đây luôn `ch["thu_muc"]`).

**Cách kiểm tra**: `tests/test_gui.py` thêm 5 case:
- gộp chung: không tạo thư mục con, 2 mp4 nằm ngay trong thư mục ra
- gộp chung / chia folder: giá trị lưu đúng vào config
- chia lại: tạo đúng 2 thư mục con

**Tránh**: `ttk.Checkbutton` KHÔNG có option `wraplength` (chỉ `ttk.Label` có) —
truyền vào sẽ `TclError: unknown option "-wraplength"` và app không mở được.
Nhãn dài thì rút ngắn chữ, đừng thêm `wraplength`.
