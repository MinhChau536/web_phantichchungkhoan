"""
core/thuyet_minh.py – gộp từ 1 module (15/10/2026).

MỤC LỤC
  • services/thesis_content.py – NỘI DUNG THUYẾT MINH ĐỀ ÁN – dùng chung cho trang "🎓 Thuyết Minh Đề Án" (pages/thesis.py) và phụ lục báo cáo PDF.
      hàm/lớp chính: s_overview, s_pages, s_fundamental, s_technical, s_forecast, s_valuation, s_pillars, s_recommendation, s_risk, s_validation, sections, explain_symbol …
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: services/thesis_content.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
NỘI DUNG THUYẾT MINH ĐỀ ÁN – dùng chung cho trang "🎓 Thuyết Minh Đề Án" (giao_dien/de_an.py) và phụ lục báo cáo PDF.

Mọi con số tham số (trọng số 5 trụ cột, trọng số phương pháp theo ngành, ngưỡng khuyến nghị, Rf, ERP, kịch bản, chu kỳ chỉ
báo kỹ thuật…) được ĐỌC TỪ CẤU HÌNH của mô hình (core/cau_hinh.py, core/cau_hinh.py)
– không gõ tay – nên khi đổi tham số, thuyết minh tự khớp với app.

Mỗi mục: {"key", "title", "icon", "pitch": [ý chính để thuyết trình], "blocks": [...]}
Khối nội dung:
  ("h", tiêu đề nhỏ) · ("p", đoạn văn – cho phép **đậm**) · ("ul", [ý]) ·
  ("f", công thức LaTeX, công thức dạng chữ (cho PDF), chú thích) · ("t", [tiêu đề cột], [[ô]]) · ("note", ghi chú)
"""


from typing import Any, Dict, List, Optional


def _pct(x: Optional[float], d: int = 1) -> str:
    if x is None:
        return "—"
    s = f"{x * 100:.{d}f}".replace(".", ",")
    return s + "%"


def _num(x: Any, d: int = 0) -> str:
    try:
        s = f"{float(x):,.{d}f}"
    except (TypeError, ValueError):
        return "—"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _cfg() -> Dict[str, Any]:
    from core.cau_hinh import load_config
    return load_config()


METHOD_LABEL = {"pe": "P/E Forward", "pb": "P/B – ROE", "ev_ebitda": "EV/EBITDA", "dcf": "DCF (FCFF)",
                "ri": "Thu nhập thặng dư (RI)", "ddm": "Chiết khấu cổ tức 2 giai đoạn (DDM)"}
