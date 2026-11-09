# Overview — Web Crawler

Tool crawl data từ website (API JSON hoặc HTML), hỗ trợ đăng nhập bằng username/password, vượt Cloudflare, crawl nhiều trang theo pagination, tự resume, xuất JSONL/CSV.

> Người mới nên đọc file này trước → rồi đến [README.md](README.md) (kiến trúc + flow) và [installation.md](installation.md) (cài đặt chi tiết).

## Sơ đồ thư mục

```
web_crawler/
├── OVERVIEW.md                  ← bạn đang đọc
├── README.md
├── installation.md
├── requirements.txt
├── .gitignore
├── config.example.yaml
├── config.voz.yaml
├── config.voz_whatsnew.yaml
├── credentials.example.yaml
├── crawler/                     # source code chính
├── tests/                       # mock server để test
└── output/                      # (tự tạo khi chạy) data crawl + checkpoint
```

## Mô tả từng file

### Tài liệu

| File | Vai trò |
|---|---|
| `OVERVIEW.md` | Tổng quan repo, vai trò từng file — điểm đọc đầu tiên |
| `README.md` | Kiến trúc hệ thống, flow diagram chi tiết, hướng dẫn crawl voz.vn, test với mock server |
| `installation.md` | Hướng dẫn cài đặt & sử dụng trên Ubuntu/Windows, chạy định kỳ (cron/Task Scheduler), xử lý sự cố |

### Config

| File | Vai trò |
|---|---|
| `config.example.yaml` | Mẫu config cho **API JSON nội bộ** (login lấy token, pagination query-param). Copy → `config.yaml` để dùng |
| `config.voz.yaml` | Config chạy thật cho **voz.vn** — thread list forum (HTML mode, curl_cffi, pagination `page-{page}`, `daily_file: true` — 1 file output/ngày) |
| `config.voz_whatsnew.yaml` | Config chạy thật cho **voz.vn** — bài viết mới `/whats-new/posts/` (pagination `next_link`, `append_mode: true` + `daily_file: true` cho chạy định kỳ) |
| `credentials.example.yaml` | Mẫu credentials. Copy → `credentials.yaml` (gitignored) hoặc dùng env `CRAWLER_USERNAME`/`CRAWLER_PASSWORD` |
| `requirements.txt` | Dependencies: `requests`, `PyYAML`, `curl_cffi` (vượt Cloudflare), `beautifulsoup4` |
| `.gitignore` | Loại trừ `credentials.yaml`, `output/`, `.venv/`, `__pycache__/` |

### Source code (`crawler/`)

| File | Vai trò |
|---|---|
| `__init__.py` | Package init, export `Crawler` |
| `__main__.py` | **Điểm chạy chính**: `python3 -m crawler`. CLI argparse (`-c`, `-k`, `--no-resume`, `--max-pages`, `--output`, `-v`) |
| `config.py` | Load + validate `config.yaml` và credentials (yaml/env) thành dataclass `AppConfig` |
| `http.py` | Lớp HTTP engine: chọn `requests` (thường) hoặc `curl_cffi` (giả lập Chrome, qua Cloudflare); tự thêm browser headers |
| `auth.py` | Đăng nhập 3 kiểu: `json`/`form` (POST → token hoặc cookie) và `xf` (XenForo: CSRF `_xfToken` → form POST → verify marker); retry + backoff |
| `client.py` | HTTP client dùng chung: rate-limit (`request_delay`), retry/backoff cho 5xx-429-network, tự re-login khi 401/403, `request_json()`/`request_html()` |
| `crawler.py` | **Tim của tool**: vòng lặp pagination (template hoặc next_link), extract items (JSON dot-path / CSS selector + fields), clamp-guard chống loop vô hạn, gọi writer + checkpoint |
| `storage.py` | `RecordWriter` ghi JSONL/CSV (append hoặc truncate), `Checkpoint` lưu/tải trạng thái resume (atomic write) |
| `jsonpath.py` | `get_path(data, "a.b.c")` — đọc field lồng nhau trong JSON response theo dot-path |

### Test & output

| File / Thư mục | Vai trò |
|---|---|
| `tests/mock_server.py` | Mock API local (port 8765): login trả token + 5 trang × 3 items — dùng test toàn bộ flow không cần internet |
| `output/` | Kết quả crawl: `voz_threads.jsonl` (data), `voz_checkpoint.json` (trạng thái resume) — tự tạo khi chạy |

## Chạy nhanh

```bash
pip install -r requirements.txt
python3 -m crawler -c config.voz.yaml          # crawl voz.vn forum
python3 -m crawler -c config.voz_whatsnew.yaml # crawl bài viết mới
```

Chi tiết: xem [installation.md](installation.md).
