# Dữ liệu đóng gói sẵn (dùng offline)

Lấy từ dự án mã nguồn mở **vn-annual-report-miner** (Trương Minh Quân, giấy phép MIT – xem
`LICENSE_vn-annual-report-miner.txt`): https://github.com/Tumiqa/vn-annual-report-miner

- `arminer_bctc/<báo cáo>/<HSX|HNX>.parquet` : BCTC năm 2009–2025 của ~700 doanh nghiệp niêm yết (VND),
  dạng dài: ticker, year, item_code, item_name, value. Dùng làm nguồn BCTC dự phòng "arminer".
- `zenodo_bctn_index.parquet` : chỉ mục ~14.000 Báo cáo thường niên trên kho Zenodo (record 20949551),
  dùng để tải từng file PDF bằng HTTP Range mà không cần tải cả kho ZIP.
