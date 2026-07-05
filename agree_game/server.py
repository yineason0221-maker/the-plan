from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
QUESTIONS_FILE = DATA_DIR / "questions.json"
DATABASE_FILE = DATA_DIR / "agree_votes.sqlite3"
GAME_HTML_FILE = BASE_DIR / "game.html"
ADMIN_HTML_FILE = BASE_DIR / "admin.html"

PORT = int(os.environ.get("PORT", "5000"))
SECRET_KEY = os.environ.get("SECRET_KEY", "agree-game-dev-secret")
ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "admin"
COOKIE_NAME = "agree_admin"
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
ADMIN_PASSWORD_KEY = "admin_password_hash"
GAME_VERSION_KEY = "game_version"
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120_000
PASSWORD_SALT_BYTES = 16


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id TEXT NOT NULL,
                question_prompt TEXT NOT NULL,
                choice_value TEXT NOT NULL,
                choice_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_votes_question_choice
            ON votes(question_id, choice_value)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_votes_created_at
            ON votes(created_at)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()
    ensure_admin_defaults()


def get_admin_setting(key: str) -> str | None:
    with connect_db() as conn:
        row = conn.execute(
            "SELECT value FROM admin_settings WHERE key = ?",
            (key,),
        ).fetchone()

    return str(row["value"]) if row else None


def set_admin_setting(key: str, value: str) -> None:
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO admin_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt_bytes = salt or secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PASSWORD_ITERATIONS,
    )
    return (
        f"{PASSWORD_ALGORITHM}"
        f"${PASSWORD_ITERATIONS}"
        f"${base64.b64encode(salt_bytes).decode('ascii')}"
        f"${base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected_digest = base64.b64decode(digest_b64.encode("ascii"))
    except (ValueError, TypeError, binascii.Error):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def ensure_admin_defaults() -> None:
    if get_admin_setting(ADMIN_PASSWORD_KEY) is None:
        set_admin_setting(ADMIN_PASSWORD_KEY, hash_password(ADMIN_DEFAULT_PASSWORD))
    if get_admin_setting(GAME_VERSION_KEY) is None:
        set_admin_setting(GAME_VERSION_KEY, "1")


def get_admin_password_hash() -> str | None:
    return get_admin_setting(ADMIN_PASSWORD_KEY)


def set_admin_password(password: str) -> None:
    set_admin_setting(ADMIN_PASSWORD_KEY, hash_password(password))


def verify_admin_password(password: str) -> bool:
    stored_hash = get_admin_password_hash()
    if not stored_hash:
        return password == ADMIN_DEFAULT_PASSWORD

    return verify_password(password, stored_hash)


def get_game_version() -> int:
    raw_value = get_admin_setting(GAME_VERSION_KEY)
    try:
        return max(1, int(raw_value)) if raw_value is not None else 1
    except ValueError:
        return 1


def set_game_version(version: int) -> None:
    set_admin_setting(GAME_VERSION_KEY, str(max(1, version)))


def bump_game_version() -> int:
    version = get_game_version() + 1
    set_game_version(version)
    return version


def load_questions() -> list[dict]:
    if not QUESTIONS_FILE.exists():
        return []

    try:
        with QUESTIONS_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return []

    raw_questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(raw_questions, list):
        return []

    questions: list[dict] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue

        question_id = str(item.get("id", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        description = str(item.get("description", "")).strip()
        active = bool(item.get("active", False))
        raw_choices = item.get("choices", [])

        if not question_id or not prompt or not isinstance(raw_choices, list):
            continue

        choices: list[dict] = []
        for choice in raw_choices:
            if not isinstance(choice, dict):
                continue
            value = str(choice.get("value", "")).strip()
            label = str(choice.get("label", "")).strip()
            if value and label:
                choices.append({"value": value, "label": label})

        if not choices:
            continue

        questions.append(
            {
                "id": question_id,
                "prompt": prompt,
                "description": description,
                "active": active,
                "choices": choices,
            }
        )

    return questions


def find_question(question_id: str) -> dict | None:
    for question in load_questions():
        if question["id"] == question_id:
            return question
    return None


def current_question() -> dict | None:
    questions = load_questions()
    for question in questions:
        if question.get("active"):
            return question
    return questions[0] if questions else None


def summarize_votes() -> dict:
    questions = load_questions()
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with connect_db() as conn:
        total_row = conn.execute("SELECT COUNT(*) AS count FROM votes").fetchone()
        total_votes = int(total_row["count"]) if total_row else 0

        grouped_rows = conn.execute(
            """
            SELECT question_id, choice_value, COUNT(*) AS count
            FROM votes
            GROUP BY question_id, choice_value
            """
        ).fetchall()
        for row in grouped_rows:
            counts[row["question_id"]][row["choice_value"]] = int(row["count"])

        recent_rows = conn.execute(
            """
            SELECT id, question_id, question_prompt, choice_value, choice_label, created_at
            FROM votes
            ORDER BY id DESC
            LIMIT 25
            """
        ).fetchall()

    question_cards: list[dict] = []
    for question in questions:
        choice_stats = []
        total_for_question = 0
        for choice in question["choices"]:
            choice_count = counts[question["id"]].get(choice["value"], 0)
            total_for_question += choice_count
            choice_stats.append(
                {
                    "value": choice["value"],
                    "label": choice["label"],
                    "count": choice_count,
                }
            )

        question_cards.append(
            {
                "id": question["id"],
                "prompt": question["prompt"],
                "description": question["description"],
                "active": question["active"],
                "total": total_for_question,
                "choices": choice_stats,
            }
        )

    recent_votes = [
        {
            "id": row["id"],
            "question_id": row["question_id"],
            "question_prompt": row["question_prompt"],
            "choice_value": row["choice_value"],
            "choice_label": row["choice_label"],
            "created_at": row["created_at"],
        }
        for row in recent_rows
    ]

    active_count = sum(1 for question in questions if question.get("active"))

    return {
        "total_votes": total_votes,
        "question_count": len(questions),
        "active_count": active_count,
        "questions": question_cards,
        "recent_votes": recent_votes,
    }


def record_vote(question: dict, choice_value: str) -> dict:
    choice = next((item for item in question["choices"] if item["value"] == choice_value), None)
    if choice is None:
        raise ValueError("選項不存在。")

    created_at = utc_now()
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO votes (
                question_id,
                question_prompt,
                choice_value,
                choice_label,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                question["id"],
                question["prompt"],
                choice["value"],
                choice["label"],
                created_at,
            ),
        )
        conn.commit()

    with connect_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM votes WHERE question_id = ?",
            (question["id"],),
        ).fetchone()

    return {
        "choice": choice,
        "count": int(row["count"]) if row else 0,
        "created_at": created_at,
    }


def clear_vote_records() -> int:
    with connect_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM votes").fetchone()
        deleted = int(row["count"]) if row else 0
        conn.execute("DELETE FROM votes")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("votes",))
        conn.commit()

    bump_game_version()
    return deleted


