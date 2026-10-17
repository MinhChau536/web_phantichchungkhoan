"""
core/cau_hinh.py – gộp từ 3 module (15/10/2026).

MỤC LỤC
  • config/settings.py – Global settings and configuration loader.
      hàm/lớp chính: Settings
  • config/constants.py – Application-wide constants for Stock Analytics.
  • config/investment_model.py – Cấu hình mô hình Khuyến nghị đầu tư & Giá mục tiêu.
      hàm/lớp chính: load_config, classify_company
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: config/settings.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Global settings and configuration loader.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    # Base paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", str(BASE_DIR / "data" / "cache")))
    REPORTS_DIR: Path = Path(os.getenv("REPORTS_DIR", str(BASE_DIR / "reports" / "output")))
    ASSETS_DIR: Path = BASE_DIR / "assets"
    DOCUMENTS_DIR: Path = Path(os.getenv("DOCUMENTS_DIR", str(BASE_DIR / "data" / "documents")))

    # Database
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "stock_analytics.duckdb"))

    # DNSE API
    _raw_dnse_url = os.getenv("DNSE_BASE_URL", "").strip()
    DNSE_BASE_URL: str = (
        _raw_dnse_url
        if _raw_dnse_url.startswith(("http://", "https://")) and len(_raw_dnse_url) > 10
        else "https://api.dnse.com.vn"
    )
    # Giá REALTIME qua DNSE OpenAPI (WebSocket). Lấy API key + secret tại Entrade X → Thông tin cá nhân → Light Speed.
    # Để trống → app dùng giá gần realtime (API biểu đồ công khai, ~3 phút/lần) như trước. Chỉ đọc giá, không đặt lệnh.
    DNSE_API_KEY: str = os.getenv("DNSE_API_KEY", "").strip()
    DNSE_API_SECRET: str = (os.getenv("DNSE_API_SECRET", "") or os.getenv("DNSE_SECRET_KEY", "")).strip()
    DNSE_WS_URL: str = (os.getenv("DNSE_WS_URL", "") or "wss://ws-openapi.dnse.com.vn").strip().rstrip("/")
    DNSE_REALTIME: bool = os.getenv("DNSE_REALTIME", "1").strip().lower() not in ("0", "false", "no", "off")
    # Nhịp làm mới ô giá trên trang khi realtime đang chạy (giây, tối thiểu 2)
    REALTIME_REFRESH_SECONDS: int = max(2, int(os.getenv("REALTIME_REFRESH_SECONDS", "3")))

    # Vnstock
    VNSTOCK_SOURCE: str = os.getenv("VNSTOCK_SOURCE", "VCI").strip()
    VNSTOCK_API_KEY: str = os.getenv("VNSTOCK_API_KEY", "").strip()

    # ── Chiến lược nguồn dữ liệu ──
    # Giá: N ngày gần nhất lấy từ DNSE, phần trước đó lấy từ vnstock / Vietstock
    DNSE_RECENT_DAYS: int = int(os.getenv("DNSE_RECENT_DAYS", "365"))
    # Thứ tự ưu tiên nguồn giá lịch sử (phần cũ hơn DNSE_RECENT_DAYS)
    PRICE_HISTORY_SOURCES: list = [
        s.strip().lower() for s in os.getenv("PRICE_HISTORY_SOURCES", "vnstock_vci,vnstock_kbs,vnstock_msn,vietstock").split(",")
        if s.strip()
    ]
    # Thứ tự ưu tiên nguồn BCTC (nguồn sau bù phần nguồn trước thiếu)
    FINANCIAL_SOURCES: list = [
        s.strip().lower() for s in os.getenv("FINANCIAL_SOURCES", "vnstock_vci,vnstock_kbs,vietstock,arminer,pdf").split(",")
        if s.strip()
    ]
    # Thứ tự ưu tiên nguồn tài liệu PDF (BCTN / BCTC)
    DOCUMENT_SOURCES: list = [
        s.strip().lower() for s in os.getenv("DOCUMENT_SOURCES", "vietstock,cafef").split(",") if s.strip()
    ]

    # App settings
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Cache TTL (seconds)
    # Giá NGÀY đã đóng cửa chỉ đổi sau giờ đóng cửa; giá trong phiên do nến tạm (cập nhật LIVE_REFRESH_SECONDS) lo →
    # nhớ chuỗi giá 30 phút (trước 5 phút) để chuyển trang không tải lại. Giá trị nhỏ hơn trong .env cũ bị nâng lên 1800.
    CACHE_TTL_PRICE: int = max(1800, int(os.getenv("CACHE_TTL_PRICE", "1800")))
    CACHE_TTL_FINANCIAL: int = int(os.getenv("CACHE_TTL_FINANCIAL", "3600"))
    CACHE_TTL_MARKET: int = int(os.getenv("CACHE_TTL_MARKET", "170"))    # < chu kỳ làm mới 180 giây → mỗi lần làm mới lấy giá mới
    CACHE_TTL_NEWS: int = int(os.getenv("CACHE_TTL_NEWS", "1800"))
    CACHE_TTL_DOCUMENTS: int = int(os.getenv("CACHE_TTL_DOCUMENTS", "86400"))
    CACHE_SCHEMA_VERSION: str = os.getenv("CACHE_SCHEMA_VERSION", "gpm1-v4").strip() or "gpm1-v4"

    # API settings
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "12"))     # giây; máy chủ treo không giữ trang quá lâu
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
    RETRY_BACKOFF: float = 1.5
    MAX_DOCUMENT_BYTES: int = int(os.getenv("MAX_DOCUMENT_BYTES", str(100 * 1024 * 1024)))
    # Giá trong phiên (DNSE) tự cập nhật mỗi 3 phút (14/10/2026). Chu kỳ 10 giây trước đây hay bị DNSE giới hạn số lượt
    # gọi → trả giá cũ/không khớp. Giá trị trong .env thấp hơn 180 giây (vd LIVE_REFRESH_SECONDS=10 cũ) bị nâng lên 180.
    LIVE_REFRESH_SECONDS: int = max(180, int(os.getenv("LIVE_REFRESH_SECONDS", "180")))

    # Point-in-time fallback. Ngày công bố thật (available_at) luôn được ưu tiên;
    # các độ trễ này chỉ dùng khi nguồn không cung cấp ngày công bố.
    ANNUAL_RELEASE_MONTH: int = int(os.getenv("ANNUAL_RELEASE_MONTH", "4"))
    QUARTER_RELEASE_LAG_DAYS: int = int(os.getenv("QUARTER_RELEASE_LAG_DAYS", "50"))
    # Beta luôn tính trên CÙNG một cửa sổ (mặc định 365 ngày lịch ≈ 250 phiên) – không phụ thuộc số ngày giá
    # mà từng trang tải → app, trang Khuyến nghị và báo cáo PDF ra cùng beta / Ke / giá mục tiêu.
    BETA_WINDOW_DAYS: int = max(180, int(os.getenv("BETA_WINDOW_DAYS", "365")))

    # Trading
    DEFAULT_TRANSACTION_FEE: float = 0.0015  # 0.15%
    DEFAULT_SLIPPAGE: float = 0.001  # 0.1%

    # Analysis defaults
    DEFAULT_LOOKBACK_DAYS: int = 365
    MIN_DATA_POINTS: int = 30

    @classmethod
    def ensure_dirs(cls):
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        (cls.BASE_DIR / "reports" / "templates").mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls):
        """Fail fast với cấu hình nguy hiểm/thường bị gõ sai."""
        if cls.REQUEST_TIMEOUT <= 0:
            raise ValueError("REQUEST_TIMEOUT phải lớn hơn 0")
        if cls.MAX_DOCUMENT_BYTES < 1024 * 1024:
            raise ValueError("MAX_DOCUMENT_BYTES phải ít nhất 1 MiB")
        if not 1 <= cls.ANNUAL_RELEASE_MONTH <= 12:
            raise ValueError("ANNUAL_RELEASE_MONTH phải nằm trong 1..12")
        if cls.QUARTER_RELEASE_LAG_DAYS < 0:
            raise ValueError("QUARTER_RELEASE_LAG_DAYS không được âm")


settings = Settings()
settings.validate()
settings.ensure_dirs()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: config/constants.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Application-wide constants for Stock Analytics.
"""
from typing import Dict, List

