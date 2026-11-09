# Installation Guide

Hướng dẫn cài đặt và sử dụng Web Crawler trên **Ubuntu/Linux** và **Windows**.

## Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| Python | **3.10+** (bắt buộc do thư viện `curl_cffi`) |
| pip | Mới nhất (`pip install --upgrade pip`) |
| RAM / Disk | ~100 MB |
| Network | Truy cập được website cần crawl |

---

## 1. Cài đặt

### 1.1. Ubuntu / Linux

```bash
# Cài Python + pip + venv (nếu chưa có)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Vào thư mục tool
cd ~/hadh14/my_project/web_crawler

# Tạo virtual environment (khuyến nghị)
python3 -m venv .venv
source .venv/bin/activate

# Cài dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

> Lần sau chạy tool cần `source .venv/bin/activate` trước, hoặc dùng trực tiếp `.venv/bin/python -m crawler`.

### 1.2. Windows

**Bước 1 — Cài Python:**
1. Tải Python 3.10+ từ https://www.python.org/downloads/ (hoặc từ Microsoft Store)
2. Chạy installer, **tick chọn "Add python.exe to PATH"** trước khi bấm Install

**Bước 2 — Cài dependencies** (chọn đúng tab terminal bạn dùng):

Command Prompt (cmd.exe):

```bat
cd %USERPROFILE%\hadh14\my_project\web_crawler
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

PowerShell:

```powershell
cd $env:USERPROFILE\hadh14\my_project\web_crawler
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

> PowerShell chặn script thì chạy thêm: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
>
> Lần sau chạy tool cần activate lại venv: `.venv\Scripts\activate` (CMD) hoặc `.venv\Scripts\Activate.ps1` (PowerShell).

### 1.3. Kiểm tra cài đặt

```bash
# Ubuntu
python3 -m crawler --help

# Windows
python -m crawler --help
```

Thấy menu help với các flag `-c/--config, -k/--credentials, --no-resume, --max-pages, --output, -v/--verbose` là OK.

---

## 2. Cấu hình

### 2.1. Credentials (username/password)

```bash
# Ubuntu
cp credentials.example.yaml credentials.yaml

# Windows
copy credentials.example.yaml credentials.yaml
```

Sửa `credentials.yaml`:

```yaml
username: tai_khoan_cua_ban
password: mat_khau_cua_ban
```

**Hoặc** không tạo file mà dùng biến môi trường (ưu tiên cao hơn file):

```bash
# Ubuntu (tạm thời cho phiên hiện tại)
export CRAWLER_USERNAME="tai_khoan"
export CRAWLER_PASSWORD="mat_khau"

# Windows CMD
set CRAWLER_USERNAME=tai_khoan
set CRAWLER_PASSWORD=mat_khau

# Windows PowerShell
$env:CRAWLER_USERNAME="tai_khoan"
$env:CRAWLER_PASSWORD="mat_khau"
```

> ⚠️ `credentials.yaml` đã được gitignore — không commit lên repo. Không share trong chat/screenshot.

### 2.2. Chọn config crawl

| File | Mục đích | Login |
|---|---|---|
| `config.voz.yaml` | voz.vn — thread list forum `/f/tu-van-cau-hinh.70/` | Không cần (public) |
| `config.voz_whatsnew.yaml` | voz.vn — bài viết mới `/whats-new/posts/` | Không cần (public) |
| `config.example.yaml` | Mẫu cho API JSON nội bộ khác | Tùy API |

Muốn crawl forum khác của voz: sửa `crawl.endpoint` trong config, vd:

```yaml
crawl:
  endpoint: /f/amd.25/          # forum AMD
```

Danh sách forum xem tại https://voz.vn/forums/. Muốn login (nội dung login-only): mở `credentials.yaml` điền account, rồi trong config đổi `login.enabled: true`.

### 2.3. Tùy chỉnh quan trọng trong config

```yaml
crawl:
  request_delay: 2.0      # giây nghỉ giữa các request — TĂNG LÊN nếu bị rate-limit
  max_pages: 0            # 0 = không giới hạn; đặt 50 nếu muốn giới hạn
  page_size: 100          # số item/trang (nếu API hỗ trợ)

output:
  format: jsonl           # jsonl | csv
  file: output/voz_threads.jsonl
  csv_columns: [id, name] # chỉ dùng khi format: csv
