"""
Cấu hình mô hình Khuyến nghị đầu tư & Giá mục tiêu 12 tháng.

MỌI con số ở đây là GIẢ ĐỊNH THIẾT KẾ ban đầu (không phải chuẩn mực tài chính bắt buộc) và có thể hiệu chỉnh:
  • sửa trực tiếp file này, hoặc
  • tạo file config/investment_model.json chứa các khóa cần ghi đè (cùng cấu trúc), hoặc
  • truyền dict `overrides` khi gọi load_config() (giao diện dùng cách này cho thanh trượt ngưỡng).
"""
from __future__ import annotations

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
        "years_for_trend": 5,
    },
    # Ngưỡng chấm điểm: (kém → 0 điểm, tốt → 100 điểm), nội suy tuyến tính. Ghi đè theo ngành ở "sector_overrides".
    "anchors": {
        "roe": (5.0, 20.0), "roa": (1.0, 10.0), "net_margin": (2.0, 15.0),
        "revenue_growth": (-5.0, 20.0), "net_income_growth": (-10.0, 25.0), "eps_growth": (-10.0, 25.0),
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
        "risk_free": 0.04,             # lợi suất TPCP 10 năm (giả định)
        "equity_premium": 0.08,        # phần bù rủi ro thị trường VN (giả định)
        "beta_bounds": (0.6, 1.6),
        "ke_bounds": (0.10, 0.18),
        "kd_bounds": (0.04, 0.12),
        "tax_rate": 0.20,
        "terminal_growth": {"bear": 0.025, "base": 0.035, "bull": 0.045},
        "growth_bounds": (-0.10, 0.20),
        "dcf_years": 5,
        "dcf_min_spread": 0.03,        # WACC − g tối thiểu
        "dcf_max_tv_share": 0.85,      # tỷ trọng giá trị cuối kỳ tối đa (cao hơn → hạ độ tin cậy)
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
    },
    # ── Risk Assessment ─────────────────────────────────────────────────────
    "risk": {
        "decline_high": -25.0,         # % giảm doanh thu/LNST coi là rủi ro cao
        "de_high": 2.0, "de_severe": 3.0, "ic_high": 1.5,
        "bank_eta_severe": 4.0,        # VCSH/TTS ngân hàng (%) dưới mức này → nghiêm trọng
        "dilution_high": 0.10,         # tăng số CP bình quân/năm
    },
    # ── Recommendation Engine ───────────────────────────────────────────────
    "recommendation": {
        "buy_min_health": 75,
        "buy_min_return": 20.0,
        "sell_max_return": -10.0,
        "hold_min_health": 50,         # dưới mức này kèm cảnh báo chất lượng
        "min_confidence": "Trung bình",
    },
}

CONFIG_JSON = Path(__file__).resolve().parent / "investment_model.json"


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


SECTOR_KEYWORDS = {
    "real_estate": ("bất động sản", "bat dong san", "real estate", "khu công nghiệp"),
    "utilities": ("điện", "dien", "nước", "utilities", "năng lượng", "dầu khí", "power"),
    "retail": ("bán lẻ", "ban le", "retail", "tiêu dùng", "consumer"),
    "technology": ("công nghệ", "cong nghe", "technology", "phần mềm", "viễn thông", "software"),
    "materials": ("thép", "thep", "vật liệu", "vlxd", "hóa chất", "phân bón", "steel", "materials", "chemical"),
}


def classify_company(industry: str = "", group: str = "", bank_flag: bool = False) -> Dict[str, str]:
    """→ {'type': nonfinancial|bank|securities|insurance, 'sector': hồ sơ ngưỡng}."""
    t = f"{industry} {group}".lower()
    if bank_flag or any(k in t for k in ("ngân hàng", "ngan hang", "bank")):
        ftype = "bank"
    elif any(k in t for k in ("chứng khoán", "chung khoan", "securities", "brokerage")):
        ftype = "securities"
    elif any(k in t for k in ("bảo hiểm", "bao hiem", "insurance")):
        ftype = "insurance"
    else:
        ftype = "nonfinancial"
    sector = next((s for s, keys in SECTOR_KEYWORDS.items() if any(k in t for k in keys)), "default")
    return {"type": ftype, "sector": sector}