# ─────────────────────────── Exchanges ──────────────────────────────────────
EXCHANGES = ["HOSE", "HNX", "UPCOM"]

# ─────────────────────────── Market Indices ──────────────────────────────────
MARKET_INDICES = {
    "VNINDEX": "VN-Index",
    "VN30": "VN30",
    "HNXINDEX": "HNX-Index",
    "UPCOMINDEX": "UPCoM-Index",
}

# ─────────────────────────── Sectors ─────────────────────────────────────────
SECTORS = [
    "Ngân hàng",
    "Bất động sản",
    "Công nghệ thông tin",
    "Công nghiệp",
    "Vật liệu cơ bản",
    "Hàng tiêu dùng",
    "Dịch vụ tiêu dùng",
    "Năng lượng",
    "Y tế",
    "Dịch vụ tài chính",
    "Bảo hiểm",
    "Viễn thông",
    "Tiện ích công cộng",
    "Nông nghiệp",
    "Hàng không - Vận tải",
]

# ─────────────────────────── Intervals ───────────────────────────────────────
INTERVALS = {
    "1m": "1 phút",
    "5m": "5 phút",
    "15m": "15 phút",
    "30m": "30 phút",
    "1H": "1 giờ",
    "1D": "1 ngày",
    "1W": "1 tuần",
    "1M": "1 tháng",
}

DNSE_INTERVAL_MAP = {
    "1D": "1",
    "1W": "W",
    "1M": "M",
    "1H": "60",
    "30m": "30",
    "15m": "15",
    "5m": "5",
    "1m": "1",
}

