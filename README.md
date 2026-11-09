# Web Crawler

Tool crawl data từ website (API JSON hoặc HTML): đăng nhập bằng username/password (config), duyệt nhiều trang theo pagination và lưu output (JSONL/CSV) với khả năng resume. Hỗ trợ vượt Cloudflare qua engine `curl_cffi`.

> 📦 **Cài đặt & hướng dẫn sử dụng chi tiết (Ubuntu/Windows):** xem [installation.md](installation.md)
>
> 🗂️ **Tổng quan repo / vai trò từng file:** xem [OVERVIEW.md](OVERVIEW.md)

## Kiến trúc

```
┌─────────────── crawler/__main__.py ───────────────┐
│  CLI (argparse): -c config -k credentials          │
│  --no-resume --max-pages --output                  │
└───────────────────────┬───────────────────────────┘
                        ▼
┌─────────────── crawler/config.py ─────────────────┐
│  load_config() -> AppConfig                        │
│  load_credentials() -> Credentials (yaml/env)      │
└───────────────────────┬───────────────────────────┘
                        ▼
┌─────────────── crawler/http.py ───────────────────┐
│  HttpEngine: chọn engine theo site.engine          │
│   - requests   (API thường)                        │
│   - curl_cffi  (Cloudflare, impersonate chrome)    │
└───────────────────────┬───────────────────────────┘
                        ▼
┌─────────────── crawler/auth.py ───────────────────┐   ┌──────────── crawler/client.py ────────────┐
│  AuthManager (login_type):                         │   │  ApiClient:                                │
│   - json/form: POST login -> token (token_path)    │◄──┤   - throttle (request_delay)               │
│     hoặc session cookie                            │   │   - retry/backoff (5xx, 429, network)      │
│   - xf: GET login page -> _xfToken -> POST form    │   │   - 401/403 -> re-login -> retry request   │
│   - verify marker sau login                        │   │   - request_json() / request_html()        │
└───────────────────────┬───────────────────────────┘   └─────────────────────┬─────────────────────────┘
                        ▼                                                     ▼
┌──────────────────────────────── crawler/crawler.py ─────────────────────────────────────────────┐
│  Crawler.run(): vòng lặp pagination                                                              │
│   - pagination: template (page-{page}) | next_link (follow link "Trang kế")                      │
│   - response_type: json (items_path dot-path) | html (items_selector + fields CSS/attr/regex)    │
│   - Stop: empty page | clamp-guard (served != requested) | total_pages | max_pages | Ctrl+C      │
└───────────────────────┬─────────────────────────────────────┬────────────────────────────────────┘
                        ▼                                     ▼
┌─────────────── crawler/storage.py ───────────┐  ┌────────────── crawler/jsonpath.py ──────────┐
│  RecordWriter: JSONL | CSV (append/truncate) │  │  get_path(data, "a.b.c")                    │
│  Checkpoint: last_page, total_items,         │  │  (đọc field lồng nhau trong JSON)           │
│               finished (atomic write)        │  └─────────────────────────────────────────────┘
└──────────────────────────────────────────────┘
```

## Flow