def sign_admin_token() -> str:
    expiry = str(int(time.time()) + TOKEN_TTL_SECONDS)
    nonce = secrets.token_urlsafe(12)
    payload = f"{expiry}:{nonce}"
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_admin_token(token: str) -> bool:
    try:
        expiry_str, nonce, signature = token.split(":")
        expiry = int(expiry_str)
    except ValueError:
        return False

    if expiry < int(time.time()):
        return False

    payload = f"{expiry_str}:{nonce}"
    expected = hmac.new(
        SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def cookie_value(handler: BaseHTTPRequestHandler, name: str) -> str | None:
    raw_cookie = handler.headers.get("Cookie")
    if not raw_cookie:
        return None

    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except Exception:
        return None

    morsel = cookie.get(name)
    return morsel.value if morsel else None


def is_admin_authenticated(handler: BaseHTTPRequestHandler) -> bool:
    token = cookie_value(handler, COOKIE_NAME)
    return bool(token and verify_admin_token(token))


def parse_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}

    content_type = handler.headers.get("Content-Type", "")
    text = raw.decode("utf-8", errors="replace")

    if "application/json" in content_type:
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}

    if "application/x-www-form-urlencoded" in content_type:
        return {key: values[0] for key, values in parse_qs(text).items() if values}

    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