```

---

## 3. Sử dụng

> ⚠️ Mọi lệnh `python -m crawler` **phải chạy trong thư mục `web_crawler`** (thư mục chứa package `crawler/` và các file config). Đường dẫn trong `--output` là relative so với thư mục này.

### 3.1. Lệnh cơ bản

> 💡 **Config mặc định:** chạy không có `-c` thì tool tìm file `config.yaml`. File này **chưa tồn tại sẵn** — hoặc chỉ định rõ bằng `-c`, hoặc tạo bản copy:
>
> ```bash
> # Cách 1: chỉ định config trực tiếp (khuyến nghị)
> python3 -m crawler -c config.voz.yaml
>
> # Cách 2: tạo config.yaml mặc định rồi chạy không cần -c
> cp config.voz.yaml config.yaml
> python3 -m crawler
> ```
>
> Nếu quên, tool sẽ báo: `Config file not found: config.yaml. Dung -c de chi dinh...`

```bash
# Ubuntu (đã activate .venv)
python3 -m crawler -c config.voz.yaml

# Windows (đã activate .venv)
python -m crawler -c config.voz.yaml
```

Các flag hay dùng:

```bash
python3 -m crawler -c config.voz.yaml            # crawl đầy đủ, tự resume nếu dở dang
python3 -m crawler -c config.voz.yaml --max-pages 50   # chỉ crawl 50 trang
python3 -m crawler -c config.voz.yaml --no-resume      # bỏ checkpoint, crawl lại từ đầu
python3 -m crawler -c config.voz.yaml --output out/data.jsonl  # đổi nơi lưu output
python3 -m crawler -c config.voz.yaml -v               # log chi tiết (debug)
```

### 3.2. Resume / chạy lại

Hành vi khi chạy **cùng một config nhiều lần** (vd lúc 13h00 và 15h00):

| Trạng thái lần chạy trước | Lần chạy sau (mặc định) |
|---|---|
| Dở dang (crash, Ctrl+C, max_pages) | **Resume**: ghi TIẾP vào file output từ đúng trang dừng, không trùng lặp |
| Đã xong (`finished: true`) | **Bỏ qua** — log `Crawl already finished...`, không ghi gì |

Muốn crawl **dữ liệu mới** ở lần chạy sau, có 2 lựa chọn:

- `--no-resume`: crawl lại từ đầu và **GHI ĐÈ** file output cũ (mất data lịch sử!)
- **`append_mode: true`** trong config (khuyến nghị cho chạy định kỳ): mỗi lần chạy sau khi lần trước đã xong sẽ **crawl mới từ trang 1 và NỐI TIẾP vào file** — data lịch sử được giữ nguyên:

```yaml
output:
  append_mode: true
```

> 💡 `config.voz_whatsnew.yaml` đã bật sẵn `append_mode: true`. Với config.voz.yaml (thread list lớn) nên giữ mặc định — crawl 1 lần đủ 305 trang.

- **Checkpoint báo "already finished"** → xem bảng trên; muốn crawl lại từ đầu dùng `--no-resume`

### 3.3. Kết quả

Output được lưu vào thư mục `output/` **trong thư mục `web_crawler`** (đường dẫn đầy đủ: `~/hadh14/my_project/web_crawler/output/`), tự tạo nếu chưa có. Mỗi config sinh 2 file:

| Config chạy | File data | File checkpoint (resume) |
|---|---|---|
| `config.voz.yaml` | `output/voz_threads.<dd-mm-yyyy>.jsonl` | `output/voz_checkpoint.json` |
| `config.voz_whatsnew.yaml` | `output/voz_whatsnew.<dd-mm-yyyy>.jsonl` | `output/voz_whatsnew_checkpoint.json` |
| `config.example.yaml` (API JSON) | `output/items.jsonl` | `output/checkpoint.json` |

> 📅 **1 file output mỗi ngày** (`output.daily_file: true` — đã bật cho 2 config voz): lần chạy đầu tiên trong ngày tạo file mới kèm date, ví dụ `voz_threads.09-11-2026.jsonl`; **các lần chạy sau trong cùng ngày ghi TIẾP vào file đó**; sang ngày hôm sau tool tự tạo file mới với date mới. Checkpoint không kèm date (chỉ track vị trí resume).
>
> 💡 Log khi chạy luôn in ra `Output file: <đường dẫn>` để biết data đang ghi vào đâu.

```
output/
├── voz_threads.09-11-2026.jsonl   # data: 1 JSON object / dòng (title, url, author, replies...)
└── voz_checkpoint.json            # trạng thái resume {last_page, total_items, finished}
```

> 💡 Dùng `--output out/data.jsonl` để đổi **nơi lưu data**. Lưu ý: flag này KHÔNG đổi đường dẫn checkpoint — checkpoint vẫn lấy từ `checkpoint_file` trong config, nên các lần chạy sau (kể cả có/không `--output`) vẫn resume đúng vị trí cũ. Muốn tách hẳn job crawl riêng, copy config và sửa cả `output.file` lẫn `output.checkpoint_file`.

Đọc data nhanh:

```bash
# Ubuntu: xem 5 dòng đầu (file có date theo ngày chạy)
head -5 output/voz_threads.$(date +%d-%m-%Y).jsonl