# ─────────────────────────── Technical Indicators ────────────────────────────
SMA_PERIODS = [10, 20, 50, 100, 200]
EMA_PERIODS = [12, 26]
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
ATR_PERIOD = 14
ADX_PERIOD = 14
MFI_PERIOD = 14
CMF_PERIOD = 20
ROC_PERIOD = 10

# ─────────────────────────── Scoring Weights ─────────────────────────────────
DEFAULT_SCORE_WEIGHTS = {
    "technical": 25,
    "momentum": 20,
    "fundamental": 25,
    "valuation": 20,
    "risk": 10,
}

SCORE_CATEGORIES = {
    (80, 100): ("Cơ hội nổi bật", "#00e676", "🌟"),
    (65, 79): ("Tích cực", "#69f0ae", "✅"),
    (50, 64): ("Trung tính", "#ffd740", "⚖️"),
    (35, 49): ("Cơ hội thấp", "#ff8f00", "⚠️"),
    (0, 34): ("Cơ hội rất thấp", "#ff1744", "🚨"),      # trước đây "Rủi ro cao" – dễ nhầm với mức rủi ro thật
}

# ─────────────────────────── Fundamental Thresholds ──────────────────────────
FUNDAMENTAL_THRESHOLDS = {
    "roe_excellent": 20,
    "roe_good": 15,
    "roe_fair": 10,
    "roa_excellent": 10,
    "roa_good": 7,
    "roa_fair": 3,
    "pe_overvalued": 30,
    "pe_fair": 20,
    "pe_cheap": 12,
    "pb_overvalued": 3,
    "pb_fair": 1.5,
    "pb_cheap": 1.0,
    "debt_equity_high": 2.0,
    "net_margin_excellent": 20,
    "net_margin_good": 10,
    "net_margin_fair": 5,
}

# ─────────────────────────── RSI Zones ───────────────────────────────────────
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
RSI_NEUTRAL_HIGH = 60
RSI_NEUTRAL_LOW = 40

# ─────────────────────────── Colors ─────────────────────────────────────────
COLOR_BULLISH = "#00e676"
COLOR_BEARISH = "#ff1744"
COLOR_NEUTRAL = "#90a4ae"
COLOR_BG_DARK = "#0a0e1a"
COLOR_BG_CARD = "#111827"
COLOR_ACCENT = "#2979ff"
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_SECONDARY = "#94a3b8"

PLOTLY_TEMPLATE = "plotly_dark"

# ─────────────────────────── Date formats ────────────────────────────────────
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DISPLAY_DATE_FORMAT = "%d/%m/%Y"
DISPLAY_DATETIME_FORMAT = "%d/%m/%Y %H:%M"

# ─────────────────────────── Time Ranges ─────────────────────────────────────
TIME_RANGES = {
    "3T": ("3 tháng", 90),
    "6T": ("6 tháng", 180),
    "1N": ("1 năm", 365),
    "3N": ("3 năm", 1095),
    "5N": ("5 năm", 1825),
    "TT": ("Tùy chỉnh", 0),
}

# ─────────────────────────── Currency ────────────────────────────────────────
CURRENCY = "VND"
PRICE_UNIT = 1  # Already in VND
VOLUME_UNIT = 1  # In shares

# ─────────────────────────── Data Schema ─────────────────────────────────────
PRICE_SCHEMA_COLUMNS = [
    "symbol", "timestamp", "open", "high", "low", "close",
    "volume", "value", "source", "interval", "adjusted", "fetched_at",
]

FINANCIAL_SCHEMA_COLUMNS = [
    "symbol", "period", "year", "quarter", "report_date",
    "currency", "report_type", "source", "fetched_at",
]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# PHẦN: config/investment_model.py
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
"""
Cấu hình mô hình Khuyến nghị đầu tư & Giá mục tiêu.

MỌI con số ở đây là GIẢ ĐỊNH THIẾT KẾ ban đầu (không phải chuẩn mực tài chính bắt buộc) và có thể hiệu chỉnh:
  • sửa trực tiếp file này, hoặc
  • tạo file config/investment_model.json chứa các khóa cần ghi đè (cùng cấu trúc), hoặc
  • truyền dict `overrides` khi gọi load_config() (giao diện dùng cách này cho thanh trượt ngưỡng).
"""