```
                        ┌───────────────────────────────────┐
                        │  Load config + credentials        │
                        │  (credentials.yaml / env var)     │
                        └──────────────┬────────────────────┘
                                       ▼
                        ┌───────────────────────────────────┐
                        │  Login (nếu login.enabled)?       │
                        │  - json/form: POST -> token/cookie│
                        │  - xf: GET /login/ -> _xfToken    │
                        │        -> POST form + verify      │
                        │  retry x3, backoff               │
                        └───────┬───────────────┬───────────┘
                          fail  │               │ OK
                                ▼               ▼
                        ┌───────────┐  ┌─────────────────────────────────┐
                        │ Exit code │  │ Checkpoint tồn tại?             │
                        │    1      │  │  - finished -> stop (không làm) │
                        └───────────┘  │  - last_page  -> resume N+1     │
                                       │  - không      -> start_page     │
                                       └──────────────┬──────────────────┘
                                                      ▼
        ┌──────────────────────────────── VÒNG LẶP CRAWL ─────────────────────────────────┐
        │                                                                                  │
        │  URL trang: template "page-{page}"  HOẶC  follow link next (next_link mode)      │
        │                                                                                  │
        │  GET/POST ──► throttle (request_delay) ──► engine (requests | curl_cffi)         │
        │      │                                                                           │
        │      ▼                                                                           │
        │  HTTP 401/403? ──► re-login (x2) ──► retry                                       │
        │  HTTP 5xx/429/network? ──► backoff lũy tiến (retry x3)                           │
        │  HTTP trong stop_status_codes (vd 404)? ──► coi như hết dữ liệu                  │
        │      │                                                                           │
        │      ▼  (thành công)                                                             │
        │  [html]  clamp-guard: pageNav served != requested? ──► DỪNG (không ghi,          │
        │          tránh loop vô hạn khi site clamp về trang cuối)                         │
        │      │                                                                           │
        │      ▼                                                                           │
        │  Extract items:                                                                  │
        │   - json: items_path = "data.items" (dot-path)                                   │
        │   - html: items_selector (CSS) + fields (selector/attr/regex/base_url)           │
        │      │                                                                           │
        │      ▼                                                                           │
        │  Ghi append JSONL/CSV ──► save checkpoint {last_page, total_items}               │
        │      │                                                                           │
        │      ▼                                                                           │
        │  Dừng khi: empty page | hết total_pages | hết next link |                        │
        │            max_pages | Ctrl+C                                                    │
        └───────────────────────────────┬──────────────────────────────────────────────────┘
                                        ▼
                              ┌──────────────────────┐
                              │ Output: items.jsonl  │
                              │ + checkpoint.json    │
                              └──────────────────────┘
```

Điểm chính của flow:

1. **Credentials tách riêng**: `credentials.yaml` bị gitignore, hoặc dùng env `CRAWLER_USERNAME` / `CRAWLER_PASSWORD` (env ưu tiên cao hơn).
2. **Login 3 kiểu**: `json` (POST JSON → token), `form` (POST form → cookie), `xf` (XenForo: CSRF `_xfToken` + form POST + verify marker). Tắt bằng `login.enabled: false` khi crawl public.
3. **Token linh hoạt**: lấy từ JSON response theo `token_path` (vd `data.token`), gửi qua `auth_header` (vd `Authorization: Bearer ...`); để trống `token_path` thì dùng session cookie.
4. **Tự re-login**: gặp 401/403 giữa chừng → login lại → retry request (tối đa 2 lần).
5. **Resumable**: checkpoint lưu sau mỗi trang (`last_page`, `total_items`); chạy lại tool sẽ tiếp tục từ trang kế tiếp; `--no-resume` để crawl lại từ đầu (truncate output). next_link mode: re-walk từ trang 1 (không ghi) đến vị trí đã lưu.
6. **Dừng thông minh**: trang rỗng, hết `totalPages`/next-link, clamp-guard (out-of-range), đạt `max_pages`, hoặc Ctrl+C (progress vẫn được lưu).
7. **Rate limit + backoff**: sleep giữa các request; 429/5xx/network error thì backoff lũy tiến.
8. **Chống Cloudflare/WAF**: engine `curl_cffi` + impersonate Chrome (TLS fingerprint); kèm bộ headers navigate-style cho cả GET lẫn POST.

## Cấu trúc thư mục

```
web_crawler/
├── config.example.yaml       # Config mẫu (API JSON)
├── config.voz.yaml           # Config voz.vn forum thread list
├── config.voz_whatsnew.yaml  # Config voz.vn whats-new
├── credentials.example.yaml  # (copy -> credentials.yaml, gitignored)
├── requirements.txt
├── crawler/
│   ├── __main__.py           # CLI entrypoint
│   ├── config.py             # Loader config + credentials
│   ├── http.py               # Engine requests / curl_cffi (Cloudflare)
│   ├── auth.py               # Login json/form/xf + verify + retry
│   ├── client.py             # HTTP: throttle, retry/backoff, re-login
│   ├── crawler.py            # Vòng lặp pagination + clamp-guard + checkpoint
│   ├── storage.py            # Ghi JSONL/CSV + checkpoint file
│   └── jsonpath.py           # Đọc field lồng nhau theo dot-path
└── tests/
    └── mock_server.py        # Mock API để test local
```