PILLAR_LABEL = {"fundamental": "Cơ bản", "valuation": "Định giá", "technical": "Kỹ thuật", "momentum": "Động lượng",
                "risk": "Quản trị rủi ro"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tổng quan
# ─────────────────────────────────────────────────────────────────────────────

def s_overview() -> Dict[str, Any]:
    return {
        "key": "overview", "icon": "🧭", "title": "Tổng quan đề án",
        "pitch": [
            "Ứng dụng web phân tích cổ phiếu Việt Nam: từ dữ liệu thô → chỉ số → định giá → khuyến nghị → báo cáo PDF.",
            "Dữ liệu thật đa nguồn (DNSE realtime, vnstock, BCTC, PDF) – tự chuẩn hóa, ghi nguồn từng ô số liệu.",
            "Định giá 12 tháng bằng 6 phương pháp, trọng số theo ngành, có độ tin cậy và 3 kịch bản.",
            "MỘT khuyến nghị theo khung đa lớp: bộ lọc loại trừ → Chất lượng, Định giá, Tăng trưởng, Thời điểm → ma trận F × T.",
            "Có công cụ backtest không nhìn trước để kiểm chứng khung khuyến nghị (cần chạy lại trước khi công bố hiệu quả).",
        ],
        "blocks": [
            ("h", "Mục tiêu"),
            ("p", "Xây dựng một hệ thống hỗ trợ ra quyết định đầu tư cổ phiếu Việt Nam theo quy trình của một chuyên viên "
                  "phân tích: thu thập dữ liệu → phân tích cơ bản → phân tích kỹ thuật → dự phóng → định giá → đánh giá rủi "
                  "ro → khuyến nghị, trong đó **mọi con số đều truy được nguồn và công thức**, và mô hình được **kiểm chứng "
                  "lại trên dữ liệu quá khứ**."),
            ("h", "Luồng xử lý"),
            ("t", ["Bước", "Nội dung", "Kết quả"], [
                ["1. Dữ liệu", "Giá (DNSE + vnstock/Vietstock), BCTC (vnstock VCI/KBS, Vietstock, BCTC đóng gói, PDF), "
                               "sự kiện quyền, cổ tức, tin tức", "Chuỗi giá đã điều chỉnh, BCTC chuẩn hóa ~45 chỉ tiêu"],
                ["2. Phân tích cơ bản", "~40 chỉ số từ BCTC, F-score, Z''-score, chất lượng lợi nhuận",
                 "Financial Health Score 0–100"],
                ["3. Phân tích kỹ thuật", "MA, RSI, MACD, Bollinger, ADX, ATR, dòng tiền, khối lượng, RS",
                 "Xu hướng & điểm kỹ thuật, mức cắt lỗ"],
                ["4. Dự phóng", "Forecast Engine theo ngành: NTM + 5 năm, 3 kịch bản", "EPS, EBITDA, FCFF, BVPS, DPS dự phóng"],
                ["5. Định giá", "6 phương pháp, trọng số theo hồ sơ ngành, Ke theo CAPM", "Giá mục tiêu, độ tin cậy"],
                ["6. Rủi ro", "Suy giảm KD, đòn bẩy, dòng tiền, pha loãng, định giá, dữ liệu, thị trường",
                 "Mức rủi ro Thấp → Nghiêm trọng"],
                ["7. Khuyến nghị", "Khung đa lớp: bộ lọc loại trừ + 4 lớp Q/V/G/T + ma trận F × T",
                 "MỘT nhãn: MUA / TÍCH LŨY TỪNG PHẦN / NẮM GIỮ / THEO DÕI / GIẢM TỶ TRỌNG–TRÁNH"],
                ["8. Báo cáo", "PDF kiểu báo cáo CTCK, cá nhân hóa theo hồ sơ nhà đầu tư", "Báo cáo phân tích 1 mã"],
            ]),
            ("h", "Nguyên tắc thiết kế"),
            ("ul", [
                "**Không bịa số**: thiếu dữ liệu → để trống và nêu lý do; không thay bằng số giả định ngầm.",
                "**Không nhìn trước (no look-ahead)**: định giá/dự phóng tại một ngày chỉ dùng BCTC đã công bố trước ngày đó "
                "(độ trễ công bố quý, năm cấu hình được).",
                "**Giải thích được**: mỗi điểm số có bảng thành phần, mỗi giá mục tiêu có công thức và nguồn số liệu.",
                "**Tham số tập trung**: mọi ngưỡng, trọng số nằm ở core/cau_hinh.py – sửa không cần đổi code.",
                "**Kiểm chứng**: quy tắc đặt trước, chạy backtest sau; không chỉnh tham số theo kết quả.",
            ]),
            ("h", "Công nghệ"),
            ("p", "Python · Streamlit (giao diện) · pandas/numpy (tính toán) · DuckDB (CSDL phân tích) · DiskCache (bộ nhớ "
                  "tạm) · Matplotlib/Plotly (biểu đồ) · fpdf2 (báo cáo PDF) · WebSocket DNSE OpenAPI (giá realtime) · "
                  "vnstock (dữ liệu thị trường) · pypdf/OCR (đọc BCTC PDF) · pytest (hơn 360 kiểm thử tự động)."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Chức năng từng trang
# ─────────────────────────────────────────────────────────────────────────────

PAGES = [
    ("🏛️ Tổng Quan Thị Trường", "Tổng quan thị trường",
     "Thẻ VN-Index, VN30, HNX, UPCoM (realtime trong phiên), biểu đồ nến chỉ số + MA20/MA50, độ rộng thị trường, bản đồ "
     "nhiệt theo ngành, top tăng/giảm/giá trị/khối lượng đột biến, cổ phiếu đang theo dõi.",
     "Nắm bối cảnh chung trước khi xem từng mã; VN-Index so với MA50 là đầu vào của 'thời điểm' trong khuyến nghị."),
    ("🔍 Phân Tích Cổ Phiếu", "Phân tích cổ phiếu",
     "4 mục: 💰 Định giá (giá mục tiêu, Bear/Base/Bull, độ nhạy, độ tin cậy) · 📊 Cơ bản (Financial Health Score, "
     "chất lượng lợi nhuận, so sánh ngành) · 📈 Kỹ thuật (biểu đồ, chỉ báo, hỗ trợ/kháng cự, ATR) · 🎯 Khuyến nghị "
     "(khung đa lớp – một nhãn duy nhất từ ma trận F × T).",
     "Trang trung tâm – toàn bộ quy trình phân tích một mã."),
    ("🔎 Lọc & So Sánh Cổ Phiếu", "Lọc và so sánh",
     "Bộ lọc theo chỉ số và bộ lọc mẫu (Value, Growth, Quality, Cổ tức, Momentum), xếp hạng tổng hợp; so sánh 2–5 mã "
     "cạnh nhau.", "Tìm ý tưởng đầu tư, chọn mã đáng phân tích sâu."),
    ("📑 Báo Cáo & Chỉ Số Tài Chính", "Chỉ số tài chính",
     "KQKD / CĐKT / LCTT nhiều năm hoặc theo quý (ghi nguồn từng ô), ~40 chỉ số, DuPont, Piotroski F-score, Altman "
     "Z''-score, tải Excel.", "Kiểm tra số liệu gốc mà định giá và chấm điểm đang dùng."),
    ("📚 Tài Liệu BCTN & BCTC", "Tài liệu BCTN, BCTC",
     "Dò và tải báo cáo thường niên / BCTC PDF (Vietstock, CafeF, kho Zenodo, website DN, tải lên tay), trích số liệu từ "
     "PDF kể cả bản scan (OCR).", "Bổ sung kỳ BCTC mà nguồn trực tuyến thiếu; đối chiếu số liệu."),
    ("📰 Tin Tức Doanh Nghiệp", "Tin tức doanh nghiệp",
     "Tin đa nguồn, lọc tin không liên quan, phân loại Tích cực / Trung tính / Tiêu cực theo từ điển từ khóa.",
     "Theo dõi sự kiện có thể làm thay đổi giả định định giá."),
    ("💼 Danh Mục & Theo Dõi", "Danh mục theo dõi",
     "Danh mục theo dõi + cảnh báo giá/%/RSI, quản lý danh mục (lãi/lỗ, phân bổ), Điểm cơ hội đầu tư 0–100 (5 trụ cột, "
     "sàng lọc tham khảo).", "Quản lý vị thế."),
    ("📄 Xuất Báo Cáo PDF", "Xuất báo cáo PDF",
     "Báo cáo phân tích 1 mã kiểu CTCK: tổng quan, hồ sơ DN, BCTC, chỉ số, so sánh ngành, kỹ thuật, tin tức, định giá 12T, "
     "rủi ro, kết luận, phụ lục phương pháp; tùy chọn cá nhân hóa theo hồ sơ nhà đầu tư.", "Sản phẩm đầu ra để chia sẻ."),
    ("🛰️ Nguồn Dữ Liệu", "Nguồn dữ liệu",
     "Trạng thái từng nguồn, giá realtime DNSE, nguồn gốc dữ liệu của mỗi mã (đoạn giá nào từ nguồn nào), nhật ký cập nhật "
     "tự động.", "Minh bạch dữ liệu – kiểm tra khi số liệu có vẻ bất thường."),
    ("🎓 Thuyết Minh Đề Án", "Thuyết minh đề án",
     "Toàn bộ lý thuyết, công thức, tham số của mô hình; ví dụ trực tiếp với mã đang chọn.", "Trình bày / bảo vệ đề án."),
]


def s_pages() -> Dict[str, Any]:
    return {
        "key": "pages", "icon": "🗂️", "title": "Chức năng từng trang",
        "pitch": [
            "10 trang, chia 4 nhóm: Thị trường · Dữ liệu doanh nghiệp · Cá nhân · Đề án.",
            "Trang trung tâm: Phân tích cổ phiếu (Định giá · Cơ bản · Kỹ thuật · Khuyến nghị).",
            "Mọi trang dùng chung một mã đang chọn ở thanh bên trái.",
        ],
        "blocks": [("t", ["Trang", "Nội dung", "Dùng để"], [[p[1], p[2], p[3]] for p in PAGES])],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Phân tích cơ bản
# ─────────────────────────────────────────────────────────────────────────────

def s_fundamental() -> Dict[str, Any]:
    c = _cfg()
    hw = c["health"]["weights"]
    nf = hw["nonfinancial"]
    an = c["anchors"]
    fp, ncp = c["health"]["fscore_penalty"], c["health"]["non_core_penalty"]
    return {
        "key": "fundamental", "icon": "📊", "title": "Phân tích cơ bản (PTCB)",
        "pitch": [
            "~40 chỉ số tính TRỰC TIẾP từ BCTC chuẩn hóa (không lấy chỉ số làm sẵn của nguồn).",
            f"Financial Health Score 0–100: Sinh lời {nf['profitability']}% · Tăng trưởng {nf['growth']}% · Thanh toán "
            f"{nf['liquidity']}% · Cơ cấu vốn {nf['leverage']}% · Dòng tiền {nf['cashflow']}%.",
            "Ngân hàng, chứng khoán, bảo hiểm có bộ chỉ tiêu và trọng số riêng.",
            "Chất lượng lợi nhuận: lợi nhuận tăng nhờ đâu (cốt lõi hay tài chính) và có thành tiền không (CFO, FCF, F-score).",
        ],
        "blocks": [
            ("h", "Chỉ số chính"),
            ("f", r"ROE=\frac{\text{LNST cổ đông mẹ}}{\overline{\text{VCSH}}}\qquad ROA=\frac{\text{LNST}}{\overline{\text{Tổng tài sản}}}",
             "ROE = LNST mẹ / VCSH bình quân; ROA = LNST / Tổng tài sản bình quân", "Số dư dùng bình quân đầu–cuối kỳ"),
            ("f", r"ROIC=\frac{EBIT\,(1-t)}{\text{VCSH}+\text{Nợ vay}-\text{Tiền}-\text{ĐTTC ngắn hạn}}",
             "ROIC = EBIT×(1−t) / (VCSH + Nợ vay − Tiền − ĐTTC ngắn hạn)", "Hiệu quả vốn đầu tư vào hoạt động kinh doanh"),
            ("f", r"ROE=\underbrace{\frac{LNST}{DT}}_{\text{biên ròng}}\times\underbrace{\frac{DT}{TTS}}_{\text{vòng quay TS}}"
                  r"\times\underbrace{\frac{TTS}{VCSH}}_{\text{đòn bẩy}}",
             "DuPont: ROE = Biên ròng × Vòng quay tài sản × Đòn bẩy", "Phân rã nguồn gốc ROE"),
            ("f", r"\text{Biên gộp}=\frac{\text{LN gộp}}{\text{DT}},\ \ \text{Biên EBITDA}=\frac{\text{EBIT}+\text{KH}}{\text{DT}},\ \ "
                  r"\text{LN cốt lõi}=\text{LN gộp}-\text{CP bán hàng}-\text{CP quản lý}",
             "Biên gộp = LN gộp/DT; Biên EBITDA = (EBIT + khấu hao)/DT; LN cốt lõi = LN gộp − CP bán hàng − CP quản lý", ""),
            ("f", r"\text{TT hiện hành}=\frac{\text{TSNH}}{\text{Nợ NH}},\ \ \text{TT nhanh}=\frac{\text{TSNH}-\text{HTK}}{\text{Nợ NH}},\ \ "
                  r"\frac{\text{Nợ vay}}{\text{VCSH}},\ \ \frac{\text{EBIT}}{\text{Lãi vay}}",
             "TT hiện hành = TSNH/Nợ NH; TT nhanh = (TSNH − HTK)/Nợ NH; Nợ vay/VCSH; EBIT/Lãi vay", ""),
            ("f", r"CCC=\underbrace{\frac{\overline{PT}}{DT}365}_{DSO}+\underbrace{\frac{\overline{HTK}}{GVHB}365}_{DIO}"
                  r"-\underbrace{\frac{\overline{PTNB}}{GVHB}365}_{DPO}",
             "Chu kỳ tiền mặt CCC = DSO + DIO − DPO (ngày)", ""),
            ("f", r"FCF=CFO-\text{Capex},\qquad \frac{CFO}{LNST}",
             "FCF = CFO − Capex; CFO/LNST đo mức lợi nhuận thành tiền", "CFO/LNST < 1 kéo dài → lợi nhuận chưa thành tiền"),
            ("h", "Piotroski F-score (0–9)"),
            ("p", "Mỗi tiêu chí đạt được 1 điểm (so năm gần nhất với năm trước): ROA > 0 · CFO > 0 · ROA tăng · CFO > LNST · "
                  "Nợ vay dài hạn/TTS giảm · Thanh toán hiện hành tăng · Không phát hành cổ phiếu thu tiền (cổ phiếu thưởng "
                  "không bị trừ) · Biên gộp tăng · Vòng quay tài sản tăng. **≥ 7 mạnh, ≤ 3 yếu.**"),
            ("h", "Altman Z''-score (thị trường mới nổi)"),
            ("f", r"Z''=3{,}25+6{,}56X_1+3{,}26X_2+6{,}72X_3+1{,}05X_4",
             "Z'' = 3,25 + 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4",
             "X1 = VLĐ/TTS; X2 = LN giữ lại/TTS; X3 = EBIT/TTS; X4 = VCSH/Tổng nợ. > 5,85 an toàn; 4,35–5,85 cảnh báo; "
             "< 4,35 nguy cơ kiệt quệ. Không áp dụng cho ngân hàng."),
            ("h", "Financial Health Score (0–100)"),
            ("p", "Mỗi chỉ tiêu được quy về thang 0–100 bằng **nội suy tuyến tính giữa ngưỡng 'kém' (0 điểm) và 'tốt' "
                  "(100 điểm)**, ngưỡng điều chỉnh theo ngành; điểm nhóm = trung bình chỉ tiêu; điểm tổng = bình quân gia "
                  "quyền các nhóm. Thiếu dữ liệu → loại khỏi mẫu số; thiếu nhóm bắt buộc hoặc độ phủ < "
                  f"{_pct(c['health']['min_coverage'], 0)} → không công bố điểm."),
            ("f", r"\text{điểm}(x)=100\times\frac{x-x_{\text{kém}}}{x_{\text{tốt}}-x_{\text{kém}}}\ \ (\text{chặn }0\text{–}100)",
             "điểm(x) = 100 × (x − ngưỡng kém) / (ngưỡng tốt − ngưỡng kém), chặn trong 0–100", ""),
            ("t", ["Loại doanh nghiệp", "Nhóm & trọng số"], [
                ["Phi tài chính", ", ".join(f"{_GL[k]} {v}%" for k, v in hw["nonfinancial"].items())],
                ["Ngân hàng", ", ".join(f"{_GL[k]} {v}%" for k, v in hw["bank"].items())],
                ["Chứng khoán", ", ".join(f"{_GL[k]} {v}%" for k, v in hw["securities"].items())],
                ["Bảo hiểm", ", ".join(f"{_GL[k]} {v}%" for k, v in hw["insurance"].items())],
            ]),
            ("t", ["Chỉ tiêu (phi tài chính)", "Ngưỡng kém → tốt"], [
                ["ROE (%)", f"{an['roe'][0]:g} → {an['roe'][1]:g}"], ["ROA (%)", f"{an['roa'][0]:g} → {an['roa'][1]:g}"],
                ["Biên LN ròng (%)", f"{an['net_margin'][0]:g} → {an['net_margin'][1]:g}"],
                ["Tăng trưởng doanh thu (%)", f"{an['revenue_growth'][0]:g} → {an['revenue_growth'][1]:g}"],
                ["Tăng trưởng LN cốt lõi (%)", f"{an['core_profit_growth'][0]:g} → {an['core_profit_growth'][1]:g}"],
                ["Thanh toán hiện hành (x)", f"{an['current_ratio'][0]:g} → {an['current_ratio'][1]:g}"],
                ["Nợ vay/VCSH (x, thấp là tốt)", f"{an['debt_to_equity'][0]:g} → {an['debt_to_equity'][1]:g}"],
                ["EBIT/Lãi vay (x)", f"{an['interest_coverage'][0]:g} → {an['interest_coverage'][1]:g}"],
                ["CFO/LNST (x)", f"{an['cfo_to_net_income'][0]:g} → {an['cfo_to_net_income'][1]:g}"],
                ["Biên FCF (%)", f"{an['fcf_margin'][0]:g} → {an['fcf_margin'][1]:g}"],
            ]),
            ("h", "Chất lượng lợi nhuận"),
            ("p", "So sánh 2 năm gần nhất: tăng trưởng LN cốt lõi so với LNST, phần mức tăng LN thuần HĐKD đến từ thu nhập "
                  "tài chính/khác, biên gộp giảm liên tiếp, CP bán hàng tăng nhanh hơn doanh thu, CFO/FCF giảm, F-score. "
                  f"Trừ thẳng vào Health Score: F-score ≤ {fp['max_score']} → −{fp['points']:g} điểm; ≥ "
                  f"{ncp['min_share']:g}% mức tăng LN HĐKD từ tài chính/khác → −{ncp['points']:g} điểm."),
        ],
    }


_GL = {"profitability": "Sinh lời", "growth": "Tăng trưởng", "liquidity": "Thanh toán", "leverage": "Cơ cấu vốn",
       "cashflow": "Dòng tiền", "capital": "An toàn vốn", "asset_quality": "Chất lượng tài sản",
       "funding": "Huy động & cho vay"}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Phân tích kỹ thuật
# ─────────────────────────────────────────────────────────────────────────────

def s_technical() -> Dict[str, Any]:
    import core.cau_hinh as k
    return {
        "key": "technical", "icon": "📈", "title": "Phân tích kỹ thuật (PTKT)",
        "pitch": [
            "Chỉ báo xu hướng (MA20/50/200, ADX), động lượng (RSI, MACD), biến động (Bollinger, ATR), dòng tiền (MFI, CMF, "
            "OBV, khối lượng).",
            "Xu hướng tổng hợp: giá so với MA20 (×1), MA50 (×2), MA200 (×3) và MA20 so với MA50 → Tăng mạnh … Giảm mạnh.",
            "Kỹ thuật CHỈ quyết định THỜI ĐIỂM mua/bán, không đảo ngược khuyến nghị 12 tháng.",
            "Cắt lỗ tham khảo = Giá − 2 × ATR(14).",
        ],
        "blocks": [
            ("h", "Chỉ báo & công thức"),
            ("f", r"SMA_n=\frac{1}{n}\sum_{i=0}^{n-1}P_{t-i}\qquad EMA_t=\alpha P_t+(1-\alpha)EMA_{t-1},\ \alpha=\frac{2}{n+1}",
             "SMA_n = trung bình n phiên; EMA_t = α·P_t + (1−α)·EMA_(t−1), α = 2/(n+1)",
             f"MA {', '.join(str(x) for x in k.SMA_PERIODS)} phiên"),
            ("f", r"RSI=100-\frac{100}{1+RS},\quad RS=\frac{\text{TB lãi}_{14}}{\text{TB lỗ}_{14}}\ (\text{làm trơn Wilder})",
             "RSI = 100 − 100/(1 + RS), RS = trung bình phiên tăng / trung bình phiên giảm (14 phiên, Wilder)",
             f"> {k.RSI_OVERBOUGHT} quá mua, < {k.RSI_OVERSOLD} quá bán"),
            ("f", rf"MACD=EMA_{{{k.MACD_FAST}}}-EMA_{{{k.MACD_SLOW}}},\quad Signal=EMA_{{{k.MACD_SIGNAL}}}(MACD),\quad "
                  r"Hist=MACD-Signal",
             f"MACD = EMA{k.MACD_FAST} − EMA{k.MACD_SLOW}; Signal = EMA{k.MACD_SIGNAL}(MACD); Histogram = MACD − Signal", ""),
            ("f", rf"BB=SMA_{{{k.BB_PERIOD}}}\pm {k.BB_STD}\sigma_{{{k.BB_PERIOD}}},\qquad \%B=\frac{{P-BB_{{\text{{dưới}}}}}}{{BB_{{\text{{trên}}}}-BB_{{\text{{dưới}}}}}}",
             f"Bollinger = SMA{k.BB_PERIOD} ± {k.BB_STD}σ; %B = (P − dải dưới)/(dải trên − dải dưới)", ""),
            ("f", r"TR=\max(H-L,|H-C_{t-1}|,|L-C_{t-1}|),\quad ATR_{14}=\text{Wilder}(TR)",
             "TR = max(H − L, |H − C trước|, |L − C trước|); ATR14 = trung bình Wilder của TR", "Biên độ dao động; dùng cho cắt lỗ"),
            ("f", r"ADX=\text{Wilder}\left(100\frac{|{+DI}-{-DI}|}{{+DI}+{-DI}}\right)",
             "ADX = trung bình Wilder của 100·|+DI − −DI|/(+DI + −DI)", "ADX ≥ 25: xu hướng mạnh; +DI > −DI: phe mua chiếm ưu thế"),
            ("f", r"MFI=100-\frac{100}{1+\frac{\sum MF^+}{\sum MF^-}},\quad CMF=\frac{\sum\frac{(C-L)-(H-C)}{H-L}V}{\sum V}",
             "MFI = RSI có trọng số khối lượng (14 phiên); CMF = Σ[((C−L)−(H−C))/(H−L)·V]/ΣV (20 phiên)", "Dòng tiền vào/ra"),
            ("f", r"RelVol=\frac{V_t}{\overline{V}_{20}},\qquad RS_{6T}=r_{\text{cổ phiếu}}-r_{\text{VN-Index}}",
             "Khối lượng tương đối = KL phiên / KL TB 20 phiên; Sức mạnh tương đối 6 tháng = lợi suất cổ phiếu − lợi suất VN-Index", ""),
            ("h", "Điểm kỹ thuật (0–100)"),
            ("t", ["Thành phần", "Điểm tối đa", "Cách chấm"], [
                ["Giá so với MA", "25", "Giá > SMA200 (10) · > SMA50 (8) · > SMA20 (7)"],
                ["RSI(14)", "15", "50–70: 15 · 40–50 hoặc 70–80: 8 · 30–40: 4 · > 80 hoặc < 30: 0"],
                ["MACD histogram", "15", "Dương & tăng: 15 · dương: 9 · âm nhưng tăng: 6 · âm & giảm: 0"],
                ["Khối lượng tương đối", "10", "> 1,5: 10 · > 1,0: 7 · > 0,7: 3 · còn lại 0"],
                ["Vị trí Bollinger", "10", "Nửa trên dải: 10 · nửa dưới: 5 · vượt dải trên: 4 · thủng dải dưới: 0"],
                ["ADX & hướng DI", "10", "ADX ≥ 25: tăng 10 / giảm 0 · 20–25: 6 / 2 · < 20: 4"],
                ["Dòng tiền", "15", "CMF (5) + MFI (5) + OBV so với SMA20 (5)"],
            ]),
            ("note", "Thành phần thiếu dữ liệu bị loại khỏi cả tử số và mẫu số (không gán 0)."),
            ("h", "Xu hướng tổng hợp"),
            ("p", "Điểm xu hướng = ±1 (giá vs SMA20) ±2 (vs SMA50) ±3 (vs SMA200) ±1 (SMA20 vs SMA50). ≥ 3: **Tăng mạnh** · "
                  "> 0: **Tăng** · 0: **Đi ngang** · > −3: **Giảm** · ≤ −3: **Giảm mạnh**."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Dự phóng
# ─────────────────────────────────────────────────────────────────────────────

def s_forecast() -> Dict[str, Any]:
    f = _cfg()["forecast"]
    gb = f["growth_bounds"]
    sb = f["scenario_bands"]
    return {
        "key": "forecast", "icon": "🔮", "title": "Dự phóng tài chính (Forecast Engine)",
        "pitch": [
            f"Mô hình động lực (driver-based) theo ngành, dự phóng NTM (12 tháng tới) và {f['years']} năm, 3 kịch bản.",
            f"Tăng trưởng năm 1 = {f['w_hist']:.0%} trung vị lịch sử + {1 - f['w_hist']:.0%} TTM, co về dài hạn, chặn "
            f"{gb[0]:+.0%}…{gb[1]:+.0%}.",
            "Khoảng Bear/Bull lấy từ phân vị 20/80 của SAI SỐ dự phóng thực tế (backtest ~1.500 mã-năm).",
            "Đầu ra phục vụ trực tiếp từng phương pháp định giá (EPS, EBITDA, FCFF, BVPS, DPS).",
        ],
        "blocks": [
            ("t", ["Loại DN", "Chuỗi dự phóng"], [
                ["Phi tài chính", "Doanh thu → biên EBITDA → khấu hao → EBIT → lãi vay → LNTT → thuế → LNST → EPS; "
                                  "FCFF = EBIT(1−t) + KH − Capex − ΔVLĐ"],
                ["Ngân hàng", "Tổng thu nhập hoạt động (theo dư nợ) → LN trước dự phòng → CP dự phòng = chi phí tín dụng × "
                              "dư nợ bình quân → LNTT"],
                ["Chứng khoán / Bảo hiểm", "LNST mẹ = ROE chuẩn hóa (trung vị lịch sử) × VCSH đầu kỳ"],
            ]),
            ("f", r"g_1=s\cdot\big[w\,\tilde g_{\text{lịch sử}}+(1-w)\,g_{TTM}\big]+(1-s)\,g_{\text{dài hạn}}",
             "g1 = s × [w × trung vị tăng trưởng lịch sử + (1 − w) × tăng trưởng TTM] + (1 − s) × g dài hạn",
             f"w = {f['w_hist']}, s = {f['growth_shrink']} (DN tăng trưởng đều: {f['growth_shrink_consistent']}; "
             f"g < 0: {f['growth_shrink_negative']}); sau đó giảm tuyến tính về g dài hạn ở năm {f['years']}"),
            ("f", r"VCSH_{t}=VCSH_{t-1}+LNST^{\text{mẹ}}_t\,(1-\text{tỷ lệ chia cổ tức}),\qquad EPS_t=\frac{LNST^{\text{mẹ}}_t}{\text{Số CP}}",
             "VCSH_t = VCSH_(t−1) + LNST mẹ × (1 − tỷ lệ chia cổ tức); EPS = LNST mẹ / số CP", ""),
            ("f", r"X_{NTM}=X_{1}+\frac{m}{12}\,(X_{2}-X_{1})",
             "Chỉ tiêu NTM = năm 1 + (số tháng đã qua kể từ kỳ gốc / 12) × (năm 2 − năm 1)", "Nội suy 12 tháng tới tính từ ngày phân tích"),
            ("t", ["Nhóm", "Tăng trưởng P20 → P80", "Biên P20 → P80", "Số quan sát"], [
                [n, (f"{b['growth']['lo']:+.1%} → {b['growth']['hi']:+.1%}" if "growth" in b else "—"),
                 (f"{b['margin']['lo']:+.1%} → {b['margin']['hi']:+.1%}" if "margin" in b else
                  (f"ROE {b['roe']['lo']:+.1%} → {b['roe']['hi']:+.1%}" if "roe" in b else "—")), str(b.get("n", ""))]
                for n, b in sb.items()]),
            ("note", "Không nhìn trước: chỉ dùng BCTC công bố trước ngày dự phóng; thiếu số liệu gốc → chỉ tiêu để trống kèm "
                     "lý do. Sai số dự phóng LNST của chính mã (backtest) được dùng để chấm độ tin cậy định giá."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. Định giá
# ─────────────────────────────────────────────────────────────────────────────

def s_valuation() -> Dict[str, Any]:
    v = _cfg()["valuation"]
    profs = v["method_profiles"]
    tg = v["terminal_growth"]
    sc = v["scenarios"]
    rows = []
    for key, p in profs.items():
        w = ", ".join(f"{METHOD_LABEL.get(m, m)} {x}%" for m, x in sorted(p["weights"].items(), key=lambda kv: -kv[1]))
        note = "; ".join(f"không {METHOD_LABEL.get(m, m)}" for m in (p.get("excluded") or {}))
        if p.get("max_confidence"):
            note += ("; " if note else "") + f"độ tin cậy tối đa {p['max_confidence']}"
        rows.append([p["label"], w, note or "—"])
    return {
        "key": "valuation", "icon": "💰", "title": "Định giá & giá mục tiêu",
        "pitch": [
            f"Chi phí vốn chủ theo CAPM: Ke = Rf ({_pct(v['risk_free'], 2)}) + β (điều chỉnh Blume) × ERP "
            f"({_pct(v['equity_premium'], 0)}), chặn {_pct(v['ke_bounds'][0], 0)}–{_pct(v['ke_bounds'][1], 0)}.",
            "6 phương pháp: P/E Forward, P/B–ROE, Thu nhập thặng dư, EV/EBITDA, DCF (FCFF), Chiết khấu cổ tức 2 giai đoạn.",
            "Trọng số theo HỒ SƠ NGÀNH (9 hồ sơ) – phương pháp không hợp lệ bị loại, trọng số chuẩn hóa lại.",
            "Giá mục tiêu (kỳ hạn 12 tháng) = Σ trọng số × giá trị từng phương pháp; kèm 3 kịch bản, độ nhạy và ĐỘ TIN CẬY (Cao/Trung bình/Thấp).",
            "Độ tin cậy Thấp → 'CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ': không đưa ra giá mục tiêu, số mô hình chỉ là giá trị tham khảo.",
            "Điểm Định giá (thẻ điểm) khi độ tin cậy thấp: 50% so với lịch sử 5 năm + 50% trung vị ngành theo vốn hóa; bỏ P/B nếu hồ sơ ngành loại P/B.",
        ],
        "blocks": [
            ("h", "Chi phí vốn"),
            ("f", r"K_e=R_f+\beta_{adj}\times ERP,\qquad \beta_{adj}=0{,}67\,\beta+0{,}33",
             "Ke = Rf + β điều chỉnh × ERP; β điều chỉnh (Blume) = 0,67 × β + 0,33",
             f"Rf = {_pct(v['risk_free'], 2)} ({v.get('risk_free_source') or 'chưa ghi nguồn'}; ngày "
             f"{v.get('risk_free_as_of') or '—'}); ERP = {_pct(v['equity_premium'], 0)}; β hồi quy lợi suất ngày so với "
             f"VN-Index 1 năm, chặn {v['beta_bounds'][0]}–{v['beta_bounds'][1]}"),
            ("f", r"WACC=\frac{E}{D+E}K_e+\frac{D}{D+E}K_d(1-t)",
             "WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1 − t)", f"Kd chặn {_pct(v['kd_bounds'][0], 0)}–{_pct(v['kd_bounds'][1], 0)}; dùng cho DCF"),
            ("h", "Các phương pháp"),
            ("f", r"\begin{gathered}P_{PE}=EPS_{NTM}\times (P/E)^*\\ (P/E)^*=\text{trung vị}\big(\text{P/E lịch sử có trọng số},\ \text{P/E ngành}\big)\end{gathered}",
             "Giá P/E = EPS NTM × P/E tham chiếu; P/E tham chiếu = trung vị (P/E lịch sử có trọng số theo độ gần, P/E trung vị ngành)",
             f"Trọng số năm gần nhất 1, năm trước {v['multiple_recency_decay']}…; trần {v['pe_peer_cap']} × P/E ngành; "
             "rủi ro cao ×0,9; tăng trưởng âm ×0,9"),
            ("f", r"\begin{gathered}P_{PB}=BVPS_{T+12}\times(P/B)^*\\ (P/B)^*=1+\sum_{t=1}^{5}\frac{ROE-K_e}{(1+K_e)^t}"
                  r"+\frac{ROE_{\infty}-K_e}{(K_e-g)(1+K_e)^5}\end{gathered}",
             "Giá P/B = BVPS tại ngày mục tiêu × P/B hợp lý 2 giai đoạn: 1 + Σ PV(ROE − Ke) trong 5 năm + PV[(ROE dài hạn − Ke)/(Ke − g)]",
             f"ROE dài hạn = min(ROE dự phóng, Ke + {_pct(v['roe_fade_spread'], 0)}) – lợi thế cạnh tranh bị bào mòn"),
            ("f", r"V_{RI}=B_0+\sum_{t=1}^{n}\frac{(ROE_t-K_e)B_{t-1}}{(1+K_e)^t}+\frac{(ROE_{\infty}-K_e)B_n(1+g)}{(K_e-g)(1+K_e)^n}",
             "Thu nhập thặng dư: V = VCSH hiện tại + Σ PV[(ROE − Ke) × VCSH đầu kỳ] + giá trị cuối kỳ", "Chính cho ngân hàng, CTCK, bảo hiểm"),
            ("f", r"P_{EV}=\frac{EBITDA_{NTM}\times(EV/EBITDA)^*-\text{Nợ vay}+\text{Tiền}+\text{ĐTTC DH}-\text{CĐTS}}{\text{Số CP}}",
             "Giá EV/EBITDA = [EBITDA NTM × bội số tham chiếu − nợ vay + tiền + ĐTTC dài hạn − lợi ích CĐ thiểu số] / số CP",
             "Cầu nối EV → vốn chủ lấy từ bảng cân đối mới nhất đã công bố"),
            ("f", r"EV_{DCF}=\sum_{t=1}^{5}\frac{FCFF_t}{(1+WACC)^t}+\frac{FCFF_5(1+g)}{(WACC-g)(1+WACC)^5}",
             "DCF: EV = Σ PV(FCFF 5 năm) + PV giá trị cuối kỳ FCFF5×(1+g)/(WACC − g)",
             f"g dài hạn Bear/Base/Bull = {_pct(tg['bear'])}/{_pct(tg['base'])}/{_pct(tg['bull'])}; WACC − g ≥ "
             f"{_pct(v['dcf_min_spread'], 0)}; giá trị cuối kỳ > {_pct(v['dcf_max_tv_share'], 0)} EV → hạ độ tin cậy"),
            ("f", r"\begin{gathered}V_{DDM}=\sum_{t=1}^{5}\frac{DPS_t}{(1+K_e)^t}+\frac{DPS_6}{(K_e-g)(1+K_e)^5}\\ "
                  r"\text{chi trả bền vững}=1-\frac{g}{ROE}\end{gathered}",
             "DDM 2 giai đoạn: Σ PV(cổ tức 5 năm) + PV[DPS6/(Ke − g)]; giai đoạn 2 chi trả bền vững = 1 − g/ROE",
             "Chỉ đối chiếu (trọng số thấp), chỉ khi chia cổ tức tiền mặt đều ≥ 3 năm"),
            ("f", r"\begin{gathered}\text{Giá mục tiêu}=\sum_i w_i\,P_i\\ \text{Giá trị hợp lý hôm nay}=\frac{\text{Giá mục tiêu}+DPS_{12T}}{1+K_e}\end{gathered}",
             "Giá mục tiêu = Σ wi × Pi; Giá trị hợp lý hôm nay = (Giá mục tiêu + cổ tức 12T)/(1 + Ke)",
             "Tổng LN kỳ vọng = (Giá mục tiêu + cổ tức − thị giá)/thị giá"),
            ("h", "Hồ sơ phương pháp theo ngành"),
            ("t", ["Hồ sơ", "Trọng số phương pháp", "Ghi chú"], rows),
            ("p", "Phương pháp không đủ dữ liệu hoặc cho kết quả bất thường bị loại; khi có ≥ 3 phương pháp, phương pháp lệch "
                  f"ngoài [{v['outlier_band'][0]}×; {v['outlier_band'][1]}×] trung vị bị loại; trọng số còn lại chuẩn hóa về 100%."),
            ("h", "Kịch bản (thay đổi GIẢ ĐỊNH, không cộng trừ thẳng vào giá)"),
            ("t", ["Kịch bản", "Tăng trưởng", "Bội số (phân vị lịch sử)", "Ke", "g dài hạn"], [
                [nm, f"{sc[k]['growth_shift']:+.0%}", f"P{sc[k]['multiple_pct']}", f"{sc[k]['ke_shift'] * 100:+.0f} điểm %",
                 _pct(tg[k])] for k, nm in (("bear", "Thận trọng (Bear)"), ("base", "Cơ sở (Base)"), ("bull", "Tích cực (Bull)"))]),
            ("h", "Độ tin cậy định giá"),
            ("p", "Bắt đầu **3 điểm** (= Cao), trừ điểm theo từng lý do; **3 = Cao · 2 = Trung bình · ≤ 1 = Thấp**; sau đó áp "
                  "mức trần theo hồ sơ ngành (BĐS, bảo hiểm tối đa Trung bình) và Rf chưa cập nhật."),
            ("t", ["Lý do", "Trừ điểm"], [
                ["Chỉ 2 phương pháp hợp lệ / chỉ 1 phương pháp", "−1 / −2"],
                [f"Các phương pháp chênh nhau > {v['spread_high']} lần / > {v['spread_mid']} lần", "−1 / −2"],
                ["Sai số dự phóng LNST của chính mã > 20% / > 40% (hoặc chưa kiểm định được)", "−1 / −2 (−1)"],
                ["BCTC cũ", "−1"], [f"Phương pháp hợp lệ chiếm < {_pct(v['min_weight_coverage'], 0)} trọng số hồ sơ", "−1"],
                ["Số CP hiện hành lệch > 10% so với kỳ BCTC gốc", "−1"],
                [f"DCF/RI: giá trị cuối kỳ > {_pct(v['dcf_max_tv_share'], 0)}", "−1"],
                ["Doanh nghiệp vừa đổi phạm vi hợp nhất", "−1"],
                [f"Biên độ kịch bản Bull/Bear > {v['scenario_max_ratio']:g} lần", "−1"],
            ]),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. 5 trụ cột
# ─────────────────────────────────────────────────────────────────────────────

def s_pillars() -> Dict[str, Any]:
    from core.cau_hinh import DEFAULT_SCORE_WEIGHTS as W, SCORE_CATEGORIES as SC
    order = ["fundamental", "valuation", "technical", "momentum", "risk"]
    return {
        "key": "pillars", "icon": "🏛️", "title": "Điểm cơ hội đầu tư – 5 trụ cột",
        "pitch": [
            " · ".join(f"{PILLAR_LABEL[k]} {W[k]}%" for k in order) + ".",
            "Mỗi trụ cột chấm 0–100 theo bảng điểm minh bạch; thiếu dữ liệu → loại khỏi mẫu số, không gán 0.",
            "Điểm tổng = bình quân gia quyền; xếp loại Cơ hội nổi bật → Cơ hội rất thấp.",
            "Là điểm SÀNG LỌC THAM KHẢO – không phải khuyến nghị; khuyến nghị duy nhất đến từ khung đa lớp (mục Khuyến nghị).",
        ],
        "blocks": [
            ("f", r"\text{Điểm cơ hội}=\frac{\sum_k w_k S_k}{\sum_{k\,\text{có dữ liệu}} w_k}\times100\%",
             "Điểm cơ hội = Σ (trọng số × điểm trụ cột) / tổng trọng số các trụ cột có dữ liệu", ""),
            ("t", ["Trụ cột", "Trọng số", "Thành phần (điểm tối đa)"], [
                ["Cơ bản", f"{W['fundamental']}%", "ROE (25) · Tăng trưởng doanh thu (20) · Biên LN ròng (20) · Nợ/VCSH (20) · "
                                                   "CFO/LNST (15); chất lượng lợi nhuận Yếu −15, Cần lưu ý −5"],
                ["Định giá", f"{W['valuation']}%", "Định giá đủ tin cậy: từ tổng LN kỳ vọng 12 tháng (−20% → 0 điểm, +40% → 100). "
                                                   "Chưa đủ tin cậy: P/E, P/B (trọng số theo hồ sơ ngành, bỏ P/B nếu ngành loại) – mỗi "
                                                   "bội số 50% so với lịch sử 5 năm + 50% trung vị ngành theo vốn hóa; rẻ hơn > 30% → "
                                                   "đủ điểm, ≤ mốc → 70%, đắt ≤ 30% → 40%, đắt > 30% → 10%"],
                ["Kỹ thuật", f"{W['technical']}%", "MA (25) · RSI (15) · MACD (15) · Khối lượng (10) · Bollinger (10) · ADX (10) · "
                                                  "Dòng tiền (15)"],
                ["Động lượng", f"{W['momentum']}%", "Ngắn hạn 5/10 phiên (25) · Trung hạn 20 phiên (20) · Dài hạn 60/120 phiên (20) · "
                                                    "Sức mạnh tương đối so với VN-Index (20)"],
                ["Quản trị rủi ro", f"{W['risk']}%", "Biến động 30 phiên năm hóa (30) · Mức sụt giảm tối đa 1 năm (30) · Beta (20) · "
                                                     "Nợ/VCSH (20) – điểm cao = rủi ro thấp"],
            ]),
            ("t", ["Điểm", "Xếp loại"], [[f"{lo}–{hi}", f"{lab}"] for (lo, hi), (lab, _, _) in SC.items()]),
            ("note", "Điểm cơ hội là điểm quy tắc nội bộ, không phải xác suất sinh lời."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. Khuyến nghị
# ─────────────────────────────────────────────────────────────────────────────

def s_recommendation() -> Dict[str, Any]:
    m = _cfg().get("multilayer") or {}
    wf = m.get("weights_f") or {"Q": 0.4, "V": 0.35, "G": 0.25}
    wr = m.get("weights_r") or {}
    fs, fm = m.get("f_strong", 70), m.get("f_mid", 55)
    rs, rw = m.get("r_strong", 60), m.get("r_weak", 40)
    from core.khuyen_nghi import MATRIX_ROWS
    return {
        "key": "recommendation", "icon": "🎯", "title": "Khuyến nghị đầu tư – khung đa lớp",
        "pitch": [
            "MỘT nhãn duy nhất cho mỗi mã: MUA · TÍCH LŨY TỪNG PHẦN · NẮM GIỮ · THEO DÕI · GIẢM TỶ TRỌNG / TRÁNH "
            "(hoặc KHÔNG ĐỦ DỮ LIỆU).",
            "Bước 1 – bộ lọc loại trừ; Bước 2 – điểm cơ bản F (Chất lượng Q, Định giá V, Tăng trưởng G) và điểm SO VỚI THỊ "
            "TRƯỜNG R (thứ hạng trong rổ VN30 + cùng ngành); Bước 3 – ma trận F × R.",
            "Doanh nghiệp tốt CHƯA đủ để MUA: cổ phiếu phải mạnh hơn thị trường, thị trường chung không giảm (VN-Index trên "
            "MA200) và lợi nhuận kỳ vọng phải bù được chi phí vốn Ke.",
            "Giá mục tiêu chỉ là MỘT đầu vào của lớp Định giá – không tự quyết định nhãn; định giá trình bày dạng KHOẢNG.",
        ],
        "blocks": [
            ("h", "Bước 1 – Bộ lọc loại trừ"),
            ("ul", ["Vướng một điều kiện → không được nhận MUA / TÍCH LŨY TỪNG PHẦN (hạ về THEO DÕI), bất kể điểm số.",
                    "Kiểm tra được từ dữ liệu: vốn chủ âm · 2 năm liền LNST dương nhưng CFO âm · thanh khoản bình quân 20 phiên "
                    f"< {m.get('min_liquidity_bn', 1):g} tỷ đồng · rủi ro nghiêm trọng của mô hình rủi ro.",
                    f"Thiếu dữ liệu (< {m.get('min_quarters', 8)} quý hoặc 3 năm BCTC, < {m.get('min_sessions', 250)} phiên giá) "
                    "→ KHÔNG ĐỦ DỮ LIỆU (không tự điền số ước đoán).",
                    "Chưa có nguồn dữ liệu (ghi 'chưa kiểm tra được', đối chiếu thủ công): ý kiến kiểm toán, cổ phiếu bị cảnh "
                    "báo/kiểm soát/đình chỉ, chậm công bố BCTC."]),
            ("h", "Bước 2 – Các lớp điểm (0–100)"),
            ("t", ["Lớp", "Thành phần trong app"], [
                ["Chất lượng (Q)", "Nhóm sinh lời, thanh toán, cơ cấu vốn, dòng tiền của Sức khỏe tài chính (60%) · Piotroski "
                                   "F-score (20%) · ROE xếp hạng % trong ngành (20%)"],
                ["Định giá (V)", "Bội số so với lịch sử 5 năm + trung vị ngành theo vốn hóa (50%) · biên an toàn từ đầu thấp "
                                 "khoảng định giá (30%, chỉ khi định giá đủ tin cậy) · P/E xếp hạng % trong ngành (20%)"],
                ["Tăng trưởng (G)", "Nhóm tăng trưởng của Sức khỏe tài chính – EPS điều chỉnh, doanh thu, LN cốt lõi (70%) · "
                                    "thay đổi biên LN gộp (30%)"],
                ["So với thị trường (R)", f"Thứ hạng % trong rổ VN30 + mã cùng ngành (trung vị = 50): động lượng 6 tháng & 12 "
                                          f"tháng bỏ tháng gần nhất ({wr.get('momentum', 60)}) · giá so với MA200 "
                                          f"({wr.get('ma200', 25)}) · tổng LN kỳ vọng so với chi phí vốn Ke ({wr.get('hurdle', 15)})"],
            ]),
            ("f", r"F=%s\,Q+%s\,V+%s\,G-\text{Điểm trừ rủi ro}" % (
                f"{wf['Q']:.2f}".replace(".", "{,}"), f"{wf['V']:.2f}".replace(".", "{,}"), f"{wf['G']:.2f}".replace(".", "{,}")),
             f"F = {wf['Q']:.2f}·Q + {wf['V']:.2f}·V + {wf['G']:.2f}·G − điểm trừ rủi ro",
             f"Điểm trừ tối đa {m.get('max_penalty', 15)}: Altman Z'' vùng nguy cơ (−8) / cảnh báo (−3); Beneish M-score "
             "> −1,78 (−5, chỉ là cờ cảnh báo). Lớp thiếu dữ liệu loại khỏi mẫu số."),
            ("h", "Bước 3 – Ma trận khuyến nghị"),
            ("t", ["Điểm cơ bản", f"R ≥ {rs} (mạnh hơn thị trường)", f"{rw} ≤ R < {rs} (ngang)", f"R < {rw} (yếu hơn)"],
             [[r[0].replace("70", str(fs)).replace("55", str(fm)), r[1], r[2], r[3]] for r in MATRIX_ROWS]),
            ("ul", ["MUA cần ĐỦ: F ≥ 70, R ≥ 60, VN-Index trên MA200 và tổng LN kỳ vọng ≥ Ke; thiếu một điều kiện → TÍCH LŨY TỪNG PHẦN.",
                    "Doanh nghiệp tốt nhưng cổ phiếu yếu hơn thị trường (F ≥ 70, R < 40) → THEO DÕI, chờ R vượt 40 hoặc giá lấy lại MA200.",
                    "TÍCH LŨY TỪNG PHẦN: chia vốn 3 phần – phần đầu khi nhãn xuất hiện, các phần sau khi R ≥ 60 hoặc BCTC quý xác nhận.",
                    "THEO DÕI ở ô F < 55, R ≥ 60: đà giá thiếu nền tảng – rủi ro đầu cơ.",
                    f"Khoảng định giá = thấp–cao của các phương pháp hợp lệ; lệch nhau > {m.get('dispersion_low_conf', 0.4):.0%} → "
                    "độ tin cậy định giá thấp (không dùng biên an toàn).",
                    "Mỗi khuyến nghị kèm: điểm Q/V/G/F/R, khoảng định giá, 3 lý do ủng hộ, 3 rủi ro, điều kiện làm luận điểm "
                    "sai, độ tin cậy và câu cảnh báo pháp lý.",
                    "Cá nhân hóa chỉ đổi MỨC PHÙ HỢP và TỶ TRỌNG theo hồ sơ – không sinh nhãn riêng.",
                    "Điểm 5 trụ cột giữ làm điểm SÀNG LỌC THAM KHẢO, không phải khuyến nghị."]),
            ("note", "Ngưỡng 70 / 55 (F), 60 / 40 (R) và trọng số là tham số khởi điểm của khung, chưa hiệu chỉnh trên dữ liệu Việt Nam – "
                     "cần backtest không chồng lấn trước khi dùng thật. Chống đổi nhãn liên tục (3 điểm / 5 phiên) sẽ làm sau."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. Rủi ro
# ─────────────────────────────────────────────────────────────────────────────

def s_risk() -> Dict[str, Any]:
    r = _cfg()["risk"]
    return {
        "key": "risk", "icon": "🛡️", "title": "Đánh giá rủi ro",
        "pitch": [
            "Rủi ro tính từ số liệu thật: suy giảm kinh doanh, đòn bẩy, dòng tiền, pha loãng, định giá, dữ liệu, thị trường.",
            "Rủi ro NGHIÊM TRỌNG chặn khuyến nghị (→ CHƯA ĐỦ CƠ SỞ).",
            "Mức tổng thể: Nghiêm trọng / Cao / Trung bình / Thấp.",
        ],
        "blocks": [
            ("t", ["Mức", "Ví dụ điều kiện"], [
                ["Nghiêm trọng", f"VCSH ≤ 0 · lỗ 2 năm liên tiếp · Nợ vay/VCSH > {r['de_severe']:g} và EBIT không đủ trả lãi · "
                                 "CFO âm khi LNST dương 2 năm (trừ BĐS) · BCTC quá cũ · ngân hàng VCSH/TTS < "
                                 f"{r['bank_eta_severe']:g}%"],
                ["Cao", f"Doanh thu/LNST giảm > {abs(r['decline_high']):g}% · Nợ vay/VCSH > {r['de_high']:g} · EBIT/lãi vay < "
                        f"{r['ic_high']:g} · số CP tăng > {r['dilution_high']:.0%}/năm · sụt giá tối đa > 35% · độ tin cậy định "
                        "giá thấp"],
                ["Trung bình / Cần theo dõi", "Xu hướng giảm mạnh, thanh khoản thấp, đặc thù ngành (chỉ ghi chú, không chấm)"],
            ]),
            ("p", "Tổng hợp: có rủi ro nghiêm trọng → Nghiêm trọng; ≥ 2 rủi ro cao → Cao; 1 cao hoặc ≥ 2 trung bình → "
                  "Trung bình; còn lại → Thấp."),
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. Kiểm chứng & hạn chế
# ─────────────────────────────────────────────────────────────────────────────

def s_validation() -> Dict[str, Any]:
    return {
        "key": "validation", "icon": "🔬", "title": "Kiểm chứng mô hình & hạn chế",
        "pitch": [
            "Backtest không nhìn trước: chạy lại đúng quy trình của app tại cuối mỗi tháng 01/2022–09/2025 (VN30, 1.350 quan sát).",
            "LN 12 tháng sau (mô hình khuyến nghị CŨ R1–R4): MUA +23,3% · NẮM GIỮ +17,3% · BÁN +1,0% · trung bình rổ +16,7%.",
            "Khung khuyến nghị đa lớp (15/10/2026) CHƯA được backtest – cần chạy lại trước khi công bố hiệu quả.",
            "Rank IC 0,21 (dương 84% số tháng): xếp hạng của mô hình có tương quan thuận với lợi nhuận thực tế.",
            "Tiêu chí đặt TRƯỚC khi chạy; kiểm chứng ngoài mẫu trên 66 mã ngoài VN30 đang tiến hành.",
        ],
        "blocks": [
            ("t", ["Nhóm khuyến nghị (mô hình cũ R1–R4)", "LN 12 tháng sau (bình quân)"], [
                ["MUA", "+23,3%"], ["NẮM GIỮ", "+17,3%"], ["CHƯA ĐỦ CƠ SỞ", "+18,3%"], ["BÁN", "+1,0%"],
                ["Trung bình rổ VN30", "+16,7%"]]),
            ("f", r"\text{Rank IC}_t=\rho_{\text{Spearman}}\big(\text{ER dự báo}_{i,t},\ r^{12T}_{i,t}\big)",
             "Rank IC = tương quan hạng Spearman giữa lợi nhuận kỳ vọng mô hình và lợi nhuận 12 tháng thực tế, theo từng tháng", ""),
            ("h", "Hạn chế"),
            ("ul", [
                "MUA tập trung ở ngân hàng; giai đoạn 2024–2025 nhóm MUA thấp hơn trung bình rổ.",
                "vnstock bản Cộng đồng giới hạn 60 lượt/phút, BCTC tối đa 8 kỳ.",
                "Bất động sản chưa có RNAV, bảo hiểm chưa có P/EV → độ tin cậy tối đa Trung bình.",
                "Phân loại sắc thái tin tức theo từ điển từ khóa – chỉ tham khảo.",
                "Kết quả phục vụ học thuật, không phải khuyến nghị đầu tư.",
            ]),
        ],
    }


def sections() -> List[Dict[str, Any]]:
    return [s_overview(), s_pages(), s_fundamental(), s_technical(), s_forecast(), s_valuation(), s_pillars(),
            s_recommendation(), s_risk(), s_validation()]


# ─────────────────────────────────────────────────────────────────────────────
# Ví dụ trực tiếp: giải trình định giá & khuyến nghị của MỘT mã từ kết quả phân tích thật
# ─────────────────────────────────────────────────────────────────────────────

def explain_symbol(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """→ {"valuation": [bước], "recommendation": [bước], "pillars": [bước]} – mỗi bước là chuỗi văn bản thuần (có thể **đậm**).
    Chỉ dùng số đã có trong kết quả phân tích; thiếu thì ghi rõ."""
    inv = analysis.get("investment") or {}
    val = inv.get("valuation") or analysis.get("fair_value") or {}
    rec = inv.get("recommendation") or {}
    health = inv.get("health") or {}
    risk = inv.get("risk") or {}
    out: Dict[str, List[str]] = {"valuation": [], "recommendation": [], "pillars": []}
    V = out["valuation"]
    price = val.get("price")
    ass = val.get("assumptions") or {}
    prof = val.get("profile") or {}
    if prof:
        V.append(f"**Hồ sơ phương pháp**: {prof.get('label', '—')} – {prof.get('reason', '')}.")
    ke = ass.get("ke") or val.get("ke")
    if ke:
        b = ass.get("beta_used") or ass.get("beta")
        V.append(f"**Chi phí vốn chủ** Ke = Rf {_pct(ass.get('risk_free'), 2)} + β {_num(b, 2)} × ERP "
                 f"{_pct(ass.get('equity_premium'), 0)} = **{_pct(ke)}**.")
    for m in val.get("methods") or []:
        mult = f" × hệ số {_num(m['multiple'], 2)}x" if m.get("multiple") else ""
        base = f"{m.get('base_label', 'cơ sở')} {_num(m.get('base'))}" if m.get("base") is not None else ""
        V.append(f"**{m['name']}**: {base}{mult} = **{_num(m.get('fair'))} đ** (trọng số {m.get('weight', 0) * 100:.0f}%).")
    for name, why in val.get("invalid") or []:
        V.append(f"Không dùng {name}: {why}.")
    if val.get("target_12m"):
        parts = " + ".join(f"{m.get('weight', 0):.2f}×{_num(m.get('fair'))}" for m in val.get("methods") or [])
        V.append(f"**Giá mục tiêu** = {parts} = **{_num(val['target_12m'])} đ**; thị giá {_num(price)} đ → upside "
                 f"**{(val.get('upside') or 0):+.1f}%**; cộng cổ tức 12T {_num(val.get('expected_dividend'))} đ → tổng LN kỳ "
                 f"vọng **{(val.get('expected_return') or 0):+.1f}%**.")
    sc = val.get("scenarios") or {}
    if sc:
        V.append("**Kịch bản**: " + " · ".join(f"{lab} {_num((sc.get(k) or {}).get('target'))}"
                                               for k, lab in (("bear", "Bear"), ("base", "Base"), ("bull", "Bull"))) + ".")
    det = val.get("confidence_detail") or {}
    if val.get("confidence"):
        why = "; ".join(det.get("reasons") or []) or "không bị trừ điểm"
        caps = "; ".join(det.get("caps") or [])
        V.append(f"**Độ tin cậy**: điểm {det.get('score', '—')}/3 → **{val['confidence']}** ({why}"
                 + (f"; trần: {caps}" if caps else "") + ")."
                 + (" → CHƯA ĐỦ CƠ SỞ ĐỊNH GIÁ, số chỉ để tham khảo." if val.get("confidence") == "Thấp" else ""))
    if not V:
        V.append("Chưa có kết quả định giá cho mã này.")

    R = out["recommendation"]
    ml = inv.get("multilayer") or {}
    if ml:
        ex = [e for e in ml.get("exclusions") or [] if e["status"] == "hit"]
        R.append("**Bộ lọc loại trừ**: " + ("vướng " + "; ".join(e["text"] for e in ex) if ex else "không vướng điều kiện nào kiểm "
                 "tra được") + f" ({sum(1 for e in ml.get('exclusions') or [] if e['status'] == 'unknown')} điều kiện chưa có dữ liệu).")
        for k, lbl in (("Q", "Chất lượng"), ("V", "Định giá"), ("G", "Tăng trưởng"), ("R", "So với thị trường")):
            parts = ", ".join(f"{r['name']} {_num(r['score'], 0)}" for r in (ml.get("layers") or {}).get(k, []) if r["score"] is not None)
            R.append(f"**{lbl} ({k}) = {_num(ml.get(k), 0)}**: {parts or 'thiếu dữ liệu'}.")
        R.append(f"**Điểm cơ bản F** = 0,40×{_num(ml.get('Q'), 0)} + 0,35×{_num(ml.get('V'), 0)} + 0,25×{_num(ml.get('G'), 0)} − "
                 f"{_num(ml.get('penalty'), 0)} (trừ rủi ro) = **{_num(ml.get('F'), 0)}**.")
        R.append(f"→ {ml.get('why', '')} Khuyến nghị: **{ml['label']}**.")
        vr = ml.get("valuation_range") or {}
        if vr.get("available"):
            R.append(f"**Khoảng định giá**: {_num(vr['low'])} – {_num(vr['high'])} đ; biên an toàn "
                     f"{(vr.get('margin_of_safety') or 0):+.1f}%; độ phân tán {(vr.get('dispersion') or 0) * 100:.0f}%.")
    if not ml:
        R.append("Chưa có kết quả khung khuyến nghị đa lớp cho mã này.")

    P = out["pillars"]
    opp = analysis.get("opportunity_score") or {}
    comp = (opp.get("composite") or {})
    for k, c in (comp.get("components") or {}).items():
        if c.get("score") is not None:
            P.append(f"{PILLAR_LABEL.get(k, k)}: {c['score']:.0f}/100 × {c['weight']}% = {c['contribution']:.1f}")
        else:
            P.append(f"{PILLAR_LABEL.get(k, k)}: thiếu dữ liệu (loại khỏi mẫu số)")
    if comp.get("score") is not None:
        P.append(f"→ **Điểm cơ hội {comp['score']}/100 – {(comp.get('classification') or {}).get('label', '')}** "
                 f"({comp.get('note', '')})." + (" Điểm sàng lọc tham khảo – không phải khuyến nghị." if ml else ""))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Số liệu minh họa cho slide (chế độ thuyết trình) & băng tiêu đề
# ─────────────────────────────────────────────────────────────────────────────

def hero_stats() -> List[tuple]:
    v = _cfg()["valuation"]
    return [("6", "phương pháp định giá"), (str(len(v["method_profiles"])), "hồ sơ ngành"), ("5", "trụ cột chấm điểm"),
            ("370+", "kiểm thử tự động"), ("+23,3%", "LN 12T nhóm MUA (backtest mô hình cũ)")]


def visual(key: str) -> Optional[Dict[str, Any]]:
    """{"title", "bars": [(nhãn, giá trị, chữ)]} hoặc {"title", "tiles": [(số, nhãn)]} – minh họa bên phải slide."""
    c = _cfg()
    if key == "overview":
        return {"title": "CON SỐ CHÍNH", "tiles": hero_stats()[:4]}
    if key == "pages":
        return {"title": "4 NHÓM TRANG", "tiles": [("3", "Thị trường"), ("3", "Dữ liệu doanh nghiệp"), ("3", "Cá nhân"),
                                                   ("1", "Đề án")]}
    if key == "fundamental":
        w = c["health"]["weights"]["nonfinancial"]
        return {"title": "TRỌNG SỐ HEALTH SCORE (PHI TÀI CHÍNH)", "bars": [(_GL[k], x, f"{x}%") for k, x in w.items()]}
    if key == "technical":
        return {"title": "ĐIỂM KỸ THUẬT – ĐIỂM TỐI ĐA", "bars": [("Giá so với MA", 25, "25"), ("RSI", 15, "15"), ("MACD", 15, "15"),
                                                              ("Dòng tiền", 15, "15"), ("Khối lượng", 10, "10"),
                                                              ("Bollinger", 10, "10"), ("ADX", 10, "10")]}
    if key == "forecast":
        f = c["forecast"]
        return {"title": "DỰ PHÓNG", "tiles": [(f"NTM + {f['years']}", "năm dự phóng"), ("3", "kịch bản Bear/Base/Bull"),
                                               ("P20/P80", "khoảng kịch bản từ sai số thực tế"), (str(f["hist_years"]), "năm lịch sử ước lượng")]}
    if key == "valuation":
        w = c["valuation"]["method_profiles"]["default"]["weights"]
        return {"title": "TRỌNG SỐ – HỒ SƠ PHI TÀI CHÍNH (CHUNG)",
                "bars": [(METHOD_LABEL.get(k, k).split(" (")[0], x, f"{x}%") for k, x in sorted(w.items(), key=lambda kv: -kv[1])]}
    if key == "pillars":
        from core.cau_hinh import DEFAULT_SCORE_WEIGHTS as W
        order = ["fundamental", "technical", "valuation", "momentum", "risk"]
        return {"title": "TRỌNG SỐ 5 TRỤ CỘT", "bars": [(PILLAR_LABEL[k], W[k], f"{W[k]}%") for k in order]}
    if key == "recommendation":
        m = c.get("multilayer") or {}
        wf = m.get("weights_f") or {"Q": 0.4, "V": 0.35, "G": 0.25}
        return {"title": "TRỌNG SỐ ĐIỂM CƠ BẢN F", "bars": [("Chất lượng (Q)", wf["Q"] * 100, f"{wf['Q'] * 100:.0f}%"),
                                                           ("Định giá (V)", wf["V"] * 100, f"{wf['V'] * 100:.0f}%"),
                                                           ("Tăng trưởng (G)", wf["G"] * 100, f"{wf['G'] * 100:.0f}%")]}
    if key == "risk":
        return {"title": "MỨC RỦI RO", "tiles": [("Nghiêm trọng", "chặn khuyến nghị"), ("Cao", "≥ 2 rủi ro cao"),
                                               ("Trung bình", "1 cao / ≥ 2 TB"), ("Thấp", "còn lại")]}
    if key == "validation":
        return {"title": "LN 12 THÁNG SAU (BACKTEST VN30 – MÔ HÌNH CŨ)", "bars": [("MUA", 23.3, "+23,3%"), ("NẮM GIỮ", 17.3, "+17,3%"),
                                                                    ("Trung bình rổ", 16.7, "+16,7%"), ("BÁN", 1.0, "+1,0%")]}
    return None