import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    # ── Financial Health Score ──────────────────────────────────────────────
    "health": {
        # trọng số nhóm (%) theo loại doanh nghiệp
        "weights": {
            "nonfinancial": {"profitability": 25, "growth": 20, "liquidity": 15, "leverage": 15, "cashflow": 25},
            "bank": {"profitability": 30, "growth": 20, "capital": 20, "asset_quality": 15, "funding": 15},
            "securities": {"profitability": 30, "growth": 20, "capital": 25, "liquidity": 25},
            "insurance": {"profitability": 30, "growth": 20, "capital": 25, "liquidity": 25},
        },
        # nhóm bắt buộc phải có số liệu thì mới công bố điểm tổng
        "critical_groups": {
            "nonfinancial": ["profitability", "cashflow"],
            "bank": ["profitability", "capital"],
            "securities": ["profitability", "capital"],
            "insurance": ["profitability", "capital"],
        },
        "min_coverage": 0.70,          # tỷ lệ trọng số có số liệu tối thiểu
        # Chất lượng lợi nhuận (analytics.financial_ratios.earnings_quality): trừ thẳng vào điểm tổng
        "fscore_penalty": {"max_score": 3, "points": 5.0},       # Piotroski F ≤ 3 (chấm ≥ 7 tiêu chí) → −5 điểm
        "non_core_penalty": {"min_share": 50.0, "points": 5.0},  # ≥ 50% mức tăng LN HĐKD từ thu nhập tài chính/khác → −5
        "years_for_trend": 5,
    },
    # Ngưỡng chấm điểm: (kém → 0 điểm, tốt → 100 điểm), nội suy tuyến tính. Ghi đè theo ngành ở "sector_overrides".
    "anchors": {
        "roe": (5.0, 20.0), "roa": (1.0, 10.0), "net_margin": (2.0, 15.0),
        "revenue_growth": (-5.0, 20.0), "net_income_growth": (-10.0, 25.0), "eps_growth": (-10.0, 25.0),
        "core_profit_growth": (-10.0, 25.0),   # tăng trưởng LN cốt lõi (LN gộp − bán hàng − quản lý) – thay LNST cho DN phi tài chính
        "current_ratio": (0.8, 2.0), "quick_ratio": (0.5, 1.5),
        "debt_to_equity": (2.0, 0.3),       # thấp là tốt
        "interest_coverage": (1.5, 8.0),
        "cfo_to_net_income": (0.3, 1.1), "fcf_margin": (-5.0, 8.0),
        # tài chính
        "bank_roe": (8.0, 20.0), "bank_roa": (0.6, 2.0), "equity_to_assets": (6.0, 12.0),
        "provision_to_income": (35.0, 10.0),  # thấp là tốt
        "liabilities_to_equity": (6.0, 1.5),  # thấp là tốt (CTCK/bảo hiểm)
    },
    "sector_overrides": {
        "real_estate": {"current_ratio": (1.0, 2.5), "quick_ratio": (0.3, 1.0), "debt_to_equity": (2.5, 0.5),
                        "cfo_to_net_income": (-0.5, 1.0)},
        "utilities": {"debt_to_equity": (3.0, 0.8), "current_ratio": (0.7, 1.5), "revenue_growth": (-5.0, 12.0)},
        "retail": {"current_ratio": (0.8, 1.5), "quick_ratio": (0.3, 1.0), "net_margin": (1.0, 6.0)},
        "technology": {"net_margin": (3.0, 15.0), "roe": (8.0, 25.0)},
        "materials": {"net_margin": (1.0, 10.0), "debt_to_equity": (2.0, 0.5)},
    },
    # ── Valuation Engine ────────────────────────────────────────────────────
    "valuation": {
        "horizon_months": 12,
        "risk_free": 0.0443,           # lợi suất trúng thầu TPCP 10 năm, phiên đấu thầu cuối tháng 9/2026 (HNX)
        # Bước 10: nguồn & ngày cập nhật Rf. App chưa tự lấy được lợi suất TPCP 10 năm theo ngày từ nguồn chính thống →
        # cập nhật tay (sửa tại đây hoặc config/investment_model.json). Quá 'risk_free_max_age_days' ngày (hoặc chưa ghi
        # ngày) → định giá hiện ghi chú cảnh báo. Gợi ý nguồn: bản tin tháng của VBMA (vbma.org.vn).
        "risk_free_as_of": "2026-09-30",  # "YYYY-MM-DD" – ngày của số liệu Rf (phiên cuối tháng 9/2026)
        "risk_free_source": "HNX – đấu thầu TPCP 10 năm cuối tháng 9/2026: 4,43%/năm (Báo Đấu thầu 10/10/2026, VTV 12/10/2026)",
        "risk_free_max_age_days": 92,  # ~3 tháng
        "pe_peer_cap": 1.5,            # P/E tham chiếu ≤ trung vị nhóm ngành × 1,5 (khi nhóm ≥ 3 DN) – chặn bội số bong bóng
        "equity_premium": 0.08,        # phần bù rủi ro thị trường VN (giả định)
        "beta_bounds": (0.6, 1.6),
        "ke_bounds": (0.10, 0.18),
        "kd_bounds": (0.04, 0.12),
        "tax_rate": 0.20,
        "terminal_growth": {"bear": 0.025, "base": 0.035, "bull": 0.045},
        "growth_bounds": (-0.10, 0.20),
        "dcf_years": 5,
        "dcf_min_spread": 0.03,        # WACC − g tối thiểu
        "dcf_max_tv_share": 0.75,      # tỷ trọng giá trị cuối kỳ tối đa (cao hơn → hạ độ tin cậy) – 14/10/2026: 0,85 → 0,75
        # ── 15/10/2026: hiệu chỉnh theo chẩn đoán định giá (tools/valuation_diag.py) – CHỐT TRƯỚC khi chạy lại backtest ──
        "backtest_cash_dividend_basis": True,   # định giá ngày quá khứ: quy đổi phần cổ tức tiền mặt nguồn đã trừ vào giá
        "multiple_recency_decay": 0.5,  # bội số tham chiếu lịch sử: trọng số năm gần nhất 1, năm trước 0,5, 0,25… (bán kỳ 1 năm)
        "beta_blume": True,             # beta điều chỉnh = 0,67 × beta + 0,33 (beta hồi quy về 1)
        "roe_fade_spread": 0.03,        # sau giai đoạn dự báo ROE về Ke + 3 điểm % (RI giá trị cuối kỳ, P/B hợp lý 2 giai đoạn)
        "scenario_max_ratio": 4.0,     # Bull / Bear > 4 lần → biên độ rộng bất thường → hạ 1 bậc. 15/10/2026: ngưỡng 2 cũ bị vượt ở 150/150 quan sát backtest (trung vị 3,0) → không phân biệt được mã; 4 ≈ phân vị 80. Chốt TRƯỚC khi chấm lại tiêu chí.
        "risk_free_unsourced_cap": "Trung bình",   # Rf chưa ghi nguồn/ngày hoặc quá cũ → độ tin cậy tối đa
        "bear_cap_current_multiple": True,         # Thận trọng: bội số ≤ bội số dự phóng hiện tại của thị trường
        "pe_abs_cap": None,            # trần P/E tuyệt đối (vd 18) – mặc định TẮT; có thể đặt riêng trong method_profiles
        "sanity_band": (0.25, 4.0),    # giá mục tiêu / thị giá ngoài khoảng này bị coi là bất thường
        "method_weights": {
            "nonfinancial": {"pe": 40, "ev_ebitda": 20, "dcf": 25, "pb": 15},
            "financial": {"pb": 60, "pe": 40},
        },
        # bộ giả định kịch bản (thay đổi GIẢ ĐỊNH, không cộng/trừ thẳng vào giá)
        "scenarios": {
            "bear": {"growth_shift": -0.08, "margin_factor": 0.90, "multiple_pct": 25, "ke_shift": 0.01, "roe_shift": -3.0},
            "base": {"growth_shift": 0.00, "margin_factor": 1.00, "multiple_pct": 50, "ke_shift": 0.00, "roe_shift": 0.0},
            "bull": {"growth_shift": 0.05, "margin_factor": 1.05, "multiple_pct": 75, "ke_shift": -0.01, "roe_shift": 2.0},
        },
        "stale_months": 18,            # BCTC năm gần nhất cũ hơn → cảnh báo dữ liệu cũ
        # ── Bước 7: Hybrid Valuation – dự phóng lấy từ Forecast Engine (core/du_phong.py) ──
        "use_forecast_engine": True,   # False = mô hình cũ (dự phóng nội bộ) – chỉ giữ để đối chiếu trước/sau
        "outlier_band": (0.5, 2.0),    # ≥ 3 phương pháp: loại phương pháp lệch ngoài [½×, 2×] trung vị các phương pháp
        "min_weight_coverage": 0.5,    # tổng trọng số gốc của các phương pháp hợp lệ < 50% → hạ độ tin cậy 1 bậc
        "pe_max_forecast_ape": 0.50,   # sai số trung vị LNST dự báo 1 năm (backtest chính mã) > 50% → không dùng P/E forward
        "pe_min_backtest_years": 5,
        # ── Bước 9 ──
        # Chu kỳ: chuẩn hóa lợi nhuận/EBITDA theo trung vị biên của N năm gần nhất (giữa chu kỳ)
        "cycle_years": 5, "cycle_min_years": 3,
        # Chiết khấu cổ tức 2 giai đoạn (đối chiếu)
        "ddm": {"min_div_years": 3, "lookback_years": 5, "max_payout_cv": 0.5, "min_spread": 0.03},
        # Ngưỡng chênh lệch giữa các phương pháp (cao/thấp) cho độ tin cậy
        "spread_high": 1.6, "spread_mid": 2.2,
        # Hồ sơ phương pháp theo ngành. Trọng số đặt THEO MỨC PHÙ HỢP CỦA PHƯƠNG PHÁP với mô hình kinh doanh (thông lệ
        # định giá), KHÔNG dò theo kết quả giá mục tiêu. 'default' = trọng số phi tài chính đang dùng trước bước 7.
        "method_profiles": {
            "default": {"label": "Phi tài chính (chung)",
                        "weights": {"pe": 35, "ev_ebitda": 20, "dcf": 25, "pb": 10, "ddm": 10},
                        "rationale": "Lợi nhuận (P/E) là neo chính, dòng tiền (DCF) và EBITDA bổ sung, P/B tham khảo; "
                                     "chiết khấu cổ tức 2 giai đoạn chỉ để đối chiếu (trọng số thấp, chỉ khi chia cổ "
                                     "tức tiền mặt đều)."},
            "technology": {"label": "Công nghệ / dịch vụ", "weights": {"pe": 40, "dcf": 30, "ev_ebitda": 20, "ddm": 10},
                           "excluded": {"pb": "Tài sản nhẹ – giá trị sổ sách ít phản ánh năng lực sinh lời"},
                           "rationale": "Doanh nghiệp tài sản nhẹ, tăng trưởng: định giá theo lợi nhuận và dòng tiền."},
            "cyclical_manufacturing": {"label": "Sản xuất / chu kỳ (thép, vật liệu, hóa chất…)",
                                       "weights": {"ev_ebitda": 35, "pb": 25, "pe": 25, "dcf": 15},
                                       "rationale": "Lợi nhuận ròng biến động theo chu kỳ (sai số dự báo LNST lớn – bước 6) "
                                                    "→ ưu tiên EBITDA (trước khấu hao, lãi vay) và giá trị sổ sách; "
                                                    "DCF nhạy với giả định dài hạn nên tỷ trọng thấp."},
            "utilities": {"label": "Tiện ích / năng lượng",
                          "weights": {"dcf": 35, "ev_ebitda": 25, "pe": 15, "pb": 10, "ddm": 15},
                          "rationale": "Dòng tiền ổn định, tài sản dài hạn lớn → DCF và EV/EBITDA là chính; cổ tức đều "
                                       "nên chiết khấu cổ tức 2 giai đoạn có tỷ trọng đối chiếu cao hơn."},
            "industrial_park": {"label": "BĐS khu công nghiệp",
                                "weights": {"dcf": 35, "ev_ebitda": 25, "pb": 20, "pe": 10, "ddm": 10},
                                "rationale": "Doanh thu cho thuê đất/hạ tầng dài hạn, dòng tiền đều hơn BĐS nhà ở → DCF "
                                             "và EV/EBITDA là chính; P/B, P/E tham khảo. Danh sách mã trong "
                                             "INDUSTRIAL_PARK_TICKERS."},
            "real_estate": {"label": "Bất động sản / dự án", "weights": {"pb": 60, "pe": 40},
                            "excluded": {"dcf": "FCFF phụ thuộc tiến độ dự án (vốn lưu động lớn); app chưa có RNAV",
                                         "ev_ebitda": "Ghi nhận doanh thu theo bàn giao dự án → EBITDA không đều"},
                            "max_confidence": "Trung bình",
                            "rationale": "Chuẩn của ngành là RNAV (giá trị từng dự án) nhưng app không có dữ liệu dự án: "
                                         "dùng giá trị sổ sách và lợi nhuận, loại DCF/EV/EBITDA; độ tin cậy tối đa "
                                         "'Trung bình'."},
            "bank": {"label": "Ngân hàng", "weights": {"ri": 40, "pb": 35, "pe": 25},
                     "excluded": {"dcf": "Nợ là nguyên liệu kinh doanh – FCFF không áp dụng",
                                  "ev_ebitda": "EBITDA không có ý nghĩa với ngân hàng"},
                     "rationale": "Ngân hàng: thu nhập thặng dư (giá trị sổ sách + phần lợi nhuận vượt chi phí vốn) "
                                  "và P/B–ROE là chính, P/E bổ sung."},
            "securities": {"label": "Chứng khoán", "weights": {"pb": 60, "ri": 20, "pe": 20},
                           "excluded": {"dcf": "Tài sản/nợ tài chính – FCFF không áp dụng",
                                        "ev_ebitda": "EBITDA không có ý nghĩa với CTCK"},
                           "rationale": "Lợi nhuận theo chu kỳ thị trường, dự báo LNST kém hơn mô hình ngây thơ "
                                        "(bước 6) → giá trị sổ sách là neo chính; thu nhập thặng dư và P/E tỷ trọng "
                                        "thấp. Rủi ro: danh mục tự doanh, cho vay ký quỹ."},
            "insurance": {"label": "Bảo hiểm", "weights": {"pb": 45, "ri": 25, "pe": 30},
                          "excluded": {"dcf": "FCFF không áp dụng", "ev_ebitda": "EBITDA không áp dụng"},
                          "max_confidence": "Trung bình",
                          "rationale": "Như tài chính: P/B–ROE và thu nhập thặng dư. Chuẩn của ngành là P/EV (giá trị "
                                       "nội tại hợp đồng) nhưng không có dữ liệu → độ tin cậy tối đa 'Trung bình'."},
        },
    },
    # ── Forecast Engine (core/du_phong.py) ──────────────────
    # Chỉ dùng cho dự báo tài chính; KHÔNG thay đổi giả định / trọng số của Valuation Engine ở trên.
    "forecast": {
        "years": 5,                     # số năm dự báo dài hạn (3–5)
        "hist_years": 5,                # số năm lịch sử tối đa dùng để ước lượng tham số
        "ratio_years": 3,               # số năm gần nhất lấy trung vị cho các tỷ lệ (biên, capex, NWC…)
        "growth_bounds": (-0.10, 0.25),
        "w_hist": 0.5,                  # trọng số tăng trưởng lịch sử (trung vị YoY) vs tăng trưởng TTM gần nhất
        "default_tax": 0.20,            # chỉ dùng khi không ước lượng được thuế suất thực tế (có cảnh báo)
        "margin_bounds": (-0.50, 0.80),
        # Tham số hiệu chỉnh (bước 6) – chọn trên tập HIỆU CHỈNH (mã train, năm ≤ 2019), kiểm tra trên tập độc lập
        "growth_shrink": 0.25,           # g1 = s × g công ty + (1 − s) × g dài hạn
        "growth_shrink_consistent": 0.6,  # 15/10/2026: tăng trưởng đều (≥ 4/5 năm tăng, trung vị ≥ 8%) → s = 0,6
        "consistent_years": 5, "consistent_min_up": 4, "consistent_min_growth": 0.08,
        "growth_shrink_negative": 0.75,  # khi g công ty < 0: s = 0,75 (giữ 75% mức giảm) thay vì 0,25 – co bất đối xứng
        "margin_anchor": 1.0,           # biên năm 1 = λ × biên kỳ gốc + (1 − λ) × trung vị gần đây
        "ratio_anchor": 1.0,            # tương tự cho thuế suất, tỷ lệ LNST mẹ, khấu hao/DT
        "margin_long_years": 5,         # biên dài hạn (đích hồi quy về trung bình ở năm cuối)
        "roe_anchor": 0.0,              # CTCK/bảo hiểm: ROE năm 1 = λ × ROE kỳ gốc + (1 − λ) × ROE chuẩn hóa
        "cyclical": {"cv_threshold": 0.35, "growth_shrink": None, "margin_anchor": None},
        "model_overrides": {"bank": {"growth_shrink": 1.0}},   # TOI ngân hàng bám tăng trưởng tín dụng – không co
        # Khoảng kịch bản theo nhóm = phân vị P20 / P80 của sai số tham số dự báo 1 năm (thực tế − dự báo) trên tập
        # HIỆU CHỈNH: 50% mã (tách cố định theo băm mã), năm 2013–2019, dữ liệu BCTC năm đóng gói (arminer).
        # Kiểm tra độ phủ trên tập độc lập (50% mã còn lại, và năm 2020–2025). n = số quan sát hiệu chỉnh.
        "scenario_bands": {
            "stable":     {"growth": {"lo": -0.111, "hi": 0.154}, "margin": {"lo": -0.020, "hi": 0.021}, "n": 742},
            "cyclical":   {"growth": {"lo": -0.232, "hi": 0.242}, "margin": {"lo": -0.031, "hi": 0.037}, "n": 284},
            "nwc_heavy":  {"growth": {"lo": -0.247, "hi": 0.515}, "margin": {"lo": -0.079, "hi": 0.074}, "n": 380},
            "bank":       {"growth": {"lo": -0.059, "hi": 0.211}, "margin": {"lo": -0.029, "hi": 0.061}, "n": 65},
            "securities": {"roe": {"lo": -0.045, "hi": 0.070}, "n": 80},
        },
        "roe_bounds": (-0.20, 0.40),
        "scenarios": {
            "bear": {"growth_shift": -0.05, "margin_shift": -0.02, "roe_shift": -0.03, "credit_cost_factor": 1.30,
                     "capex_factor": 1.10},
            "base": {"growth_shift": 0.00, "margin_shift": 0.00, "roe_shift": 0.00, "credit_cost_factor": 1.00,
                     "capex_factor": 1.00},
            "bull": {"growth_shift": 0.03, "margin_shift": 0.01, "roe_shift": 0.02, "credit_cost_factor": 0.85,
                     "capex_factor": 0.95},
        },
    },
    # ── Risk Assessment ─────────────────────────────────────────────────────
    "risk": {
        "decline_high": -25.0,         # % giảm doanh thu/LNST coi là rủi ro cao
        "de_high": 2.0, "de_severe": 3.0, "ic_high": 1.5,
        "bank_eta_severe": 4.0,        # VCSH/TTS ngân hàng (%) dưới mức này → nghiêm trọng
        "dilution_high": 0.10,         # tăng số CP bình quân/năm
    },
    # ── Khung khuyến nghị đa lớp (15/10/2026) – MỘT nhãn duy nhất từ ma trận F × R ───────────────────────
    # Tham số khởi điểm theo tài liệu "Khung khuyến nghị cổ phiếu đa lớp" v1.0 – CHƯA hiệu chỉnh trên dữ liệu VN,
    # phải backtest không chồng lấn trước khi dùng thật (tools/reco_trend / trang Backtest).
    "multilayer": {
        "weights_f": {"Q": 0.40, "V": 0.35, "G": 0.25},
        # T: động lượng 40 · MA 30 · khối ngoại 20 · khối lượng 10 – chưa có dữ liệu khối ngoại → chia lại tỷ lệ
        "weights_t": {"momentum": 40, "ma": 30, "foreign": 20, "volume": 10},
        "f_strong": 65, "f_mid": 55,   # 16/10/2026: 70 → 65 (theo yêu cầu nhóm; chưa backtest)
        "t_good": 50,
        # Trục thứ hai = SỨC MẠNH SO VỚI THỊ TRƯỜNG R (thứ hạng % trong rổ VN30 + mã cùng ngành; trung vị = 50)
        "weights_r": {"momentum": 60, "ma200": 25, "hurdle": 15},
        "leader_top_pct": 0.30,   # VN-Index dưới MA200: mã thuộc top 30% sức mạnh giá trong rổ vẫn được MUA (16/10/2026)
        "r_strong": 60, "r_weak": 40, "min_universe": 10,
        "market_gate": True,                     # VN-Index dưới MA200 → không MUA (tối đa TÍCH LŨY TỪNG PHẦN)
        "max_penalty": 15,
        # Thanh khoản tối thiểu (GTGD bình quân 20 phiên, tỷ đồng). 1 tỷ/phiên: vị thế 500 triệu thoát hết trong ~5 phiên
        # nếu chỉ chiếm ≤ 10% GTGD mỗi phiên (quy ước thực hành phổ biến). Dưới "liquidity_warn" chỉ cảnh báo.
        "min_liquidity_bn": 1.0,
        "liquidity_warn_bn": 5.0,
        "min_quarters": 8, "min_sessions": 250,
        "dispersion_low_conf": 0.40,             # độ lệch giữa các phương pháp định giá > 40% → độ tin cậy thấp
        "min_peers_percentile": 5,               # số DN cùng ngành tối thiểu để xếp hạng phần trăm
    },
}

