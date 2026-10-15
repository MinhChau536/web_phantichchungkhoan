"""
Chấm KHUNG KHUYẾN NGHỊ ĐA LỚP trên rows.csv do tools/reco_trend_backtest.py tạo (mục 9 của tài liệu khung).

Chỉ số (không chỉnh ngưỡng để ép kết quả):
  • LN 12 tháng sau theo nhãn (MUA / TÍCH LŨY TỪNG PHẦN / NẮM GIỮ / THEO DÕI / GIẢM TỶ TRỌNG / TRÁNH), tỷ lệ thắng VN-Index.
  • Rank IC (Spearman) giữa điểm F và LN 12T: (a) theo từng tháng rồi lấy trung bình; (b) MẪU KHÔNG CHỒNG LẤN – mỗi mã chỉ
    lấy 1 quan sát mỗi 12 tháng (cửa sổ 12T không giao nhau) để tránh số quan sát hiệu dụng bị thổi phồng.
  • Chênh lệch LN 12T giữa nhóm 20% điểm F cao nhất và 20% thấp nhất.
  • Đường cơ sở: "giữ nguyên giá" (LN 0) và VN-Index cùng kỳ. Không thắng đường cơ sở → không gắn nhãn khuyến nghị mạnh.
  • Mức độ đổi nhãn: tỷ lệ tháng mà nhãn của một mã khác tháng trước.
Dùng: python tools/multilayer_eval.py [đường dẫn rows.csv]
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ORDER = ["MUA", "TÍCH LŨY TỪNG PHẦN", "NẮM GIỮ", "THEO DÕI", "GIẢM TỶ TRỌNG / TRÁNH", "KHÔNG ĐỦ DỮ LIỆU"]


def _ic(d: pd.DataFrame) -> float:
    d = d.dropna(subset=["ml_F", "ret_12T"])
    return d["ml_F"].rank().corr(d["ret_12T"].rank()) if len(d) >= 5 else np.nan


def evaluate(path: str) -> dict:
    df = pd.read_csv(path)
    ok = df[df["loi"].isna()] if "loi" in df else df
    ok = ok[ok["ml_label"].notna()].copy()
    ok["T"] = pd.to_datetime(ok["T"])
    res = {"tong_quan_sat": len(df), "co_nhan_da_lop": len(ok)}
    lab = ok.dropna(subset=["ret_12T"])
    beat = (lab["ret_12T"] > lab["vnindex_ret_12T"]) if "vnindex_ret_12T" in lab else pd.Series(dtype=bool)
    res["theo_nhan"] = {k: {"n": int((lab.ml_label == k).sum()), "ln_12T_tb": lab.loc[lab.ml_label == k, "ret_12T"].mean(),
                            "ln_12T_trung_vi": lab.loc[lab.ml_label == k, "ret_12T"].median(),
                            "ty_le_thang_vnindex": beat[lab.ml_label == k].mean() if len(beat) else None}
                        for k in ORDER if (lab.ml_label == k).any()}
    monthly = [(_ic(g), len(g)) for _, g in lab.groupby("T")]
    ics = [x for x, n in monthly if not np.isnan(x)]
    res["rank_ic_theo_thang"] = {"tb": float(np.mean(ics)) if ics else None, "so_thang": len(ics),
                                 "ty_le_duong": float(np.mean([x > 0 for x in ics])) if ics else None}
    # mẫu không chồng lấn: mỗi mã lấy các ngày cách nhau ≥ 12 tháng (bắt đầu từ quan sát đầu tiên)
    keep = []
    for _, g in lab.sort_values("T").groupby("ma"):
        last = None
        for i, r in g.iterrows():
            if last is None or r["T"] >= last + pd.DateOffset(months=12):
                keep.append(i)
                last = r["T"]
    nol = lab.loc[keep]
    res["rank_ic_khong_chong_lan"] = {"ic": _ic(nol), "n": len(nol),
                                      "ghi_chu": "n nhỏ → kết luận thận trọng; IC phải dương có ý nghĩa mới đáng tin"}
    if len(lab) >= 25:
        q = lab["ml_F"].rank(pct=True)
        res["chenh_lech_top_bottom_20"] = lab.loc[q >= 0.8, "ret_12T"].mean() - lab.loc[q <= 0.2, "ret_12T"].mean()
    strong = lab[lab.ml_label.isin(["MUA", "TÍCH LŨY TỪNG PHẦN"])]
    res["duong_co_so"] = {"nhom_MUA_TICH_LUY_tb": strong["ret_12T"].mean(), "giu_nguyen_gia": 0.0,
                          "vnindex_cung_ky_tb": strong["vnindex_ret_12T"].mean() if "vnindex_ret_12T" in strong else None}
    vb = res["duong_co_so"]["vnindex_cung_ky_tb"]
    res["ket_luan_duong_co_so"] = ("ĐẠT – nhóm MUA/TÍCH LŨY thắng cả 'giữ nguyên giá' và VN-Index"
                                   if len(strong) and strong["ret_12T"].mean() > 0 and (vb is None or strong["ret_12T"].mean() > vb)
                                   else "CHƯA ĐẠT – không gắn nhãn khuyến nghị mạnh cho tới khi hiệu chỉnh lại")
    sw = []
    for _, g in ok.sort_values("T").groupby("ma"):
        s = g["ml_label"].tolist()
        sw += [a != b for a, b in zip(s[:-1], s[1:])]
    res["ty_le_doi_nhan_moi_thang"] = float(np.mean(sw)) if sw else None
    return res


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tools", "reco_trend_out", "rows.csv")
    print(json.dumps(evaluate(p), ensure_ascii=False, indent=1,
                     default=lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 4)))