# Windows PowerShell
Get-Content ("output\voz_threads.{0}.jsonl" -f (Get-Date -Format "dd-MM-yyyy")) -TotalCount 5
```

```python
# Python / pandas
import pandas as pd
from datetime import datetime
stamp = datetime.now().strftime("%d-%m-%Y")
df = pd.read_json(f"output/voz_threads.{stamp}.jsonl", lines=True)
print(df.head(), df.shape)
```

### 3.4. Chạy định kỳ (tùy chọn)

> ⚠️ Khi chạy định kỳ (cron/Task Scheduler), nhớ bật `output.append_mode: true` trong config — nếu không, các lần chạy sau khi lần trước đã xong sẽ bị **bỏ qua hoàn toàn** (mặc định) hoặc **ghi đè mất data cũ** (nếu dùng `--no-resume`).

**Ubuntu — cron:**

```bash
crontab -e
# Thêm dòng: crawl lúc 6h sáng mỗi ngày
0 6 * * * cd /home/<user>/hadh14/my_project/web_crawler && .venv/bin/python -m crawler -c config.voz.yaml >> crawl.log 2>&1
```

**Windows — Task Scheduler:**
1. Mở Task Scheduler → Create Basic Task
2. Trigger: Daily 6:00
3. Action: Start a program
   - Program: `C:\...\web_crawler\.venv\Scripts\python.exe`
   - Arguments: `-m crawler -c config.voz.yaml`
   - Start in: `C:\...\web_crawler`

---

## 4. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `HTTP 403` / "Just a moment" ngay request đầu | Cloudflare chặn | Đảm bảo `site.engine: curl_cffi` trong config; `pip install -U curl_cffi` |
| `engine=curl_cffi requires: pip install curl_cffi` | Thiếu thư viện | `pip install curl_cffi` |
| Lỗi build khi `pip install curl_cffi` (Linux) | Thiếu compiler | `sudo apt install -y build-essential python3-dev` |
| `ensurepip is not available` khi tạo venv | Thiếu gói venv | `sudo apt install -y python3.10-venv`; không có sudo thì: `pip3 install virtualenv` → `python3 -m virtualenv .venv` |
| `Login rejected: marker ... still present` | Sai username/password | Kiểm tra `credentials.yaml` |
| `Token not found at 'data.token'` | Sai `token_path` | Bắt request login bằng DevTools (F12 → Network) xem response thật |
| `HTTP 429` lặp lại | Bị rate-limit | Tăng `crawl.request_delay` (vd 5.0), giảm tần suất chạy |
| Crawl chậm nhưng không lỗi | `request_delay` lớn | Bình thường — giữ nguyên để tránh bị block |
| Checkpoint báo finished nhưng thiếu data | Trang cuối chưa kịp ghi | Xem `checkpoint.json` → chạy lại `--no-resume` nếu cần |
| Windows: `'python' is not recognized` | Python chưa vào PATH | Cài lại Python, tick "Add to PATH" |
| Windows: `cannot be loaded because running scripts is disabled` | PowerShell chặn venv | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |

---

## 5. Đóng góp / mở rộng

Thêm site mới:

1. Probe cấu trúc: mở DevTools (F12) → Network → xem request list + login
2. Copy config làm mẫu và sửa: `cp config.voz.yaml config_moi.yaml` (site HTML) hoặc `cp config.example.yaml config_moi.yaml` (API JSON) → sửa `site.base_url`, `crawl.endpoint`, `items_selector`, `fields`
3. API JSON: tham khảo `config.example.yaml` (`response_type: json`, `items_path`, `token_path`)
4. Test cục bộ: `python3 -m crawler -c config_moi.yaml --max-pages 3 -v`
5. Crawl đầy đủ khi selector đã chuẩn
