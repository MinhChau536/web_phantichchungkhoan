"""
Nguồn BCTC năm đóng gói sẵn (offline) từ dự án vn-annual-report-miner (MIT) – xem data/bundled/README.md.

Trả về bảng cùng dạng ma trận như VCI (item, item_en, item_id, các cột năm – năm mới nhất đứng trước)
để đi chung đường chuẩn hóa canonicalize() với các nguồn khác. Chỉ có kỳ NĂM; giá trị theo VND.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent.parent / "bundled" / "arminer_bctc"
_STATEMENTS = {"income_statement": "income_statement", "balance_sheet": "balance_sheet", "cash_flow": "cash_flow"}


@lru_cache(maxsize=8)
def _load(statement: str) -> pd.DataFrame:
    frames = []
    for ex in ("HSX", "HNX"):
        p = BASE / statement / f"{ex}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p, columns=["ticker", "year", "item_code", "item_name", "value"]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


class ArminerClient:
    name = "arminer"

    def available(self) -> bool:
        return BASE.exists() and any(BASE.rglob("*.parquet"))

    def get_financial_statement(self, symbol: str, statement: str, period: str = "year") -> pd.DataFrame:
        if period not in ("year", "annual", "Y") or statement not in _STATEMENTS:
            return pd.DataFrame()
        df = _load(_STATEMENTS[statement])
        if df.empty:
            return pd.DataFrame()
        sub = df[df["ticker"] == symbol.upper()]
        if sub.empty:
            return pd.DataFrame()
        mat = sub.pivot_table(index=["item_name", "item_code"], columns="year", values="value", aggfunc="first")
        mat = mat[sorted(mat.columns, reverse=True)]
        mat.columns = [str(int(c)) for c in mat.columns]
        mat = mat.reset_index().rename(columns={"item_name": "item", "item_code": "item_id"})
        mat.insert(1, "item_en", None)
        return mat

    def health_check(self):
        return {"provider": "arminer (offline)", "available": self.available()}
