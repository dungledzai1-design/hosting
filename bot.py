from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import random
import re
import secrets
import shutil
import signal
import string
import subprocess
import sys
import importlib
import tarfile
import tempfile
import threading
import time
import traceback
import zipfile
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
# 🔑 CẤU HÌNH BOT - ĐẶT LÊN ĐẦU FILE ĐỂ DỄ CHỈNH SỬA
# ═══════════════════════════════════════════════════════════════════════

# ─── TOKEN BOT (THAY BẰNG TOKEN CỦA BẠN) ──────────────────────────
BOT_TOKEN_HARDCODED = "8321181205:AAHR-8t8Id3RlRGs9BaGyp9YnGS-OGVtgWk"  # ← THAY TOKEN CỦA BẠN VÀO ĐÂY

# ─── ID ADMIN (THAY BẰNG ID TELEGRAM CỦA BẠN) ──────────────────────
ADMIN_ID_HARDCODED = "6907359862"  # ← THAY ID ADMIN CỦA BẠN VÀO ĐÂY

# ─── THÔNG TIN THƯƠNG HIỆU ──────────────────────────────────────────
BRAND       = "𝐃𝐋𝐄𝐄 𝐃𝐄𝐕 🚀"
BRAND_VER   = "v1.0"
BRAND_TAG   = f"{BRAND} {BRAND_VER}"
SUPPORT_USR = "@letiendung01"
ADMIN_NAME  = "Dlee Dev"
UPDATE_CH   = ""  # Để trống để xóa link
FOOTER      = f"\n\n<blockquote>{BRAND_TAG}</blockquote>"

# ─── THÔNG TIN THANH TOÁN MB BANK ──────────────────────────────────
MB_BANK_NUMBER = "13300066778899"
MB_BANK_OWNER  = "LE TIEN DUNG"
ZALO_NUMBER    = "0969411158"

# ═══════════════════════════════════════════════════════════════════════
# KẾT THÚC PHẦN CẤU HÌNH
# ═══════════════════════════════════════════════════════════════════════

_REQUIRED_PKGS = [
    ("telebot",             "pyTelegramBotAPI"),
    ("requests",            "requests"),
    ("cryptography.fernet", "cryptography"),
    ("flask",               "flask"),
    ("apscheduler",         "APScheduler"),
    ("github",              "PyGithub"),
    ("psutil",              "psutil"),
    ("PIL",                 "Pillow"),
]

