# 📈 Stock Analytics (GPM1)

Ứng dụng web (Streamlit) phân tích cổ phiếu Việt Nam: lấy giá và báo cáo tài chính (BCTC) từ nhiều nguồn, tự chuẩn hóa
và tính chỉ số, định giá 12 tháng bằng nhiều phương pháp, chấm sức khỏe tài chính, phân tích kỹ thuật, đưa ra
**khuyến nghị 12 tháng + hành động đề xuất**, và xuất **báo cáo PDF** dạng báo cáo phân tích của công ty chứng khoán.

> Đồ án học thuật. Mọi kết quả chỉ để tham khảo, **không phải khuyến nghị đầu tư**.
> Cách cài đặt và chạy từng bước: xem **[CACH_CHAY_CHI_TIET.md](CACH_CHAY_CHI_TIET.md)**.
> Mô tả chi tiết cách app lấy dữ liệu và tính toán: xem tài liệu Word **Mo_ta_he_thong_Stock_Analytics_Pro.docx**.

---

## 1. Các trang của app (menu bên trái – nền tối, chia nhóm Thị trường · Dữ liệu doanh nghiệp · Cá nhân · Đề án)

| Trang | Nội dung chính |
|---|---|
| 🏛️ **Tổng quan thị trường** | Thẻ VN-Index, VN30, HNX, UPCoM và mã đang theo dõi (trong phiên: realtime nếu có API key DNSE, ngược lại ~3 phút theo nến phút DNSE); biểu đồ nến chỉ số + MA20/MA50; độ rộng thị trường; bản đồ nhiệt theo ngành; top tăng/giảm/giá trị/khối lượng đột biến |
| 🔍 **Phân tích cổ phiếu** | 4 phần: **💰 Định giá** (giá mục tiêu 12 tháng, Bear/Base/Bull, độ nhạy, độ tin cậy) · **📊 Cơ bản** (Financial Health Score, chất lượng lợi nhuận, so sánh ngành) · **📈 Kỹ thuật** (biểu đồ giá + MA/Bollinger, RSI/MACD/ADX/MFI/OBV, hỗ trợ/kháng cự, ATR) · **🎯 Khuyến nghị** (MỘT khuyến nghị theo khung đa lớp: bộ lọc loại trừ, điểm Q/V/G/T, ma trận F × T) |
| 📑 **Báo cáo & Chỉ số tài chính** | KQKD / CĐKT / LCTT nhiều năm hoặc theo quý, **nguồn của từng ô**, bảng gốc từng nguồn, tải Excel · ~40 chỉ số tính từ BCTC, DuPont, Piotroski F-score, Altman Z''-score |
| 📚 **Tài liệu BCTN & BCTC** | Dò tìm và tải báo cáo thường niên / BCTC PDF theo năm (Vietstock, CafeF, kho Zenodo, website DN, tải lên thủ công), trích số liệu từ PDF (kể cả bản scan nếu cài OCR) |
| 📰 **Tin tức doanh nghiệp** | Tin đa nguồn (vnstock, Google News RSS, CafeF, VnExpress…), lọc tin không liên quan, phân loại Tích cực / Trung tính / Tiêu cực, lưu theo ngày |
| 🔎 **Lọc & So sánh cổ phiếu** | Bộ lọc theo chỉ số + bộ lọc mẫu (Value, Growth, Quality, Cổ tức, Momentum), xếp hạng tổng hợp · So sánh 2–5 mã |
| 💼 **Danh mục & Theo dõi** | Danh mục theo dõi + cảnh báo giá/%/RSI · Quản lý danh mục (lãi/lỗ, phân bổ) · Điểm cơ hội đầu tư 0–100 · Backtest khuyến nghị 12 tháng |
| 📄 **Xuất báo cáo PDF** | Báo cáo phân tích một mã: tổng quan, hồ sơ DN, BCTC, chỉ số, so sánh ngành, kỹ thuật, tin tức (có link bấm được), định giá 12T, rủi ro, kết luận; tùy chọn báo cáo cá nhân hóa theo hồ sơ nhà đầu tư |
| 🛰️ **Nguồn dữ liệu** | Trạng thái từng nguồn, nguồn gốc dữ liệu của mỗi mã, nhật ký cập nhật tự động |
| 🎓 **Thuyết minh đề án** | Toàn bộ lý thuyết, công thức, tham số của mô hình (PTCB, PTKT, dự phóng, định giá, 5 trụ cột, khuyến nghị, rủi ro, kiểm chứng); chế độ thuyết trình; ví dụ trực tiếp với mã đang chọn. Nội dung dùng chung với phụ lục PDF (`core/thuyet_minh.py`), tham số đọc từ cấu hình |

