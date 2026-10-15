# Cách chạy Stock Analytics – hướng dẫn chi tiết

Tài liệu này hướng dẫn từ lúc nhận bộ mã nguồn đến lúc chạy app, cập nhật dữ liệu tự động, chạy kiểm thử và chạy các
công cụ kiểm chứng mô hình. Các lệnh viết cho **Windows PowerShell**; macOS/Linux ghi chú riêng khi khác.

---

## 1. Chuẩn bị (làm 1 lần)

1. **Cài Python.** Khuyến nghị **Python 3.12** (https://www.python.org/downloads/), khi cài tick
   **"Add python.exe to PATH"**. Python 3.10–3.13 đều chạy được. Python 3.14 vẫn chạy được nếu dùng `run_app.ps1`
   (script cài vnstock bỏ qua gói vẽ biểu đồ chưa hỗ trợ 3.14).
2. **Giải nén** bản phát hành (vd `GPM1_v3_merged.zip`) ra một thư mục, ví dụ `C:\Users\<tên>\Documents\Codex\GPM1`.
   - Nếu đang có bản cũ: giải nén bản mới vào **thư mục mới**, rồi chép từ bản cũ sang: file `.env`, file
     `data\stock_analytics.duckdb` (CSDL – giữ lịch sử giá, BCTC, tin, danh mục), thư mục `data\documents\` (PDF đã tải).
     Không chép `data\cache\` (bộ nhớ tạm sẽ tự tạo lại).
   - Không nên giải nén đè lên bản cũ: file đã xóa ở bản mới sẽ còn sót lại trong thư mục.
3. **Mở PowerShell tại thư mục GPM1**: trong File Explorer, bấm vào thanh địa chỉ, gõ `powershell`, Enter.

---

## 2. Chạy app

### Cách 1 – nhanh nhất (Windows)
```
.\run_app.ps1
```
Script tự tạo môi trường ảo `.venv`, cài thư viện nếu thiếu (lần đầu mất vài phút), cài vnstock, rồi mở app.
Nếu PowerShell báo bị chặn chạy script, chạy 1 lần: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Cách 2 – thủ công
```
python -m venv .venv
.venv\Scripts\Activate.ps1                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Trình duyệt tự mở **http://localhost:8501**. Tắt app: `Ctrl + C` trong cửa sổ PowerShell.

Các lần sau chỉ cần: `.venv\Scripts\Activate.ps1` rồi `streamlit run app.py` (hoặc `.\run_app.ps1`).

---

## 3. Cấu hình `.env` (không bắt buộc)

Chép mẫu: `copy .env.example .env`, rồi sửa nếu cần. **Không chia sẻ file `.env`** (chứa khóa API, tài khoản).

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `VNSTOCK_API_KEY` | Khóa API vnstock (để trống = bản Cộng đồng, 60 lượt/phút) | trống |
| `VNSTOCK_SOURCE` | Nguồn vnstock mặc định | `VCI` |
| `DNSE_API_KEY`, `DNSE_API_SECRET` | Khóa DNSE OpenAPI để có **giá realtime** (xem mục 3a). Để trống = giá ~3 phút/lần | trống |
| `DNSE_REALTIME` | Đặt `0` để tạm tắt realtime dù đã có key | `1` |
| `REALTIME_REFRESH_SECONDS` | Nhịp làm mới ô giá trên trang khi có realtime (giây, tối thiểu 2) | `3` |
| `DNSE_WS_URL` | Máy chủ realtime (Sandbox: `wss://ws-sb-openapi.dnse.com.vn`) | `wss://ws-openapi.dnse.com.vn` |
| `DNSE_RECENT_DAYS` | Số ngày giá gần nhất lấy từ DNSE | `365` |
| `PRICE_HISTORY_SOURCES` | Thứ tự nguồn giá cũ hơn | `vnstock_vci,vnstock_kbs,vnstock_msn,vietstock` |
| `FINANCIAL_SOURCES` | Thứ tự nguồn BCTC | `vnstock_vci,vnstock_kbs,vietstock,arminer,pdf` |
| `DOCUMENT_SOURCES` | Thứ tự nơi dò tài liệu PDF | `vietstock,cafef` |
| `LIVE_REFRESH_SECONDS` | Chu kỳ làm mới giá trong phiên (tối thiểu 180) | `180` |
| `CACHE_TTL_PRICE` / `CACHE_TTL_FINANCIAL` / `CACHE_TTL_MARKET` | Thời gian nhớ tạm (giây) | `1800` / `3600` / `170` |
| `QUARTER_RELEASE_LAG_DAYS` | Số ngày sau cuối quý coi là BCTC quý đã công bố (khi nguồn không có ngày công bố) | `50` |
| `ANNUAL_RELEASE_MONTH` | Tháng coi là BCTC năm đã công bố | `4` |
| `BETA_WINDOW_DAYS` | Cửa sổ tính beta (ngày lịch) | `365` |
| `DB_PATH`, `CACHE_DIR`, `REPORTS_DIR`, `DOCUMENTS_DIR` | Đường dẫn dữ liệu | trong thư mục `data/`, `reports/output` |
| `CACHE_SCHEMA_VERSION` | Đổi chuỗi này để bỏ toàn bộ bộ nhớ tạm cũ | `gpm1-v4` |

Tham số **mô hình** (ngưỡng khuyến nghị, trọng số, Rf, ERP…) không nằm trong `.env` mà ở
`core/cau_hinh.py` (ghi đè bằng `config/investment_model.json` nếu muốn, không cần sửa code).

### 3a. Bật giá REALTIME từ DNSE (tùy chọn)
Không có key, app vẫn lấy giá DNSE qua API biểu đồ công khai, cập nhật ~3 phút/lần. Có key → giá khớp lệnh từng giây
(WebSocket DNSE OpenAPI), các ô giá trên trang Phân tích, Danh mục theo dõi, Tổng quan thị trường tự làm mới mỗi 3 giây.

1. Đăng nhập **Entrade X** (entradex.dnse.com.vn) → **Thông tin cá nhân → Light Speed** → copy **API key**.
   **API secret** chỉ hiện một lần lúc tạo key; nếu chưa lưu thì tạo lại key để nhận secret mới.
   Phần OTP (Smart OTP / Email OTP) chỉ dùng khi đặt lệnh – app chỉ đọc giá nên **không cần**.
2. Mở `.env`, thêm (không có dấu cách, không có ngoặc kép):
   ```
   DNSE_API_KEY=...
   DNSE_API_SECRET=...
   ```
   Có thể xóa các dòng cũ `DNSE_USERNAME`, `DNSE_PASSWORD`, `DNSE_TOKEN` – app không dùng.
3. Tắt app (`Ctrl + C`) rồi chạy lại. Trang **🛰️ Nguồn dữ liệu → Giá realtime** báo "🟢 Đang nhận giá realtime";
   trên trang Phân tích, dòng phiên ghi "⚡ realtime HH:MM:SS".

Sai key → trạng thái "🔴 Sai API key / secret", app tự quay về giá ~3 phút/lần (không thử lại liên tục). Mất mạng →
tự kết nối lại. Định giá, BCTC, báo cáo PDF, backtest không đổi (dùng giá đóng cửa).

### Cập nhật lãi suất phi rủi ro Rf (3 tháng/lần)
Trong `core/cau_hinh.py`, mục `"valuation"`: sửa `risk_free` (vd `0.0443`), `risk_free_as_of`
(`"YYYY-MM-DD"`) và `risk_free_source` (ghi nguồn). Rf quá 92 ngày hoặc không ghi nguồn → độ tin cậy định giá tối đa
"Trung bình" và app hiện cảnh báo. Nguồn: kết quả đấu thầu TPCP 10 năm trên HNX hoặc bản tin VBMA.

### Nhập cổ tức đã công bố (khi vnstock không có)
Thêm vào `config/announced_dividends.json` theo mẫu có sẵn của FPT: `ex_date` (ngày GDKHQ), `dps` (đồng/cp),
`source` (link nguồn). App ưu tiên dữ liệu nhập tay này.

---

## 4. Kiểm thử

```
pytest tests/ -q
```
Khoảng 360 kiểm thử trong 5 file theo nhóm (dữ liệu, phân tích, định giá & dự phóng, khuyến nghị, giao diện & báo cáo), chạy trên CSDL bộ nhớ và thư mục tạm (không đụng dữ liệu thật), không cần mạng. Nên chạy sau mỗi
lần sửa code hoặc đổi tham số mô hình.

---

## 5. Công cụ kiểm chứng & chẩn đoán (thư mục `tools/`)

Các công cụ này **chỉ đọc dữ liệu**, cần mạng và vnstock. Chạy tại thư mục GPM1 sau khi kích hoạt `.venv`.
Kết quả ghi vào `tools\reco_trend_out\`. Chạy dở bị ngắt → **chạy lại đúng lệnh** sẽ tiếp tục, không mất kết quả.

| Mục đích | Lệnh |
|---|---|
| Backtest khung khuyến nghị trên VN30, mỗi tháng từ 2022 (~1.350 lượt, ~1,5 giờ) | `python tools/reco_trend_backtest.py --start 2022-01 --step 1 --out tools/reco_trend_out/rows.csv` |
| Bản nhanh: vài mã, mỗi quý | `python tools/reco_trend_backtest.py --symbols FPT,HPG,VCB --start 2022-01 --step 3 --out tools/reco_trend_out/rows_nhe.csv` |
| Kiểm chứng NGOÀI MẪU (66 mã ngoài VN30, đã chốt trước) | `python tools/reco_trend_backtest.py --symbols @tools/oos_basket.txt --start 2022-01 --step 3 --out tools/reco_trend_out/rows_oos.csv --pause 3` |
| Chấm kết quả (LN theo nhãn, Rank IC theo tháng & mẫu không chồng lấn, top–bottom 20%, so với VN-Index, tỷ lệ đổi nhãn) | `python tools/multilayer_eval.py tools/reco_trend_out/rows.csv` |

Mẹo:
- **Hết lượt gọi vnstock** (60 lượt/phút): thêm `--pause 2` hoặc `--pause 3` để chạy chậm lại; công cụ cũng tự chờ
  65 giây rồi thử lại. Nếu vẫn bị chặn (giới hạn theo ngày), chạy lại lệnh vào hôm sau – kết quả được nối tiếp.
- Muốn chạy lại từ đầu với code mới: dùng **tên file `--out` mới** (file cũ sẽ bị bỏ qua các dòng đã có).
- Tắt chế độ ngủ của máy khi chạy lâu (Settings → System → Power → Sleep: Never).
- Windows: thêm `> ten_file.txt` để lưu kết quả ra file; công cụ đã tự dùng UTF-8 nên không lỗi tiếng Việt.

---

## 6. (Tùy chọn) Đọc BCTC PDF bản scan bằng OCR

Nhiều BCTC trên CafeF là ảnh scan. Cài thêm 1 lần:
```
.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```
Tắt app rồi chạy lại. OCR chạy trên máy, ~1–3 giây/trang, kết quả được lưu lại.

---

## 7. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `'pip' / 'streamlit' / 'python' is not recognized` | Dùng `python -m pip …`, `python -m streamlit run app.py`; cài lại Python có tick "Add to PATH" |
| Lỗi cài `numpy` / `vnstock_ezchart` / "Unknown compiler" | Đang dùng Python 3.14 → chạy `.\run_app.ps1` hoặc cài Python 3.12 |
| `UnicodeEncodeError` khi ghi `> file.txt` | Dùng bản công cụ mới (đã ép UTF-8) hoặc chạy `$env:PYTHONIOENCODING="utf-8"` trước |
| "Rate Limit Exceeded" / chương trình tự thoát | Hết 60 lượt/phút của vnstock → đợi 1 phút rồi chạy lại; dùng `--pause` |
| Số liệu có vẻ cũ sau khi cập nhật code | Xóa thư mục `data\cache\` (hoặc đổi `CACHE_SCHEMA_VERSION`) rồi chạy lại |
| Trang báo lỗi khi xem một mã | Mở mục "Chi tiết lỗi" trên trang để xem nguyên nhân; thường do nguồn dữ liệu tạm lỗi |
| Giá không tự cập nhật trong phiên | Không có key DNSE: giá làm mới ~3 phút/lần; bấm nút làm mới trên trang. Muốn realtime → mục 3a |
| Trang Nguồn dữ liệu báo "Sai API key / secret" | Copy lại key/secret (đúng Production, chưa bị tạo lại), sửa `.env`, chạy lại app |
| Realtime báo "Mất kết nối" liên tục | Tường lửa / diệt virus chặn WebSocket cổng 443 → xem trạng thái ở trang 🛰️ Nguồn dữ liệu |

---

## 8. Đóng gói để gửi người khác

Gửi cả thư mục GPM1 **trừ**: `.env` (thông tin cá nhân), `.venv\`, `data\cache\`, `data\*.duckdb*`, `data\documents\`,
`reports\output\`, `tools\reco_trend_out\`, `__pycache__\`, `.pytest_cache\`. Người nhận làm theo mục 1–2.
