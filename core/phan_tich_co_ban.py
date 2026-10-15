"""
core/phan_tich_co_ban.py – gộp từ 5 module (15/10/2026).

MỤC LỤC
  • analytics/period_utils.py – Tiện ích nhận diện & sắp xếp kỳ báo cáo tài chính.
      hàm/lớp chính: flatten_columns, parse_period_key, key_to_label, order_tabular, ordered_period_columns, growth_vs_prior
  • analytics/financial_ratios.py – Bộ tính chỉ số tài chính TỪ BÁO CÁO TÀI CHÍNH đã chuẩn hóa (không phụ thuộc bảng
      hàm/lớp chính: ebit_ebitda, expense_positive, core_ebit_ebitda, detect_period, is_bank, shares_series, compute_ratios, ratio_table, cagr, valuation_snapshot, dupont, piotroski …
  • analytics/financial_health.py – Financial Health Score (0–100) – chấm điểm sức khỏe tài chính từ BCTC năm, giải thích được từng điểm.
      hàm/lớp chính: lin_score, FinancialHealthEngine
  • analytics/fundamental.py – Fundamental Analysis engine.
      hàm/lớp chính: FundamentalAnalyzer
  • analytics/peers.py – So sánh ngành (peer comparison).
      hàm/lớp chính: related_symbols, find_sector_basket, extract_peer_metrics, weighted_median, compute_peer_stats
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/period_utils.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Tiện ích nhận diện & sắp xếp kỳ báo cáo tài chính.

Vấn đề cũ: code lấy `.iloc[-1]` làm "kỳ mới nhất" và `.iloc[-2]` làm "kỳ trước"
mà không kiểm tra thứ tự kỳ. Với dữ liệu quý, phép so sánh đó là QoQ (quý liền
trước) chứ không phải YoY, và nếu nguồn trả về kỳ mới nhất đứng đầu thì "mới nhất"
thực ra lại là kỳ cũ nhất.

Khóa kỳ (period key) = năm * 10 + quý   (quý 1..4; báo cáo năm dùng 0)
  ví dụ Q3/2025 -> 20253, năm 2024 -> 20240
=> sắp xếp số học đúng thứ tự thời gian và cùng kỳ năm trước = key - 10.
"""


import re
from typing import List, Optional, Tuple

import pandas as pd

META_COLS = {"item", "item_en", "item_id", "symbol", "source", "fetched_at",
             "unit", "levels", "level", "ticker", "cp", "report_type"}

_YEAR_NAMES = {"năm", "nam", "year", "yearreport", "fiscalyear"}
_QUARTER_NAMES = {"kỳ", "ky", "quý", "quy", "quarter", "lengthreport", "period_quarter"}


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Gộp MultiIndex columns (vnstock VCI trả về dạng này cho bảng ratio) thành chuỗi."""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " ".join(str(x) for x in col if str(x) and not str(x).startswith("Unnamed")).strip()
            for col in df.columns
        ]
    else:
        df = df.copy()
        df.columns = [str(c) for c in df.columns]
    # Nguồn có thể trả về tên cột trùng nhau → giữ cột đầu tiên
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    return df


def _norm(name: str) -> str:
    return str(name).strip().lower().replace("_", "").replace(" ", "")


def _last_token(name: str) -> str:
    parts = str(name).strip().lower().split()
    return parts[-1] if parts else ""


def parse_period_key(label) -> Optional[int]:
    """Đọc nhãn kỳ dạng '2024-Q3', 'Q3/2024', '2024Q3', 'Q3 2024', '2024' → khóa số."""
    if label is None:
        return None
    txt = str(label).strip().upper()
    m_year = re.search(r"(19|20)\d{2}", txt)
    if not m_year:
        return None
    year = int(m_year.group(0))
    rest = txt[:m_year.start()] + " " + txt[m_year.end():]
    m_q = re.search(r"Q\s*([1-4])", rest) or re.search(r"(?:^|[^0-9])([1-4])(?:[^0-9]|$)", rest)
    q = int(m_q.group(1)) if m_q else 0
    return year * 10 + q


def key_to_label(key) -> str:
    try:
        k = int(key)
    except (TypeError, ValueError):
        return str(key)
    year, q = divmod(k, 10)
    return f"Q{q}/{year}" if 1 <= q <= 4 else str(year)


def _find_col(df: pd.DataFrame, names: set) -> Optional[str]:
    for c in df.columns:
        if _norm(c) in names or _last_token(c) in names:
            return c
    return None


def order_tabular(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bảng dạng mỗi dòng = 1 kỳ (có cột Năm / Kỳ): sắp xếp tăng dần theo thời gian
    và đặt index = khóa kỳ. Không nhận diện được thì giữ nguyên.
    """
    if df is None or df.empty:
        return df
    year_col = _find_col(df, _YEAR_NAMES)
    if year_col is None:
        return df
    years = pd.to_numeric(df[year_col], errors="coerce")
    q_col = _find_col(df, _QUARTER_NAMES)
    if q_col is not None:
        qs = pd.to_numeric(df[q_col], errors="coerce").fillna(0)
        qs = qs.where(qs.between(1, 4), 0)
    else:
        qs = pd.Series(0, index=df.index)
    keys = years * 10 + qs
    if keys.isna().all():
        return df
    out = df.copy()
    out.index = keys.astype("Int64")
    out = out[out.index.notna()]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.index = out.index.astype(int)
    return out


def ordered_period_columns(df: pd.DataFrame) -> Tuple[List[str], List[Optional[int]]]:
    """
    Bảng dạng ma trận (mỗi dòng = 1 chỉ tiêu, mỗi cột = 1 kỳ): trả về danh sách cột kỳ
    theo đúng thứ tự thời gian cùng khóa kỳ tương ứng (None nếu không đọc được).
    """
    cols = [c for c in df.columns if _norm(c) not in META_COLS]
    keyed = [(c, parse_period_key(c)) for c in cols]
    if keyed and all(k is not None for _, k in keyed):
        keyed.sort(key=lambda x: x[1])
        return [c for c, _ in keyed], [k for _, k in keyed]
    cols_sorted = sorted(cols)
    return cols_sorted, [None] * len(cols_sorted)


def growth_vs_prior(series: pd.Series) -> dict:
    """
    Tăng trưởng của kỳ mới nhất.

    - Có khóa kỳ & là quý  -> so với CÙNG QUÝ năm trước (YoY)
    - Có khóa kỳ & là năm  -> so với năm trước
    - Không xác định được  -> so với kỳ liền trước (ghi rõ basis để người đọc biết)
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    res = {"pct": None, "basis": None, "latest_period": None, "compare_period": None}
    if len(s) < 2:
        return res

    latest_key = s.index[-1]
    latest = float(s.iloc[-1])
    prior = None

    is_int_key = all(isinstance(k, (int,)) or (hasattr(k, "is_integer") and float(k).is_integer())
                     for k in s.index) and all(int(k) > 10000 for k in s.index)
    if is_int_key:
        lk = int(latest_key)
        target = lk - 10
        idx = [int(k) for k in s.index]
        if target in idx:
            prior = float(s.iloc[idx.index(target)])
            res["basis"] = "YoY (cùng kỳ năm trước)" if lk % 10 else "So với năm trước"
            res["compare_period"] = key_to_label(target)
        res["latest_period"] = key_to_label(lk)
        if prior is None:
            prior = float(s.iloc[-2])
            res["basis"] = "So với kỳ liền trước (thiếu số liệu cùng kỳ năm trước)"
            res["compare_period"] = key_to_label(int(s.index[-2]))
    else:
        prior = float(s.iloc[-2])
        res["basis"] = "So với kỳ liền trước (không xác định được kỳ báo cáo)"

    if prior is not None and prior != 0:
        res["pct"] = (latest - prior) / abs(prior) * 100
    return res


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/financial_ratios.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Bộ tính chỉ số tài chính TỪ BÁO CÁO TÀI CHÍNH đã chuẩn hóa (không phụ thuộc bảng
chỉ số dựng sẵn của nhà cung cấp dữ liệu).

Đầu vào: bảng rộng canonical (index = khóa kỳ năm*10+quý, cột = chỉ tiêu chuẩn, VND).

Quy ước:
  - Kỳ NĂM: chỉ tiêu dòng (doanh thu, lợi nhuận, dòng tiền) dùng số của năm.
  - Kỳ QUÝ: chỉ tiêu dòng dùng TTM (tổng 4 quý liên tiếp gần nhất) khi tính tỷ suất
    sinh lời/vòng quay/định giá; bảng kết quả vẫn có số từng quý.
  - Chỉ tiêu số dư (tài sản, vốn…) dùng BÌNH QUÂN đầu kỳ – cuối kỳ cho các tỷ số
    dạng dòng/số dư (ROE, ROA, vòng quay…). Đầu kỳ = kỳ trước (năm) hoặc cùng kỳ năm
    trước (quý, khớp với TTM).
  - Phần trăm lưu dạng số % (15.2 nghĩa là 15,2%). Thiếu dữ liệu → NaN, không gán giả định.
"""


from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd



PAR_VALUE = 10_000  # mệnh giá cổ phiếu VN (đồng) – dùng ước tính số CP khi thiếu dữ liệu

# key: (nhãn, nhóm, định dạng, cao hơn là tốt?)
RATIO_META: Dict[str, tuple] = {
    # Khả năng sinh lời
    "gross_margin": ("Biên lợi nhuận gộp", "Khả năng sinh lời", "%", True),
    "operating_margin": ("Biên lợi nhuận HĐKD", "Khả năng sinh lời", "%", True),
    "ebitda_margin": ("Biên EBITDA", "Khả năng sinh lời", "%", True),
    "net_margin": ("Biên lợi nhuận ròng", "Khả năng sinh lời", "%", True),
    "net_margin_parent": ("Biên LN ròng cổ đông mẹ", "Khả năng sinh lời", "%", True),
    "roe": ("ROE", "Khả năng sinh lời", "%", True),
    "roa": ("ROA", "Khả năng sinh lời", "%", True),
    "roic": ("ROIC (vốn đầu tư không gồm tiền & ĐTNH)", "Khả năng sinh lời", "%", True),
    # Thanh khoản
    "current_ratio": ("Thanh toán hiện hành", "Thanh khoản", "x", True),
    "quick_ratio": ("Thanh toán nhanh", "Thanh khoản", "x", True),
    "cash_ratio": ("Thanh toán tiền mặt", "Thanh khoản", "x", True),
    # Đòn bẩy
    "debt_to_equity": ("Nợ vay / VCSH", "Cơ cấu vốn", "x", False),
    "liabilities_to_equity": ("Nợ phải trả / VCSH", "Cơ cấu vốn", "x", False),
    "liabilities_to_assets": ("Nợ phải trả / Tổng tài sản", "Cơ cấu vốn", "%", False),
    "net_debt_to_ebitda": ("Nợ vay ròng / EBITDA", "Cơ cấu vốn", "x", False),
    "interest_coverage": ("Khả năng trả lãi (EBIT / lãi vay)", "Cơ cấu vốn", "x", True),
    "equity_multiplier": ("Đòn bẩy tài chính (TTS / VCSH)", "Cơ cấu vốn", "x", None),
    # Hiệu quả hoạt động
    "asset_turnover": ("Vòng quay tổng tài sản", "Hiệu quả hoạt động", "x", True),
    "inventory_turnover": ("Vòng quay hàng tồn kho", "Hiệu quả hoạt động", "x", True),
    "dio": ("Số ngày tồn kho", "Hiệu quả hoạt động", "days", False),
    "dso": ("Số ngày thu tiền", "Hiệu quả hoạt động", "days", False),
    "dpo": ("Số ngày trả tiền", "Hiệu quả hoạt động", "days", None),
    "ccc": ("Chu kỳ tiền mặt", "Hiệu quả hoạt động", "days", False),
    # Tăng trưởng
    "revenue_growth": ("Tăng trưởng doanh thu (YoY)", "Tăng trưởng", "%", True),
    "net_income_growth": ("Tăng trưởng LNST (YoY)", "Tăng trưởng", "%", True),
    "core_profit_growth": ("Tăng trưởng LN cốt lõi (YoY)", "Tăng trưởng", "%", True),
    "eps_growth": ("Tăng trưởng EPS điều chỉnh (YoY)", "Tăng trưởng", "%", True),
    "equity_growth": ("Tăng trưởng VCSH (YoY)", "Tăng trưởng", "%", True),
    "assets_growth": ("Tăng trưởng tổng tài sản (YoY)", "Tăng trưởng", "%", None),
    # Dòng tiền
    "fcf": ("Dòng tiền tự do (FCF)", "Dòng tiền", "vnd", True),
    "cfo_to_net_income": ("CFO / LNST", "Dòng tiền", "x", True),
    "fcf_margin": ("Biên FCF", "Dòng tiền", "%", True),
    "capex_to_revenue": ("Capex / Doanh thu", "Dòng tiền", "%", None),
    "dividend_payout": ("Tỷ lệ chi trả cổ tức", "Dòng tiền", "%", None),
    # Trên mỗi cổ phiếu
    "eps": ("EPS điều chỉnh (LNST mẹ / CP, hồi tố CP thưởng)", "Trên mỗi cổ phiếu", "vnd", True),
    "bvps": ("Giá trị sổ sách / CP (điều chỉnh)", "Trên mỗi cổ phiếu", "vnd", True),
    "dps": ("Cổ tức tiền mặt / CP (điều chỉnh)", "Trên mỗi cổ phiếu", "vnd", True),
    # Ngân hàng
    "loan_to_deposit": ("Cho vay / Tiền gửi (LDR)", "Ngân hàng", "%", None),
    "equity_to_assets": ("VCSH / Tổng tài sản", "Ngân hàng", "%", True),
    "provision_to_income": ("Chi phí dự phòng / TN hoạt động", "Ngân hàng", "%", False),
}

