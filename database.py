"""
database.py — SQLite storage layer for the Quoridor game.

Used by BOTH:
  * main.py   (local / offline accounts, profile, history, leaderboard)
  * server.py (online authoritative accounts, ELO, match records)

Everything is plain sqlite3 (no external dependency) and thread-safe.
"""

import os
import sqlite3
import hashlib
import secrets
import threading
import time

DB_PATH = os.environ.get(
    "QUORIDOR_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "quoridor.db"),
)

_LOCK = threading.RLock()
_CONN = None

START_ELO = 1000
MIN_DELTA = 15
MAX_DELTA = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    salt        TEXT NOT NULL,
    pwhash      TEXT NOT NULL,
    pfp         INTEGER NOT NULL DEFAULT 0,
    flag        TEXT NOT NULL DEFAULT 'UN',
    elo         INTEGER NOT NULL DEFAULT 1000,
    wins        INTEGER NOT NULL DEFAULT 0,
    losses      INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname    TEXT NOT NULL COLLATE NOCASE,
    opponent    TEXT NOT NULL,
    result      TEXT NOT NULL,          -- 'win' | 'loss'
    elo_delta   INTEGER NOT NULL DEFAULT 0,
    elo_after   INTEGER NOT NULL DEFAULT 1000,
    mode        TEXT NOT NULL DEFAULT 'casual',
    ts          REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_nick ON matches(nickname);