CONFIG_JSON = Path(__file__).resolve().parent.parent / "config" / "investment_model.json"


def _merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = tuple(v) if isinstance(v, list) and isinstance(base.get(k), tuple) else v
    return base


def load_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if CONFIG_JSON.exists():
        try:
            _merge(cfg, json.loads(CONFIG_JSON.read_text(encoding="utf-8")))
        except Exception:
            pass
    return _merge(cfg, overrides or {})


# BĐS khu công nghiệp (bước 9): doanh thu cho thuê đất/hạ tầng dài hạn, dòng tiền đều hơn BĐS nhà ở → định giá theo
# dòng tiền. Phân ngành ICB không tách được nhóm này nên dùng danh sách mã (sửa tại đây). Tiêu chí: hoạt động chính
# là phát triển & cho thuê KCN theo báo cáo thường niên.
INDUSTRIAL_PARK_TICKERS = ("KBC", "IDC", "SZC", "BCM", "SIP", "LHG", "NTC", "D2D", "TIP", "ITA", "SNZ")

SECTOR_KEYWORDS = {
    "real_estate": ("bất động sản", "bat dong san", "real estate", "khu công nghiệp"),
    "utilities": ("điện", "dien", "nước", "utilities", "năng lượng", "dầu khí", "power"),
    "retail": ("bán lẻ", "ban le", "retail", "tiêu dùng", "consumer"),
    "technology": ("công nghệ", "cong nghe", "technology", "phần mềm", "viễn thông", "software"),
    "materials": ("thép", "thep", "vật liệu", "vlxd", "hóa chất", "phân bón", "steel", "materials", "chemical"),
}