---

## 2. Dữ liệu lấy từ đâu

```
GIÁ NGÀY   ┌──── phần cũ hơn 365 ngày ────┐┌──── 365 ngày gần nhất ────┐┌── phiên hôm nay ──┐
           vnstock VCI → KBS → MSN → Vietstock   DNSE (API biểu đồ công khai)   nến tạm từ nến 1 phút DNSE
           • quy về VND • nối 2 đoạn bằng hệ số nếu lệch giá ở phiên trùng • tự sửa bước nhảy chưa điều chỉnh quyền
           • lưu DuckDB; mạng lỗi → dùng giá đã lưu

GIÁ HIỆN TẠI   DNSE → vnstock → Vietstock (nhớ 170 giây)

TRONG PHIÊN    có DNSE_API_KEY + DNSE_API_SECRET → REALTIME qua WebSocket DNSE OpenAPI (khớp lệnh từng giây, trang làm mới
               3 giây/lần) · không có key / mất kết nối / sai key → nến 1 phút DNSE công khai (~3 phút/lần)

BCTC       vnstock VCI → vnstock KBS → Vietstock → arminer (BCTC năm đóng gói sẵn, offline) → PDF đã tải
           • chuẩn hóa về ~45 chỉ tiêu chung • số quý lũy kế → số từng quý • gộp theo thứ tự ưu tiên, ghi nguồn từng ô
           • nguồn phụ lệch > 5% ở quá nửa số ô trùng kỳ (số quý) → loại cả nguồn • lưu DuckDB

KHÁC       thông tin DN, sự kiện quyền, cổ đông, ban lãnh đạo, tin tức: vnstock · cổ tức đã công bố: nhập tay có nguồn
           (config/announced_dividends.json) → vnstock → bảng sự kiện
```

Đổi thứ tự / số ngày trong `.env`: `DNSE_RECENT_DAYS`, `PRICE_HISTORY_SOURCES`, `FINANCIAL_SOURCES`, `DOCUMENT_SOURCES`.

---

## 3. Mô hình phân tích (tóm tắt)

| Khối | File chính | Tóm tắt |
|---|---|---|
| Chỉ số tài chính | `core/phan_tich_co_ban.py` | ~40 chỉ số; kỳ quý dùng TTM; số dư dùng bình quân đầu–cuối kỳ; chất lượng lợi nhuận (LN cốt lõi, phần tăng từ thu nhập tài chính, CFO/FCF, F-score); phát hiện đổi phạm vi hợp nhất |
| Sức khỏe tài chính | `core/phan_tich_co_ban.py` | Điểm 0–100 theo nhóm (phi tài chính: sinh lời 25, tăng trưởng 20, thanh toán 15, cơ cấu vốn 15, dòng tiền 25; ngân hàng/CTCK/bảo hiểm có bộ riêng); trừ điểm chất lượng lợi nhuận |
| Dự báo | `core/du_phong.py` | Dự báo NTM và 5 năm, 3 kịch bản; mô hình riêng cho phi tài chính / ngân hàng / CTCK–bảo hiểm; không nhìn trước dữ liệu |
| Định giá | `core/dinh_gia.py` | P/E forward, P/B–ROE, EV/EBITDA, DCF (FCFF), thu nhập thặng dư (RI), DDM; trọng số theo hồ sơ ngành; loại phương pháp bất thường; Bear/Base/Bull; độ tin cậy Cao/Trung bình/Thấp |
| Rủi ro | `core/khuyen_nghi.py` | Rủi ro từ BCTC & giá; rủi ro nghiêm trọng là điều kiện loại trừ (không MUA/TÍCH LŨY) |
| Khuyến nghị (1 nhãn) | `core/khuyen_nghi.py` | Khung đa lớp: bộ lọc loại trừ → 4 lớp Chất lượng, Định giá, Tăng trưởng, Thời điểm → ma trận F × T: MUA / TÍCH LŨY TỪNG PHẦN / NẮM GIỮ / THEO DÕI / GIẢM TỶ TRỌNG–TRÁNH |
| Kỹ thuật & động lượng | `core/phan_tich_ky_thuat.py`, `core/dinh_gia.py` (beta) | SMA/EMA, RSI, MACD, Bollinger, ATR, ADX, MFI, OBV, CMF; xu hướng theo MA20/50/200; sức mạnh tương đối so với VN-Index; beta có kiểm tra độ tin cậy |
| Điểm cơ hội | `core/khuyen_nghi.py` | Kỹ thuật 25, động lượng 20, cơ bản 25, định giá 20, rủi ro 10 (điểm sàng lọc tham khảo, không phải khuyến nghị) |