VALUATION_META: Dict[str, tuple] = {
    "pe": ("P/E", "x"), "pb": ("P/B", "x"), "ps": ("P/S", "x"), "ev_ebitda": ("EV/EBITDA", "x"),
    "earnings_yield": ("Lợi suất lợi nhuận (E/P)", "%"), "dividend_yield": ("Tỷ suất cổ tức", "%"),
    "market_cap": ("Vốn hóa", "vnd"), "enterprise_value": ("Giá trị doanh nghiệp (EV)", "vnd"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name].astype(float) if name in df.columns else pd.Series(np.nan, index=df.index, dtype=float)


def ebit_ebitda(wide: pd.DataFrame, flow=None):
    """Định nghĩa DUY NHẤT của EBIT/EBITDA trong toàn hệ thống (bảng chỉ số, P/E–EV snapshot, định giá 12T).

    EBIT   = Lợi nhuận trước thuế + chi phí lãi vay   (thiếu LNTT → LN thuần HĐKD + lãi vay; theo VAS, LN thuần
             HĐKD đã trừ chi phí tài chính gồm lãi vay nên phải cộng lại).
    EBITDA = EBIT + khấu hao (từ LCTT). Thiếu khấu hao → NaN (không giả định bằng 0).
    flow: hàm áp cho chỉ tiêu dòng (vd _ttm cho kỳ quý); mặc định giữ nguyên.
    """
    f = flow or (lambda s: s)
    pbt = f(_col(wide, "profit_before_tax"))
    op = f(_col(wide, "operating_profit"))
    interest = f(_col(wide, "interest_expense").abs())
    dep = f(_col(wide, "depreciation").abs())
    ebit = pbt.where(pbt.notna(), op) + interest.fillna(0)
    return ebit, ebit + dep


def expense_positive(s: pd.Series) -> pd.Series:
    """Quy chi phí về số DƯƠNG theo quy ước dấu của cả chuỗi, không lấy trị tuyệt đối từng kỳ.

    Nguồn dữ liệu ghi chi phí khác dấu nhau (vnstock/VCI: số âm; PDF/Vietstock: số dương). Trị tuyệt đối từng kỳ
    sai ở kỳ chi phí ÂM THẬT (vd hoàn nhập dự phòng đầu tư lớn hơn chi phí lãi vay → CP tài chính âm): |x| biến
    khoản hoàn nhập thành chi phí. Cách làm: đa số kỳ khác 0 là số âm → chuỗi theo quy ước "chi phí ghi âm" → đổi dấu
    cả chuỗi; ngược lại giữ nguyên. Kỳ hoàn nhập vì thế giữ đúng dấu (chi phí âm = thu nhập)."""
    if s is None or len(s) == 0:
        return s
    x = pd.to_numeric(s, errors="coerce")
    nz = x[x.notna() & (x != 0)]
    if len(nz) and float((nz < 0).mean()) > 0.5:
        return -x
    return x


def core_ebit_ebitda(wide: pd.DataFrame, flow=None):
    """EBIT/EBITDA CỐT LÕI (bước 9) – chỉ từ hoạt động kinh doanh chính, dùng cho DCF (FCFF) và EV/EBITDA.

    Lý do: theo VAS, LN thuần HĐKD (và LNTT) đã gồm doanh thu tài chính (lãi tiền gửi, cổ tức), chi phí tài chính
    khác lãi vay, lãi/lỗ công ty liên doanh–liên kết và thu nhập khác. Các tài sản sinh ra những khoản này (tiền,
    tiền gửi, đầu tư tài chính, khoản đầu tư vào công ty liên kết) được CỘNG RIÊNG khi đi từ EV sang vốn chủ → nếu
    để thu nhập của chúng trong EBIT sẽ tính trùng hai lần.

      Cách 1: EBIT cốt lõi = LN gộp − |CP bán hàng| − |CP quản lý DN|
      Cách 2 (thiếu một trong ba dòng trên): LN thuần HĐKD − DT tài chính + CP tài chính − lãi/lỗ công ty liên kết
               (CP tài chính quy về số dương theo QUY ƯỚC DẤU của chuỗi – xem expense_positive – không lấy trị tuyệt
               đối từng kỳ, để kỳ hoàn nhập (CP tài chính âm thật) không bị đảo thành chi phí)
               (đòi hỏi đủ cả bốn dòng; thiếu → NaN, KHÔNG coi bằng 0)
      EBITDA cốt lõi = EBIT cốt lõi + |khấu hao|; thiếu khấu hao → NaN.
    Trả (ebit_core, ebitda_core, method) – method: Series nhãn cách tính từng kỳ ('gp_sga' | 'op_adj' | None)."""
    f = flow or (lambda s: s)
    gp = f(_col(wide, "gross_profit"))
    se, ga = f(_col(wide, "selling_expense")).abs(), f(_col(wide, "admin_expense")).abs()
    m1 = gp - se - ga
    op, fi = f(_col(wide, "operating_profit")), f(_col(wide, "financial_income"))
    fe, assoc = expense_positive(f(_col(wide, "financial_expense"))), f(_col(wide, "associates_income"))
    m2 = op - fi + fe - assoc
    ebit = m1.where(m1.notna(), m2)
    method = pd.Series(np.where(m1.notna(), "gp_sga", np.where(m2.notna(), "op_adj", None)), index=ebit.index)
    dep = f(_col(wide, "depreciation").abs())
    return ebit, ebit + dep, method


def _div(a, b, pct: bool = False):
    with np.errstate(divide="ignore", invalid="ignore"):
        b = b.where(b != 0) if isinstance(b, pd.Series) else (np.nan if b == 0 else b)
        out = a / b
    return out * 100 if pct else out


def _lag(s: pd.Series, period: str) -> pd.Series:
    """Giá trị kỳ so sánh: năm trước (kỳ năm) hoặc cùng quý năm trước (kỳ quý), khớp theo khóa kỳ."""
    shifted = s.copy()
    shifted.index = shifted.index + 10      # key+10 = cùng kỳ năm sau → dời về
    return shifted.reindex(s.index)


def _ttm(s: pd.Series) -> pd.Series:
    """Tổng 4 quý liên tiếp (yêu cầu đủ 4 quý liền nhau theo khóa kỳ)."""
    out = pd.Series(np.nan, index=s.index, dtype=float)
    idx = list(s.index)
    for k in idx:
        y, q = divmod(int(k), 10)
        if not 1 <= q <= 4:
            continue
        keys = []
        yy, qq = y, q
        for _ in range(4):
            keys.append(yy * 10 + qq)
            qq -= 1
            if qq == 0:
                yy, qq = yy - 1, 4
        if all(kk in s.index and pd.notna(s.loc[kk]) for kk in keys):
            out.loc[k] = float(sum(s.loc[kk] for kk in keys))
    return out


def detect_period(wide: pd.DataFrame) -> str:
    if wide.empty:
        return "year"
    qs = (np.asarray(wide.index, dtype=int) % 10)
    return "quarter" if (qs > 0).mean() > 0.5 else "year"


def is_bank(wide: pd.DataFrame) -> bool:
    return any(c in wide.columns and wide[c].notna().any() for c in ("customer_deposits", "net_interest_income"))


def shares_series(wide: pd.DataFrame) -> pd.Series:
    sh = _col(wide, "shares_outstanding")
    est = _col(wide, "charter_capital") / PAR_VALUE
    return sh.where(sh > 0, est)


# ─────────────────────────────────────────────────────────────────────────────
# Main ratio computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_ratios(wide: pd.DataFrame, period: Optional[str] = None) -> pd.DataFrame:
    """Bảng chỉ số theo từng kỳ (index = khóa kỳ, cột = khóa trong RATIO_META)."""
    if wide is None or wide.empty:
        return pd.DataFrame()
    wide = wide.sort_index()
    period = period or detect_period(wide)
    bank = is_bank(wide)

    flow = (lambda s: _ttm(s)) if period == "quarter" else (lambda s: s)
    avg = lambda s: pd.concat([s, _lag(s, period)], axis=1).mean(axis=1, skipna=False)  # noqa: E731

    rev_raw = _col(wide, "total_operating_income") if bank and "revenue" not in wide.columns else _col(wide, "revenue")
    rev = flow(rev_raw)
    cogs = flow(_col(wide, "cogs").abs())
    gp = flow(_col(wide, "gross_profit"))
    gp = gp.where(gp.notna(), rev - cogs)
    op = flow(_col(wide, "operating_profit"))
    pbt = flow(_col(wide, "profit_before_tax"))
    ni = flow(_col(wide, "net_income"))
    ni_parent = flow(_col(wide, "net_income_parent"))
    ni_parent = ni_parent.where(ni_parent.notna(), ni)
    ni = ni.where(ni.notna(), ni_parent)
    interest = flow(_col(wide, "interest_expense").abs())
    dep = flow(_col(wide, "depreciation").abs())
    tax = flow(_col(wide, "income_tax").abs())
    cfo = flow(_col(wide, "cfo"))
    capex = flow(_col(wide, "capex").abs())
    div_paid = flow(_col(wide, "dividends_paid").abs())

    ta, eq, tl = _col(wide, "total_assets"), _col(wide, "equity"), _col(wide, "total_liabilities")
    tl = tl.where(tl.notna(), ta - eq)
    ca, cl = _col(wide, "current_assets"), _col(wide, "current_liabilities")
    inv, recv, pay = _col(wide, "inventory"), _col(wide, "receivables"), _col(wide, "payables")
    cash = _col(wide, "cash")
    sti = _col(wide, "short_term_investments").fillna(0)
    std, ltd = _col(wide, "short_term_debt"), _col(wide, "long_term_debt")
    debt = (std.fillna(0) + ltd.fillna(0)).where(std.notna() | ltd.notna())   # NaN nếu không có số liệu vay
    minority = _col(wide, "minority_interest").fillna(0)
    eq_parent = eq - minority

    ebit, ebitda = ebit_ebitda(wide, flow)
    tax_rate = _div(tax, pbt).clip(0, 0.5).fillna(0.2)

    r = pd.DataFrame(index=wide.index)
    r["gross_margin"] = _div(gp, rev, pct=True) if not bank else np.nan
    r["operating_margin"] = _div(op, rev, pct=True)
    r["ebitda_margin"] = _div(ebitda, rev, pct=True) if not bank else np.nan
    r["net_margin"] = _div(ni, rev, pct=True)
    # Biên LN của CỔ ĐÔNG MẸ – cùng cơ sở với EPS, P/E (biên LN ròng ở trên gồm cả phần cổ đông thiểu số)
    r["net_margin_parent"] = _div(ni_parent, rev, pct=True)
    r["roe"] = _div(ni_parent, avg(eq_parent), pct=True)
    r["roa"] = _div(ni, avg(ta), pct=True)
    invested = eq + debt - cash.fillna(0) - sti
    r["roic"] = _div(ebit * (1 - tax_rate), avg(invested), pct=True) if not bank else np.nan

    r["current_ratio"] = _div(ca, cl)
    r["quick_ratio"] = _div(ca - inv.fillna(0), cl)
    r["cash_ratio"] = _div(cash + sti, cl)

    r["debt_to_equity"] = _div(debt, eq)
    r["liabilities_to_equity"] = _div(tl, eq)
    r["liabilities_to_assets"] = _div(tl, ta, pct=True)
    r["net_debt_to_ebitda"] = _div(debt - cash.fillna(0) - sti, ebitda) if not bank else np.nan
    r["interest_coverage"] = _div(ebit, interest) if not bank else np.nan
    r["equity_multiplier"] = _div(avg(ta), avg(eq))

    r["asset_turnover"] = _div(rev, avg(ta))
    r["inventory_turnover"] = _div(cogs, avg(inv))
    r["dio"] = _div(365 * avg(inv), cogs)
    r["dso"] = _div(365 * avg(recv), rev)
    r["dpo"] = _div(365 * avg(pay), cogs)
    r["ccc"] = r["dio"] + r["dso"] - r["dpo"]

    # Tăng trưởng: so với kỳ trước (năm) hoặc cùng kỳ năm trước (quý) trên số TỪNG KỲ
    shares = shares_series(wide)
    eps_period = _div(_col(wide, "net_income_parent").where(_col(wide, "net_income_parent").notna(),
                                                             _col(wide, "net_income")), shares)
    for key, s in (("revenue_growth", rev_raw), ("net_income_growth", _col(wide, "net_income")),
                   ("eps_growth", eps_period), ("equity_growth", eq), ("assets_growth", ta)):
        prev = _lag(s, period)
        r[key] = _div(s - prev, prev.abs(), pct=True)
    # Tăng trưởng EPS ĐIỀU CHỈNH: cổ phiếu thưởng / cổ tức bằng cổ phiếu không làm loãng giá trị nên không được làm giảm
    # tăng trưởng EPS. Chỉ phần phát hành THU TIỀN MỚI (LCTT "tiền thu từ phát hành cổ phiếu") mới tính là pha loãng:
    #   g_EPS = (LNST mẹ_t / LNST mẹ_t−1) / (1 + tiền thu phát hành_t / VCSH mẹ_t−1) − 1
    # Không có dòng tiền phát hành trong BCTC → giữ cách tính theo số CP từng kỳ (EPS báo cáo).
    if "equity_issued" in wide.columns and wide["equity_issued"].notna().any():
        ni_par = _col(wide, "net_income_parent").where(_col(wide, "net_income_parent").notna(), _col(wide, "net_income"))
        iss = flow(_col(wide, "equity_issued").abs().fillna(0))
        prev_ni, prev_eqp = _lag(ni_par, period), _lag(eq_parent, period)
        dil = _div(iss, prev_eqp).fillna(0).clip(lower=0)
        adj = ((ni_par / prev_ni) / (1 + dil) - 1) * 100
        adj = adj.where((prev_ni > 0) & ni_par.notna())
        r["eps_growth"] = adj.where(adj.notna(), r["eps_growth"])

    # LN CỐT LÕI (LN gộp − CP bán hàng − CP quản lý; dự phòng: LN HĐKD − thu nhập tài chính ± ...) – tăng trưởng từ hoạt động
    # kinh doanh chính, không gồm thu nhập tài chính (lãi tiền gửi, cổ tức, chênh lệch tỷ giá) – xem earnings_quality().
    if not bank:
        core, _, _ = core_ebit_ebitda(wide, flow)
        prev_core = _lag(core, period)
        r["core_profit_growth"] = _div(core - prev_core, prev_core.abs(), pct=True).where(prev_core > 0)

    r["fcf"] = cfo - capex
    r["cfo_to_net_income"] = _div(cfo, ni)
    r["fcf_margin"] = _div(cfo - capex, rev, pct=True)
    r["capex_to_revenue"] = _div(capex, rev, pct=True)
    r["dividend_payout"] = _div(div_paid, ni_parent, pct=True)

    r["eps"] = _div(ni_parent, shares)
    r["bvps"] = _div(eq_parent, shares)
    r["dps"] = _div(div_paid, shares)

    if bank:
        r["loan_to_deposit"] = _div(_col(wide, "customer_loans"), _col(wide, "customer_deposits"), pct=True)
        r["equity_to_assets"] = _div(eq, ta, pct=True)
        r["provision_to_income"] = _div(flow(_col(wide, "provision_expense").abs()), rev, pct=True)

    r = r.replace([np.inf, -np.inf], np.nan)
    return r.dropna(axis=1, how="all")


def ratio_table(ratios: pd.DataFrame) -> pd.DataFrame:
    """Bảng hiển thị: dòng = chỉ số (có nhóm, nhãn), cột = kỳ (nhãn đẹp)."""
    if ratios.empty:
        return pd.DataFrame()
    rows = []
    for key in RATIO_META:
        if key not in ratios.columns:
            continue
        label, group, fmt, _ = RATIO_META[key]
        row = {"Nhóm": group, "Chỉ số": label, "_key": key, "_fmt": fmt}
        for k, v in ratios[key].items():
            row[key_to_label(k)] = v
        rows.append(row)
    return pd.DataFrame(rows)


def cagr(series: pd.Series, years: int) -> Optional[float]:
    """CAGR n năm trên số liệu NĂM (cần giá trị dương ở hai đầu)."""
    s = series.dropna()
    s = s[[int(k) % 10 == 0 for k in s.index]] if len(s) else s
    if len(s) < years + 1:
        return None
    start, end = float(s.iloc[-(years + 1)]), float(s.iloc[-1])
    if start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100


# ─────────────────────────────────────────────────────────────────────────────
# Valuation snapshot (cần giá hiện tại)
# ─────────────────────────────────────────────────────────────────────────────

def _num_or_none(v) -> Optional[float]:
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def valuation_snapshot(wide: pd.DataFrame, price: Optional[float], period: Optional[str] = None,
                       ratios: Optional[pd.DataFrame] = None, shares_now: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Định giá tại giá hiện tại (VND/cp) dựa trên kỳ BCTC mới nhất (TTM nếu là quý).

    shares_now: {"shares", "source"} – số CP lưu hành HIỆN HÀNH (cùng cơ sở với thị giá). Khi khác số CP cuối kỳ BCTC
    > 1% (vd chia thưởng/phát hành sau kỳ báo cáo) → vốn hóa tính trên số CP hiện hành và EPS/BVPS/DPS quy đổi về số CP
    hiện hành (cùng LNST/VCSH/cổ tức, chia cho nhiều CP hơn) để P/E, P/B, tỷ suất cổ tức không bị lệch cơ sở."""
    out: Dict[str, Any] = {k: None for k in VALUATION_META}
    if wide is None or wide.empty or not price:
        return out
    period = period or detect_period(wide)
    ratios = ratios if ratios is not None else compute_ratios(wide, period)
    if ratios.empty:
        return out
    valid = ratios.dropna(subset=[c for c in ("eps", "bvps") if c in ratios.columns], how="all")
    if valid.empty:
        return out
    last = valid.iloc[-1]
    shares = shares_series(wide).loc[:valid.index[-1]].dropna()
    if shares.empty:
        return out
    sh = float(shares.iloc[-1])
    eps, bvps, dps = last.get("eps"), last.get("bvps"), last.get("dps")
    share_note = None
    now = _num_or_none((shares_now or {}).get("shares"))
    if now and sh and abs(now / sh - 1) > 0.01 and 0.5 < now / sh < 2.0:
        f = sh / now
        eps, bvps, dps = (x * f if x is not None and pd.notna(x) else x for x in (eps, bvps, dps))
        share_note = (f"Số CP hiện hành {now / 1e6:,.1f} triệu ({(shares_now or {}).get('source') or 'hiện hành'}) khác số CP "
                      f"cuối kỳ BCTC {sh / 1e6:,.1f} triệu ({now / sh - 1:+.1%}) → vốn hóa, EPS, BVPS, cổ tức/CP tính trên số CP "
                      "hiện hành.")
        sh = now
    mcap = price * sh
    flow = _ttm if period == "quarter" else (lambda s: s)
    k = valid.index[-1]
    rev = flow(_col(wide, "revenue")).loc[k]
    ebitda = ebit_ebitda(wide, flow)[1].loc[k]
    w_last = wide.loc[k]
    debt = np.nansum([w_last.get("short_term_debt", np.nan), w_last.get("long_term_debt", np.nan)])
    cash = np.nansum([w_last.get("cash", np.nan), w_last.get("short_term_investments", np.nan)])
    mi = w_last.get("minority_interest", np.nan)
    ev = mcap + debt - cash + (0.0 if mi is None or pd.isna(mi) else float(mi))   # NaN "or 0" vẫn là NaN → phải kiểm tra

    def pos(v):
        return v is not None and pd.notna(v) and v > 0

    # Khoản thiếu số liệu bị tạm coi = 0 khi tính EV / EBITDA → ghi lại để giao diện/báo cáo cảnh báo
    def miss(*cols):
        return all(w_last.get(c) is None or pd.isna(w_last.get(c)) for c in cols)
    gaps = [lbl for lbl, cols in (("vay nợ", ("short_term_debt", "long_term_debt")),
                                  ("tiền & ĐTTC ngắn hạn", ("cash", "short_term_investments")),
                                  ("lợi ích CĐ thiểu số", ("minority_interest",)),
                                  ("chi phí lãi vay", ("interest_expense",))) if miss(*cols)]

    out.update({
        "data_gaps": gaps,
        "price": price, "shares": sh, "market_cap": mcap, "enterprise_value": ev,
        "pe": price / eps if pos(eps) else None,
        "pb": price / bvps if pos(bvps) else None,
        "ps": mcap / rev if pos(rev) else None,
        "ev_ebitda": ev / ebitda if pos(ebitda) else None,
        "earnings_yield": eps / price * 100 if eps is not None and pd.notna(eps) else None,
        "dividend_yield": dps / price * 100 if pos(dps) else None,
        "eps_ttm": float(eps) if eps is not None and pd.notna(eps) else None,
        "bvps": float(bvps) if bvps is not None and pd.notna(bvps) else None,
        "as_of_period": key_to_label(valid.index[-1]),
        # nhãn kỳ của EPS: kỳ năm → "năm 2025" (KHÔNG phải TTM); kỳ quý → "TTM Q2/2026"
        "eps_basis": (f"TTM {key_to_label(valid.index[-1])}" if period == "quarter" else f"năm {key_to_label(valid.index[-1])}"),
        "share_note": share_note,
    })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# DuPont, Piotroski F-score, Altman Z''-score
# ─────────────────────────────────────────────────────────────────────────────

def dupont(ratios: pd.DataFrame) -> pd.DataFrame:
    """ROE = Biên LN ròng × Vòng quay tài sản × Đòn bẩy tài chính (3 bước)."""
    need = {"net_margin", "asset_turnover", "equity_multiplier"}
    if ratios.empty or not need <= set(ratios.columns):
        return pd.DataFrame()
    d = ratios[["net_margin", "asset_turnover", "equity_multiplier"]].copy()
    d["roe_dupont"] = d["net_margin"] / 100 * d["asset_turnover"] * d["equity_multiplier"] * 100
    if "roe" in ratios.columns:
        d["roe_reported"] = ratios["roe"]
    return d.dropna(how="all")


def piotroski(wide: pd.DataFrame) -> Dict[str, Any]:
    """
    Piotroski F-score (0–9) trên 2 năm gần nhất (dữ liệu NĂM). Tiêu chí nào thiếu dữ liệu
    được bỏ qua và báo rõ số tiêu chí đã chấm.
    """
    annual = wide[[int(k) % 10 == 0 for k in wide.index]] if not wide.empty else wide
    if len(annual) < 2:
        return {"score": None, "max": 0, "checks": [], "note": "Cần ít nhất 2 năm BCTC"}
    r = compute_ratios(annual, "year")
    t, p = annual.index[-1], annual.index[-2]
    g = lambda df, c, k: (float(df.loc[k, c]) if c in df.columns and pd.notna(df.loc[k, c]) else None)  # noqa: E731
    ta_t, ta_p = g(annual, "total_assets", t), g(annual, "total_assets", p)
    ni_t, ni_p = g(annual, "net_income", t), g(annual, "net_income", p)
    roa_t = ni_t / ta_t if ni_t is not None and ta_t else None
    roa_p = ni_p / ta_p if ni_p is not None and ta_p else None
    cfo_t = g(annual, "cfo", t)
    ltd_t, ltd_p = g(annual, "long_term_debt", t), g(annual, "long_term_debt", p)
    cr_t, cr_p = g(r, "current_ratio", t), g(r, "current_ratio", p)
    sh = shares_series(annual)
    sh_t, sh_p = (float(sh.loc[t]) if pd.notna(sh.loc[t]) else None), (float(sh.loc[p]) if pd.notna(sh.loc[p]) else None)
    gm_t, gm_p = g(r, "gross_margin", t), g(r, "gross_margin", p)
    at_t = (g(annual, "revenue", t) / ta_t) if g(annual, "revenue", t) and ta_t else None
    at_p = (g(annual, "revenue", p) / ta_p) if g(annual, "revenue", p) and ta_p else None

    def chk(name, cond):
        return {"name": name, "pass": (None if cond is None else bool(cond))}

    # Piotroski: phát hành cổ phiếu THU TIỀN (huy động vốn) mới bị trừ điểm; cổ phiếu thưởng / cổ tức bằng cổ phiếu thì không.
    iss_t, eq_p = g(annual, "equity_issued", t), g(annual, "equity", p)
    if iss_t is not None and eq_p:
        issue_ok = abs(iss_t) <= 0.01 * eq_p          # ≤ 1% VCSH đầu kỳ (vd ESOP nhỏ) coi như không huy động thêm
    else:
        issue_ok = (sh_t <= sh_p * 1.001) if (sh_t is not None and sh_p is not None) else None

    def both(a, b):
        return a is not None and b is not None

    checks = [
        chk("ROA dương", None if roa_t is None else roa_t > 0),
        chk("Dòng tiền HĐKD dương", None if cfo_t is None else cfo_t > 0),
        chk("ROA tăng so với năm trước", (roa_t > roa_p) if both(roa_t, roa_p) else None),
        chk("CFO > LNST (chất lượng lợi nhuận)", (cfo_t > ni_t) if both(cfo_t, ni_t) else None),
        chk("Nợ vay dài hạn/Tổng TS giảm",
            (ltd_t / ta_t <= ltd_p / ta_p) if both(ltd_t, ltd_p) and ta_t and ta_p else None),
        chk("Hệ số thanh toán hiện hành tăng", (cr_t > cr_p) if both(cr_t, cr_p) else None),
        chk("Không phát hành thêm cổ phiếu thu tiền", issue_ok),
        chk("Biên lợi nhuận gộp tăng", (gm_t > gm_p) if both(gm_t, gm_p) else None),
        chk("Vòng quay tài sản tăng", (at_t > at_p) if both(at_t, at_p) else None),
    ]
    scored = [c for c in checks if c["pass"] is not None]
    score = sum(1 for c in scored if c["pass"])
    return {"score": score if scored else None, "max": len(scored), "checks": checks,
            "year": key_to_label(t),
            "interpretation": None if not scored else
            ("Mạnh" if score >= 7 else "Trung bình" if score >= 4 else "Yếu") + f" ({score}/{len(scored)})"}


def earnings_quality(wide: pd.DataFrame) -> Dict[str, Any]:
    """
    Chất lượng lợi nhuận (BCTC NĂM, 2 năm gần nhất) – trả lời "lợi nhuận tăng nhờ đâu và có thành tiền không":
      • LN cốt lõi (LN gộp − CP bán hàng − CP quản lý) so với LN thuần HĐKD → phần tăng đến từ thu nhập tài chính/khác
      • Tăng trưởng doanh thu, LN cốt lõi, LNST, CP bán hàng; biên gộp năm gần nhất so với năm trước (và số năm giảm liên tiếp)
      • CFO/LNST, FCF = CFO − capex và thay đổi so với năm trước
      • Piotroski F-score
    flags: danh sách cảnh báo (mức 'cao' | 'trung bình') – dùng cho Financial Health Score, điểm cơ bản và báo cáo.
    """
    out: Dict[str, Any] = {"available": False, "flags": [], "rows": []}
    if wide is None or wide.empty or is_bank(wide):
        out["note"] = "Không áp dụng cho ngân hàng / thiếu dữ liệu"
        return out
    a = wide[[int(k) % 10 == 0 for k in wide.index]].sort_index()
    if len(a) < 2:
        out["note"] = "Cần ít nhất 2 năm BCTC"
        return out
    t, p = a.index[-1], a.index[-2]

    def v(col, k):
        x = a[col].get(k) if col in a.columns else None
        return float(x) if x is not None and pd.notna(x) else None

    def gr(x1, x0):
        return (x1 / x0 - 1) * 100 if x1 is not None and x0 not in (None, 0) and x0 > 0 else None

    core, _, _ = core_ebit_ebitda(a)
    c_t, c_p = (float(core.get(t)) if pd.notna(core.get(t)) else None), (float(core.get(p)) if pd.notna(core.get(p)) else None)
    op_t, op_p = v("operating_profit", t), v("operating_profit", p)
    ni_t, ni_p = v("net_income", t), v("net_income", p)
    rev_t, rev_p = v("revenue", t), v("revenue", p)
    se = lambda k: abs(v("selling_expense", k)) if v("selling_expense", k) is not None else None  # noqa: E731
    cfo_t, cfo_p = v("cfo", t), v("cfo", p)
    cap_t = abs(v("capex", t)) if v("capex", t) is not None else None
    cap_p = abs(v("capex", p)) if v("capex", p) is not None else None
    fcf_t = cfo_t - cap_t if cfo_t is not None and cap_t is not None else None
    fcf_p = cfo_p - cap_p if cfo_p is not None and cap_p is not None else None
    gm = (a["gross_profit"] / a["revenue"] * 100) if {"gross_profit", "revenue"} <= set(a.columns) else pd.Series(dtype=float)
    gm = gm.dropna()
    down = 0
    for i in range(len(gm) - 1, 0, -1):
        if gm.iloc[i] < gm.iloc[i - 1]:
            down += 1
        else:
            break
    non_core_share = None
    if None not in (c_t, c_p, op_t, op_p) and (op_t - op_p) > 0:
        non_core_share = ((op_t - op_p) - (c_t - c_p)) / (op_t - op_p) * 100
    fs = piotroski(a)
    fs_prev = piotroski(a.iloc[:-1]) if len(a) >= 3 else {}
    out.update(available=True, year=key_to_label(t), prev_year=key_to_label(p),
               net_income=ni_t, net_income_prev=ni_p, op_profit=op_t, op_profit_prev=op_p,
               cfo_prev=cfo_p, cfo_to_ni_prev=(cfo_p / ni_p) if cfo_p is not None and ni_p else None,
               fscore_prev=fs_prev.get("score"), fscore_prev_max=fs_prev.get("max"),
               core_profit=c_t, core_profit_prev=c_p, core_growth=gr(c_t, c_p), op_growth=gr(op_t, op_p),
               net_income_growth=gr(ni_t, ni_p), revenue_growth=gr(rev_t, rev_p), selling_growth=gr(se(t), se(p)),
               non_core_share_of_op_growth=non_core_share,
               gross_margin=float(gm.iloc[-1]) if len(gm) else None,
               gross_margin_prev=float(gm.iloc[-2]) if len(gm) > 1 else None, gross_margin_down_years=down,
               cfo=cfo_t, cfo_growth=gr(cfo_t, cfo_p), cfo_to_ni=(cfo_t / ni_t) if cfo_t is not None and ni_t else None,
               fcf=fcf_t, fcf_prev=fcf_p, fcf_growth=gr(fcf_t, fcf_p) if fcf_p and fcf_p > 0 else None,
               fscore=fs.get("score"), fscore_max=fs.get("max"))
    f = out["flags"]
    if non_core_share is not None and non_core_share >= 50:
        pc = lambda x: f"{x:+.1f}%" if x is not None else "—"   # noqa: E731  (vd LN năm trước âm → không tính được %)
        f.append({"level": "cao", "text": f"{non_core_share:.0f}% mức tăng LN thuần HĐKD đến từ thu nhập tài chính/khác – "
                  f"LN cốt lõi chỉ tăng {pc(out['core_growth'])} so với LNST {pc(out['net_income_growth'])}."})
    elif out["core_growth"] is not None and out["net_income_growth"] is not None and \
            out["net_income_growth"] - out["core_growth"] >= 10:
        f.append({"level": "trung bình", "text": f"LN cốt lõi tăng {out['core_growth']:+.1f}%, thấp hơn nhiều so với "
                  f"LNST {out['net_income_growth']:+.1f}%."})
    if down >= 3:
        f.append({"level": "trung bình", "text": f"Biên LN gộp giảm {down} năm liên tiếp (còn {out['gross_margin']:.1f}%)."})
    if out["selling_growth"] is not None and out["revenue_growth"] is not None and \
            out["selling_growth"] - out["revenue_growth"] >= 8:
        f.append({"level": "trung bình", "text": f"CP bán hàng tăng {out['selling_growth']:+.1f}%, nhanh hơn doanh thu "
                  f"({out['revenue_growth']:+.1f}%)."})
    if out["cfo_growth"] is not None and out["cfo_growth"] <= -10:
        f.append({"level": "trung bình", "text": f"CFO giảm {abs(out['cfo_growth']):.0f}% so với năm trước "
                  f"(CFO/LNST {out['cfo_to_ni']:.2f}x)." if out["cfo_to_ni"] is not None else
                  f"CFO giảm {abs(out['cfo_growth']):.0f}% so với năm trước."})
    if out["fcf_growth"] is not None and out["fcf_growth"] <= -25:
        f.append({"level": "trung bình", "text": f"FCF giảm {abs(out['fcf_growth']):.0f}% ({fcf_p / 1e9:,.0f} → {fcf_t / 1e9:,.0f} tỷ)."})
    if out["fscore"] is not None and out["fscore_max"] and out["fscore_max"] >= 7 and out["fscore"] <= 3:
        f.append({"level": "cao", "text": f"Piotroski F-score {out['fscore']}/{out['fscore_max']} – các chỉ báo cơ bản xấu đi "
                  "so với năm trước."})
    n_hi = sum(1 for x in f if x["level"] == "cao")
    out["verdict"] = ("Yếu" if n_hi >= 2 else "Cần lưu ý" if f else "Tốt")
    return out


def detect_scope_change(q: Optional[pd.DataFrame], min_rev_drop: float = 15.0, min_gap: float = 25.0,
                        min_mi_shift: float = 5.0, full_quarters: int = 4) -> Dict[str, Any]:
    """
    Phát hiện THAY ĐỔI PHẠM VI HỢP NHẤT từ số QUÝ (từng quý): công ty con lớn chuyển thành công ty liên kết (hoặc ngược
    lại) làm doanh thu đổi đột ngột trong khi LNST cổ đông mẹ gần như không đổi. Ví dụ FPT từ 1/1/2026 hạch toán
    FPT Telecom theo phương pháp vốn chủ sở hữu: doanh thu quý −20% so với cùng kỳ (số 2025 chưa điều chỉnh lại) nhưng
    LNST mẹ +14%, phần LN của cổ đông thiểu số từ ~16% về ~0%.

    Một quý k bị coi là "khác cơ sở" so với cùng kỳ k−10 khi đồng thời:
      • |tăng trưởng doanh thu| ≥ min_rev_drop (%), và chênh lệch với tăng trưởng LNST mẹ ≥ min_gap (điểm %);
      • tỷ trọng LN của cổ đông thiểu số trong LNST thay đổi ≥ min_mi_shift (điểm %).
    active = chuỗi quý "khác cơ sở" gần nhất chưa đủ full_quarters quý → TTM và tăng trưởng doanh thu so cùng kỳ không
    còn so sánh được; số liệu năm cũ (doanh thu, EBITDA, bội số lịch sử) khác cơ sở với bảng cân đối mới.
    """
    out: Dict[str, Any] = {"detected": False, "active": False}
    if q is None or q.empty or not {"revenue", "net_income"} <= set(q.columns):
        return out
    qq = q[[int(k) % 10 > 0 for k in q.index]].sort_index()
    nip = _col(qq, "net_income_parent")
    ni = _col(qq, "net_income")
    rev = _col(qq, "revenue")
    flags = []
    for k in qq.index:
        p = int(k) - 10
        if p not in qq.index:
            continue
        r1, r0, n1, n0, a1, a0 = (rev.get(k), rev.get(p), nip.get(k), nip.get(p), ni.get(k), ni.get(p))
        if any(pd.isna(x) for x in (r1, r0, n1, n0, a1, a0)) or r0 <= 0 or n0 <= 0 or a1 <= 0 or a0 <= 0:
            continue
        g_rev, g_nip = (r1 / r0 - 1) * 100, (n1 / n0 - 1) * 100
        mi1, mi0 = (a1 - n1) / a1 * 100, (a0 - n0) / a0 * 100
        hit = abs(g_rev) >= min_rev_drop and abs(g_rev - g_nip) >= min_gap and abs(mi1 - mi0) >= min_mi_shift
        flags.append((int(k), hit, g_rev, g_nip, mi0, mi1))
    if not flags or not flags[-1][1]:
        return out
    run = []
    for f in reversed(flags):
        if not f[1]:
            break
        run.append(f)
    run = run[::-1]
    since = run[0][0]
    n_new = len([k for k in qq.index if int(k) >= since])
    last = run[-1]
    out.update(detected=True, active=n_new < full_quarters, since=key_to_label(since), quarters_new=n_new,
               text=(f"Doanh thu quý {key_to_label(last[0])} {last[2]:+.0f}% so với cùng kỳ trong khi LNST cổ đông mẹ "
                     f"{last[3]:+.0f}%; phần LN của cổ đông thiểu số từ {last[4]:.0f}% về {last[5]:.0f}% LNST → nhiều khả "
                     f"năng doanh nghiệp đã THAY ĐỔI PHẠM VI HỢP NHẤT từ {key_to_label(since)} (vd công ty con chuyển thành "
                     "công ty liên kết). Số liệu trước đó chưa được điều chỉnh lại theo cơ sở mới."))
    return out


def altman_z(wide: pd.DataFrame) -> Dict[str, Any]:
    """
    Altman Z''-score phiên bản thị trường mới nổi (Altman 2005), áp dụng cho DN phi tài chính:
      Z'' = 3.25 + 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4
      X1 = (TSNH − Nợ NH)/TTS, X2 = LNST chưa phân phối/TTS, X3 = EBIT/TTS, X4 = VCSH/Nợ phải trả
      Vùng: > 5.85 an toàn · 4.35–5.85 cảnh báo · < 4.35 nguy cơ
    """
    if wide is None or wide.empty or is_bank(wide):
        return {"score": None, "note": "Không áp dụng cho ngân hàng / thiếu dữ liệu"}
    annual = wide[[int(k) % 10 == 0 for k in wide.index]]
    src = annual if not annual.empty else wide
    last = src.iloc[-1]
    ta = last.get("total_assets")
    need = ["current_assets", "current_liabilities", "retained_earnings", "profit_before_tax", "equity"]
    if not ta or any(pd.isna(last.get(c)) for c in need):
        return {"score": None, "note": "Thiếu chỉ tiêu để tính Z-score"}
    tl = last.get("total_liabilities")
    tl = tl if tl and pd.notna(tl) else ta - last["equity"]
    ebit = last["profit_before_tax"] + abs(last.get("interest_expense") or 0)
    x1 = (last["current_assets"] - last["current_liabilities"]) / ta
    x2 = last["retained_earnings"] / ta
    x3 = ebit / ta
    x4 = last["equity"] / tl if tl else np.nan
    z = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    zone = "An toàn" if z > 5.85 else "Vùng cảnh báo" if z >= 4.35 else "Nguy cơ kiệt quệ tài chính"
    return {"score": round(float(z), 2), "zone": zone, "period": key_to_label(src.index[-1]),
            "components": {"X1": x1, "X2": x2, "X3": x3, "X4": x4}}


def adjust_per_share(ratios: pd.DataFrame, wide: pd.DataFrame, shares_now: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Góp ý GK (II.1): EPS / BVPS / DPS các kỳ quá khứ quy về CÙNG MẪU SỐ với thị giá hiện tại.

    Thị giá lịch sử (vnstock) đã điều chỉnh cho cổ phiếu thưởng / chia tách, còn EPS chia cho số CP cuối từng kỳ thì chưa →
    trong cùng báo cáo xuất hiện nhiều con số EPS khác nhau. Hệ số hồi tố của kỳ t:
        F_t = (CP hiện hành / CP cuối kỳ gần nhất) × Π_{s>t} thưởng_s,   thưởng_s = (CP_s / CP_s−1) / (1 + tiền phát hành_s / VCSH mẹ_s−1)
    Phần tăng CP do phát hành THU TIỀN được loại ra (không phải pha loãng kỹ thuật). EPS điều chỉnh = EPS báo cáo / F_t.
    Kỳ gần nhất: EPS điều chỉnh = LNST mẹ / CP hiện hành – khớp đúng EPS dùng cho P/E ở phần định giá.
    Giữ cột gốc ở eps_reported / bvps_reported / dps_reported."""
    if ratios is None or ratios.empty or wide is None or wide.empty or "eps" not in ratios.columns:
        return ratios
    wide = wide.sort_index()
    sh = shares_series(wide).reindex(ratios.index)
    valid = sh.dropna()
    valid = valid[valid > 0]
    if valid.empty:
        return ratios
    eqp = (_col(wide, "equity") - _col(wide, "minority_interest").fillna(0)).reindex(ratios.index)
    iss = _col(wide, "equity_issued").abs().reindex(ratios.index) if "equity_issued" in wide.columns \
        else pd.Series(0.0, index=ratios.index)
    keys = list(valid.index)
    bonus = {keys[0]: 1.0}
    for prev, cur in zip(keys[:-1], keys[1:]):
        g = valid[cur] / valid[prev]
        e0 = eqp.get(prev)
        dil = float(iss.get(cur) or 0) / float(e0) if e0 is not None and pd.notna(e0) and e0 > 0 and pd.notna(iss.get(cur)) else 0.0
        b = g / (1 + max(0.0, dil))
        bonus[cur] = b if 1.0 < b < 3.0 else 1.0          # chỉ hồi tố khi CP tăng thật (thưởng/chia tách), chặn số liệu lỗi
    now = _num_or_none((shares_now or {}).get("shares"))
    last = float(valid.iloc[-1])
    post = now / last if now and 0.5 < now / last < 2.0 and abs(now / last - 1) > 0.01 else 1.0
    factors, f = {}, post
    for k in reversed(keys):
        factors[k] = f
        f *= bonus[k]
    fac = pd.Series(factors).reindex(ratios.index)
    if (fac.dropna() - 1).abs().max() <= 0.005:
        return ratios
    out = ratios.copy()
    for c in ("eps", "bvps", "dps"):
        if c in out.columns:
            out[f"{c}_reported"] = out[c]
            out[c] = out[c] / fac.where(fac.notna(), 1.0)
    out.attrs["per_share_adjusted"] = True
    return out


def summarize(wide: pd.DataFrame, period: Optional[str] = None, price: Optional[float] = None,
              shares_now: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Gói đầy đủ cho giao diện / báo cáo."""
    period = period or detect_period(wide)
    ratios = compute_ratios(wide, period)
    # Định giá tính trên cột GỐC (đã tự quy về CP hiện hành); bảng chỉ số dùng EPS/BVPS ĐIỀU CHỈNH cùng cơ sở.
    valuation = valuation_snapshot(wide, price, period, ratios, shares_now=shares_now)
    try:
        ratios = adjust_per_share(ratios, wide, shares_now)
    except Exception:                                    # không để lỗi hồi tố làm hỏng cả báo cáo
        pass
    out = {
        "period": period, "ratios": ratios, "table": ratio_table(ratios),
        "valuation": valuation,
        "dupont": dupont(ratios), "is_bank": is_bank(wide),
        "piotroski": piotroski(wide) if period == "year" else None,
        "earnings_quality": earnings_quality(wide) if period == "year" else None,
        "altman": altman_z(wide),
        "cagr": {},
    }
    if period == "year" and not wide.empty:
        for name, col in (("revenue", "revenue"), ("net_income", "net_income")):
            if col in wide.columns:
                out["cagr"][f"{name}_3y"] = cagr(wide[col], 3)
                out["cagr"][f"{name}_5y"] = cagr(wide[col], 5)
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/financial_health.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Financial Health Score (0–100) – chấm điểm sức khỏe tài chính từ BCTC năm, giải thích được từng điểm.

Đầu vào lấy từ bộ tính chỉ số sẵn có (analytics.financial_ratios.compute_ratios) – không tính lại.

Doanh nghiệp phi tài chính (trọng số mặc định, cấu hình ở core/cau_hinh.py):
  Sinh lời 25% (ROE, ROA, biên LN ròng) · Tăng trưởng 20% (doanh thu, LNST, EPS) · Thanh toán 15% (hiện hành, nhanh)
  · Cơ cấu vốn 15% (Nợ vay/VCSH, EBIT/lãi vay) · Chất lượng dòng tiền 25% (CFO/LNST, biên FCF, xu hướng CFO nhiều kỳ)
Ngân hàng: Sinh lời · Tăng trưởng · An toàn vốn (VCSH/TTS) · Chất lượng tài sản (CP dự phòng/TN hoạt động) · Huy động (LDR)
Chứng khoán / Bảo hiểm: Sinh lời · Tăng trưởng · An toàn vốn (Nợ phải trả/VCSH, VCSH/TTS) · Thanh khoản

Chuẩn hóa: mỗi chỉ tiêu nội suy tuyến tính giữa ngưỡng "kém" (0 điểm) và "tốt" (100 điểm), ngưỡng theo ngành.
Thiếu dữ liệu: chỉ tiêu thiếu bị loại khỏi nhóm; nhóm thiếu hẳn bị loại và trọng số chuẩn hóa lại.
Điểm tổng KHÔNG được công bố (score = None, chỉ còn điểm tham khảo) khi thiếu nhóm bắt buộc hoặc độ phủ < ngưỡng.
"""


import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.cau_hinh import load_config

GROUP_LABELS = {
    "profitability": "Khả năng sinh lời", "growth": "Tăng trưởng", "liquidity": "Khả năng thanh toán",
    "leverage": "Cơ cấu vốn", "cashflow": "Chất lượng dòng tiền", "capital": "An toàn vốn",
    "asset_quality": "Chất lượng tài sản", "funding": "Huy động & cho vay",
}
METRIC_LABELS = {
    "roe": ("ROE", "%"), "roa": ("ROA", "%"), "net_margin": ("Biên LN ròng", "%"),
    "revenue_growth": ("Tăng trưởng doanh thu", "%"), "net_income_growth": ("Tăng trưởng LNST", "%"),
    "core_profit_growth": ("Tăng trưởng LN cốt lõi", "%"),
    "eps_growth": ("Tăng trưởng EPS", "%"), "current_ratio": ("Thanh toán hiện hành", "x"),
    "quick_ratio": ("Thanh toán nhanh", "x"), "debt_to_equity": ("Nợ vay / VCSH", "x"),
    "interest_coverage": ("EBIT / Chi phí lãi vay", "x"), "cfo_to_net_income": ("CFO / LNST", "x"),
    "fcf_margin": ("Biên dòng tiền tự do (FCF/DT)", "%"), "cfo_trend": ("Xu hướng CFO nhiều kỳ", ""),
    "equity_to_assets": ("VCSH / Tổng tài sản", "%"), "provision_to_income": ("CP dự phòng / TN hoạt động", "%"),
    "loan_to_deposit": ("Cho vay / Tiền gửi (LDR)", "%"), "liabilities_to_equity": ("Nợ phải trả / VCSH", "x"),
}


def lin_score(value: Optional[float], poor: float, good: float) -> Optional[float]:
    """0 điểm tại 'kém', 100 tại 'tốt' (tự hiểu chiều 'thấp là tốt' khi poor > good)."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    if good == poor:
        return 100.0 if value >= good else 0.0
    return float(np.clip((value - poor) / (good - poor) * 100, 0, 100))


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _fmt(v, unit):
    if v is None:
        return "—"
    return f"{v:,.1f}%" if unit == "%" else f"{v:,.2f}x" if unit == "x" else f"{v:,.2f}"


class FinancialHealthEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = config or load_config()

    def _anchor(self, key: str, sector: str) -> Tuple[float, float]:
        over = self.cfg["sector_overrides"].get(sector, {})
        return tuple(over.get(key, self.cfg["anchors"][key]))

    # ── chỉ tiêu đặc biệt ──
    @staticmethod
    def _prev(wide: pd.DataFrame, col: str) -> Optional[float]:
        if wide is None or col not in wide.columns or len(wide) < 2:
            return None
        return _num(wide[col].iloc[-2])

    def _metric(self, key, value, sector, anchor_key=None, explain="") -> Dict[str, Any]:
        poor, good = self._anchor(anchor_key or key, sector)
        label, unit = METRIC_LABELS[key]
        sc = lin_score(value, poor, good)
        direction = "thấp là tốt" if poor > good else "cao là tốt"
        return {"key": key, "label": label, "value": value, "unit": unit, "score": sc,
                "display": _fmt(value, unit),
                "explain": explain or f"{label} = {_fmt(value, unit)}; 0 điểm tại {poor:g}, 100 điểm tại {good:g} ({direction})."}

    def _cfo_trend(self, wide: pd.DataFrame) -> Dict[str, Any]:
        label, _ = METRIC_LABELS["cfo_trend"]
        n = self.cfg["health"]["years_for_trend"]
        if wide is None or "cfo" not in wide.columns:
            return {"key": "cfo_trend", "label": label, "value": None, "unit": "", "score": None, "display": "—",
                    "explain": "Không có số liệu lưu chuyển tiền HĐKD."}
        cfo = wide["cfo"].dropna().tail(n)
        if len(cfo) < 3:
            return {"key": "cfo_trend", "label": label, "value": None, "unit": "", "score": None, "display": "—",
                    "explain": f"Cần ≥ 3 năm CFO (hiện có {len(cfo)})."}
        pos_share = float((cfo > 0).mean())
        # "tăng/giảm" = CFO năm gần nhất so với NĂM TRƯỚC (trước đây so với bình quân các năm trước → CFO giảm 13% vẫn ghi "tăng")
        prev, last = float(cfo.iloc[-2]), float(cfo.iloc[-1])
        chg = (last / prev - 1) * 100 if prev > 0 else None
        rising = last >= prev
        sc = pos_share * 80 + (20 if rising else 0)
        return {"key": "cfo_trend", "label": label, "value": pos_share, "unit": "", "score": sc,
                "display": f"{int((cfo > 0).sum())}/{len(cfo)} năm dương · năm gần nhất "
                           + (f"{chg:+.0f}%" if chg is not None else ("tăng" if rising else "giảm")),
                "explain": f"{(cfo > 0).sum()}/{len(cfo)} năm CFO dương (×80) + 20 điểm nếu CFO năm gần nhất ≥ năm trước."}

    # ── mô hình ──
    def score(self, ratios: Optional[pd.DataFrame], wide: Optional[pd.DataFrame], company: Dict[str, str]) -> Dict[str, Any]:
        ftype, sector = company.get("type", "nonfinancial"), company.get("sector", "default")
        out: Dict[str, Any] = {"type": ftype, "sector": sector, "groups": [], "notes": [], "missing": []}
        if ratios is None or ratios.empty:
            out.update(available=False, score=None, partial_score=None, coverage=0.0,
                       notes=["Không có chỉ số tài chính từ BCTC năm – không chấm điểm."])
            return out
        last = ratios.iloc[-1]
        out["period"] = int(ratios.index[-1])
        g = lambda k: _num(last.get(k))  # noqa: E731
        groups: Dict[str, List[Dict[str, Any]]] = {}

        if ftype == "nonfinancial":
            groups["profitability"] = [self._metric("roe", g("roe"), sector), self._metric("roa", g("roa"), sector),
                                       self._metric("net_margin", g("net_margin"), sector)]
            ni_prev = self._prev(wide, "net_income_parent") or self._prev(wide, "net_income")
            growth = [self._metric("revenue_growth", g("revenue_growth"), sector)]
            if ni_prev is not None and ni_prev <= 0:
                out["notes"].append("LNST năm trước ≤ 0 → tăng trưởng LNST/EPS không có ý nghĩa, loại khỏi nhóm Tăng trưởng.")
            else:
                # LN CỐT LÕI thay LNST khi có số liệu: LNST gồm thu nhập tài chính (lãi tiền gửi, chênh lệch tỷ giá…) – tăng
                # trưởng nhờ các khoản này không phản ánh hoạt động kinh doanh chính (vd FPT 2025: LNST +19%, cốt lõi +4,6%).
                cg = g("core_profit_growth")
                growth += [self._metric("core_profit_growth", cg, sector) if cg is not None
                           else self._metric("net_income_growth", g("net_income_growth"), sector),
                           self._metric("eps_growth", g("eps_growth"), sector)]
            groups["growth"] = growth
            groups["liquidity"] = [self._metric("current_ratio", g("current_ratio"), sector),
                                   self._metric("quick_ratio", g("quick_ratio"), sector)]
            eq = _num(wide["equity"].iloc[-1]) if wide is not None and "equity" in wide.columns else None
            de = self._metric("debt_to_equity", g("debt_to_equity"), sector)
            if eq is not None and eq <= 0:
                de.update(score=0.0, explain="VCSH âm → 0 điểm cơ cấu vốn.")
            ic_val = g("interest_coverage")
            interest = _num(wide["interest_expense"].iloc[-1]) if wide is not None and "interest_expense" in wide.columns else None
            ic = self._metric("interest_coverage", ic_val, sector)
            if ic_val is None and interest is not None and abs(interest) < 1:
                ic.update(score=100.0, display="không có lãi vay", explain="Không phát sinh chi phí lãi vay → 100 điểm.")
            elif ic_val is not None and ic_val < 0:
                ic.update(score=0.0, explain="EBIT âm → không đủ trả lãi, 0 điểm.")
            groups["leverage"] = [de, ic]
            ni = _num(wide["net_income"].iloc[-1]) if wide is not None and "net_income" in wide.columns else None
            cfo = _num(wide["cfo"].iloc[-1]) if wide is not None and "cfo" in wide.columns else None
            cfo_ni = self._metric("cfo_to_net_income", g("cfo_to_net_income"), sector)
            if ni is not None and ni <= 0:
                if cfo is not None and cfo > 0:
                    cfo_ni.update(score=60.0, display="LNST ≤ 0, CFO > 0",
                                  explain="LNST không dương nên tỷ lệ CFO/LNST không có ý nghĩa; CFO dương → 60 điểm.")
                else:
                    cfo_ni.update(score=0.0 if cfo is not None else None, display="LNST ≤ 0, CFO ≤ 0" if cfo is not None else "—",
                                  explain="LNST và CFO cùng không dương → 0 điểm.")
            groups["cashflow"] = [cfo_ni, self._metric("fcf_margin", g("fcf_margin"), sector), self._cfo_trend(wide)]
        elif ftype == "bank":
            groups["profitability"] = [self._metric("roe", g("roe"), sector, "bank_roe"),
                                       self._metric("roa", g("roa"), sector, "bank_roa")]
            groups["growth"] = [self._metric("revenue_growth", g("revenue_growth"), sector,
                                             explain=f"Tăng trưởng tổng thu nhập hoạt động = {_fmt(g('revenue_growth'), '%')}."),
                                self._metric("net_income_growth", g("net_income_growth"), sector),
                                self._metric("eps_growth", g("eps_growth"), sector)]
            for m in groups["growth"][:1]:
                m["score"] = lin_score(m["value"], *self._anchor("revenue_growth", sector))
            groups["capital"] = [self._metric("equity_to_assets", g("equity_to_assets"), sector)]
            groups["asset_quality"] = [self._metric("provision_to_income", g("provision_to_income"), sector)]
            ldr = g("loan_to_deposit")
            sc = None if ldr is None else float(100 if 75 <= ldr <= 100 else max(0, 100 - abs(ldr - (75 if ldr < 75 else 100)) * 4))
            groups["funding"] = [{"key": "loan_to_deposit", "label": METRIC_LABELS["loan_to_deposit"][0], "value": ldr,
                                  "unit": "%", "score": sc, "display": _fmt(ldr, "%"),
                                  "explain": "LDR đơn giản = cho vay KH / tiền gửi KH (khác LDR theo công thức NHNN). 100 điểm trong 75–100%; "
                                             "mỗi điểm % lệch khỏi vùng này trừ 4 điểm."}]
        else:   # chứng khoán / bảo hiểm
            groups["profitability"] = [self._metric("roe", g("roe"), sector), self._metric("roa", g("roa"), sector),
                                       self._metric("net_margin", g("net_margin"), sector)]
            groups["growth"] = [self._metric("revenue_growth", g("revenue_growth"), sector),
                                self._metric("net_income_growth", g("net_income_growth"), sector)]
            eta = None
            if wide is not None and {"equity", "total_assets"} <= set(wide.columns):
                e, t = _num(wide["equity"].iloc[-1]), _num(wide["total_assets"].iloc[-1])
                eta = e / t * 100 if e is not None and t else None
            groups["capital"] = [self._metric("liabilities_to_equity", g("liabilities_to_equity"), sector),
                                 self._metric("equity_to_assets", eta, sector)]
            groups["liquidity"] = [self._metric("current_ratio", g("current_ratio"), sector)]

        weights = self.cfg["health"]["weights"][ftype]
        total_w, acc, avail_w = sum(weights.values()), 0.0, 0.0
        for key, metrics in groups.items():
            scored = [m for m in metrics if m["score"] is not None]
            gs = float(np.mean([m["score"] for m in scored])) if scored else None
            for m in metrics:
                if m["score"] is None:
                    out["missing"].append(f"{GROUP_LABELS[key]}: {m['label']}")
            out["groups"].append({"key": key, "label": GROUP_LABELS[key], "weight": weights.get(key, 0),
                                  "score": gs, "metrics": metrics})
            if gs is not None:
                acc += gs * weights.get(key, 0)
                avail_w += weights.get(key, 0)
        coverage = avail_w / total_w if total_w else 0.0
        partial = acc / avail_w if avail_w else None
        # Chất lượng lợi nhuận: F-score thấp / tăng trưởng nhờ thu nhập tài chính → trừ thẳng (ghi rõ trong notes)
        if partial is not None and ftype == "nonfinancial" and wide is not None:
            from core.phan_tich_co_ban import earnings_quality
            q = earnings_quality(wide)
            out["earnings_quality"] = q
            pen = []
            fp, nc = self.cfg["health"].get("fscore_penalty") or {}, self.cfg["health"].get("non_core_penalty") or {}
            if fp and q.get("fscore") is not None and (q.get("fscore_max") or 0) >= 7 and q["fscore"] <= fp["max_score"]:
                pen.append((fp["points"], f"Piotroski F-score {q['fscore']}/{q['fscore_max']} ≤ {fp['max_score']}"))
            share = q.get("non_core_share_of_op_growth")
            if nc and share is not None and share >= nc["min_share"]:
                pen.append((nc["points"], f"{share:.0f}% mức tăng LN HĐKD đến từ thu nhập tài chính/khác"))
            for pts, why in pen:
                partial = max(0.0, partial - pts)
                out["notes"].append(f"Chất lượng lợi nhuận: {why} → −{pts:g} điểm.")
            out["quality_penalty"] = sum(x for x, _ in pen)
        crit_missing = [GROUP_LABELS[c] for c in self.cfg["health"]["critical_groups"][ftype]
                        if not any(gr["key"] == c and gr["score"] is not None for gr in out["groups"])]
        reliable = partial is not None and not crit_missing and coverage >= self.cfg["health"]["min_coverage"]
        if crit_missing:
            out["notes"].append("Thiếu nhóm bắt buộc: " + ", ".join(crit_missing) + " → không công bố điểm tổng.")
        if coverage < self.cfg["health"]["min_coverage"]:
            out["notes"].append(f"Độ phủ số liệu {coverage * 100:.0f}% < {self.cfg['health']['min_coverage'] * 100:.0f}% → không công bố điểm tổng.")
        out.update(available=reliable, score=round(partial, 1) if reliable else None,
                   partial_score=round(partial, 1) if partial is not None else None, coverage=coverage,
                   rating_text=self.rating_text(partial if reliable else None))
        return out

    @staticmethod
    def rating_text(score: Optional[float]) -> str:
        if score is None:
            return "Chưa đủ dữ liệu"
        return "Rất tốt" if score >= 80 else "Tốt" if score >= 65 else "Trung bình" if score >= 50 else "Yếu" if score >= 35 else "Rất yếu"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/fundamental.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Fundamental Analysis engine.

Analyzes financial statements (IS, BS, CF) and computes:
- Revenue / profit trends
- Profitability ratios (ROE, ROA, margins)
- Debt structure
- Cash flow quality
- Earnings quality warnings
"""


import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


from core.cau_hinh import FUNDAMENTAL_THRESHOLDS as THR

logger = logging.getLogger(__name__)


def _safe_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None or old == 0:
        return None
    return (new - old) / abs(old) * 100


class FundamentalAnalyzer:
    """
    Compute fundamental metrics from financial statement DataFrames.

    Parameters
    ----------
    is_df : Income Statement (quarterly preferred)
    bs_df : Balance Sheet
    cf_df : Cash Flow
    ratio_df : Pre-computed ratios from provider
    symbol : Ticker
    """

    def __init__(
        self,
        is_df: pd.DataFrame,
        bs_df: pd.DataFrame,
        cf_df: pd.DataFrame,
        ratio_df: pd.DataFrame = None,
        symbol: str = "",
        canonical: Optional[pd.DataFrame] = None,
        period: str = "year",
    ):
        """
        canonical: bảng BCTC đã chuẩn hóa (DataRepository.get_financials()["data"]).
                   Khi có, mọi chỉ số được TÍNH TỪ BCTC bằng analytics.financial_ratios
                   thay vì đọc bảng chỉ số dựng sẵn của nhà cung cấp.
        """
        self.canonical = canonical if canonical is not None and not canonical.empty else None
        self.period = period
        # Chuẩn hóa cột (gộp MultiIndex) và SẮP XẾP KỲ tăng dần theo thời gian,
        # để .iloc[-1] luôn là kỳ mới nhất và có thể so sánh đúng cùng kỳ năm trước.
        self.is_df = order_tabular(flatten_columns(is_df))
        self.bs_df = order_tabular(flatten_columns(bs_df))
        self.cf_df = order_tabular(flatten_columns(cf_df))
        self.ratio_df = order_tabular(flatten_columns(ratio_df))
        self.symbol = symbol
        self._metrics: Dict[str, Any] = {}

    # ─────────────────── Column helpers ──────────────────────────────────────

    def _find_col(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """Return first matching column name (case-insensitive)."""
        if df is None or df.empty:
            return None
        for c in candidates:
            for col in df.columns:
                col = str(col)
                if col.lower() == c.lower() or c.lower() in col.lower():
                    return col
        return None

    def _series(self, df: pd.DataFrame, candidates: List[str]) -> pd.Series:
        if df is None or df.empty:
            return pd.Series(dtype=float)

        # 1. Check matching column name (tabular format)
        col = self._find_col(df, candidates)
        if col and col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            if s.notna().any():
                return s

        # 2. Check matrix format (rows are item_id / item, columns are periods)
        id_cols = [c for c in ["item_id", "item", "item_en"] if c in df.columns]
        if id_cols:
            # Cột kỳ được sắp theo đúng thứ tự thời gian (không phải sort chữ cái)
            period_cols, period_keys = ordered_period_columns(df)
            if period_cols:
                for c in candidates:
                    c_clean = c.lower().replace("_", "").replace(" ", "").replace("/", "").replace("%", "")
                    for _, row in df.iterrows():
                        rks = [str(row[ic]).lower() for ic in id_cols if pd.notna(row[ic])]
                        matched = any(
                            c_clean == rk.replace("_", "").replace(" ", "").replace("/", "").replace("%", "")
                            or c_clean in rk.replace("_", "").replace(" ", "").replace("/", "").replace("%", "")
                            or rk.replace("_", "").replace(" ", "").replace("/", "").replace("%", "") in c_clean
                            for rk in rks
                        )
                        if matched:
                            vals = pd.to_numeric(row[period_cols], errors="coerce")
                            if all(k is not None for k in period_keys):
                                vals.index = period_keys
                            vals = vals.dropna()
                            if not vals.empty:
                                return vals

        return pd.Series(dtype=float)

    # ─────────────────── Revenue & Profit ────────────────────────────────────

    def get_revenue_profit_trend(self) -> Dict[str, Any]:
        if self.is_df.empty:
            return {"available": False, "reason": "Không có dữ liệu KQKD"}

        # Try common Vietnamese and English column names
        revenue = self._series(self.is_df, [
            "doanh thu", "revenue", "net revenue", "doanh_thu", "doanh thu thuần", "operating_sales", "net_sales"
        ])
        net_profit = self._series(self.is_df, [
            "lợi nhuận sau thuế", "net profit", "profit after tax", "loi_nhuan", "LNST", "net_profit", "profit_after_tax"
        ])
        gross_profit = self._series(self.is_df, [
            "lợi nhuận gộp", "gross profit", "loi nhuan gop", "gross_profit"
        ])

        result: Dict[str, Any] = {"available": True}

        if not revenue.empty and revenue.notna().any():
            rev = revenue.dropna()
            g = growth_vs_prior(rev)
            result["revenue_latest"] = float(rev.iloc[-1])
            result["revenue_prev"] = float(rev.iloc[-2]) if len(rev) > 1 else None
            # revenue_yoy = tăng trưởng so với CÙNG KỲ năm trước khi xác định được kỳ
            result["revenue_yoy"] = g["pct"]
            result["revenue_growth_basis"] = g["basis"]
            result["latest_period"] = g["latest_period"]
            result["compare_period"] = g["compare_period"]
            result["revenue_series"] = rev.values.tolist()
            result["periods"] = [key_to_label(k) for k in rev.index]

        if not net_profit.empty and net_profit.notna().any():
            npf = net_profit.dropna()
            g = growth_vs_prior(npf)
            result["net_profit_latest"] = float(npf.iloc[-1])
            result["net_profit_prev"] = float(npf.iloc[-2]) if len(npf) > 1 else None
            result["net_profit_yoy"] = g["pct"]
            result["net_profit_growth_basis"] = g["basis"]
            result["net_profit_series"] = npf.values.tolist()
            result["net_profit_periods"] = [key_to_label(k) for k in npf.index]

        # Margin
        rev_l = result.get("revenue_latest")
        np_l = result.get("net_profit_latest")
        gp_vals = gross_profit.dropna().values if not gross_profit.empty else []
        gp_l = float(gp_vals[-1]) if len(gp_vals) else None

        if rev_l and rev_l != 0:
            if np_l is not None:
                result["net_margin"] = np_l / rev_l * 100
            if gp_l is not None:
                result["gross_margin"] = gp_l / rev_l * 100

        # Quality warning: revenue up but profit down
        result["warnings"] = []
        rev_yoy = result.get("revenue_yoy")
        np_yoy = result.get("net_profit_yoy")
        if rev_yoy is not None and np_yoy is not None:
            if rev_yoy > 5 and np_yoy < -5:
                result["warnings"].append("Doanh thu tăng nhưng lợi nhuận giảm – cần kiểm tra chi phí")

        return result

    # ─────────────────── ROE / ROA ────────────────────────────────────────────

    def get_return_metrics(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        # From ratio df if available
        if not self.ratio_df.empty:
            roe = self._series(self.ratio_df, ["roe", "return on equity"])
            roa = self._series(self.ratio_df, ["roa", "return on assets"])
            if not roe.empty and roe.notna().any():
                v = float(roe.dropna().iloc[-1])
                result["roe"] = v * 100 if abs(v) < 1.0 else v
            if not roa.empty and roa.notna().any():
                v = float(roa.dropna().iloc[-1])
                result["roa"] = v * 100 if abs(v) < 1.0 else v

        # Compute from IS + BS if not available from ratios
        if "roe" not in result and not self.is_df.empty and not self.bs_df.empty:
            np_series = self._series(self.is_df, ["lợi nhuận sau thuế", "net profit", "LNST", "net_profit", "profit_after_tax"])
            equity_series = self._series(self.bs_df, ["vốn chủ sở hữu", "equity", "total equity", "owners_equity"])
            if np_series.notna().any() and equity_series.notna().any():
                np_val = float(np_series.dropna().iloc[-1])
                eq_val = float(equity_series.dropna().iloc[-1])
                if eq_val != 0:
                    result["roe"] = np_val / eq_val * 100

        if "roa" not in result and not self.is_df.empty and not self.bs_df.empty:
            np_series = self._series(self.is_df, ["lợi nhuận sau thuế", "net profit", "LNST", "net_profit", "profit_after_tax"])
            asset_series = self._series(self.bs_df, ["tổng tài sản", "total assets", "total_assets"])
            if np_series.notna().any() and asset_series.notna().any():
                np_val = float(np_series.dropna().iloc[-1])
                ta_val = float(asset_series.dropna().iloc[-1])
                if ta_val != 0:
                    result["roa"] = np_val / ta_val * 100

        return result

    # ─────────────────── Debt ────────────────────────────────────────────────

    def get_debt_metrics(self) -> Dict[str, Any]:
        if self.bs_df.empty and self.ratio_df.empty:
            return {"available": False}

        result: Dict[str, Any] = {"available": True}
        total_debt = self._series(self.bs_df, ["tổng nợ", "total debt", "total liabilities", "nợ phải trả", "liabilities"])
        equity = self._series(self.bs_df, ["vốn chủ sở hữu", "equity", "total equity", "owners_equity"])
        total_assets = self._series(self.bs_df, ["tổng tài sản", "total assets", "total_assets"])

        if not total_debt.empty and total_debt.notna().any():
            result["total_debt"] = float(total_debt.dropna().iloc[-1])
        if not equity.empty and equity.notna().any():
            eq = float(equity.dropna().iloc[-1])
            result["equity"] = eq
            td = result.get("total_debt")
            if td is not None and eq != 0:
                result["debt_to_equity"] = td / eq

        if not total_assets.empty and total_assets.notna().any():
            ta = float(total_assets.dropna().iloc[-1])
            result["total_assets"] = ta
            td = result.get("total_debt")
            if td is not None and ta != 0:
                result["debt_to_assets"] = td / ta

        # Also fallback to pre-calculated ratio from ratio_df
        if "debt_to_equity" not in result and not self.ratio_df.empty:
            de_r = self._series(self.ratio_df, ["debt_to_equity", "debtPerEquity", "nợ/vốn chủ", "nợ trên vốn chủ"])
            if not de_r.empty and de_r.notna().any():
                result["debt_to_equity"] = float(de_r.dropna().iloc[-1])

        # Warning
        result["warnings"] = []
        de = result.get("debt_to_equity")
        if de is not None and de > THR["debt_equity_high"]:
            result["warnings"].append(f"Tỷ lệ Nợ/VCSH cao: {de:.2f}x")

        return result

    # ─────────────────── Cash Flow ────────────────────────────────────────────

    def get_cashflow_metrics(self) -> Dict[str, Any]:
        if self.cf_df.empty:
            return {"available": False}

        result: Dict[str, Any] = {"available": True}
        cfo = self._series(self.cf_df, [
            "tiền từ hoạt động kinh doanh", "operating cash flow", "CFO", "cash from operations", "operating_cash_flows", "hoạt động kinh doanh"
        ])
        capex = self._series(self.cf_df, [
            "mua tài sản cố định", "capex", "capital expenditure", "purchase_of_fixed_assets", "tiền chi để mua sắm"
        ])

        if not cfo.empty and cfo.notna().any():
            result["cfo_latest"] = float(cfo.dropna().iloc[-1])
            result["cfo_series"] = cfo.dropna().tolist()

        if not capex.empty and capex.notna().any():
            cap = float(capex.dropna().iloc[-1])
            result["capex_latest"] = cap
            cfo_l = result.get("cfo_latest")
            if cfo_l is not None:
                result["fcf"] = cfo_l + cap  # capex usually negative in CF

        result["warnings"] = []
        cfo_l = result.get("cfo_latest")
        np_ref = None  # Would need IS data
        if cfo_l is not None and cfo_l < 0:
            result["warnings"].append("Dòng tiền hoạt động âm – cần chú ý")

        return result

    # ─────────────────── Full metrics ────────────────────────────────────────

    # ─────────────────── Canonical path (tính từ BCTC) ───────────────────────

    def _compute_all_canonical(self) -> Dict[str, Any]:
        from core.phan_tich_co_ban import compute_ratios
        w = self.canonical.sort_index()
        ratios = compute_ratios(w, self.period)
        last = ratios.iloc[-1] if not ratios.empty else pd.Series(dtype=float)
        val = lambda s, k: (float(s[k]) if k in s.index and pd.notna(s[k]) else None)  # noqa: E731
        rp: Dict[str, Any] = {"available": True, "warnings": []}
        rev_col = "revenue" if "revenue" in w.columns else ("total_operating_income" if "total_operating_income" in w.columns else None)
        if rev_col:
            rev = w[rev_col].dropna()
            g = growth_vs_prior(rev)
            rp.update({"revenue_latest": float(rev.iloc[-1]) if len(rev) else None,
                       "revenue_yoy": g["pct"], "revenue_growth_basis": g["basis"],
                       "latest_period": g["latest_period"], "compare_period": g["compare_period"],
                       "revenue_series": rev.values.tolist(), "periods": [key_to_label(k) for k in rev.index]})
        ni_col = "net_income_parent" if "net_income_parent" in w.columns else ("net_income" if "net_income" in w.columns else None)
        if ni_col:
            npf = w[ni_col].dropna()
            g = growth_vs_prior(npf)
            rp.update({"net_profit_latest": float(npf.iloc[-1]) if len(npf) else None,
                       "net_profit_yoy": g["pct"], "net_profit_growth_basis": g["basis"],
                       "net_profit_series": npf.values.tolist(),
                       "net_profit_periods": [key_to_label(k) for k in npf.index]})
        rp["net_margin"] = val(last, "net_margin")
        rp["gross_margin"] = val(last, "gross_margin")
        if rp.get("revenue_yoy") is not None and rp.get("net_profit_yoy") is not None \
                and rp["revenue_yoy"] > 5 and rp["net_profit_yoy"] < -5:
            rp["warnings"].append("Doanh thu tăng nhưng lợi nhuận giảm – cần kiểm tra chi phí")
        de = val(last, "debt_to_equity")
        if de is None:
            de = val(last, "liabilities_to_equity")
        debt = {"available": True, "debt_to_equity": de,
                "liabilities_to_equity": val(last, "liabilities_to_equity"),
                "debt_to_assets": (val(last, "liabilities_to_assets") or 0) / 100 if val(last, "liabilities_to_assets") is not None else None,
                "warnings": []}
        if de is not None and de > THR["debt_equity_high"]:
            debt["warnings"].append(f"Tỷ lệ Nợ/VCSH cao: {de:.2f}x")
        cfo = w["cfo"].dropna() if "cfo" in w.columns else pd.Series(dtype=float)
        cf = {"available": not cfo.empty, "cfo_latest": float(cfo.iloc[-1]) if not cfo.empty else None,
              "fcf": val(last, "fcf"), "cfo_series": cfo.tolist(), "warnings": []}
        if cf["cfo_latest"] is not None and cf["cfo_latest"] < 0:
            cf["warnings"].append("Dòng tiền hoạt động âm – cần chú ý")
        return {
            "revenue_profit": rp,
            "return_metrics": {"roe": val(last, "roe"), "roa": val(last, "roa"), "roic": val(last, "roic")},
            "debt": debt,
            "cashflow": cf,
            "ratios": ratios,
            "symbol": self.symbol,
            "basis": "Tính từ BCTC chuẩn hóa" + (" (TTM)" if self.period == "quarter" else ""),
        }

    def compute_all(self) -> Dict[str, Any]:
        if self.canonical is not None:
            return self._compute_all_canonical()
        return {
            "revenue_profit": self.get_revenue_profit_trend(),
            "return_metrics": self.get_return_metrics(),
            "debt": self.get_debt_metrics(),
            "cashflow": self.get_cashflow_metrics(),
            "symbol": self.symbol,
        }

    # ─────────────────── Fundamental Score ───────────────────────────────────

    def _earnings_quality(self) -> Optional[Dict[str, Any]]:
        if self.canonical is None:
            return None
        try:
            from core.phan_tich_co_ban import earnings_quality
            return earnings_quality(self.canonical)
        except Exception:
            return None

    def compute_fundamental_score(self) -> Dict[str, Any]:
        """
        Score fundamental quality 0–100.

        Components:
          ROE (25), Revenue growth (20), Margin (20), Debt (20), CFO quality (15)
        """
        metrics = self.compute_all()
        components: Dict[str, Any] = {}
        total = 0.0
        max_pts = 0
        missing = []

        # ── ROE (25) ──
        max_pts += 25
        rm = metrics.get("return_metrics", {})
        roe = rm.get("roe")
        if roe is not None:
            if roe >= THR["roe_excellent"]:
                s = 25
            elif roe >= THR["roe_good"]:
                s = 18
            elif roe >= THR["roe_fair"]:
                s = 12
            elif roe >= 0:
                s = 5
            else:
                s = 0
            components["roe"] = {"score": s, "max": 25, "value": round(roe, 2)}
            total += s
        else:
            missing.append("ROE")
            components["roe"] = {"score": None, "max": 25, "reason": "Không có dữ liệu"}

        # ── Revenue Growth (20) ──
        max_pts += 20
        rp = metrics.get("revenue_profit", {})
        rev_yoy = rp.get("revenue_yoy")
        if rev_yoy is not None:
            if rev_yoy >= 20:
                s = 20
            elif rev_yoy >= 10:
                s = 15
            elif rev_yoy >= 0:
                s = 10
            elif rev_yoy >= -10:
                s = 5
            else:
                s = 0
            components["revenue_growth"] = {
                "score": s, "max": 20, "value": round(rev_yoy, 1),
                "basis": rp.get("revenue_growth_basis"),
            }
            total += s
        else:
            missing.append("Tăng trưởng DT")
            components["revenue_growth"] = {"score": None, "max": 20}

        # ── Net Margin (20) ──
        max_pts += 20
        margin = rp.get("net_margin")
        if margin is not None:
            if margin >= THR["net_margin_excellent"]:
                s = 20
            elif margin >= THR["net_margin_good"]:
                s = 14
            elif margin >= THR["net_margin_fair"]:
                s = 8
            elif margin >= 0:
                s = 3
            else:
                s = 0
            components["margin"] = {"score": s, "max": 20, "value": round(margin, 2)}
            total += s
        else:
            missing.append("Biên lợi nhuận")
            components["margin"] = {"score": None, "max": 20}

        # ── Debt (20) ──
        max_pts += 20
        debt = metrics.get("debt", {})
        de = debt.get("debt_to_equity")
        if de is not None:
            if de <= 0.5:
                s = 20
            elif de <= 1.0:
                s = 15
            elif de <= 1.5:
                s = 10
            elif de <= THR["debt_equity_high"]:
                s = 5
            else:
                s = 0
            components["debt"] = {"score": s, "max": 20, "value": round(de, 2)}
            total += s
        else:
            missing.append("Cơ cấu nợ")
            components["debt"] = {"score": None, "max": 20}

        # ── CFO quality (15) ──
        max_pts += 15
        cf = metrics.get("cashflow", {})
        cfo = cf.get("cfo_latest")
        np_l = rp.get("net_profit_latest")
        if cfo is not None:
            if cfo > 0:
                if np_l and np_l > 0:
                    # CFO/NP ratio > 1 is ideal
                    ratio = cfo / np_l
                    if ratio >= 1.0:
                        s = 15
                    elif ratio >= 0.5:
                        s = 10
                    else:
                        s = 5
                else:
                    s = 8
            else:
                s = 0
            components["cashflow"] = {"score": s, "max": 15, "cfo": cfo}
            total += s
        else:
            missing.append("Dòng tiền")
            components["cashflow"] = {"score": None, "max": 15}

        # Compute score only on available data
        available_max = sum(
            c["max"] for c in components.values() if c.get("score") is not None
        )
        available_total = sum(
            c["score"] for c in components.values() if c.get("score") is not None
        )

        if available_max == 0:
            final_score = None
            note = "Không đủ dữ liệu để chấm điểm"
        else:
            final_score = round((available_total / available_max) * 100)
            note = f"Tính trên {len(components) - len(missing)}/{len(components)} nhóm chỉ tiêu"
            # Chất lượng lợi nhuận (F-score, LN cốt lõi so với LNST, CFO/FCF): "Yếu" −15 điểm, "Cần lưu ý" −5 điểm.
            q = self._earnings_quality()
            if q and q.get("available"):
                pen = 15 if q.get("verdict") == "Yếu" else 5 if q.get("verdict") == "Cần lưu ý" else 0
                components["earnings_quality"] = {"score": -pen if pen else 0, "max": 0, "verdict": q.get("verdict"),
                                                  "flags": [f["text"] for f in q.get("flags", [])]}
                if pen:
                    final_score = max(0, final_score - pen)
                    note += f"; chất lượng lợi nhuận {q['verdict'].lower()} → −{pen} điểm"

        return {
            "score": final_score,
            "note": note,
            "components": components,
            "missing_data": missing,
        }


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: analytics/peers.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
So sánh ngành (peer comparison).

Tính TRUNG VỊ các chỉ số P/E, P/B, ROE, Biên LN ròng, Nợ/VCSH của các doanh nghiệp
cùng nhóm ngành (lấy từ BASKETS trong core/du_lieu.py), dùng dữ liệu thật
từ bảng chỉ số tài chính của từng mã.

Thay thế cho các hằng số cố định trước đây (P/E = 15, P/B = 1.5 cho mọi mã,
và số "trung vị ngành" gõ tay trong báo cáo PDF).
"""


import logging
from statistics import median
from typing import Any, Callable, Dict, List, Optional

import pandas as pd



logger = logging.getLogger(__name__)

# Rổ chỉ số (không phải ngành) – bỏ qua khi tìm nhóm ngành
_INDEX_BASKET_MARKERS = ("Tất cả", "VN30", "HNX30")

# Lọc giá trị ngoại lai trước khi lấy trung vị
_BOUNDS = {
    "pe": (0, 100),
    "pb": (0, 20),
    "roe": (-100, 100),
    "net_margin": (-100, 100),
    "de": (0, 20),
}
MIN_PEERS = 3          # cần tối thiểu 3 DN có số liệu mới công bố trung vị

# Công ty mẹ – con / cùng tập đoàn: loại khỏi nhóm so sánh của nhau (số liệu hợp nhất trùng lặp, không phải "đối thủ").
RELATED_GROUPS = [
    {"FPT", "FOX", "FRT", "FTS"},          # FPT – FPT Telecom – FPT Retail – CK FPT
    {"CTR", "VGI", "VTP", "VTK"},          # nhóm Viettel
    {"VIC", "VHM", "VRE", "VEF"},          # Vingroup
    {"MSN", "MCH", "MML", "MSR"},          # Masan
    {"GAS", "PVS", "PVD", "PVT", "PVC", "PVB", "PLX", "BSR", "OIL", "POW"},   # PVN (không đối thủ trực tiếp)
    {"HPG", "HPX"}, {"GEX", "VIX", "GEE", "GEG", "VGC"}, {"REE", "VSH"},
]


def related_symbols(symbol: str) -> set:
    s = symbol.upper()
    return set().union(*[g for g in RELATED_GROUPS if s in g]) - {s} if any(s in g for g in RELATED_GROUPS) else set()


def _exchange(symbol: str) -> str:
    try:
        from core.du_lieu import get_symbol_map
        return str((get_symbol_map().get(symbol.upper()) or {}).get("exchange") or "").upper()
    except Exception:
        return ""
DEFAULT_MAX_PEERS = 8  # giới hạn số mã gọi API (vnstock giới hạn tần suất request)


def find_sector_basket(symbol: str) -> Optional[str]:
    """Tên nhóm ngành đầu tiên chứa mã (bỏ qua các rổ chỉ số VN30/HNX30)."""
    sym = symbol.upper().strip()
    for name, tickers in BASKETS.items():
        if any(m in name for m in _INDEX_BASKET_MARKERS):
            continue
        if sym in tickers:
            return name
    return None


def _clean_group_name(name: str) -> str:
    # Bỏ emoji ở đầu tên rổ: "🏦 Ngân hàng" -> "Ngân hàng"
    parts = name.split(" ", 1)
    return parts[1] if len(parts) == 2 and not parts[0].isalnum() else name


def _pct(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return v * 100 if abs(v) < 1.0 else v


def extract_peer_metrics(symbol: str, ratio_df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Đọc P/E, P/B, ROE, Biên LN ròng, Nợ/VCSH (kỳ mới nhất) từ bảng ratio của 1 mã."""
    if ratio_df is None or ratio_df.empty:
        return {}
    ve = ValuationEngine(symbol, 0, ratio_df=ratio_df)
    fa = FundamentalAnalyzer(None, None, None, ratio_df=ratio_df, symbol=symbol)

    def last(candidates: List[str]) -> Optional[float]:
        s = fa._series(fa.ratio_df, candidates)
        s = pd.to_numeric(s, errors="coerce").dropna()
        return float(s.iloc[-1]) if not s.empty else None

    pe = ve._col(ve.ratio_df, ["pe_ratio", "p/e", "pe", "price earning", "price to earnings"])
    pb = ve._col(ve.ratio_df, ["pb_ratio", "p/b", "pb", "price book", "price to book"])
    roe = fa.get_return_metrics().get("roe")
    margin = _pct(last(["net_profit_margin", "biên lợi nhuận ròng", "net margin", "netprofitmargin"]))
    de = last(["debt_to_equity", "debtPerEquity", "nợ/vcsh", "nợ/vốn chủ", "nợ trên vốn chủ"])
    mcap = ve._col(ve.ratio_df, ["market_cap", "market_capital", "marketcap", "vốn hóa", "von hoa", "market capitalization"])
    return {"pe": pe, "pb": pb, "roe": roe, "net_margin": margin, "de": de,
            "mcap": float(mcap) if mcap is not None and mcap > 0 else None}


def weighted_median(values: List[Optional[float]], weights: List[Optional[float]], key: str) -> Optional[float]:
    """Trung vị CÓ TRỌNG SỐ VỐN HÓA (góp ý GK II.2): doanh nghiệp vài trăm tỷ không kéo trung vị ngang tập đoàn lớn.
    Cần ≥ MIN_PEERS mã có cả bội số hợp lệ và vốn hóa; không đủ → None (dùng trung vị thường)."""
    lo, hi = _BOUNDS[key]
    pairs = sorted((float(v), float(w)) for v, w in zip(values, weights)
                   if v is not None and w is not None and pd.notna(v) and pd.notna(w) and lo < float(v) < hi and w > 0)
    if len(pairs) < MIN_PEERS:
        return None
    total, acc = sum(w for _, w in pairs), 0.0
    for v, w in pairs:
        acc += w
        if acc >= total / 2:
            return round(v, 2)
    return round(pairs[-1][0], 2)


def _robust_median(values: List[Optional[float]], key: str) -> Optional[float]:
    lo, hi = _BOUNDS[key]
    clean = [float(v) for v in values if v is not None and pd.notna(v) and lo < float(v) < hi]
    return round(median(clean), 2) if len(clean) >= MIN_PEERS else None


def compute_peer_stats(
    symbol: str,
    ratio_fetcher: Callable[[str], pd.DataFrame],
    max_peers: int = DEFAULT_MAX_PEERS,
) -> Dict[str, Any]:
    """
    Parameters
    ----------
    symbol        : mã cần so sánh
    ratio_fetcher : hàm(symbol) -> DataFrame chỉ số tài chính (vd. repo.get_financial_ratios)

    Returns
    -------
    dict: group, peers, n, pe, pb, roe, net_margin, de, n_<metric>
          (giá trị None nếu có ít hơn MIN_PEERS doanh nghiệp có số liệu)
    """
    basket = find_sector_basket(symbol)
    if basket is None:
        return {"group": None, "n": 0, "reason": "Mã chưa được phân loại vào nhóm ngành nào"}

    # Loại công ty mẹ/con cùng tập đoàn; mã niêm yết HOSE/HNX thì ưu tiên so với mã HOSE/HNX (UPCoM thường thanh khoản
    # thấp, bội số kém tin cậy) – chỉ loại UPCoM khi còn đủ MIN_PEERS + 1 mã.
    excluded: List[str] = []
    rel = related_symbols(symbol)
    cands = [t for t in BASKETS[basket] if t != symbol.upper()]
    excluded += [f"{t} (cùng tập đoàn)" for t in cands if t in rel]
    cands = [t for t in cands if t not in rel]
    if _exchange(symbol) in ("HOSE", "HSX", "HNX"):
        listed = [t for t in cands if _exchange(t) not in ("UPCOM",)]
        if len(listed) >= MIN_PEERS + 1:
            excluded += [f"{t} (UPCoM)" for t in cands if t not in listed]
            cands = listed
    peers = cands[:max_peers]
    rows: List[Dict[str, Optional[float]]] = []
    used: List[str] = []
    for peer in peers:
        try:
            m = extract_peer_metrics(peer, ratio_fetcher(peer))
            if any(v is not None for v in m.values()):
                rows.append(m)
                used.append(peer)
        except Exception as exc:  # một mã lỗi không làm hỏng cả nhóm
            logger.debug("Peer %s failed: %s", peer, exc)

    out: Dict[str, Any] = {"group": _clean_group_name(basket), "peers": used, "n": len(used), "excluded": excluded}
    # Số liệu từng mã (đã lọc ngoài khoảng hợp lệ) – để vẽ biểu đồ so sánh ngành
    out["by_peer"] = {t: {k: (round(float(r[k]), 2) if r.get(k) is not None and pd.notna(r.get(k))
                              and _BOUNDS[k][0] < float(r[k]) < _BOUNDS[k][1] else None) for k in _BOUNDS}
                      for t, r in zip(used, rows)}
    caps = [r.get("mcap") for r in rows]
    for key in ("pe", "pb"):
        out[f"{key}_capw"] = weighted_median([r.get(key) for r in rows], caps, key)
    for key in _BOUNDS:
        vals = [r.get(key) for r in rows]
        out[key] = _robust_median(vals, key)
        lo, hi = _BOUNDS[key]
        out[f"n_{key}"] = sum(1 for v in vals if v is not None and lo < float(v) < hi)
    return out


# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Import chéo (các file import lẫn nhau) – đặt CUỐI file để tránh vòng lặp import; chỉ được dùng bên trong hàm.
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
from core.dinh_gia import ValuationEngine
from core.du_lieu import BASKETS