def classify_company(industry: str = "", group: str = "", bank_flag: bool = False,
                     symbol: Optional[str] = None) -> Dict[str, str]:
    """→ {'type': nonfinancial|bank|securities|insurance, 'sector': hồ sơ ngưỡng}. symbol (tùy chọn) để nhận diện BĐS
    khu công nghiệp theo INDUSTRIAL_PARK_TICKERS."""
    t = f"{industry} {group}".lower()
    ind = str(industry or "").lower()
    # 15/10/2026: tên NGÀNH chứng khoán / bảo hiểm được ưu tiên hơn tín hiệu dữ liệu "có thu nhập lãi / tiền gửi" (bank_flag)
    # – BCTC công ty chứng khoán (SSI) và bảo hiểm (BVH) cũng có các dòng này nên trước đây bị định giá như ngân hàng.
    bank_kw = any(k in t for k in ("ngân hàng", "ngan hang", "bank"))
    sec_kw = any(k in ind for k in ("chứng khoán", "chung khoan", "securities", "brokerage", "financial services",
                                    "dịch vụ tài chính", "môi giới"))
    ins_kw = any(k in ind for k in ("bảo hiểm", "bao hiem", "insurance"))
    if sec_kw and not any(k in ind for k in ("ngân hàng", "bank")):
        ftype = "securities"
    elif ins_kw and not any(k in ind for k in ("ngân hàng", "bank")):
        ftype = "insurance"
    elif bank_flag or bank_kw:
        ftype = "bank"
    elif any(k in t for k in ("chứng khoán", "chung khoan", "securities", "brokerage")):
        ftype = "securities"
    elif any(k in t for k in ("bảo hiểm", "bao hiem", "insurance")):
        ftype = "insurance"
    else:
        ftype = "nonfinancial"
    sector = next((s for s, keys in SECTOR_KEYWORDS.items() if any(k in t for k in keys)), "default")
    out = {"type": ftype, "sector": sector, "industry_text": t.strip()}
    if symbol:
        out["symbol"] = str(symbol).upper()
        if ftype == "nonfinancial" and out["symbol"] in INDUSTRIAL_PARK_TICKERS:
            out["sector"] = "industrial_park"
    return out