Tham số mô hình (ngưỡng, trọng số, Rf, ERP…) nằm ở **`core/cau_hinh.py`** (có thể ghi đè bằng
`config/investment_model.json`). Lãi suất phi rủi ro Rf hiện là **4,43%** (đấu thầu TPCP 10 năm cuối tháng 9/2026, HNX)
– cần cập nhật lại khi số liệu cũ hơn 3 tháng.

---

## 4. Cấu trúc thư mục (gộp 15/10/2026: ~115 file → 21 file Python chính)

```
GPM1/
├── app.py                      # khung app: thanh bên, điều hướng giữa các trang
├── core/                       # TOÀN BỘ LOGIC (không có giao diện)
│   ├── pipeline.py             # ĐIỀU PHỐI: phân tích 1 mã từ đầu đến cuối (StockService.full_analysis)
│   ├── phan_tich_co_ban.py     # chỉ số tài chính, sức khỏe tài chính, phân tích cơ bản, so sánh ngành
│   ├── phan_tich_ky_thuat.py   # chỉ báo kỹ thuật, xu hướng, động lượng
│   ├── du_phong.py             # dự phóng tài chính (Forecast Engine) NTM + 5 năm, 3 kịch bản
│   ├── dinh_gia.py             # Ke/WACC, beta, 6 phương pháp định giá, giá mục tiêu, độ tin cậy
│   ├── khuyen_nghi.py          # khung khuyến nghị đa lớp (1 nhãn), rủi ro, điểm 5 trụ cột, cá nhân hóa
│   ├── tin_tuc.py              # tin tức doanh nghiệp + nhận định tin tức
│   ├── thi_truong_danh_muc.py  # tổng quan thị trường, bộ lọc, danh mục theo dõi, danh mục đầu tư
│   ├── kiem_chung.py           # chiến lược nhóm (tín hiệu RS)
│   ├── bao_cao_pdf.py          # báo cáo PDF (bìa, các mục, phụ lục) + xuất Excel
│   ├── thuyet_minh.py          # nội dung trang Thuyết minh đề án & phụ lục PDF
│   ├── du_lieu.py              # kho dữ liệu: ghép giá, gộp BCTC đa nguồn, chuẩn hóa, cache, DuckDB, danh sách mã
│   ├── nguon_du_lieu.py        # kết nối vnstock, DNSE (cả realtime WebSocket), Vietstock, BCTC đóng gói
│   ├── tai_lieu_bctc.py        # tài liệu BCTN/BCTC: tìm, tải, đọc PDF, OCR
│   └── cau_hinh.py             # cấu hình (.env) + tham số mô hình + hằng số
├── giao_dien/                  # GIAO DIỆN Streamlit
│   ├── chung.py                # CSS, biểu đồ, thẻ, logo, thanh bên, trang gộp
│   ├── thi_truong.py           # Tổng quan thị trường · Phân tích cổ phiếu (4 tab) · Lọc & so sánh
│   ├── doanh_nghiep.py         # Báo cáo & chỉ số tài chính · Tài liệu BCTN/BCTC · Tin tức
│   ├── ca_nhan.py              # Theo dõi · Danh mục · Điểm cơ hội · Xuất PDF · Nguồn dữ liệu
│   └── de_an.py                # Thuyết minh đề án (cả chế độ thuyết trình)
├── config/                     # announced_dividends.json (cổ tức nhập tay có nguồn)
├── data/                       # listed_stocks.json, bundled/ (BCTC đóng gói, giấy phép MIT); cache & CSDL sinh khi chạy
├── assets/                     # phông chữ, ảnh nền báo cáo
├── tools/                      # reco_trend_backtest.py (backtest khuyến nghị) · multilayer_eval.py (chấm kết quả)
└── tests/                      # 5 file kiểm thử theo nhóm + fakes.py (dữ liệu giả cho test)
```

