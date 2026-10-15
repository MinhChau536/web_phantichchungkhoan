"""
Kho Báo cáo thường niên trên Zenodo (~14.000 file PDF, 2000–2025), record 20949551.

Cách lấy 1 file mà KHÔNG tải cả kho ZIP nhiều GB: mở file ZIP từ xa bằng HTTP Range
(chỉ đọc phần mục lục ở cuối ZIP và đúng khối dữ liệu của file cần lấy).
Ý tưởng và chỉ mục (data/bundled/zenodo_bctn_index.parquet) lấy từ dự án vn-annual-report-miner
(Trương Minh Quân, giấy phép MIT – data/bundled/LICENSE_vn-annual-report-miner.txt); mã được viết gọn lại.
"""
from __future__ import annotations

import io
import logging
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

RECORD_ID = "20949551"
RECORD_URL = f"https://zenodo.org/records/{RECORD_ID}"
FILES_URL = f"https://zenodo.org/api/records/{RECORD_ID}/files"
ARCHIVES = {
    "2000_2005": "vn_bctn_2000_2005.zip", "2006_2010": "vn_bctn_2006_2010.zip",
    "2011_2015": "vn_bctn_2011_2015.zip", "2016_2020": "vn_bctn_2016_2020.zip",
    "2021_2025": "vn_bctn_2021_2025.zip",
}
INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "bundled" / "zenodo_bctn_index.parquet"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36",
            "Accept-Encoding": "identity"}


class HTTPRangeFile(io.RawIOBase):
    """File đọc-được-tìm-kiếm (seekable) trên HTTP Range, đệm theo khối – đủ để zipfile đọc ZIP từ xa."""

    def __init__(self, url: str, session: Optional[requests.Session] = None, block: int = 1 << 20,
                 timeout: float = 30):
        self.url, self.block, self.timeout = url, block, timeout
        self.s = session or requests.Session()
        self.pos, self._cache = 0, {}
        r = self.s.get(url, headers={**_HEADERS, "Range": "bytes=0-0"}, timeout=timeout)
        if r.status_code not in (200, 206):
            raise IOError(f"HTTP {r.status_code} khi mở {url}")
        cr = r.headers.get("Content-Range", "")
        self.size = int(cr.split("/")[-1]) if "/" in cr else int(r.headers.get("Content-Length", 0))
        if r.status_code == 200 and "/" not in cr:
            raise IOError("Máy chủ không hỗ trợ tải theo khoảng (Range)")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.pos, 2: self.size}[whence]
        self.pos = max(0, min(base + offset, self.size))
        return self.pos

    def _blk(self, i: int) -> bytes:
        if i not in self._cache:
            start = i * self.block
            end = min(start + self.block, self.size) - 1
            r = self.s.get(self.url, headers={**_HEADERS, "Range": f"bytes={start}-{end}"}, timeout=self.timeout)
            r.raise_for_status()
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[i] = r.content
        return self._cache[i]

    def readinto(self, b) -> int:
        n = 0
        while n < len(b) and self.pos < self.size:
            data = self._blk(self.pos // self.block)
            off = self.pos % self.block
            chunk = data[off: off + len(b) - n]
            if not chunk:
                break
            b[n: n + len(chunk)] = chunk
            n += len(chunk)
            self.pos += len(chunk)
        return n


@lru_cache(maxsize=1)
def load_index() -> pd.DataFrame:
    if not INDEX_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(INDEX_PATH)
    return df[df.get("status", "ok") == "ok"] if "status" in df.columns else df


def list_reports(symbol: str) -> List[Dict]:
    """Các BCTN của mã trong kho Zenodo: [{year, archive_period, relative_path, size_mb}], năm mới trước."""
    idx = load_index()
    if idx.empty:
        return []
    sub = idx[(idx["ticker_folder"].str.upper() == symbol.upper()) & (idx["archive_period"].isin(ARCHIVES))]
    sub = sub.sort_values("year_full", ascending=False).drop_duplicates("year_full")
    return [{"year": int(r.year_full), "archive_period": r.archive_period, "relative_path": r.relative_path,
             "size_mb": float(r.file_size_mb)} for r in sub.itertuples()]


def make_url(archive_period: str, relative_path: str) -> str:
    return f"zenodo://{archive_period}/{relative_path}"


def parse_url(url: str):
    rest = url[len("zenodo://"):]
    archive, rel = rest.split("/", 1)
    return archive, rel


def fetch_pdf(archive_period: str, relative_path: str, session: Optional[requests.Session] = None,
              base_url: Optional[str] = None) -> bytes:
    """Lấy nội dung 1 file PDF trong kho ZIP trên Zenodo (base_url dùng cho kiểm thử)."""
    zip_name = ARCHIVES.get(archive_period)
    if not zip_name:
        raise ValueError(f"Không có kho cho giai đoạn {archive_period}")
    url = f"{base_url or FILES_URL}/{zip_name}/content"
    with zipfile.ZipFile(HTTPRangeFile(url, session=session)) as zf:
        want = relative_path.replace("\\", "/").lstrip("/").lower()
        name = next((n for n in zf.namelist() if n.replace("\\", "/").lower().endswith(want)), None)
        if name is None:
            base = Path(want).name
            name = next((n for n in zf.namelist() if Path(n).name.lower() == base), None)
        if name is None:
            raise FileNotFoundError(f"{relative_path} không có trong {zip_name}")
        return zf.read(name)