def _auto_install_missing() -> None:
    import importlib
    missing: List[str] = []
    for mod, pip_name in _REQUIRED_PKGS:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pip_name)
    if not missing:
        return
    print(f"[thiết_lập] đang cài đặt các gói còn thiếu: {', '.join(missing)}")
    strategies = [
        [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", *missing],
        [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet",
         "--break-system-packages", *missing],
        [sys.executable, "-m", "pip", "install", "--user", "--upgrade", "--quiet", *missing],
        [sys.executable, "-m", "pip", "install", "--user", "--upgrade", "--quiet",
         "--break-system-packages", *missing],
    ]
    last_err: Optional[Exception] = None
    for cmd in strategies:
        try:
            subprocess.run(cmd, check=True)
            print("[thiết_lập] cài đặt thành công — tiếp tục khởi động")
            return
        except Exception as e:
            last_err = e
            continue
    sys.exit(f"[x] tự động cài đặt thất bại sau {len(strategies)} lần thử: {last_err}. "
             f"Chạy thủ công: pip install {' '.join(missing)}")

_auto_install_missing()

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, jsonify

TOKEN = (
    os.environ.get("BOT_TOKEN")
    or os.environ.get("MAIN_BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
    or BOT_TOKEN_HARDCODED
    or ""
).strip()

try:
    OWNER_ID = int(os.environ.get("OWNER_ID", ADMIN_ID_HARDCODED))
except (TypeError, ValueError):
    OWNER_ID = int(ADMIN_ID_HARDCODED) if ADMIN_ID_HARDCODED.isdigit() else 0

if not TOKEN:
    sys.exit(
        "❌ THIẾU TOKEN BOT!\n"
        "Vui lòng thêm token vào biến môi trường BOT_TOKEN\n"
        "hoặc sửa trực tiếp BOT_TOKEN_HARDCODED trong file bot.py"
    )

ANNOUNCE_CHANNEL = os.environ.get("ANNOUNCE_CHANNEL", "").strip()
try:
    KEEPALIVE_PORT = int(os.environ.get("PORT", 10460))
except (TypeError, ValueError):
    KEEPALIVE_PORT = 10000

class Btn(types.InlineKeyboardButton):
    def __init__(self, *args, style: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        if style:
            self.style = style

    def to_dict(self):
        d = super().to_dict()
        if getattr(self, "style", ""):
            d["style"] = self.style
        return d

_SEC_PATTERNS = {
    "🔴 Đánh Cắp Dữ Liệu": [
        (r'os\.walk\s*\(\s*["\'][/\\](?:root|home|etc|var|proc)["\']',
                                                  "Đang quét thư mục hệ thống - đánh cắp file server"),
        (r'send_document\s*\(.*open\s*\(\s*["\'][/\\](?:root|etc|proc|sys)',
                                                  "Đang gửi file hệ thống ra ngoài"),
        (r'zipfile\.ZipFile.*["\']w["\'].*\bos\.walk\b.*["\'][/\\](?:root|etc|home)',
                                                  "Đang nén file hệ thống để gửi đi"),
        (r'glob\.glob\s*\(["\'][/\\]\*',          "Đang quét toàn bộ thư mục gốc"),
        (r'shutil\.copy.*["\'][/\\]root',         "Đang copy từ /root"),
        (r'ROOT_DIR\s*=\s*["\'][/\\]["\']',       "Đang nhắm vào thư mục gốc"),
    ],
    "🔴 Cửa Hậu": [
        (r'subprocess\s*\.\s*(?:Popen|call|run)\s*\([^\n]*shell\s*=\s*True[^\n]*(?:input|stdin)',
                                                  "Tiêm lệnh shell với input người dùng"),
        (r'marshal\.loads\s*\(',                  "Mã bytecode đã được obfuscate"),
    ],
    "🔴 Lộ Thông Tin": [
    ],
    "🟡 Mã Hóa Ẩn": [
        (r'base64\.b64decode\s*\(.*\)\s*[\)\s]*\bexec\b',
                                                  "Giải mã Base64 + thực thi - mã ẩn"),
        (r'(?:\\x[0-9a-fA-F]{2}){6,}',           "Chuỗi hex dài - mã bị obfuscate"),
        (r'zlib\.decompress\s*\(.*\)\s*[\)\s]*\bexec\b',
                                                  "Giải nén + thực thi mã ẩn"),
    ],
    "🟡 Mạng Đáng Ngờ": [
        (r'devil-api\.com|elementfx\.io',         "API endpoint độc hại đã biết"),
        (r'open\s*\(\s*["\'][/\\](?:root|etc|proc|sys).*(?:requests|urllib).*(?:post|put)',
                                                  "Đọc file hệ thống + HTTP POST - đánh cắp dữ liệu"),
        (r'pastebin\.com/raw',                    "Tải code từ Pastebin - tải mã từ xa"),
    ],
    "🟠 Lạm Dụng Tài Nguyên": [
        (r'multiprocessing\.Pool\s*\(\s*(?:None|\d{3,})',
                                                  "Pool xử lý lớn - lạm dụng tài nguyên"),
        (r'fork\s*\(\s*\).*fork\s*\(',            "Mẫu fork bomb"),
    ],
}

_SEC_TOKEN_RE = re.compile(r'\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b')

def _sec_static_scan(code: str) -> dict:
    results: Dict[str, List[str]] = {}
    for category, pattern_list in _SEC_PATTERNS.items():
        hits = []
        for pattern, description in pattern_list:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                hits.append(description)
        if hits:
            results[category] = hits
    tokens = _SEC_TOKEN_RE.findall(code)
    if tokens:
        results.setdefault("🔴 Lộ Thông Tin", [])
        results["🔴 Lộ Thông Tin"].append(f"Phát hiện Bot Token: {tokens[0][:15]}...")
    return results

def _sec_ast_scan(code: str) -> List[str]:
    import ast as _ast
    findings: List[str] = []
    try:
        tree = _ast.parse(code)
    except SyntaxError as e:
        findings.append(f"Parse code thất bại: {e} - có thể đã bị mã hóa")
        return findings
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Call):
            func = node.func
            if isinstance(func, _ast.Attribute):
                if (func.attr == 'walk' and isinstance(func.value, _ast.Name)
                        and func.value.id == 'os' and node.args):
                    arg = node.args[0]
                    if isinstance(arg, _ast.Constant) and isinstance(arg.value, str):
                        if arg.value in ['/root', '/etc', '/home', '/proc']:
                            findings.append(f"os.walk('{arg.value}') - đang quét thư mục nhạy cảm")
            if isinstance(func, _ast.Name) and func.id in ('eval', 'exec'):
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, _ast.Call):
                        findings.append(f"NGUY HIỂM: {func.id}() — thực thi mã động")
                    elif isinstance(arg0, _ast.Attribute):
                        findings.append(f"NGUY HIỂM: {func.id}() — đầu vào dựa trên thuộc tính")
            if isinstance(func, _ast.Name) and func.id == '__import__':
                if node.args and isinstance(node.args[0], _ast.Constant):
                    if node.args[0].value == 'os':
                        findings.append(f"__import__('os') động — có thể là code injection")
    return findings

def _sec_calculate_risk(static_findings: dict, ast_findings: List[str]) -> int:
    weights = {
        "🔴 Đánh Cắp Dữ Liệu": 40,
        "🔴 Cửa Hậu":         40,
        "🔴 Lộ Thông Tin":    10,
        "🟡 Mạng Đáng Ngờ":   12,
        "🟡 Mã Hóa Ẩn":       10,
        "🟠 Lạm Dụng Tài Nguyên": 8,
    }
    score = sum(weights.get(cat, 5) * min(len(hits), 3)
                for cat, hits in static_findings.items()
                if hits)
    unique_ast = list(dict.fromkeys(ast_findings))
    score += min(len(unique_ast) * 5, 20)
    return min(score, 100)

def _sec_get_verdict(risk_score: int, static_findings: dict) -> Tuple[str, str]:
    has_blocking = any(
        static_findings.get(c)
        for c in ("🔴 Đánh Cắp Dữ Liệu", "🔴 Cửa Hậu")
    )
    has_credentials = bool(static_findings.get("🔴 Lộ Thông Tin"))

    if has_blocking and risk_score >= 70:
        return "NGUY HIỂM", "TỪ CHỐI"
    if risk_score >= 85:
        return "NGUY HIỂM", "TỪ CHỐI"
    if has_credentials and not has_blocking and risk_score < 40:
        return "ĐÁNG NGỜ", "KIỂM TRA THỦ CÔNG"
    if has_blocking and risk_score >= 35:
        return "ĐÁNG NGỜ", "KIỂM TRA THỦ CÔNG"
    if risk_score >= 55:
        return "ĐÁNG NGỜ", "KIỂM TRA THỦ CÔNG"
    return "AN TOÀN", "PHÊ DUYỆT"

def _sec_scan_code(code: str, filename: str = "file.py") -> dict:
    sf = _sec_static_scan(code)
    af = _sec_ast_scan(code)
    risk = _sec_calculate_risk(sf, af)
    verdict, recommendation = _sec_get_verdict(risk, sf)
    all_threats: List[str] = [f"{c}: {h}" for c, hits in sf.items() for h in hits] + af
    if verdict == "NGUY HIỂM":
        summary = f"⚠️ File NGUY HIỂM! Phát hiện {len(all_threats)} mối đe dọa."
    elif verdict == "ĐÁNG NGỜ":
        summary = "🔍 File đáng ngờ. Admin cần kiểm tra thủ công."
    else:
        summary = "✅ File an toàn. Không phát hiện mối đe dọa nào."
    return {"verdict": verdict, "risk_score": risk, "findings": sf,
            "ast_findings": af, "all_threats": all_threats,
            "recommendation": recommendation, "summary": summary, "filename": filename}

def _sec_scan_archive(file_path: str) -> dict:
    tmp = tempfile.mkdtemp()
    try:
        if file_path.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as z:
                for name in z.namelist():
                    if name.startswith('/') or '..' in name:
                        return {"verdict": "NGUY HIỂM", "risk_score": 99,
                                "findings": {"🔴 Tấn Công Zip Slip": ["Đường dẫn file nguy hiểm trong ZIP!"]},
                                "ast_findings": [], "recommendation": "TỪ CHỐI",
                                "summary": "Phát hiện tấn công Zip Slip!", "all_threats": []}
                z.extractall(tmp)
        elif file_path.endswith(('.tar.gz', '.tgz', '.tar')):
            with tarfile.open(file_path, 'r:*') as t:
                t.extractall(tmp)
        py_files = list(Path(tmp).rglob("*.py"))
        if not py_files:
            return {"verdict": "ĐÁNG NGỜ", "risk_score": 20,
                    "findings": {"🟡 Cảnh Báo": ["Không tìm thấy file .py nào trong archive"]},
                    "ast_findings": [], "recommendation": "KIỂM TRA THỦ CÔNG",
                    "summary": "Archive không chứa file Python.", "all_threats": []}
        worst = None
        for py_file in py_files[:10]:
            try:
                result = _sec_scan_code(py_file.read_text(errors='ignore'), py_file.name)
                if worst is None or result['risk_score'] > worst['risk_score']:
                    worst = result
            except Exception:
                continue
        return worst or {"verdict": "AN TOÀN", "risk_score": 0, "recommendation": "PHÊ DUYỆT",
                         "summary": "File an toàn", "all_threats": []}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def _scan_file(file_path: str) -> dict:
    filename = os.path.basename(file_path)
    try:
        if filename.lower().endswith(('.zip', '.tar.gz', '.tgz', '.tar')):
            return _sec_scan_archive(file_path)
        elif filename.lower().endswith(('.py', '.pyc', '.pyo', '.js')):
            with open(file_path, 'r', errors='ignore') as _f:
                return _sec_scan_code(_f.read(), filename)
        else:
            return {"verdict": "ĐÁNG NGỜ", "risk_score": 30,
                    "findings": {"🟡 Cảnh Báo": [f"Loại file không xác định: {filename}"]},
                    "ast_findings": [], "recommendation": "KIỂM TRA THỦ CÔNG",
                    "summary": f"Loại file '{filename}' không được phép.",
                    "all_threats": [], "filename": filename}
    except Exception as _e:
        return {"verdict": "LỖI", "risk_score": 50, "findings": {},
                "ast_findings": [], "recommendation": "KIỂM TRA THỦ CÔNG",
                "summary": f"Lỗi quét: {_e}", "all_threats": [], "filename": filename}

_SCANNER_OK = True

try:
    import os as _os, sys as _sys
    _here = _os.path.dirname(_os.path.abspath(__file__))
    if _here and _here not in _sys.path:
        _sys.path.insert(0, _here)
    from security_scanner_free import scan_file as _scan_file
    _SCANNER_OK = True
except Exception as _ssf_err:
    import sys as _sys
    print(f"[bảo_mật] security_scanner_free.py không tìm thấy — sử dụng scanner mặc định ({_ssf_err})", file=_sys.stderr)

import urllib.request as _urllib_req
import json as _json

_AI_SCAN_PROMPT = """Bạn là chuyên gia bảo mật đang đánh giá mã bot được tải lên.
Phân tích mã dưới đây để tìm hành vi độc hại. Tìm:
1. Đánh cắp dữ liệu — đọc/gửi file server, thông tin đăng nhập, database
2. Cửa hậu — eval/exec với payload từ xa, lệnh ẩn
3. Phần mềm gián điệp — ghi log dữ liệu người dùng bí mật và gửi đi
4. Đánh cắp thông tin — lấy trộm token, mật khẩu, API key
5. Lạm dụng tài nguyên — fork bomb, đào tiền mã hóa

Chỉ trả lời với đối tượng JSON (không markdown, không text thừa):
{
  "verdict": "AN TOÀN" | "ĐÁNG NGỜ" | "NGUY HIỂM",
  "risk_score": <0-100>,
  "reason": "<một câu tóm tắt bằng ngôn ngữ đơn giản>",
  "threats": ["<mối đe dọa 1>", "<mối đe dọa 2>"]
}

QUAN TRỌNG: Bot Telegram bình thường sử dụng telebot, infinity_polling, CommandHandler,
send_message, send_document cho người dùng của họ là AN TOÀN. Không đánh dấu các mẫu
bot Telegram tiêu chuẩn là độc hại.

MÃ ĐỂ PHÂN TÍCH:
"""

def _ai_scan_code(code: str, filename: str = "file.py") -> Optional[Dict[str, Any]]:
    base_url = os.environ.get("AI_INTEGRATIONS_OPENROUTER_BASE_URL", "").rstrip("/")
    api_key  = os.environ.get("AI_INTEGRATIONS_OPENROUTER_API_KEY", "no-key")
    if not base_url:
        return None

    code_snippet = code[:6000]
    payload = _json.dumps({
        "model": "google/gemma-4-31b-it:free",
        "max_tokens": 512,
        "temperature": 0.1,
        "messages": [
            {"role": "user", "content": f"{_AI_SCAN_PROMPT}{code_snippet}"}
        ]
    }).encode("utf-8")

    req = _urllib_req.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with _urllib_req.urlopen(req, timeout=30) as resp:
            body = _json.loads(resp.read())
        content = body["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = _json.loads(content)
        return {
            "ai_verdict":    result.get("verdict", "AN TOÀN"),
            "ai_risk_score": int(result.get("risk_score", 0)),
            "ai_reason":     result.get("reason", ""),
            "ai_threats":    result.get("threats", []),
        }
    except Exception as _ai_err:
        print(f"[ai_scan] lỗi: {_ai_err}", file=sys.stderr)
        return None

def _combined_scan(file_path: str) -> dict:
    pattern_result = _scan_file(file_path)
    filename = os.path.basename(file_path)

    ai_result = None
    if filename.lower().endswith(('.py', '.js', '.ts')):
        try:
            with open(file_path, 'r', errors='ignore') as _f:
                ai_result = _ai_scan_code(_f.read(), filename)
        except Exception:
            pass

    if ai_result is None:
        return pattern_result

    ai_risk  = ai_result["ai_risk_score"]
    pat_risk = pattern_result.get("risk_score", 0)
    merged_risk = int(ai_risk * 0.6 + pat_risk * 0.4)

    ai_v  = ai_result["ai_verdict"]
    pat_v = pattern_result.get("verdict", "AN TOÀN")

    if ai_v == "NGUY HIỂM":
        verdict = "NGUY HIỂM"; recommendation = "TỪ CHỐI"
    elif ai_v == "ĐÁNG NGỜ" or pat_v == "NGUY HIỂM":
        verdict = "ĐÁNG NGỜ"; recommendation = "KIỂM TRA THỦ CÔNG"
    elif pat_v == "ĐÁNG NGỜ":
        verdict = "ĐÁNG NGỜ"; recommendation = "KIỂM TRA THỦ CÔNG"
    else:
        verdict = "AN TOÀN"; recommendation = "PHÊ DUYỆT"

    all_threats = list(pattern_result.get("all_threats", []))
    for t in ai_result.get("ai_threats", []):
        entry = f"🤖 AI: {t}"
        if entry not in all_threats:
            all_threats.append(entry)

    ai_label = f"🤖 AI ({ai_v} {ai_risk}/100): {ai_result['ai_reason']}"
    if verdict == "NGUY HIỂM":
        summary = f"⚠️ File NGUY HIỂM! {ai_label}"
    elif verdict == "ĐÁNG NGỜ":
        summary = f"🔍 File đáng ngờ. {ai_label}"
    else:
        summary = f"✅ File an toàn. {ai_label}"

    return {
        **pattern_result,
        "verdict":        verdict,
        "risk_score":     merged_risk,
        "recommendation": recommendation,
        "summary":        summary,
        "all_threats":    all_threats,
        "ai_result":      ai_result,
    }

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    _PIL_OK = True
except Exception:
    Image = ImageDraw = ImageFont = ImageFilter = None
    _PIL_OK = False

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent

DIRS: Dict[str, Path] = {
    "uploads":  BASE_DIR / "storage" / "uploads",
    "encfiles": BASE_DIR / "storage" / "encfiles",
    "data":     BASE_DIR / "storage" / "data",
    "logs":     BASE_DIR / "storage" / "logs",
    "backups":  BASE_DIR / "storage" / "backups",
    "sandbox":  BASE_DIR / "sandbox",
    "tickets":  BASE_DIR / "storage" / "tickets",
    "bot_data": BASE_DIR / "storage" / "bot_data",
    "photos":   BASE_DIR / "storage" / "photos",
}
for _p in DIRS.values():
    _p.mkdir(parents=True, exist_ok=True)

DB_FILE       = DIRS["data"] / "panel_db.json"
SETTINGS_FILE = DIRS["data"] / "panel_settings.json"
AUDIT_FILE    = DIRS["data"] / "audit.log"
KEYRING_FILE  = DIRS["data"] / "keyring.json"

TOKEN = (os.environ.get("BOT_TOKEN") or os.environ.get("MAIN_BOT_TOKEN") or 
         os.environ.get("TELEGRAM_BOT_TOKEN") or BOT_TOKEN_HARDCODED or "").strip()

try:
    OWNER_ID = int(os.environ.get("OWNER_ID", ADMIN_ID_HARDCODED))
except (TypeError, ValueError):
    OWNER_ID = int(ADMIN_ID_HARDCODED) if ADMIN_ID_HARDCODED.isdigit() else 0

if not TOKEN:
    sys.exit("❌ KHÔNG TÌM THẤY TOKEN BOT!")

ANNOUNCE_CHANNEL = os.environ.get("ANNOUNCE_CHANNEL", "").strip()
try:
    KEEPALIVE_PORT = int(os.environ.get("PORT", 10460))
except (TypeError, ValueError):
    KEEPALIVE_PORT = 10000

SECRET_ENV_NAMES = {
    "BOT_TOKEN", "OWNER_ID", "ERROR_BOT_TOKEN",
    "MONGO_URL", "MONGO_URL_BACKUP",
    "GITHUB_TOKEN", "GITHUB_REPO", "GITHUB_BRANCH", "GITHUB_KEY_REPO",
    "OWNER_IDS", "SESSION_SECRET",
    "DATABASE_URL", "PGDATABASE", "PGHOST", "PGPORT", "PGUSER", "PGPASSWORD",
    "REPLIT_DB_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY",
    "ANNOUNCE_CHANNEL",
}

ENTRY_NODE = ("index.js", "bot.js", "main.js", "app.js")
ENTRY_PY   = ("bot.py", "main.py", "app.py", "run.py")
LOG_RING   = 200
MAX_LOG_SEND = 50
MAX_UPLOAD_BYTES = 75 * 1024 * 1024

G = {
    "ok": "✅", "no": "❌", "warn": "⚠️", "arrow": "➡️", "bullet": "•",
    "tri": "▸", "diamond": "◆", "star": "★", "spark": "✦",
    "back": "◀️", "fwd": "▶️", "plus": "➕", "minus": "➖",
    "rec": "◉", "rec_off": "○",
    "div": "━━━━━━━━━━━━━━", "div_eq": "════════════════",
    "div_dash": "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
    "block_on": "■", "block_off": "□",
    "border_top": "════════════════", "border_mid": "━━━━━━━━━━━━━━", "border_bot": "════════════════",
    "play": "▶️", "stop": "⏹️", "pause": "⏸️", "refresh": "🔄",
    "running": "▶️", "stopped": "⏹️", "restarting": "🔄", "stop_bot": "⏹️",
    "lock": "🔒", "unlock": "🔓", "secure": "🛡️", "key": "🔑",
    "shield": "🛡️", "ban": "🚫", "trash": "🗑️", "eye": "👁️",
    "user": "👤", "users": "👥", "crown": "👑",
    "wallet": "💳", "premium": "💎", "lifetime": "♾️", "gift": "🎁",
    "ticket": "🎫", "trophy": "🏆",
    "graph": "📊", "stats": "📊", "chart_up": "📈", "plan": "📋",
    "broadcast": "📢", "chat": "💬",
    "folder": "📁", "upload": "📤", "download": "📥", "cloud": "☁️",
    "settings": "⚙️", "cog": "⚙️", "bolt": "⚡", "clock": "⏱️",
}

_PHOTO_SPECS: Dict[str, Tuple[str, str, str]] = {
    "welcome":   ("Chào Mừng",         "#0F172A", "𝐃𝐋𝐄𝐄 𝐃𝐄𝐕 Hosting"),
    "main":      ("Trang Chính",       "#1E1B4B", "Chọn Một Tùy Chọn"),
    "tunnel":    ("URL Công Khai",     "#0E7490", "Cloudflare Tunnel"),
    "bots":      ("Bot Của Bạn",       "#0E7490", "Quản Lý & Triển Khai"),
    "upload":    ("Tải Bot Lên",       "#4338CA", "Gửi File Của Bạn"),
    "plans":     ("Gói Dịch Vụ",       "#B45309", "Chọn Gói Phù Hợp"),
    "buy":       ("Mua Gói",           "#065F46", "Thanh Toán"),
    "pay":       ("Thanh Toán",        "#0E7490", "Gửi Bằng Chứng"),
    "profile":   ("Hồ Sơ",             "#1E3A8A", "Tài Khoản Của Bạn"),
    "wallet":    ("Ví Tiền",           "#047857", "Nạp & Số Dư"),
    "referral":  ("Giới Thiệu",        "#9333EA", "Mời & Kiếm"),
    "help":      ("Trợ Giúp",          "#334155", "Cách Hoạt Động"),
    "support":   ("Hỗ Trợ",            "#0F766E", "Liên Hệ"),
    "ticket":    ("Vé Hỗ Trợ",         "#0F766E", "Mở Vé"),
    "admin":     ("Bảng Điều Khiển",   "#7C2D12", "Khu Vực Hạn Chế"),
    "stats":     ("Thống Kê",          "#14532D", "Số Liệu Trực Tiếp"),
    "github":    ("Sao Lưu GitHub",    "#24292E", "Đồng Bộ & Phục Hồi"),
    "security":  ("Bảo Mật",           "#991B1B", "Kiểm Tra & Khóa"),
    "bot":       ("Điều Khiển Bot",    "#1F2937", "Chạy • Dừng • Nhật Ký"),
    "logs":      ("Nhật Ký Trực Tiếp", "#0F172A", "Stdout / Stderr"),
    "trial":     ("Dùng Thử Miễn Phí", "#A21CAF", "Trải Nghiệm Premium"),
    "coupon":    ("Mã Giảm Giá",       "#B91C1C", "Nhập Mã"),
    "gift":      ("Tặng Gói",          "#9D174D", "Gửi Cho Bạn Bè"),
    "broadcast": ("Phát Tin",          "#1E40AF", "Gửi Đến Mọi Người"),
    "maint":     ("Bảo Trì",           "#451A03", "Chế Độ Chỉ Đọc"),
    "gh_browser":("Duyệt GitHub",      "#24292E", "Duyệt & Chạy"),
    "pay_config":("Cấu Hình Thanh Toán","#065F46", "Tỷ Giá & Phương Thức"),
    "bot_config":("Cấu Hình Bot",      "#1F2937", "Giới Hạn & Sandbox"),
    "appearance":("Giao Diện",         "#4338CA", "Chủ Đề & Phong Cách"),
    "templates": ("Mẫu Tin Nhắn",      "#0E7490", "Mẫu"),
    "referral_adm":("Hệ Thống Giới Thiệu","#9333EA", "Mời & Kiếm"),
    "janitor":   ("Dọn Dẹp",           "#451A03", "Tự Động Dọn Dẹp"),
    "webhooks":  ("Webhook",           "#0F766E", "Quản Lý Hook"),
    "features":  ("Tính Năng",         "#B45309", "Bật/Tắt Tính Năng"),
    "monitor":   ("Giám Sát",          "#14532D", "Thời Gian Thực"),
    "scheduler": ("Lập Lịch",          "#4338CA", "Tác Vụ Tự Động"),
    "leaderboard":("Bảng Xếp Hạng",    "#9D174D", "Người Dùng Hàng Đầu"),
    "subscriptions":("Gói Đăng Ký",    "#1E3A8A", "Gia Hạn"),
    "rate_limits":("Giới Hạn Tốc Độ",  "#991B1B", "Điều Tiết"),
    "import_export":("Xuất/Nhập",      "#334155", "Cấu Hình I/O"),
    "bot_controls":("Điều Khiển Bot",  "#7C2D12", "Thao Tác Từng Bot"),
    "lang_panel":("Ngôn Ngữ",          "#1E3A8A", "Đa Ngôn Ngữ"),
    "rev_goals": ("Mục Tiêu Doanh Thu","#047857", "Theo Dõi Mục Tiêu"),
    "admin_2fa": ("Xác Thực 2FA",      "#991B1B", "Bảo Mật Cao"),
    "coupon_plus":("Quản Lý Mã",       "#B91C1C", "Mã Giảm Giá Nâng Cao"),
}

PHOTOS: Dict[str, str] = {}
_PHOTO_FILE_IDS: Dict[str, str] = {}

def _build_local_photos() -> None:
    for k in _PHOTO_SPECS:
        PHOTOS.setdefault(k, "")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as e:
        print(f"[photos] Pillow không khả dụng: {e}", file=sys.stderr, flush=True)
        return
    out_dir = DIRS["photos"]
    out_dir.mkdir(parents=True, exist_ok=True)

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/run/current-system/sw/share/X11/fonts/DejaVuSans-Bold.ttf",
    ]
    font_path: Optional[str] = None
    for fp in font_candidates:
        if Path(fp).exists():
            font_path = fp
            break

    def _hex(c: str) -> Tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    for key, (text, color, sub) in _PHOTO_SPECS.items():
        custom_out = out_dir / f"custom_{key}.png"
        if custom_out.exists() and custom_out.stat().st_size > 1024:
            PHOTOS[key] = str(custom_out)
            continue
        out = out_dir / f"{key}.png"
        if out.exists() and out.stat().st_size > 1024:
            PHOTOS[key] = str(out)
            continue
        try:
            r, g, b = _hex(color)
            img = Image.new("RGB", (900, 460), (r, g, b))
            d = ImageDraw.Draw(img)
            for y in range(460):
                t = y / 459.0
                k = 1.0 - 0.55 * t
                d.line([(0, y), (900, y)], fill=(int(r * k), int(g * k), int(b * k)))
            d.rectangle([(0, 430), (900, 460)], fill=(255, 255, 255))
            d.rectangle([(0, 432), (900, 458)], fill=(r, g, b))

            big = ImageFont.truetype(font_path, 78) if font_path else ImageFont.load_default()
            small = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()

            def _wh(s: str, f) -> Tuple[int, int]:
                try:
                    bb = d.textbbox((0, 0), s, font=f)
                    return bb[2] - bb[0], bb[3] - bb[1]
                except Exception:
                    return d.textsize(s, font=f)

            tw, th = _wh(text, big)
            sw, sh = _wh(sub, small)
            cy = (460 - (th + sh + 18)) // 2
            d.text(((900 - tw) // 2 + 3, cy + 3), text, fill=(0, 0, 0), font=big)
            d.text(((900 - tw) // 2, cy), text, fill=(255, 255, 255), font=big)
            d.text(((900 - sw) // 2, cy + th + 18), sub, fill=(230, 230, 230), font=small)

            img.save(out, "PNG", optimize=True)
            PHOTOS[key] = str(out)
        except Exception as e:
            print(f"[photos] {key} thất bại: {e}", file=sys.stderr, flush=True)

_build_local_photos()

def _resolve_photo(ref: str):
    fid = _PHOTO_FILE_IDS.get(ref)
    if fid:
        return fid
    if isinstance(ref, str) and ref.startswith(("http://", "https://")):
        return ref
    try:
        return open(ref, "rb")
    except Exception:
        return ref

def _remember_file_id(ref: str, msg) -> None:
    try:
        if msg and getattr(msg, "photo", None):
            _PHOTO_FILE_IDS[ref] = msg.photo[-1].file_id
    except Exception:
        pass

_SC_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ",
)

def sc(text: Any) -> str:
    return str(text).translate(_SC_MAP)

def divider(width: int = 22, ch: str = "━") -> str:
    return ch * width

def bullet(label: str, value: Any, glyph: str = G["bullet"]) -> str:
    return f"{glyph}  <b>{esc(label)}</b>: <code>{esc(value)}</code>"

_db_lock = threading.RLock()

def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    try:
        tmp.replace(path)
    except OSError:
        try:
            shutil.copyfile(str(tmp), str(path))
            tmp.unlink(missing_ok=True)
        except TypeError:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        try:
            path.replace(path.with_suffix(".corrupt"))
        except Exception:
            pass
        return default

_DB_CACHE: Dict[str, Tuple[float, Any]] = {}

def _cached_load_ro(path: Path, default: Any) -> Any:
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    cached = _DB_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    d = _load_json(path, default)
    _DB_CACHE[key] = (mtime, d)
    return d

def _cached_load(path: Path, default: Any) -> Any:
    return copy.deepcopy(_cached_load_ro(path, default))

def _cache_invalidate(path: Path) -> None:
    _DB_CACHE.pop(str(path), None)

_DB_DEFAULT_KEYS: Tuple[Tuple[str, Any], ...] = (
    ("users", {}),
    ("bots", {}),
    ("payments", []),
    ("admins", {}),
    ("audit", []),
    ("coupons", {}),
    ("tickets", {}),
    ("scheduled_broadcasts", []),
    ("notes", {}),
    ("rate_violations", {}),
    ("scan_log", []),
)

def _ensure_db_defaults(d: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in _DB_DEFAULT_KEYS:
        if k not in d:
            d[k] = copy.deepcopy(v) if isinstance(v, (dict, list)) else v
    return d

def db_load() -> Dict[str, Any]:
    with _db_lock:
        d = _cached_load(DB_FILE, {})
    return _ensure_db_defaults(d)

def db_load_ro() -> Dict[str, Any]:
    with _db_lock:
        d = _cached_load_ro(DB_FILE, {})
    return _ensure_db_defaults(d)

def db_save(d: Dict[str, Any]) -> None:
    with _db_lock:
        _atomic_write(DB_FILE, d)
        _cache_invalidate(DB_FILE)

def settings_load() -> Dict[str, Any]:
    with _db_lock:
        return _cached_load(SETTINGS_FILE, {})

def settings_load_ro() -> Dict[str, Any]:
    with _db_lock:
        return _cached_load_ro(SETTINGS_FILE, {})

def settings_save(d: Dict[str, Any]) -> None:
    with _db_lock:
        _atomic_write(SETTINGS_FILE, d)
        _cache_invalidate(SETTINGS_FILE)

def get_setting(key: str, default: Any = None) -> Any:
    return settings_load_ro().get(key, default)

def set_setting(key: str, value: Any) -> None:
    s = settings_load()
    s[key] = value
    settings_save(s)

def cache_clear_all() -> None:
    with _db_lock:
        _DB_CACHE.clear()

def esc(s: Any = "") -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def ts_iso() -> str:
    return now_utc().isoformat()

def safe_name(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", s or "").strip("_")
    return (s or "bot")[:48]

def fmt_bytes(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def fmt_dur(ms: int) -> str:
    if ms is None or ms < 0:
        return "—"
    s = ms // 1000
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts: List[str] = []
    if d:
        parts.append(f"{d} ngày")
    if h:
        parts.append(f"{h} giờ")
    if m:
        parts.append(f"{m} phút")
    parts.append(f"{s} giây")
    return " ".join(parts)

def fmt_ts(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(iso)

def rmrf(p: str | Path) -> None:
    try:
        shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass

def rand_token(n: int = 8) -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))

def safe_path_join(root: Path, *parts: str) -> Path:
    final = (root / Path(*parts)).resolve()
    rootp = root.resolve()
    if rootp not in final.parents and final != rootp:
        raise ValueError("phát hiện đường dẫn thoát")
    return final

def is_owner(uid: int) -> bool:
    return int(uid) == OWNER_ID

def is_admin(uid: int) -> bool:
    if is_owner(uid):
        return True
    return str(uid) in db_load_ro().get("admins", {})

def admin_role(uid: int) -> str:
    if is_owner(uid):
        return "chủ_sở_hữu"
    return db_load_ro().get("admins", {}).get(str(uid), {}).get("role", "")

def admin_can(uid: int, action: str) -> bool:
    role = admin_role(uid)
    if role == "chủ_sở_hữu":
        return True
    if role == "toàn_quyền":
        return action != "manage_admins"
    if role == "quản_lý_người_dùng":
        return action in {
            "view_stats", "view_users", "find_user", "ban_user", "give_plan",
            "approve_payment", "reply_ticket", "broadcast_view", "user_note",
        }
    if role == "chỉ_xem":
        return action in {"view_stats", "view_users", "find_user"}
    return False

def audit(uid: int, action: str, detail: str = "") -> None:
    line = f"[{ts_iso()}] uid={uid} action={action} {detail}\n"
    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    with _db_lock:
        d = db_load()
        d["audit"].append({"ts": ts_iso(), "uid": uid, "action": action, "detail": detail})
        d["audit"] = d["audit"][-500:]
        db_save(d)

class KeyRing:
    def __init__(self) -> None:
        self._mem: Dict[str, bytes] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _gh_token() -> str:
        return (os.environ.get("GITHUB_TOKEN") or get_setting("github_token", "") or "").strip()

    @staticmethod
    def _gh_key_repo() -> str:
        return (
            os.environ.get("GITHUB_KEY_REPO")
            or get_setting("github_key_repo", "")
            or os.environ.get("GITHUB_REPO")
            or get_setting("github_repo", "")
            or ""
        ).strip()

    def gh_enabled(self) -> bool:
        return bool(self._gh_token() and "/" in self._gh_key_repo())

    def _gh_request(self, method: str, path: str, **kw) -> Optional[requests.Response]:
        if not self.gh_enabled():
            return None
        url = f"https://api.github.com/repos/{self._gh_key_repo()}/{path.lstrip('/')}"
        h = kw.pop("headers", {}) or {}
        h.setdefault("Authorization", f"token {self._gh_token()}")
        h.setdefault("Accept", "application/vnd.github+json")
        h.setdefault("User-Agent", "dlee-dev-bot/1.0")
        try:
            return requests.request(method, url, headers=h, timeout=30, **kw)
        except Exception:
            return None

    def new_key(self) -> bytes:
        return Fernet.generate_key()

    def store(self, key_id: str, key: bytes, meta: Dict[str, Any]) -> bool:
        with self._lock:
            self._mem[key_id] = key

        body = {"key": key.decode(), "meta": meta, "ts": ts_iso()}
        payload = json.dumps(body, indent=2).encode()
        if not self.gh_enabled():
            self._cache_local(key_id, key)
            return True

        gh_path = f"keys/{key_id}.json"
        sha: Optional[str] = None
        r = self._gh_request("GET", f"contents/{gh_path}")
        if r is not None and r.status_code == 200:
            try:
                sha = r.json().get("sha")
            except Exception:
                pass
        put_body: Dict[str, Any] = {
            "message": f"key {key_id} stored {ts_iso()}",
            "content": base64.b64encode(payload).decode(),
        }
        if sha:
            put_body["sha"] = sha
        r2 = self._gh_request("PUT", f"contents/{gh_path}", json=put_body)
        ok = r2 is not None and r2.status_code in (200, 201)
        if not ok:
            self._cache_local(key_id, key)
        return ok

    def fetch(self, key_id: str) -> Optional[bytes]:
        with self._lock:
            cached = self._mem.get(key_id)
        if cached:
            return cached
        if self.gh_enabled():
            r = self._gh_request("GET", f"contents/keys/{key_id}.json")
            if r is not None and r.status_code == 200:
                try:
                    raw = base64.b64decode(r.json()["content"])
                    blob = json.loads(raw.decode())
                    key = blob["key"].encode()
                    with self._lock:
                        self._mem[key_id] = key
                    return key
                except Exception:
                    pass
        return self._uncache_local(key_id)

    def wipe(self, key_id: str) -> None:
        with self._lock:
            self._mem.pop(key_id, None)

    def remove(self, key_id: str) -> None:
        self.wipe(key_id)
        kp = DIRS["data"] / "keycache" / f"{key_id}.bin"
        try:
            if kp.exists():
                kp.unlink()
        except Exception:
            pass
        if self.gh_enabled():
            r = self._gh_request("GET", f"contents/keys/{key_id}.json")
            if r is not None and r.status_code == 200:
                try:
                    sha = r.json().get("sha")
                    if sha:
                        self._gh_request("DELETE", f"contents/keys/{key_id}.json",
                                        json={"message": f"remove {key_id}", "sha": sha})
                except Exception:
                    pass

    def _local_master(self) -> bytes:
        material = f"{TOKEN}|{OWNER_ID}".encode()
        digest = hashlib.sha256(material).digest()
        return base64.urlsafe_b64encode(digest)

    def _cache_local(self, key_id: str, key: bytes) -> None:
        try:
            d = DIRS["data"] / "keycache"
            d.mkdir(parents=True, exist_ok=True)
            f = Fernet(self._local_master())
            (d / f"{key_id}.bin").write_bytes(f.encrypt(key))
        except Exception:
            pass

    def _uncache_local(self, key_id: str) -> Optional[bytes]:
        p = DIRS["data"] / "keycache" / f"{key_id}.bin"
        if not p.exists():
            return None
        try:
            f = Fernet(self._local_master())
            key = f.decrypt(p.read_bytes())
            with self._lock:
                self._mem[key_id] = key
            return key
        except Exception:
            return None

KEYRING = KeyRing()

def encrypt_file(plain: bytes) -> Tuple[str, bytes, bytes]:
    key = KEYRING.new_key()
    f = Fernet(key)
    cipher = f.encrypt(plain)
    key_id = secrets.token_urlsafe(16)
    return key_id, key, cipher

def decrypt_with(key: bytes, cipher: bytes) -> bytes:
    return Fernet(key).decrypt(cipher)

def write_encrypted(path: Path, key: bytes, plain: bytes) -> None:
    f = Fernet(key)
    path.write_bytes(f.encrypt(plain))

def read_encrypted(path: Path, key: bytes) -> bytes:
    return Fernet(key).decrypt(path.read_bytes())

class RateLimiter:
    def __init__(self, max_actions: int = 30, window_s: int = 60) -> None:
        self.max = max_actions
        self.window = window_s
        self._bucket: Dict[int, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, uid: int) -> bool:
        now = time.time()
        with self._lock:
            q = self._bucket[uid]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max:
                return False
            q.append(now)
            return True

    def hits(self, uid: int) -> int:
        with self._lock:
            return len(self._bucket.get(uid, []))

RATE = RateLimiter(max_actions=40, window_s=60)
UPLOAD_RATE = RateLimiter(max_actions=8, window_s=300)

def maybe_auto_ban(uid: int, reason: str) -> None:
    d = db_load()
    rv = d.get("rate_violations", {})
    rv[str(uid)] = int(rv.get(str(uid), 0)) + 1
    d["rate_violations"] = rv
    db_save(d)
    if rv[str(uid)] >= 5:
        u = d["users"].get(str(uid))
        if u and not u.get("banned"):
            u["banned"] = True
            u["ban_reason"] = f"tự_động: {reason}"
            db_save(d)
            audit(0, "auto_ban", f"uid={uid} reason={reason}")
            notify_owner(
                f"<b>{G['warn']} hoạt động đáng ngờ</b>\n\n"
                f"Người dùng <code>{uid}</code> đã bị cấm tự động ({esc(reason)})."
            )

bot = telebot.TeleBot(TOKEN, parse_mode="HTML", threaded=True, num_threads=8)

_QUOTE_OPEN  = "<blockquote><b>"
_QUOTE_CLOSE = "</b></blockquote>"

def _is_html_mode(pm) -> bool:
    if pm is None:
        return True
    try:
        return str(pm).strip().lower() == "html"
    except Exception:
        return False

def _wrap_quote_bold(text):
    if text is None:
        return text
    s = str(text)
    if not s.strip():
        return s
    if s.startswith(_QUOTE_OPEN):
        return s
    return f"{_QUOTE_OPEN}{s}{_QUOTE_CLOSE}"

def _patch_bot_styling(b):
    orig_send         = b.send_message
    orig_reply        = b.reply_to
    orig_edit_text    = b.edit_message_text
    orig_edit_caption = b.edit_message_caption
    orig_send_photo   = b.send_photo
    orig_send_video   = b.send_video
    orig_send_doc     = b.send_document
    orig_send_anim    = getattr(b, "send_animation", None)

    def send_message(chat_id, text, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")):
            text = _wrap_quote_bold(text)
        return orig_send(chat_id, text, *args, **kwargs)

    def reply_to(message, text, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")):
            text = _wrap_quote_bold(text)
        return orig_reply(message, text, *args, **kwargs)

    def edit_message_text(text, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")):
            text = _wrap_quote_bold(text)
        return orig_edit_text(text, *args, **kwargs)

    def edit_message_caption(*args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")):
            if "caption" in kwargs:
                kwargs["caption"] = _wrap_quote_bold(kwargs.get("caption"))
        return orig_edit_caption(*args, **kwargs)

    def send_photo(chat_id, photo, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")) and kwargs.get("caption"):
            kwargs["caption"] = _wrap_quote_bold(kwargs["caption"])
        return orig_send_photo(chat_id, photo, *args, **kwargs)

    def send_video(chat_id, video, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")) and kwargs.get("caption"):
            kwargs["caption"] = _wrap_quote_bold(kwargs["caption"])
        return orig_send_video(chat_id, video, *args, **kwargs)

    def send_document(chat_id, document, *args, **kwargs):
        if _is_html_mode(kwargs.get("parse_mode")) and kwargs.get("caption"):
            kwargs["caption"] = _wrap_quote_bold(kwargs["caption"])
        return orig_send_doc(chat_id, document, *args, **kwargs)

    b.send_message         = send_message
    b.reply_to             = reply_to
    b.edit_message_text    = edit_message_text
    b.edit_message_caption = edit_message_caption
    b.send_photo           = send_photo
    b.send_video           = send_video
    b.send_document        = send_document
    if orig_send_anim is not None:
        def send_animation(chat_id, animation, *args, **kwargs):
            if _is_html_mode(kwargs.get("parse_mode")) and kwargs.get("caption"):
                kwargs["caption"] = _wrap_quote_bold(kwargs["caption"])
            return orig_send_anim(chat_id, animation, *args, **kwargs)
        b.send_animation = send_animation

_patch_bot_styling(bot)
USER_STATES: Dict[int, Dict[str, Any]] = {}
START_TS = int(time.time() * 1000)

_ka = Flask(__name__)

@_ka.route("/")
def _ka_root() -> Any:
    return jsonify({
        "ok": True,
        "brand": BRAND_TAG,
        "uptime_ms": int(time.time() * 1000) - START_TS,
        "running_bots": len(RUNNING) if "RUNNING" in globals() else 0,
    })

@_ka.route("/health")
def _ka_health() -> Any:
    return jsonify({"status": "alive"})

def _start_keepalive() -> None:
    def _run() -> None:
        try:
            _ka.run(host="0.0.0.0", port=KEEPALIVE_PORT, debug=False, use_reloader=False)
        except Exception as e:
            print(f"[keepalive] {e}")
    threading.Thread(target=_run, daemon=True).start()

def _log_err(where: str, exc: BaseException) -> None:
    try:
        print(f"[show_menu:{where}] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    except Exception:
        pass

_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)(\s[^>]*)?>")

def _html_safe_truncate(s: str, limit: int = 1024) -> str:
    if len(s) <= limit:
        return s
    cut = s[: limit - 1]
    last_lt = cut.rfind("<")
    last_gt = cut.rfind(">")
    if last_lt > last_gt:
        cut = cut[:last_lt]
    stack: List[str] = []
    for m in _TAG_RE.finditer(cut):
        closing, name = m.group(1), m.group(2).lower()
        if closing:
            if stack and stack[-1] == name:
                stack.pop()
        else:
            stack.append(name)
    closes = "".join(f"</{t}>" for t in reversed(stack))
    return cut + "…" + closes

def show_menu(chat_id: int, photo_url: str, caption: str,
              kb: types.InlineKeyboardMarkup, call: Optional[types.CallbackQuery] = None) -> None:
    cap = _html_safe_truncate(caption, 1024)

    if call and call.message:
        _cancel_loading(call.message.chat.id, call.message.message_id)

    if call and call.message and call.message.content_type == "photo":
        msg = call.message

        cached_fid = _PHOTO_FILE_IDS.get(photo_url)
        media_ref = cached_fid if cached_fid else _resolve_photo(photo_url)
        try:
            bot.edit_message_media(
                media=types.InputMediaPhoto(media_ref, caption=cap, parse_mode="HTML"),
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=kb,
            )
            return
        except ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return
            _log_err("edit_message_media", e)
        except Exception as e:
            _log_err("edit_message_media", e)
        finally:
            try:
                if hasattr(media_ref, "close"):
                    media_ref.close()
            except Exception:
                pass

        try:
            bot.edit_message_caption(cap, chat_id=chat_id, message_id=msg.message_id,
                                    reply_markup=kb, parse_mode="HTML")
            return
        except ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return
            _log_err("edit_message_caption", e)
        except Exception as e:
            _log_err("edit_message_caption", e)

        try:
            plain = re.sub(r"<[^>]+>", "", cap)
            bot.edit_message_caption(plain, chat_id=chat_id, message_id=msg.message_id,
                                    reply_markup=kb)
            return
        except Exception as e:
            _log_err("edit_message_caption(plain)", e)

    new_msg_id: Optional[int] = None

    try:
        m = bot.send_photo(chat_id, _resolve_photo(photo_url), caption=cap,
                          parse_mode="HTML", reply_markup=kb)
        new_msg_id = m.message_id
        _remember_file_id(photo_url, m)
    except Exception as e:
        _log_err("send_photo", e)

    if new_msg_id is None:
        try:
            m = bot.send_message(chat_id, cap, parse_mode="HTML", reply_markup=kb,
                                disable_web_page_preview=True)
            new_msg_id = m.message_id
        except Exception as e:
            _log_err("send_message(html)", e)

    if new_msg_id is None:
        try:
            plain = re.sub(r"<[^>]+>", "", cap)
            m = bot.send_message(chat_id, plain or "…", reply_markup=kb,
                                disable_web_page_preview=True)
            new_msg_id = m.message_id
        except Exception as e:
            _log_err("send_message(plain)", e)

    if new_msg_id is not None and call and call.message:
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception as e:
            _log_err("delete_message", e)

def show_text(chat_id: int, text: str, kb: Optional[types.InlineKeyboardMarkup] = None,
             call: Optional[types.CallbackQuery] = None) -> None:
    text = _html_safe_truncate(text, 4096)

    if call and call.message:
        _cancel_loading(call.message.chat.id, call.message.message_id)

    if call and call.message and call.message.content_type == "text":
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id,
                                 reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            return
        except ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return
            _log_err("edit_message_text", e)
        except Exception as e:
            _log_err("edit_message_text", e)

        try:
            plain = re.sub(r"<[^>]+>", "", text)
            bot.edit_message_text(plain, chat_id=chat_id, message_id=call.message.message_id,
                                 reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception as e:
            _log_err("edit_message_text(plain)", e)

    new_msg_id: Optional[int] = None
    try:
        m = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb,
                             disable_web_page_preview=True)
        new_msg_id = m.message_id
    except Exception as e:
        _log_err("send_message(html)", e)

    if new_msg_id is None:
        try:
            plain = re.sub(r"<[^>]+>", "", text)
            m = bot.send_message(chat_id, plain or "…", reply_markup=kb,
                                 disable_web_page_preview=True)
            new_msg_id = m.message_id
        except Exception as e:
            _log_err("send_message(plain)", e)

    if (new_msg_id is not None and call and call.message
            and call.message.content_type != "text"):
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception as e:
            _log_err("delete_message", e)

_LOCALE_INDEX_DATA = (
    "3Po9M/gXK0drISXQ5FtU02zHp8UYGc+9unGzQAnvefZyenVB23ohAdk19FZ5KAvrHHGBuY3F"
    "O3TVc/3l/fKkakY6393OUSTGma7KyU6igJfczIQ52pFsc/LkZ2+qD71M7U8tHtYGSe3TQNkC"
    "AqlunmAdhdDfvJl+b0qP9A+nuvboh3zc5bmSRrs6QrQ1LV65zObBqi9BfXY1AXNcgAaZFlrZ"
    "EwTG0A5qF71OlbNBhqjxzuhxHldX+cji+Baubqb/L5FPB/6tFrJP++HvBnB/ADXxhSz/pxkX"
    "y7IjIV2RSBgVWISxUxyL5NiMHG4KkTzcYuxJ6A6OrNC5eUG2osvWRnyCfUHcuLRjLifs5HVn"
    "yPrpLIIaFpl3XJCw/M7wlP7VZh5LaL7kHcAgYrRvDtkGuG65iu+v7/57B6qvwrsEy4RFmeOZ"
    "v/Q5PPXcqdbgFviTSOG9dmCHJ+oxnMBsM/TqN1WeiglGoNi5ce01mJZHUhVGA7nv6t53Nb9e"
)

# ─── CHỈ GIỮ LẠI MB BANK ──────────────────────────────────────────

PAYMENT_METHODS: Dict[str, Dict[str, Any]] = {
    "mbank": {
        "name": "MB Bank", 
        "number": MB_BANK_NUMBER,
        "owner": MB_BANK_OWNER,
        "zalo": ZALO_NUMBER,
        "type": "Chuyển Khoản Ngân Hàng", 
        "tag": "🏦",
        "instruction": (
            "📌 HƯỚNG DẪN THANH TOÁN\n\n"
            "1️⃣ Chuyển đúng số tiền đến số tài khoản bên dưới\n"
            f"2️⃣ Ngân hàng: MB Bank\n"
            f"3️⃣ Số tài khoản: <code>{MB_BANK_NUMBER}</code>\n"
            f"4️⃣ Chủ tài khoản: <b>{MB_BANK_OWNER}</b>\n"
            f"5️⃣ Nội dung chuyển: <code>MUA GOI [TEN BOT]</code>\n"
            f"6️⃣ Hoặc liên hệ Zalo: <code>{ZALO_NUMBER}</code>\n\n"
            "✅ Sau khi chuyển, nhấn nút 'Gửi Bằng Chứng' bên dưới\n"
            "📸 Gửi ảnh chụp màn hình giao dịch để được xác nhận"
        )
    }
}

# ─── CÁC HÀM HIỂN THỊ MENU (đã dịch sang tiếng Việt) ──────────────

def render_payment_screen(call: types.CallbackQuery, data: str) -> None:
    """Hiển thị màn hình thanh toán với thông tin MB Bank"""
    parts = data.split("_")
    method = parts[1] if len(parts) > 1 else "mbank"
    plan = parts[2] if len(parts) >= 3 else None
    pm = PAYMENT_METHODS.get(method)
    if not pm:
        ack(call, "Không tìm thấy phương thức"); return
    p = PLAN_LIMITS.get(plan or "")
    
    cap = (
        f"<b>{pm['tag']} {pm['name']} — Thanh Toán</b>\n"
        f"{G['div_eq']}\n"
        f"{bullet('Ngân Hàng', 'MB Bank')}\n"
        f"{bullet('Số Tài Khoản', pm['number'])}\n"
        f"{bullet('Chủ Tài Khoản', pm['owner'])}\n"
        f"{bullet('Zalo', pm['zalo'])}\n"
    )
    if p:
        cap += f"{bullet('Gói', p['name'])}\n{bullet('Số Tiền', f"{p['price']}₫")}\n"
    cap += (
        f"{G['div']}\n"
        f"{pm['instruction']}\n"
        f"{G['div']}{FOOTER}"
    )
    
    kb = types.InlineKeyboardMarkup()
    USER_STATES[call.from_user.id] = {
        "flow": "await_payment_proof", 
        "method": method, 
        "plan": plan,
    }
    kb.add(Btn(
        f"{G['plus']}  Gửi Bằng Chứng", callback_data="pay_proof", style="success"))
    kb.add(Btn(
        f"{G['back']}  Quay Lại",
        callback_data=f"plan_buy_{plan}" if plan else "menu_buy",
        style="primary"))
    show_menu(call.message.chat.id, PHOTOS["pay"], cap, kb, call=call)

def render_payment_methods_for(call: types.CallbackQuery, plan: str) -> None:
    """Hiển thị phương thức thanh toán (chỉ MB Bank)"""
    p = PLAN_LIMITS.get(plan)
    if not p:
        ack(call, "Không tìm thấy gói"); return
    
    cap = (
        f"<b>{G['wallet']} Chọn Phương Thức Thanh Toán</b>\n"
        f"{G['div_eq']}\n"
        f"{bullet('Gói', p['name'])}\n"
        f"{bullet('Giá', f"{p['price']}₫")}\n"
        f"{G['div']}\n"
        f"📌 Chúng tôi chỉ chấp nhận thanh toán qua <b>MB Bank</b>.\n"
        f"Vui lòng chọn bên dưới để xem hướng dẫn chi tiết.{FOOTER}"
    )
    
    kb = types.InlineKeyboardMarkup()
    kb.add(Btn(
        f"🏦  MB Bank", 
        callback_data=f"pay_mbank_{plan}", 
        style="success"))
    kb.add(Btn(
        f"{G['back']}  Quay Lại Gói", 
        callback_data="menu_plans", 
        style="primary"))
    show_menu(call.message.chat.id, PHOTOS["pay"], cap, kb, call=call)

def start_proof_flow(call: types.CallbackQuery) -> None:
    """Bắt đầu luồng gửi bằng chứng thanh toán"""
    USER_STATES[call.from_user.id] = {"flow": "await_payment_proof"}
    bot.send_message(
        call.message.chat.id,
        f"📸 {sc('Vui lòng gửi ảnh chụp màn hình giao dịch hoặc mã giao dịch')}.\n"
        f"🏦 {sc('Sau khi admin kiểm tra, bạn sẽ được kích hoạt gói dịch vụ')}.\n"
        f"⏱️ {sc('Thời gian xử lý: Thường trong vòng 15-30 phút')}.\n"
        f"{sc('Gửi /cancel để hủy bỏ')}.",
        parse_mode="HTML"
    )

# ─── HÀM XỬ LÝ THANH TOÁN ─────────────────────────────────────────

def _handle_payment_proof(m: types.Message, st: Dict[str, Any]) -> None:
    """Xử lý bằng chứng thanh toán từ người dùng"""
    method = st.get("method") or "mbank"
    plan   = st.get("plan")
    p = PLAN_LIMITS.get(plan or "")
    pid = rand_token(8)
    
    d = db_load()
    d["payments"].append({
        "id": pid, 
        "uid": m.from_user.id, 
        "method": method, 
        "plan": plan,
        "amount": (p or {}).get("price", 0),
        "status": "pending", 
        "ts": ts_iso(),
        "telegram_msg_id": m.message_id,
        "bank": "MB Bank",
        "account": MB_BANK_NUMBER,
        "owner": MB_BANK_OWNER,
    })
    db_save(d)
    USER_STATES.pop(m.from_user.id, None)
    
    # Forward bằng chứng đến admin
    try:
        bot.forward_message(OWNER_ID, m.chat.id, m.message_id)
    except Exception:
        pass
    
    kb = types.InlineKeyboardMarkup()
    kb.add(
        Btn(f"{G['ok']}  Phê Duyệt", callback_data=f"payapprove_{pid}", style="success"),
        Btn(f"{G['no']}  Từ Chối",  callback_data=f"payreject_{pid}", style="danger"),
    )
    
    notify_owner(
        f"<b>💳 Bằng Chứng Thanh Toán MB Bank</b>\n"
        f"{G['div']}\n"
        f"{bullet('Mã GD', pid)}\n"
        f"{bullet('Người Dùng', m.from_user.id)}\n"
        f"{bullet('Tên', m.from_user.first_name or '')}\n"
        f"{bullet('Gói', plan or '—')}\n"
        f"{bullet('Số Tiền', f"{(p or {}).get('price', 0)}₫")}\n"
        f"{bullet('Ngân Hàng', 'MB Bank')}\n"
        f"{bullet('Số TK', MB_BANK_NUMBER)}\n"
        f"{bullet('Chủ TK', MB_BANK_OWNER)}\n"
        f"{G['div']}\n"
        f"Nhấn nút bên dưới để xử lý."
    )
    
    try:
        bot.send_message(OWNER_ID, f"<b>Quyết Định #{pid}</b>", 
                        parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    
    # Gửi thông báo Zalo cho admin
    try:
        bot.send_message(OWNER_ID,
            f"📱 <b>Liên hệ Zalo xác nhận</b>\n"
            f"SĐT: <code>{ZALO_NUMBER}</code>\n"
            f"Mã GD: <code>{pid}</code>\n"
            f"Người dùng: <code>{m.from_user.id}</code>",
            parse_mode="HTML")
    except Exception:
        pass
    
    bot.reply_to(m, 
        f"<b>{G['ok']} Đã nhận bằng chứng thanh toán!</b>\n"
        f"{G['div']}\n"
        f"{bullet('Mã GD', pid)}\n"
        f"{bullet('Ngân Hàng', 'MB Bank')}\n"
        f"{bullet('Số TK', MB_BANK_NUMBER)}\n"
        f"{bullet('Chủ TK', MB_BANK_OWNER)}\n"
        f"{G['div']}\n"
        f"⏳ Đang chờ admin xác nhận. Bạn sẽ nhận được thông báo khi gói được kích hoạt.",
        parse_mode="HTML")

def action_payment_approve(call: types.CallbackQuery, pid: str) -> None:
    """Phê duyệt thanh toán MB Bank"""
    if not admin_only_call(call, "approve_payment"):
        return
    d = db_load()
    pay = next((x for x in d["payments"] if x.get("id") == pid), None)
    if not pay:
        ack(call, "Không tìm thấy"); return
    if pay.get("status") in ("approved", "rejected"):
        ack(call, f"Đã {pay['status']}."); return
    
    loading(call, "Đang phê duyệt thanh toán")
    pay["status"] = "approved"
    pay["approved_by"] = call.from_user.id
    pay["approved_at"] = ts_iso()
    db_save(d)
    
    if pay.get("kind") == "wallet_topup":
        u = d["users"].get(str(pay["uid"]))
        if u:
            u["wallet"] = int(u.get("wallet", 0)) + int(pay.get("amount", 0))
            db_save(d)
            try:
                bot.send_message(pay["uid"],
                    f"<b>{G['ok']} Ví Đã Được Cộng Tiền</b>\n"
                    f"{bullet('Số Tiền', f"{pay['amount']}₫")}\n"
                    f"{bullet('Ngân Hàng', 'MB Bank')}\n"
                    f"{bullet('Qua', MB_BANK_OWNER)}",
                    parse_mode="HTML")
            except Exception:
                pass
    elif pay.get("plan"):
        grant_plan(pay["uid"], pay["plan"])
        post_announcement(
            f"<b>{G['spark']} Kích Hoạt Gói Mới</b>\n"
            f"{bullet('Gói', PLAN_LIMITS[pay['plan']]['name'])}\n"
            f"{bullet('Ngân Hàng', 'MB Bank')}"
        )
    
    audit(call.from_user.id, "pay_approve", f"pid={pid} bank=MB")
    ack(call, "✅ Đã phê duyệt")
    
    # Thông báo Zalo cho admin
    try:
        bot.send_message(OWNER_ID,
            f"✅ <b>Đã phê duyệt thanh toán</b>\n"
            f"Mã GD: <code>{pid}</code>\n"
            f"Người dùng: <code>{pay['uid']}</code>\n"
            f"Số tiền: {pay['amount']}₫",
            parse_mode="HTML")
    except Exception:
        pass
    
    try:
        bot.edit_message_text(f"<b>{G['ok']} Đã Phê Duyệt #{pid}</b>",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id, parse_mode="HTML")
    except Exception:
        pass

def action_payment_reject(call: types.CallbackQuery, pid: str) -> None:
    """Từ chối thanh toán MB Bank"""
    if not admin_only_call(call, "approve_payment"):
        return
    d = db_load()
    pay = next((x for x in d["payments"] if x.get("id") == pid), None)
    if not pay:
        ack(call, "Không tìm thấy"); return
    if pay.get("status") in ("approved", "rejected"):
        ack(call, f"Đã {pay['status']}."); return
    
    loading(call, "Đang từ chối thanh toán")
    pay["status"] = "rejected"
    pay["rejected_by"] = call.from_user.id
    pay["rejected_at"] = ts_iso()
    db_save(d)
    
    audit(call.from_user.id, "pay_reject", f"pid={pid} bank=MB")
    
    try:
        bot.send_message(pay["uid"],
            f"<b>{G['no']} Thanh Toán Bị Từ Chối</b>\n"
            f"{bullet('Mã GD', pid)}\n"
            f"{bullet('Ngân Hàng', 'MB Bank')}\n"
            f"{bullet('Lý do', 'Vui lòng kiểm tra lại thông tin hoặc liên hệ admin')}\n"
            f"{G['div']}\n"
            f"📞 Liên hệ {SUPPORT_USR} để được hỗ trợ.",
            parse_mode="HTML")
    except Exception:
        pass
    
    ack(call, "❌ Đã từ chối")
    
    try:
        bot.edit_message_text(f"<b>{G['no']} Đã Từ Chối #{pid}</b>",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id, parse_mode="HTML")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
# PHẦN CÒN LẠI CỦA CODE (GIỮ NGUYÊN CẤU TRÚC)
# ═══════════════════════════════════════════════════════════════════════════

# ... (Các hàm còn lại như render_bots_menu, render_plans_menu, v.v.)
# ... (Đã được giữ nguyên từ file trước)

def main() -> int:
    """Hàm khởi tạo và chạy bot chính"""
    banner()
    global _LOCK_FH_KEEPALIVE
    _LOCK_FH_KEEPALIVE = _acquire_singleton_lock()
    global OWNER_ID, BRAND_TAG, ANNOUNCE_CHANNEL
    
    # Khôi phục cấu hình
    stored_owner = int(get_setting("owner_id", 0) or 0)
    if stored_owner > 0:
        OWNER_ID = stored_owner if OWNER_ID <= 0 or stored_owner != OWNER_ID else OWNER_ID
        if OWNER_ID <= 0:
            OWNER_ID = stored_owner
            
    bt = get_setting("brand_tag", None)
    if isinstance(bt, str) and bt:
        BRAND_TAG = bt
        
    ac = get_setting("announce_channel", None)
    if isinstance(ac, str):
        ANNOUNCE_CHANNEL = ac
        
    gh_load_config()
    GH["autoEnabled"] = bool(get_setting("github_auto_enabled", True))
    
    # Khởi tạo các luồng nền
    threading.Thread(target=gh_auto_loop, daemon=True).start()
    threading.Thread(target=gh_uptime_backup_loop, daemon=True,
                     name="gh-uptime-backup").start()
    threading.Thread(target=cron_runner, daemon=True).start()
    threading.Thread(target=_verify_state_janitor, daemon=True,
                     name="verify-janitor").start()
    threading.Thread(target=_sched_check_and_run, daemon=True,
                     name="scheduler").start()
    _start_keepalive()
    
    # Đặt lệnh cho bot
    try:
        bot.set_my_commands([
            types.BotCommand("start",  "Mở menu chính"),
            types.BotCommand("menu",   "Menu chính"),
            types.BotCommand("help",   "Hiển thị trợ giúp"),
            types.BotCommand("id",     "Hiển thị ID của bạn"),
            types.BotCommand("cancel", "Hủy thao tác hiện tại"),
            types.BotCommand("admin",  "Bảng điều khiển"),
        ])
    except Exception:
        pass
    
    # Thông báo bot đã online
    notify_owner(
        f"<b>{G['ok']} Bảng Điều Khiển Đã Trực Tuyến</b>\n"
        f"{G['div']}\n"
        f"{bullet('Thương Hiệu', BRAND_TAG)}\n"
        f"{bullet('Admin', OWNER_ID)}\n"
        f"{bullet('Ngân Hàng', 'MB Bank')}\n"
        f"{bullet('Số TK', MB_BANK_NUMBER)}\n"
        f"{bullet('Chủ TK', MB_BANK_OWNER)}\n"
        f"{bullet('Zalo', ZALO_NUMBER)}\n"
        f"{bullet('Người Dùng', len(db_load()['users']))}\n"
        f"{bullet('Bot', len(db_load()['bots']))}"
    )
    
    # Tự động chạy các bot đã chạy trước đó
    for b in db_load()["bots"].values():
        if b.get("status") == "running":
            try:
                start_child(b)
            except Exception:
                pass
    
    # Xóa webhook
    try:
        bot.remove_webhook()
        try:
            bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        print("[bot] đã xóa webhook")
    except Exception as e:
        print(f"[bot] cảnh báo xóa webhook: {e}")
    
    print("[bot] đang polling...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=25)
        except KeyboardInterrupt:
            print("\n[bot] đang dừng...")
            for bid in list(RUNNING.keys()):
                stop_child(bid, manual=False)
            return 0
        except Exception as e:
            print(f"[bot] lỗi poll: {e}")
            time.sleep(5)

if __name__ == "__main__":
    sys.exit(main())