class AgreeHandler(BaseHTTPRequestHandler):
    server_version = "AgreeGame/2.0"

    def log_message(self, format: str, *args) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path in {"/", "/game", "/game.html"}:
            return self.serve_file(GAME_HTML_FILE, "text/html; charset=utf-8")

        if path in {"/admin", "/admin.html"}:
            return self.serve_file(ADMIN_HTML_FILE, "text/html; charset=utf-8")

        if path.startswith("/assets/"):
            asset_path = (ASSETS_DIR / path.removeprefix("/assets/")).resolve()
            if ASSETS_DIR.resolve() not in asset_path.parents and asset_path != ASSETS_DIR.resolve():
                return self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "找不到頁面。"})
            return self.serve_asset(asset_path)

        if path == "/api/questions":
            return self.send_json(HTTPStatus.OK, {"ok": True, "questions": load_questions()})

        if path == "/api/current-question":
            question = current_question()
            payload = {
                "ok": True,
                "question": question,
                "question_count": len(load_questions()),
                "total_votes": summarize_votes()["total_votes"],
                "vote_version": get_game_version(),
            }
            if question is not None:
                with connect_db() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) AS count FROM votes WHERE question_id = ?",
                        (question["id"],),
                    ).fetchone()
                payload["vote_count"] = int(row["count"]) if row else 0
            else:
                payload["vote_count"] = 0
            return self.send_json(HTTPStatus.OK, payload)

        if path == "/api/admin/stats":
            if not is_admin_authenticated(self):
                return self.send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"ok": False, "error": "尚未登入。"},
                )
            stats = summarize_votes()
            stats["ok"] = True
            return self.send_json(HTTPStatus.OK, stats)

        if path == "/api/health":
            return self.send_json(HTTPStatus.OK, {"ok": True})

        return self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "找不到頁面。"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/vote":
            return self.handle_vote()

        if path == "/api/admin/login":
            return self.handle_admin_login()

        if path == "/api/admin/logout":
            return self.handle_admin_logout()

        if path == "/api/admin/password":
            return self.handle_admin_password_change()

        if path == "/api/admin/clear-records":
            return self.handle_admin_clear_records()

        return self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "找不到頁面。"})

    def serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            return self.send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"缺少檔案：{file_path.name}"},
            )

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def serve_asset(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            return self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "找不到檔案。"})

        content_type = "text/plain; charset=utf-8"
        if file_path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".json":
            content_type = "application/json; charset=utf-8"

        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def handle_vote(self) -> None:
        payload = parse_body(self)
        question_id = str(payload.get("question_id", "")).strip()
        choice_value = str(payload.get("choice", "")).strip()

        if not question_id or not choice_value:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "缺少題目或選項。"},
            )

        question = find_question(question_id)
        if question is None:
            return self.send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "題目不存在。"},
            )

        try:
            result = record_vote(question, choice_value)
        except ValueError as exc:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )

        return self.send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": f"已記錄：{result['choice']['label']}",
                "choice": result["choice"]["label"],
                "count": result["count"],
            },
        )

    def handle_admin_login(self) -> None:
        payload = parse_body(self)
        password = str(payload.get("password", ""))
        if not verify_admin_password(password):
            return self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "密碼錯誤。"},
            )

        stats = summarize_votes()
        token = sign_admin_token()
        self.send_json(
            HTTPStatus.OK,
            {"ok": True, "message": "登入成功。", **stats},
            extra_headers=[
                (
                    "Set-Cookie",
                    f"{COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age={TOKEN_TTL_SECONDS}",
                )
            ],
        )

    def handle_admin_password_change(self) -> None:
        if not is_admin_authenticated(self):
            return self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "尚未登入。"},
            )

        payload = parse_body(self)
        current_password = str(payload.get("current_password", "")).strip()
        new_password = str(payload.get("new_password", "")).strip()
        confirm_password = str(payload.get("confirm_password", "")).strip()

        if not current_password or not new_password or not confirm_password:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "請填寫完整密碼資料。"},
            )

        if new_password != confirm_password:
            return self.send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "兩次新密碼不一致。"},
            )

        if not verify_admin_password(current_password):
            return self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "目前密碼錯誤。"},
            )

        set_admin_password(new_password)
        return self.send_json(
            HTTPStatus.OK,
            {"ok": True, "message": "密碼已更新。"},
        )

    def handle_admin_clear_records(self) -> None:
        if not is_admin_authenticated(self):
            return self.send_json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "尚未登入。"},
            )

        deleted = clear_vote_records()
        stats = summarize_votes()
        return self.send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": f"已清空 {deleted} 筆紀錄。",
                "deleted": deleted,
                **stats,
            },
        )

    def handle_admin_logout(self) -> None:
        self.send_json(
            HTTPStatus.OK,
            {"ok": True, "message": "已登出。"},
            extra_headers=[
                (
                    "Set-Cookie",
                    f"{COOKIE_NAME}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0",
                )
            ],
        )

    def send_json(
        self,
        status: HTTPStatus,
        payload: dict,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), AgreeHandler)
    print(f"Agree Game running on http://127.0.0.1:{PORT}")
    print(f"Game page: http://127.0.0.1:{PORT}/")
    print(f"Admin page: http://127.0.0.1:{PORT}/admin")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