## Crawl voz.vn

voz.vn là forum XenForo có Cloudflare WAF. Tool đã update để hỗ trợ:

- **Engine `curl_cffi`** (`site.engine: curl_cffi`, `impersonate: chrome`): giả lập TLS fingerprint Chrome để vượt Cloudflare; POST đi kèm bộ headers navigate-style để qua WAF
- **Login XenForo** (`login.login_type: xf`): GET `/login/` lấy `_xfToken` → POST `/login/login` (form) → verify qua marker trên trang sau login
- **HTML mode** (`crawl.response_type: html`): parse items bằng CSS selector (`items_selector`) + field extraction (`fields`: selector/attr/regex/base_url)
- **Pagination 2 kiểu**: `template` (`page-{page}` — dùng cho forum) và `next_link` (follow link "Trang kế" — dùng cho whats-new)
- **Chống clamp-loop**: voz.vn clamp trang out-of-range về trang cuối; tool phát hiện qua `served_page_selector` (pageNav) và dừng thay vì crawl lặp vô hạn

Configs mẫu:

```bash
cp credentials.example.yaml credentials.yaml   # điền account voz (nếu có)

python3 -m crawler -c config.voz.yaml            # crawl thread list forum /f/tu-van-cau-hinh.70/ (305 trang)
python3 -m crawler -c config.voz_whatsnew.yaml   # crawl bài viết mới /whats-new/posts/
python3 -m crawler -c config.voz.yaml --max-pages 50   # giới hạn số trang
```

Field mỗi item (forum): `title, url, thread_id, author, created, replies, views, last_post_time, last_post_user`. Output mặc định `output/voz_threads.<dd-mm-yyyy>.jsonl` (**1 file/ngày** nhờ `daily_file: true` — ví dụ `voz_threads.09-11-2026.jsonl`; các lần chạy cùng ngày ghi tiếp vào file) + checkpoint `output/voz_checkpoint.json` (resume tự động). Chi tiết: [installation.md](installation.md) mục 3.2–3.3.

Lưu ý: crawl public forum **không cần login**. Chỉ bật `login.enabled: true` khi cần nội dung login-only.

## Sử dụng

```bash
pip install -r requirements.txt

cp config.example.yaml config.yaml        # chỉnh endpoint/pagination theo API thực tế
cp credentials.example.yaml credentials.yaml  # điền username/password

cd web_crawler
python3 -m crawler                          # crawl với config mặc định
python3 -m crawler --no-resume              # crawl lại từ đầu
python3 -m crawler --max-pages 10           # giới hạn số trang
python3 -m crawler --output out/data.jsonl  # ghi đè đường dẫn output
CRAWLER_USERNAME=me CRAWLER_PASSWORD=secret python3 -m crawler  # credentials qua env
```

Exit code: `0` thành công, `1` lỗi (login fail, HTTP lỗi...), `130` bị Ctrl+C.

## Test với mock server

```bash
cd web_crawler
python3 tests/mock_server.py &          # mock API tại 127.0.0.1:8765 (login + 5 trang x 3 items)

# config trỏ tới mock server
sed -e 's|base_url: https://api.example.com|base_url: http://127.0.0.1:8765|' \
    config.example.yaml > /tmp/test_config.yaml

# crawl (credentials mock: user/pass123)
CRAWLER_USERNAME=user CRAWLER_PASSWORD=pass123 \
python3 -m crawler -c /tmp/test_config.yaml --no-resume --max-pages 5
# mong đợi: 5 trang x 3 items = 15 items, output tại output/items.jsonl

kill %1                                 # tắt mock server
```

Các kịch bản đã verify: crawl đủ 5 trang, resume giữa chừng, `--no-resume` truncate, token hết hạn → tự re-login, sai mật khẩu → exit 1, output CSV/JSONL đúng.

## Điểm cần lưu ý khi dùng thật

- Xem API thực tế trả gì: mở DevTools → tab Network → bắt request login + request danh sách, điền `token_path`, `items_path`, `total_pages_path` tương ứng.
- Nếu API trả token dạng cookie: để `token_path` và `auth_header` rỗng, requests.Session tự giữ cookie.
- Tăng `request_delay` nếu server có rate limit, tránh bị block.