Đầu mỗi file trong `core/` và `giao_dien/` có **MỤC LỤC** liệt kê các phần đã gộp và các hàm/lớp chính. Luồng chính:
`app.py` → `giao_dien/*.py` → `core/pipeline.py` → (`du_lieu` → `phan_tich_co_ban`, `phan_tich_ky_thuat` → `du_phong` →
`dinh_gia` → `khuyen_nghi`) → `bao_cao_pdf`.

Dữ liệu sinh ra khi chạy (không nằm trong bản phát hành): `data/stock_analytics.duckdb` (CSDL), `data/cache/`
(bộ nhớ tạm), `data/documents/` (PDF đã tải), `reports/output/` (PDF đã xuất), `tools/reco_trend_out/` (kết quả backtest).

---

## 5. Kiểm chứng khung khuyến nghị (backtest)

`tools/reco_trend_backtest.py` chạy lại đúng quy trình của app tại các ngày cuối tháng trong quá khứ (không dùng dữ liệu
công bố sau ngày đó) rồi đo lợi nhuận 3/6/12 tháng sau; `tools/multilayer_eval.py` chấm theo mục 9 của khung: lợi nhuận
theo nhãn, Rank IC (theo tháng và mẫu không chồng lấn), chênh lệch nhóm điểm cao/thấp, so với VN-Index, tỷ lệ đổi nhãn.
Khung đa lớp chưa được backtest – kết quả cũ (+23,3% nhóm MUA) là của mô hình R1–R4 đã bỏ.

---

## 6. Giới hạn cần biết

* **vnstock bản Cộng đồng**: 60 lượt gọi/phút, BCTC tối đa 8 kỳ; chạy nhiều mã liên tục sẽ hết lượt (app tự chờ rồi thử lại).
* **Vietstock, CafeF, website DN** không có API chính thức – có thể ngừng hoạt động khi trang đổi cấu trúc; chuỗi dự phòng tự chuyển nguồn.
* Bảng sự kiện quyền của vnstock chỉ trả ~50 sự kiện gần nhất; một số mã không có lịch sử cổ tức → app ước tính từ LCTT khi cần.
* Bất động sản: chưa có RNAV (dữ liệu từng dự án) → độ tin cậy tối đa "Trung bình"; bảo hiểm chưa có P/EV.
* Giấy phép vnstock: dùng cá nhân/học thuật; phân phối lại dữ liệu cho bên thứ ba cần thỏa thuận với tác giả.

## ⚖️ Miễn trừ trách nhiệm
Hệ thống phục vụ **nghiên cứu và học thuật**. Kết quả phân tích, chấm điểm và backtest chỉ mang tính tham khảo,
**không phải khuyến nghị đầu tư**.

### Khung khuyến nghị đa lớp (15/10/2026)
Mỗi mã chỉ có **một nhãn khuyến nghị**: MUA · TÍCH LŨY TỪNG PHẦN · NẮM GIỮ · THEO DÕI · GIẢM TỶ TRỌNG / TRÁNH (hoặc KHÔNG ĐỦ DỮ LIỆU),
từ ma trận điểm cơ bản F = 0,40·Q + 0,35·V + 0,25·G − điểm trừ rủi ro và điểm Thời điểm T (`core/khuyen_nghi.py`,
tham số ở `core/cau_hinh.py` → `multilayer`).
Bộ lọc loại trừ chặn MUA/TÍCH LŨY; điều kiện không có dữ liệu (ý kiến kiểm toán, cảnh báo/kiểm soát, chậm công bố) ghi
"chưa kiểm tra được". Điểm 5 trụ cột giữ làm điểm sàng lọc tham khảo. Ngưỡng 70/55/50 chưa hiệu chỉnh – chạy
`tools/reco_trend_backtest.py` rồi `tools/multilayer_eval.py` để kiểm chứng.