CREATE INDEX IF NOT EXISTS idx_users_elo   ON users(elo DESC);
"""


# --------------------------------------------------------------------------
# connection / bootstrap
# --------------------------------------------------------------------------
def conn():
    global _CONN
    with _LOCK:
        if _CONN is None:
            _CONN = sqlite3.connect(DB_PATH, check_same_thread=False)
            _CONN.row_factory = sqlite3.Row
            try:
                _CONN.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass
        return _CONN


def init_db():
    with _LOCK:
        c = conn()
        c.executescript(SCHEMA)
        c.commit()


# --------------------------------------------------------------------------
# password helpers
# --------------------------------------------------------------------------
def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + "::" + password).encode("utf-8")).hexdigest()


def _row_to_user(row) -> dict:
    if row is None:
        return None
    total = row["wins"] + row["losses"]
    return {
        "nickname": row["nickname"],
        "pfp": row["pfp"],
        "flag": row["flag"],
        "elo": row["elo"],
        "wins": row["wins"],
        "losses": row["losses"],
        "matches": total,
        "winrate": round(row["wins"] * 100.0 / total, 1) if total else 0.0,
    }


# --------------------------------------------------------------------------
# accounts
# --------------------------------------------------------------------------
def create_user(nickname: str, password: str):
    """Returns (True, user_dict) or (False, error_code)."""
    nickname = (nickname or "").strip()
    password = password or ""
    if len(nickname) < 3 or len(password) < 3:
        return False, "short"
    if len(nickname) > 16:
        return False, "short"
    init_db()
    with _LOCK:
        c = conn()
        if c.execute("SELECT 1 FROM users WHERE nickname = ?", (nickname,)).fetchone():
            return False, "taken"
        salt = secrets.token_hex(8)
        c.execute(
            "INSERT INTO users (nickname, salt, pwhash, pfp, flag, elo, wins, losses, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (nickname, salt, _hash(password, salt), 0, "UN", START_ELO, 0, 0, time.time()),
        )
        c.commit()
    return True, get_user(nickname)


def login(nickname: str, password: str):
    """Returns (True, user_dict) or (False, error_code)."""
    init_db()
    with _LOCK:
        row = conn().execute(
            "SELECT * FROM users WHERE nickname = ?", ((nickname or "").strip(),)
        ).fetchone()
    if row is None:
        return False, "nouser"
    if _hash(password or "", row["salt"]) != row["pwhash"]:
        return False, "badpw"
    return True, _row_to_user(row)


def login_or_create(nickname: str, password: str):
    """Used by the online server: log in, or register if the name is free."""
    ok, res = login(nickname, password)
    if ok:
        return True, res
    if res == "nouser":
        return create_user(nickname, password)
    return False, res


def get_user(nickname: str):
    init_db()
    with _LOCK:
        row = conn().execute(
            "SELECT * FROM users WHERE nickname = ?", ((nickname or "").strip(),)
        ).fetchone()
    return _row_to_user(row)


def set_profile(nickname: str, pfp: int, flag: str):
    init_db()
    with _LOCK:
        c = conn()
        c.execute(
            "UPDATE users SET pfp = ?, flag = ? WHERE nickname = ?",
            (int(pfp), str(flag)[:3], nickname),
        )
        c.commit()
    return get_user(nickname)


# --------------------------------------------------------------------------
# ELO
# --------------------------------------------------------------------------
def expected(a: int, b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))


def elo_delta(winner_elo: int, loser_elo: int) -> int:
    """15 .. 30 points, scaled by the rating gap."""
    raw = round(40 * (1.0 - expected(winner_elo, loser_elo)))
    return int(max(MIN_DELTA, min(MAX_DELTA, raw)))


# --------------------------------------------------------------------------
# matches
# --------------------------------------------------------------------------
def record_match(nickname, opponent, result, delta, elo_after, mode="casual"):
    init_db()
    with _LOCK:
        c = conn()
        c.execute(
            "INSERT INTO matches (nickname, opponent, result, elo_delta, elo_after, mode, ts)"
            " VALUES (?,?,?,?,?,?,?)",
            (nickname, opponent, result, int(delta), int(elo_after), mode, time.time()),
        )
        c.commit()


def apply_result(winner: str, loser: str, ranked: bool = True, mode: str = "casual"):
    """
    Updates W/L counters for both players, adjusts ELO when `ranked`,
    writes both history rows and returns:
        {"winner": {...}, "loser": {...}}  with 'delta' and 'elo' keys.
    """
    init_db()
    wu = get_user(winner)
    lu = get_user(loser)
    if wu is None or lu is None:
        return None

    delta = elo_delta(wu["elo"], lu["elo"]) if ranked else 0
    w_elo = wu["elo"] + delta
    l_elo = max(100, lu["elo"] - delta)

    with _LOCK:
        c = conn()
        c.execute(
            "UPDATE users SET wins = wins + 1, elo = ? WHERE nickname = ?", (w_elo, winner)
        )
        c.execute(
            "UPDATE users SET losses = losses + 1, elo = ? WHERE nickname = ?", (l_elo, loser)
        )
        c.commit()

    record_match(winner, loser, "win", delta, w_elo, mode)
    record_match(loser, winner, "loss", -delta, l_elo, mode)
    return {
        "winner": {"nickname": winner, "delta": delta, "elo": w_elo},
        "loser": {"nickname": loser, "delta": -delta, "elo": l_elo},
    }


def record_local(nickname: str, opponent: str, win: bool, mode: str = "ai"):
    """Offline games: count the match, never touch ELO."""
    u = get_user(nickname)
    if u is None:
        return None
    with _LOCK:
        c = conn()
        if win:
            c.execute("UPDATE users SET wins = wins + 1 WHERE nickname = ?", (nickname,))
        else:
            c.execute("UPDATE users SET losses = losses + 1 WHERE nickname = ?", (nickname,))
        c.commit()
    u = get_user(nickname)
    record_match(nickname, opponent, "win" if win else "loss", 0, u["elo"], mode)
    return u


def history(nickname: str, limit: int = 50):
    init_db()
    with _LOCK:
        rows = conn().execute(
            "SELECT opponent, result, elo_delta, elo_after, mode, ts FROM matches"
            " WHERE nickname = ? ORDER BY id DESC LIMIT ?",
            (nickname, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def leaderboard(kind: str = "elo", limit: int = 20):
    """kind: 'elo' (Top ELO Players) or 'matches' (Most Matches Played)."""
    init_db()
    order = "elo DESC" if kind == "elo" else "(wins + losses) DESC, elo DESC"
    with _LOCK:
        rows = conn().execute(
            "SELECT nickname, pfp, flag, elo, wins, losses FROM users"
            f" ORDER BY {order} LIMIT ?",
            (int(limit),),
        ).fetchall()
    out = []
    for r in rows:
        total = r["wins"] + r["losses"]
        out.append(
            {
                "nickname": r["nickname"],
                "pfp": r["pfp"],
                "flag": r["flag"],
                "elo": r["elo"],
                "matches": total,
                "winrate": round(r["wins"] * 100.0 / total, 1) if total else 0.0,
            }
        )
    return out


if __name__ == "__main__":
    init_db()
    print("Database ready at", DB_PATH)
