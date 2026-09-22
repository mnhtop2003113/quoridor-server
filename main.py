"""
main.py — Quoridor desktop game (pygame).

Run:        python main.py
Build exe:  pyinstaller --noconsole --onefile --name Quoridor main.py

Requires: pygame  (pip install pygame)
Uses:     database.py (local accounts / history), server.py (online play)
"""

import json
import math
import os
import queue
import random
import socket
import sys
import threading
import time
from collections import deque

import pygame

import database as db

# ==========================================================================
#  THEME / LAYOUT
# ==========================================================================
W, H = 1100, 800
FPS = 60

BG        = (245, 247, 250)
GRID_LINE = (232, 236, 242)
WHITE     = (255, 255, 255)
INK       = (26, 30, 38)
MUTED     = (124, 132, 146)
LINE      = (224, 228, 236)
SOFT      = (240, 243, 248)

RED       = (211, 66, 66)
RED_D     = (166, 38, 38)
RED_L     = (252, 235, 235)
BLUE      = (52, 96, 186)
BLUE_D    = (32, 64, 136)
BLUE_L    = (232, 239, 252)
GREEN     = (32, 158, 88)
DARK      = (38, 43, 54)

CELL, GAP = 52, 10
BOARD_PX  = 9 * CELL + 8 * GAP           # 548
BX, BY    = (W - BOARD_PX) // 2, 150

# Automatic matchmaking target — no manual host/IP entry in the UI.
DEFAULT_HOST = "quoridor-server-nnkx.onrender.com"
DEFAULT_PORT = 5555

# Bottom wall-tray geometry (drag-and-drop source tiles).
BAR    = pygame.Rect(W // 2 - 190, 692, 380, 84)
TILE_H = pygame.Rect(BAR.x + 22, BAR.y + 40, 158, 36)
TILE_V = pygame.Rect(BAR.right - 180, BAR.y + 40, 158, 36)

PFP_COLORS = [
    (211, 66, 66), (52, 96, 186), (32, 158, 88), (232, 160, 40),
    (140, 84, 196), (32, 160, 172), (232, 104, 152), (90, 98, 118),
]

# layout, stripe colors, center-dot color
FLAGS = {
    "UN": ("solid", [(94, 150, 210)], None),
    "MN": ("v", [(200, 16, 46), (0, 102, 178), (200, 16, 46)], None),
    "KR": ("solid", [(255, 255, 255)], (206, 30, 46)),
    "VN": ("solid", [(218, 37, 29)], (255, 205, 0)),
    "US": ("h", [(191, 10, 48), (255, 255, 255), (191, 10, 48), (255, 255, 255)], None),
    "GB": ("solid", [(1, 33, 105)], (255, 255, 255)),
    "JP": ("solid", [(255, 255, 255)], (188, 0, 45)),
    "CN": ("solid", [(222, 41, 16)], (255, 222, 0)),
    "RU": ("h", [(255, 255, 255), (0, 57, 166), (213, 43, 30)], None),
    "DE": ("h", [(20, 20, 20), (221, 0, 0), (255, 206, 0)], None),
    "FR": ("v", [(0, 85, 164), (255, 255, 255), (239, 65, 53)], None),
    "TR": ("solid", [(227, 10, 23)], (255, 255, 255)),
    "KZ": ("solid", [(0, 175, 202)], (255, 237, 0)),
    "IN": ("h", [(255, 153, 51), (255, 255, 255), (19, 136, 8)], None),
}
FLAG_CODES = list(FLAGS.keys())

# ==========================================================================
#  LANGUAGES
# ==========================================================================
LANGS = [("en", "English"), ("mn", "Монгол"), ("ko", "한국어"), ("vi", "Tiếng Việt")]

T = {
    "en": {
        "title": "QUORIDOR", "pick_lang": "Choose your language",
        "signin": "Sign In", "signup": "Sign Up", "nick": "Nickname", "pw": "Password",
        "guest": "Continue as guest", "taken": "This name is already taken!",
        "nouser": "No such player.", "badpw": "Wrong password.",
        "short": "Nickname and password need at least 3 characters.",
        "menu": "Main Menu", "offline": "Play Offline", "online": "Play Online",
        "profile": "Profile", "history": "Match History", "lb": "Leaderboard",
        "howto": "How to Play", "quit": "Quit",
        "local": "Local 2 Players", "ai": "Play vs Bot",
        "easy": "Easy", "normal": "Normal", "expert": "Expert",
        "back": "Back", "casual": "Classic Online (casual)", "ranked": "Ranked Online",
        "bullet": "Bullet · 1 min", "blitz": "Blitz · 3 min", "rapid": "Classic · 5 min",
        "host": "Server address (host:port)", "connect": "Connect",
        "searching": "Searching for an opponent...", "cancel": "Cancel",
        "walls": "walls left", "surrender": "Give up", "rematch": "Rematch",
        "winner": "WINNER", "elo": "ELO", "matches": "Matches", "winrate": "Winrate",
        "wins": "Wins", "losses": "Losses", "flag": "Country flag", "avatar": "Profile picture",
        "save": "Save", "top_elo": "Top ELO Players", "most_matches": "Most Matches Played",
        "rank": "#", "player": "Player", "result": "Result", "win": "Win", "loss": "Loss",
        "opponent": "Opponent", "date": "Date", "empty": "Nothing here yet.",
        "horiz": "Horizontal", "vert": "Vertical",
        "disconnected": "Connection lost.", "timeout": "Time out!",
        "your_turn": "YOUR TURN", "opp_turn": "OPPONENT'S TURN",
        "logged": "Signed in as", "logout": "Sign out", "connecting": "Connecting...",
        "opp_left": "Opponent left the game.", "bot": "Bot",
        "rules": [
            "Goal: be the first to walk your pawn to the opposite side of the board.",
            "On your turn you either move one step (up/down/left/right) or place one wall.",
            "Click a highlighted square to move. Click a grid intersection to place a wall.",
            "Use the Horizontal / Vertical buttons to rotate the wall before placing it.",
            "A wall may never completely block a player's last path to the goal.",
            "Each player has 10 walls. Jump over the opponent when you stand face to face.",
        ],
    },
    "mn": {
        "title": "QUORIDOR", "pick_lang": "Хэлээ сонгоно уу",
        "signin": "Нэвтрэх", "signup": "Бүртгүүлэх", "nick": "Хоч нэр", "pw": "Нууц үг",
        "guest": "Зочноор үргэлжлүүлэх", "taken": "Энэ нэр аль хэдийн бүртгэгдсэн байна!",
        "nouser": "Ийм тоглогч олдсонгүй.", "badpw": "Нууц үг буруу байна.",
        "short": "Нэр болон нууц үг дор хаяж 3 тэмдэгт байх ёстой.",
        "menu": "Үндсэн цэс", "offline": "Офлайн тоглох", "online": "Онлайн тоглох",
        "profile": "Хувийн мэдээлэл", "history": "Тоглолтын түүх", "lb": "Тэргүүлэгчид",
        "howto": "Хэрхэн тоглох вэ", "quit": "Гарах",
        "local": "Нэг компьютер дээр 2 хүн", "ai": "Ботын эсрэг тоглох",
        "easy": "Хялбар", "normal": "Дунд", "expert": "Мастер",
        "back": "Буцах", "casual": "Энгийн онлайн", "ranked": "Зэрэглэлийн онлайн",
        "bullet": "Bullet · 1 мин", "blitz": "Blitz · 3 мин", "rapid": "Classic · 5 мин",
        "host": "Серверийн хаяг (host:port)", "connect": "Холбогдох",
        "searching": "Өрсөлдөгч хайж байна...", "cancel": "Цуцлах",
        "walls": "хана үлдсэн", "surrender": "Бууж өгөх", "rematch": "Дахин тоглох",
        "winner": "ЯЛАГЧ", "elo": "ELO", "matches": "Тоглолт", "winrate": "Ялалтын хувь",
        "wins": "Ялалт", "losses": "Ялагдал", "flag": "Улсын далбаа", "avatar": "Профайл зураг",
        "save": "Хадгалах", "top_elo": "Шилдэг ELO", "most_matches": "Хамгийн олон тоглолт",
        "rank": "№", "player": "Тоглогч", "result": "Үр дүн", "win": "Ялсан", "loss": "Хожигдсон",
        "opponent": "Өрсөлдөгч", "date": "Огноо", "empty": "Одоогоор мэдээлэл алга.",
        "horiz": "Хэвтээ", "vert": "Босоо",
        "disconnected": "Холболт тасарлаа.", "timeout": "Цаг дууслаа!",
        "your_turn": "ТАНЫ ЭЭЛЖ", "opp_turn": "ӨРСӨЛДӨГЧИЙН ЭЭЛЖ",
        "logged": "Нэвтэрсэн:", "logout": "Гарах", "connecting": "Холбогдож байна...",
        "opp_left": "Өрсөлдөгч тоглоомоос гарлаа.", "bot": "Бот",
        "rules": [
            "Зорилго: пешкээ самбарын эсрэг талын эгнээнд хамгийн түрүүнд хүргэх.",
            "Ээлж тутамдаа нэг нүүдэл хийх (дээш/доош/зүүн/баруун) эсвэл нэг хана тавина.",
            "Тодруулсан нүд дээр дарж нүүнэ. Нүднүүдийн уулзвар дээр дарж хана тавина.",
            "Хана тавихаасаа өмнө Хэвтээ / Босоо товчоор чиглэлийг нь сольж болно.",
            "Аль ч тоглогчийн замыг бүрэн хааж хана тавихыг хориглоно.",
            "Тоглогч тус бүр 10 хантай. Нүүр тулсан үедээ өрсөлдөгчөө үсэрч давна.",
        ],
    },
    "ko": {
        "title": "QUORIDOR", "pick_lang": "언어를 선택하세요",
        "signin": "로그인", "signup": "회원가입", "nick": "닉네임", "pw": "비밀번호",
        "guest": "게스트로 계속하기", "taken": "이미 사용 중인 이름입니다!",
        "nouser": "존재하지 않는 플레이어입니다.", "badpw": "비밀번호가 틀렸습니다.",
        "short": "닉네임과 비밀번호는 3자 이상이어야 합니다.",
        "menu": "메인 메뉴", "offline": "오프라인 플레이", "online": "온라인 플레이",
        "profile": "프로필", "history": "전적 기록", "lb": "리더보드",
        "howto": "게임 방법", "quit": "종료",
        "local": "한 컴퓨터로 2인", "ai": "봇과 대결",
        "easy": "쉬움", "normal": "보통", "expert": "전문가",
        "back": "뒤로", "casual": "일반 온라인", "ranked": "랭크 온라인",
        "bullet": "불릿 · 1분", "blitz": "블리츠 · 3분", "rapid": "클래식 · 5분",
        "host": "서버 주소 (host:port)", "connect": "접속",
        "searching": "상대를 찾는 중...", "cancel": "취소",
        "walls": "벽 남음", "surrender": "기권", "rematch": "재대결",
        "winner": "승자", "elo": "ELO", "matches": "경기 수", "winrate": "승률",
        "wins": "승", "losses": "패", "flag": "국기", "avatar": "프로필 사진",
        "save": "저장", "top_elo": "ELO 상위", "most_matches": "최다 경기",
        "rank": "#", "player": "플레이어", "result": "결과", "win": "승리", "loss": "패배",
        "opponent": "상대", "date": "날짜", "empty": "아직 기록이 없습니다.",
        "horiz": "가로", "vert": "세로",
        "disconnected": "연결이 끊겼습니다.", "timeout": "시간 초과!",
        "your_turn": "내 차례", "opp_turn": "상대 차례",
        "logged": "로그인:", "logout": "로그아웃", "connecting": "접속 중...",
        "opp_left": "상대가 게임을 떠났습니다.", "bot": "봇",
        "rules": [
            "목표: 내 말을 보드 반대편 줄까지 먼저 이동시키세요.",
            "자기 차례에는 한 칸 이동하거나 벽 하나를 놓습니다.",
            "강조된 칸을 클릭해 이동하고, 교차점을 클릭해 벽을 놓습니다.",
            "벽을 놓기 전에 가로 / 세로 버튼으로 방향을 바꿀 수 있습니다.",
            "어느 쪽이든 목표까지 가는 길을 완전히 막는 벽은 놓을 수 없습니다.",
            "각자 벽 10개. 서로 마주 보면 상대를 뛰어넘을 수 있습니다.",
        ],
    },
    "vi": {
        "title": "QUORIDOR", "pick_lang": "Chọn ngôn ngữ của bạn",
        "signin": "Đăng nhập", "signup": "Đăng ký", "nick": "Biệt danh", "pw": "Mật khẩu",
        "guest": "Tiếp tục với tư cách khách", "taken": "Tên này đã có người dùng!",
        "nouser": "Không tìm thấy người chơi.", "badpw": "Sai mật khẩu.",
        "short": "Biệt danh và mật khẩu cần ít nhất 3 ký tự.",
        "menu": "Menu chính", "offline": "Chơi ngoại tuyến", "online": "Chơi trực tuyến",
        "profile": "Hồ sơ", "history": "Lịch sử trận", "lb": "Bảng xếp hạng",
        "howto": "Cách chơi", "quit": "Thoát",
        "local": "2 người một máy", "ai": "Đấu với máy",
        "easy": "Dễ", "normal": "Thường", "expert": "Chuyên gia",
        "back": "Quay lại", "casual": "Trực tuyến thường", "ranked": "Xếp hạng",
        "bullet": "Bullet · 1 phút", "blitz": "Blitz · 3 phút", "rapid": "Classic · 5 phút",
        "host": "Địa chỉ máy chủ (host:port)", "connect": "Kết nối",
        "searching": "Đang tìm đối thủ...", "cancel": "Hủy",
        "walls": "tường còn lại", "surrender": "Đầu hàng", "rematch": "Chơi lại",
        "winner": "NGƯỜI THẮNG", "elo": "ELO", "matches": "Số trận", "winrate": "Tỉ lệ thắng",
        "wins": "Thắng", "losses": "Thua", "flag": "Quốc kỳ", "avatar": "Ảnh đại diện",
        "save": "Lưu", "top_elo": "ELO cao nhất", "most_matches": "Nhiều trận nhất",
        "rank": "#", "player": "Người chơi", "result": "Kết quả", "win": "Thắng", "loss": "Thua",
        "opponent": "Đối thủ", "date": "Ngày", "empty": "Chưa có dữ liệu.",
        "horiz": "Ngang", "vert": "Dọc",
        "disconnected": "Mất kết nối.", "timeout": "Hết giờ!",
        "your_turn": "LƯỢT CỦA BẠN", "opp_turn": "LƯỢT ĐỐI THỦ",
        "logged": "Đã đăng nhập:", "logout": "Đăng xuất", "connecting": "Đang kết nối...",
        "opp_left": "Đối thủ đã rời trận.", "bot": "Máy",
        "rules": [
            "Mục tiêu: đưa quân của bạn tới hàng đối diện trước tiên.",
            "Mỗi lượt bạn đi một ô hoặc đặt một bức tường.",
            "Bấm vào ô được đánh dấu để đi. Bấm vào giao điểm để đặt tường.",
            "Dùng nút Ngang / Dọc để xoay hướng tường trước khi đặt.",
            "Không được đặt tường chặn hoàn toàn đường về đích của bất kỳ ai.",
            "Mỗi người có 10 tường. Khi đối mặt, bạn có thể nhảy qua đối thủ.",
        ],
    },
}

TC_SECONDS = {"none": 0, "bullet": 60, "blitz": 180, "rapid": 300}


# ==========================================================================
#  FONTS & DRAW HELPERS
# ==========================================================================
_FONTS = {}
_FONT_PATH = None


def _find_font_path():
    """Pick a real, installed system font file that can render Unicode
    (Mongolian Cyrillic + Korean + Vietnamese diacritics), so text never
    silently comes out as blank glyphs. Tries Windows / macOS / Linux
    names, in order of how much script coverage they have."""
    global _FONT_PATH
    if _FONT_PATH is not None:
        return _FONT_PATH or None

    candidates = [
        # Windows — Malgun Gothic covers Korean + Cyrillic (Mongolian) well
        "malgungothic", "malgun gothic", "segoeui", "segoe ui", "arial",
        # macOS
        "applesdgothicneo", "helvetica",
        # Linux
        "notosanscjkkr", "notosanskr", "notosans", "nanumgothic",
        "dejavusans", "liberationsans", "freesans",
    ]
    for name in candidates:
        try:
            p = pygame.font.match_font(name)
        except Exception:
            p = None
        if p:
            _FONT_PATH = p
            print(f"[font] using system font: {name} -> {p}")
            return p

    # last resort: scan every installed font pygame knows about for
    # anything that looks like it has broad coverage
    try:
        for name in pygame.font.get_fonts():
            low = name.lower()
            if any(k in low for k in ("noto", "malgun", "gothic", "unicode", "arial", "dejavu")):
                p = pygame.font.match_font(name)
                if p:
                    _FONT_PATH = p
                    print(f"[font] using scanned system font: {name} -> {p}")
                    return p
    except Exception:
        pass

    print("[font] WARNING: no Unicode-capable system font found; "
          "falling back to pygame's built-in default font. "
          "Mongolian/Korean/Vietnamese text may not render correctly.")
    _FONT_PATH = ""
    return None


def font(size, bold=False):
    key = (size, bold)
    f = _FONTS.get(key)
    if f is None:
        path = _find_font_path()
        try:
            f = pygame.font.Font(path, size) if path else pygame.font.SysFont(None, size)
        except Exception:
            f = pygame.font.SysFont(None, size)
        f.set_bold(bold)
        _FONTS[key] = f
    return f


def text(surf, s, pos, size=18, color=INK, bold=False, align="left"):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if align == "center":
        r.center = pos
    elif align == "right":
        r.midright = pos
    elif align == "midleft":
        r.midleft = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def card(surf, rect, radius=16, fill=WHITE, border=LINE, shadow=True):
    rect = pygame.Rect(rect)
    if shadow:
        sh = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
        pygame.draw.rect(sh, (24, 32, 48, 22), (12, 14, rect.w, rect.h), border_radius=radius)
        surf.blit(sh, (rect.x - 12, rect.y - 10))
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, 1, border_radius=radius)
    return rect


def ball(surf, center, radius, color):
    dark = tuple(max(0, c - 55) for c in color)
    light = tuple(min(255, c + 70) for c in color)
    pygame.draw.circle(surf, dark, center, radius)
    pygame.draw.circle(surf, color, (center[0], center[1] - 1), radius - 2)
    pygame.draw.circle(surf, light, (center[0] - radius // 3, center[1] - radius // 3),
                       max(2, radius // 4))
    glare = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(glare, (255, 255, 255, 70), (radius, radius - radius // 3),
                       max(2, radius // 2))
    surf.blit(glare, (center[0] - radius, center[1] - radius))


def draw_flag(surf, rect, code):
    rect = pygame.Rect(rect)
    layout, colors, dot = FLAGS.get(code, FLAGS["UN"])
    pygame.draw.rect(surf, colors[0], rect, border_radius=4)
    if layout == "h":
        h = rect.h / len(colors)
        for i, c in enumerate(colors):
            pygame.draw.rect(surf, c, (rect.x, rect.y + i * h, rect.w, math.ceil(h)))
    elif layout == "v":
        w = rect.w / len(colors)
        for i, c in enumerate(colors):
            pygame.draw.rect(surf, c, (rect.x + i * w, rect.y, math.ceil(w), rect.h))
    if dot:
        pygame.draw.circle(surf, dot, rect.center, max(3, rect.h // 3))
    pygame.draw.rect(surf, (210, 214, 222), rect, 1, border_radius=4)



def draw_avatar(surf, center, radius, pfp, flag=None):
    ball(surf, center, radius, PFP_COLORS[int(pfp) % len(PFP_COLORS)])
    if flag:
        fr = pygame.Rect(0, 0, radius, int(radius * 0.7))
        fr.center = (center[0] + radius - 4, center[1] + radius - 4)
        draw_flag(surf, fr, flag)


def background(surf):
    surf.fill(BG)
    for x in range(0, W, 40):
        pygame.draw.line(surf, GRID_LINE, (x, 0), (x, H))
    for y in range(0, H, 40):
        pygame.draw.line(surf, GRID_LINE, (0, y), (W, y))
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.circle(glow, (211, 66, 66, 12), (int(W * 0.12), int(H * 0.16)), 260)
    pygame.draw.circle(glow, (52, 96, 186, 12), (int(W * 0.9), int(H * 0.86)), 300)
    surf.blit(glow, (0, 0))


# ==========================================================================
#  WIDGETS
# ==========================================================================
class Button:
    def __init__(self, rect, label, on_click=None, kind="primary",
                 color=DARK, size=19, enabled=True, icon=None, data=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.kind = kind            # primary | ghost | danger | soft
        self.color = color
        self.size = size
        self.enabled = enabled
        self.icon = icon            # None | 'h' | 'v'
        self.data = data
        self.hover = False
        self.active = False

    def handle(self, e):
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.enabled and self.rect.collidepoint(e.pos):
                if self.on_click:
                    self.on_click(self)
                return True
        return False

    def draw(self, surf):
        r = self.rect
        hov = self.hover and self.enabled
        if self.kind == "primary":
            base = self.color if self.enabled else (188, 192, 200)
            fill = tuple(min(255, c + 18) for c in base) if hov else base
            card(surf, r, 14, fill, None, shadow=self.enabled)
            text(surf, self.label, r.center, self.size, WHITE, True, "center")
        elif self.kind == "danger":
            fill = RED if not hov else tuple(min(255, c + 18) for c in RED)
            card(surf, r, 14, fill, None, shadow=True)
            text(surf, self.label, r.center, self.size, WHITE, True, "center")
        elif self.kind == "soft":
            fill = SOFT if not hov else (233, 238, 246)
            border = self.color if self.active else LINE
            card(surf, r, 14, fill, border, shadow=False)
            if self.active:
                pygame.draw.rect(surf, self.color, r, 2, border_radius=14)
            self._icon(surf, r)
            if self.label:
                text(surf, self.label, r.center, self.size, INK if self.enabled else MUTED,
                     True, "center")
        else:  # ghost
            fill = WHITE if not hov else (248, 250, 253)
            card(surf, r, 14, fill, LINE, shadow=hov)
            text(surf, self.label, r.center, self.size, INK, False, "center")

    def _icon(self, surf, r):
        if self.icon == "h":
            pygame.draw.rect(surf, DARK, (r.centerx - 22, r.centery - 5, 44, 10), border_radius=5)
        elif self.icon == "v":
            pygame.draw.rect(surf, DARK, (r.centerx - 5, r.centery - 22, 10, 44), border_radius=5)


class TextInput:
    def __init__(self, rect, placeholder="", password=False, maxlen=24):
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.password = password
        self.maxlen = maxlen
        self.text = ""
        self.active = False

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(e.pos)
        elif e.type == pygame.KEYDOWN and self.active:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "submit"
            elif e.key == pygame.K_TAB:
                return "tab"
            elif e.key == pygame.K_v and (e.mod & pygame.KMOD_CTRL):
                pass
            elif e.unicode and e.unicode.isprintable() and len(self.text) < self.maxlen:
                self.text += e.unicode
        return None

    def draw(self, surf):
        r = self.rect
        card(surf, r, 12, WHITE, (108, 132, 190) if self.active else LINE, shadow=False)
        if self.active:
            pygame.draw.rect(surf, (108, 132, 190), r, 2, border_radius=12)
        shown = ("•" * len(self.text)) if self.password else self.text
        col = INK if self.text else MUTED
        label = shown if self.text else self.placeholder
        img = font(19).render(label, True, col)
        surf.blit(img, (r.x + 14, r.centery - img.get_height() // 2))
        if self.active and (pygame.time.get_ticks() // 500) % 2 == 0:
            cx = r.x + 15 + (font(19).size(shown)[0] if self.text else 0)
            pygame.draw.line(surf, INK, (cx, r.centery - 11), (cx, r.centery + 11), 2)


# ==========================================================================
#  GAME ENGINE
# ==========================================================================
N = 9


class Game:
    """Player 0 = RED, starts at the bottom row and must reach row 0.
       Player 1 = BLUE, starts at the top row and must reach row 8."""

    def __init__(self, walls=10):
        self.pawn = [(8, 4), (0, 4)]
        self.goal = [0, 8]
        self.walls = [walls, walls]
        self.h = set()
        self.v = set()
        self.turn = 0
        self.winner = None

    def clone(self):
        g = Game()
        g.pawn = list(self.pawn)
        g.walls = list(self.walls)
        g.h = set(self.h)
        g.v = set(self.v)
        g.turn = self.turn
        g.winner = self.winner
        return g

    # -- movement -----------------------------------------------------
    def blocked(self, r, c, nr, nc):
        if nr == r + 1:
            return (r, c) in self.h or (r, c - 1) in self.h
        if nr == r - 1:
            return (r - 1, c) in self.h or (r - 1, c - 1) in self.h
        if nc == c + 1:
            return (r, c) in self.v or (r - 1, c) in self.v
        if nc == c - 1:
            return (r, c - 1) in self.v or (r - 1, c - 1) in self.v
        return True

    def moves(self, p):
        res = set()
        r, c = self.pawn[p]
        orr, occ = self.pawn[1 - p]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < N and 0 <= nc < N):
                continue
            if self.blocked(r, c, nr, nc):
                continue
            if (nr, nc) == (orr, occ):
                jr, jc = nr + dr, nc + dc
                if 0 <= jr < N and 0 <= jc < N and not self.blocked(nr, nc, jr, jc):
                    res.add((jr, jc))
                else:
                    for sr, sc in ((dc, dr), (-dc, -dr)):
                        ar, ac = nr + sr, nc + sc
                        if 0 <= ar < N and 0 <= ac < N and not self.blocked(nr, nc, ar, ac):
                            res.add((ar, ac))
            else:
                res.add((nr, nc))
        return res

    # -- walls --------------------------------------------------------
    def wall_free(self, o, r, c):
        if not (0 <= r < N - 1 and 0 <= c < N - 1):
            return False
        if (r, c) in self.h or (r, c) in self.v:
            return False
        if o == "h":
            return not ((r, c - 1) in self.h or (r, c + 1) in self.h)
        return not ((r - 1, c) in self.v or (r + 1, c) in self.v)

    def can_wall(self, o, r, c, player=None):
        if player is not None and self.walls[player] <= 0:
            return False
        if not self.wall_free(o, r, c):
            return False
        target = self.h if o == "h" else self.v
        target.add((r, c))
        ok = self.dist(0) is not None and self.dist(1) is not None
        target.discard((r, c))
        return ok

    # -- search -------------------------------------------------------
    def dist(self, p):
        start = self.pawn[p]
        goal = self.goal[p]
        seen = {start}
        q = deque([(start, 0)])
        while q:
            (r, c), d = q.popleft()
            if r == goal:
                return d
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < N and 0 <= nc < N and (nr, nc) not in seen \
                        and not self.blocked(r, c, nr, nc):
                    seen.add((nr, nc))
                    q.append(((nr, nc), d + 1))
        return None

    def step_towards_goal(self, p):
        """First cell on a shortest path (ignoring the opponent pawn)."""
        start = self.pawn[p]
        goal = self.goal[p]
        prev = {start: None}
        q = deque([start])
        end = None
        while q:
            cur = q.popleft()
            if cur[0] == goal:
                end = cur
                break
            r, c = cur
            for nxt in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nxt[0] < N and 0 <= nxt[1] < N and nxt not in prev \
                        and not self.blocked(r, c, nxt[0], nxt[1]):
                    prev[nxt] = cur
                    q.append(nxt)
        if end is None:
            return None
        node = end
        while prev[node] is not None and prev[node] != start:
            node = prev[node]
        return node

    # -- apply --------------------------------------------------------
    def apply(self, mv, player=None):
        p = self.turn if player is None else player
        if mv[0] == "pawn":
            self.pawn[p] = (mv[1], mv[2])
            if self.pawn[p][0] == self.goal[p]:
                self.winner = p
        else:
            o, r, c = mv[1], mv[2], mv[3]
            (self.h if o == "h" else self.v).add((r, c))
            self.walls[p] = max(0, self.walls[p] - 1)
        self.turn = 1 - p
        return mv


# --------------------------------------------------------------------------
#  AI
# --------------------------------------------------------------------------
def _best_pawn_move(g, p):
    best, best_d = None, 10 ** 6
    for (r, c) in g.moves(p):
        t = g.clone()
        t.pawn[p] = (r, c)
        if r == g.goal[p]:
            return ("pawn", r, c)
        d = t.dist(p)
        if d is None:
            continue
        if d < best_d:
            best_d, best = d, ("pawn", r, c)
    if best is None:
        mv = list(g.moves(p))
        if not mv:
            return None
        r, c = random.choice(mv)
        best = ("pawn", r, c)
    return best


def _wall_candidates(g, p, limit=36):
    """Intersections around the opponent's shortest path."""
    o = 1 - p
    cells = [g.pawn[o]]
    t = g.clone()
    guard = 0
    while guard < 20:
        guard += 1
        nxt = t.step_towards_goal(o)
        if nxt is None or nxt[0] == t.goal[o]:
            if nxt:
                cells.append(nxt)
            break
        cells.append(nxt)
        t.pawn[o] = nxt
    out = []
    seen = set()
    for (r, c) in cells:
        for dr in (-1, 0):
            for dc in (-1, 0):
                rr, cc = r + dr, c + dc
                for orient in ("h", "v"):
                    key = (orient, rr, cc)
                    if key in seen:
                        continue
                    seen.add(key)
                    if g.wall_free(orient, rr, cc):
                        out.append(key)
    random.shuffle(out)
    return out[:limit]


def ai_choose(g, p, level):
    """level 0=easy 1=normal 2=expert. Returns a move tuple."""
    o = 1 - p
    my_d = g.dist(p) or 99
    op_d = g.dist(o) or 99

    if level == 0:
        if random.random() < 0.3:
            mv = list(g.moves(p))
            if mv:
                r, c = random.choice(mv)
                return ("pawn", r, c)
        if g.walls[p] > 0 and random.random() < 0.12:
            for orient, r, c in _wall_candidates(g, p, 8):
                if g.can_wall(orient, r, c, p):
                    return ("wall", orient, r, c)
        return _best_pawn_move(g, p)

    # --- normal / expert : score every reasonable option --------------
    best_move, best_score = None, -10 ** 6
    for (r, c) in g.moves(p):
        t = g.clone()
        t.pawn[p] = (r, c)
        if r == g.goal[p]:
            return ("pawn", r, c)
        md = t.dist(p)
        od = t.dist(o)
        if md is None or od is None:
            continue
        score = od - md * 1.15
        if score > best_score:
            best_score, best_move = score, ("pawn", r, c)

    if g.walls[p] > 0 and (level == 2 or op_d <= my_d):
        limit = 40 if level == 2 else 16
        penalty = 0.6 if level == 2 else 1.4
        for orient, r, c in _wall_candidates(g, p, limit):
            if not g.can_wall(orient, r, c, p):
                continue
            t = g.clone()
            (t.h if orient == "h" else t.v).add((r, c))
            md = t.dist(p)
            od = t.dist(o)
            if md is None or od is None:
                continue
            score = od - md * 1.15 - penalty
            if level == 2 and g.walls[p] < 3:
                score -= 1.0
            if score > best_score:
                best_score, best_move = score, ("wall", orient, r, c)

    return best_move or _best_pawn_move(g, p)


# ==========================================================================
#  NETWORK CLIENT
# ==========================================================================
class Net:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=8)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.q = queue.Queue()
        self.alive = True
        threading.Thread(target=self._rx, daemon=True).start()

    def _rx(self):
        buf = b""
        try:
            while self.alive:
                data = self.sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            self.q.put(json.loads(line.decode("utf-8")))
                        except ValueError:
                            pass
        except OSError:
            pass
        self.alive = False
        self.q.put({"t": "disconnected"})

    def send(self, obj):
        if not self.alive:
            return
        try:
            self.sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


# ==========================================================================
#  APPLICATION
# ==========================================================================
class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Quoridor")
        self.sc = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        db.init_db()

        self.lang = None
        self.user = None            # dict or None (guest)
        self.screen = "lang"
        self.msg = ""
        self.msg_color = RED
        self.btns = []
        self.modal = None           # 'howto' | None
        self.running = True

        self.inp_nick = TextInput((0, 0, 360, 52), "", False, 16)
        self.inp_pw = TextInput((0, 0, 360, 52), "", True, 24)

        self.net = None
        self.lb_kind = "elo"
        self.lb_rows = []
        self.hist_rows = []
        self.scroll = 0

        # match state
        self.g = None
        self.online = False
        self.ranked = False
        self.my_color = 0
        self.ai_level = None
        self.tc = 0
        self.clocks = [0, 0]
        self.last_tick = 0
        self.drag = None            # {'orient':'h'/'v', 'pos':(x,y)} while dragging a wall tile
        self.wall_owner = {}
        self.anim = None
        self.wall_anim = []
        self.over = None            # {"winner":i,"reason":..,"delta":..}
        self.ai_at = 0
        self.names = ["RED", "BLUE"]
        self.faces = [{"pfp": 0, "flag": "UN", "elo": 1000},
                      {"pfp": 1, "flag": "UN", "elo": 1000}]

        # IMPORTANT: build the widget list for the very first screen.
        # Without this call self.btns stays [] until the first goto(),
        # so the language buttons exist nowhere to be drawn (this was
        # the bug behind "buttons completely invisible" on launch).
        self.build()

    # ------------------------------------------------------------------
    def t(self, key):
        d = T.get(self.lang or "en", T["en"])
        return d.get(key, T["en"].get(key, key))

    def flash(self, message, color=RED):
        self.msg = message
        self.msg_color = color

    def goto(self, screen):
        self.screen = screen
        self.msg = ""
        self.scroll = 0
        self.build()

    # ==================================================================
    #  SCREEN BUILDERS
    # ==================================================================
    def build(self):
        self.btns = []
        b = self.btns
        s = self.screen
        cx = W // 2

        if s == "lang":
            for i, (code, label) in enumerate(LANGS):
                r = (cx - 330 + (i % 2) * 340, 330 + (i // 2) * 90, 320, 68)
                b.append(Button(r, label, self.on_lang, "ghost", size=22, data=code))

        elif s == "auth":
            self.inp_nick.rect.topleft = (cx - 180, 300)
            self.inp_pw.rect.topleft = (cx - 180, 392)
            b.append(Button((cx - 180, 470, 172, 54), self.t("signin"), self.on_signin))
            b.append(Button((cx + 8, 470, 172, 54), self.t("signup"), self.on_signup,
                            "primary", BLUE))
            b.append(Button((cx - 180, 540, 360, 48), self.t("guest"), self.on_guest, "ghost"))

        elif s == "menu":
            items = [("offline", self.t("offline")), ("online", self.t("online")),
                     ("profile", self.t("profile")), ("history", self.t("history")),
                     ("lb", self.t("lb")), ("howto", self.t("howto"))]
            for i, (key, label) in enumerate(items):
                x = cx - 330 + (i % 2) * 340
                y = 280 + (i // 2) * 84
                kind = "primary" if i < 2 else "ghost"
                col = DARK if i == 0 else BLUE
                b.append(Button((x, y, 320, 66), label, self.on_menu, kind, col,
                                size=21, data=key))
            b.append(Button((cx - 90, 560, 180, 50), self.t("quit"),
                            lambda _b: self.quit(), "ghost"))
            if self.user:
                b.append(Button((W - 170, 40, 130, 42), self.t("logout"),
                                self.on_logout, "ghost", size=16))

        elif s == "offline":
            b.append(Button((cx - 200, 260, 400, 66), self.t("local"),
                            lambda _b: self.start_offline(None), "primary", DARK, 21))
            for i, (lvl, key) in enumerate([(0, "easy"), (1, "normal"), (2, "expert")]):
                b.append(Button((cx - 200, 370 + i * 80, 400, 62),
                                f"{self.t('ai')} · {self.t(key)}",
                                lambda bt: self.start_offline(bt.data), "ghost",
                                size=20, data=lvl))
            b.append(Button((cx - 90, 630, 180, 50), self.t("back"),
                            lambda _b: self.goto("menu"), "ghost"))

        elif s == "online":
            b.append(Button((cx - 210, 280, 420, 58), self.t("casual"),
                            lambda _b: self.start_online("casual", "none"), "primary", DARK, 20))
            for i, key in enumerate(["bullet", "blitz", "rapid"]):
                b.append(Button((cx - 210, 360 + i * 74, 420, 58),
                                f"{self.t('ranked')} · {self.t(key)}",
                                lambda bt: self.start_online("ranked", bt.data),
                                "primary", BLUE, 19, data=key))
            b.append(Button((cx - 90, 640, 180, 50), self.t("back"),
                            lambda _b: self.goto("menu"), "ghost"))

        elif s == "queue":
            b.append(Button((cx - 90, 470, 180, 52), self.t("cancel"),
                            lambda _b: self.cancel_queue(), "ghost"))

        elif s == "profile":
            for i in range(8):
                r = (cx - 280 + (i % 4) * 90, 300 + (i // 4) * 90, 70, 70)
                bt = Button(r, "", self.on_pick_pfp, "soft", BLUE, data=i)
                bt.active = bool(self.user) and self.user.get("pfp", 0) == i
                b.append(bt)
            for i, code in enumerate(FLAG_CODES):
                r = (cx - 280 + (i % 7) * 82, 500 + (i // 7) * 66, 64, 48)
                bt = Button(r, "", self.on_pick_flag, "soft", BLUE, data=code)
                bt.active = bool(self.user) and self.user.get("flag", "UN") == code
                b.append(bt)
            b.append(Button((cx - 90, 660, 180, 50), self.t("back"),
                            lambda _b: self.goto("menu"), "ghost"))

        elif s == "history":
            b.append(Button((cx - 90, 700, 180, 50), self.t("back"),
                            lambda _b: self.goto("menu"), "ghost"))

        elif s == "lb":
            b.append(Button((cx - 310, 190, 300, 52), self.t("top_elo"),
                            lambda _b: self.load_lb("elo"), "soft", BLUE, 18))
            b.append(Button((cx + 10, 190, 300, 52), self.t("most_matches"),
                            lambda _b: self.load_lb("matches"), "soft", BLUE, 18))
            self.btns[0].active = self.lb_kind == "elo"
            self.btns[1].active = self.lb_kind == "matches"
            b.append(Button((cx - 90, 700, 180, 50), self.t("back"),
                            lambda _b: self.goto("menu"), "ghost"))

        elif s == "game":
            b.append(Button((W - 190, 706, 150, 56), self.t("surrender"),
                            lambda _b: self.surrender(), "danger", size=18))
            if self.over:
                b.append(Button((cx - 200, 470, 190, 56), self.t("rematch"),
                                lambda _b: self.rematch(), "primary", DARK, 19))
                b.append(Button((cx + 10, 470, 190, 56), self.t("menu"),
                                lambda _b: self.leave_game(), "ghost", size=19))

        if self.modal == "howto":
            self.btns = [Button((W // 2 + 268, 150, 44, 44), "X",
                                lambda _b: self.close_modal(), "ghost", size=18)]

    # ==================================================================
    #  CALLBACKS
    # ==================================================================
    def on_lang(self, bt):
        self.lang = bt.data
        self.goto("auth")

    def on_signin(self, _b):
        ok, res = db.login(self.inp_nick.text, self.inp_pw.text)
        if ok:
            self.user = res
            self.goto("menu")
        else:
            self.flash(self.t(res))

    def on_signup(self, _b):
        ok, res = db.create_user(self.inp_nick.text, self.inp_pw.text)
        if ok:
            self.user = res
            self.goto("menu")
        else:
            self.flash(self.t(res))

    def on_guest(self, _b):
        self.user = None
        self.goto("menu")

    def on_logout(self, _b):
        self.user = None
        self.close_net()
        self.goto("auth")

    def on_menu(self, bt):
        key = bt.data
        if key == "howto":
            self.modal = "howto"
            self.build()
        elif key == "history":
            self.load_history()
        elif key == "lb":
            self.load_lb(self.lb_kind)
        elif key == "profile":
            if not self.user:
                self.flash(self.t("nouser"))
            else:
                self.goto("profile")
        else:
            self.goto(key)

    def on_pick_pfp(self, bt):
        if self.user:
            self.user = db.set_profile(self.user["nickname"], bt.data, self.user["flag"])
            if self.net and self.net.alive:
                self.net.send({"t": "setprofile", "pfp": self.user["pfp"],
                               "flag": self.user["flag"]})
            self.build()

    def on_pick_flag(self, bt):
        if self.user:
            self.user = db.set_profile(self.user["nickname"], self.user["pfp"], bt.data)
            if self.net and self.net.alive:
                self.net.send({"t": "setprofile", "pfp": self.user["pfp"],
                               "flag": self.user["flag"]})
            self.build()

    def close_modal(self):
        self.modal = None
        self.build()

    def quit(self):
        self.running = False

    # ==================================================================
    #  DATA LOADING
    # ==================================================================
    def load_history(self):
        self.hist_rows = []
        if self.net and self.net.alive:
            self.net.send({"t": "history"})
        elif self.user:
            self.hist_rows = db.history(self.user["nickname"], 50)
        self.goto("history")

    def load_lb(self, kind):
        self.lb_kind = kind
        if self.net and self.net.alive:
            self.lb_rows = []
            self.net.send({"t": "leaderboard", "kind": kind})
        else:
            self.lb_rows = db.leaderboard(kind, 20)
        self.goto("lb")

    # ==================================================================
    #  MATCH SET-UP
    # ==================================================================
    def start_offline(self, ai_level):
        self.close_net()
        self.online = False
        self.ranked = False
        self.ai_level = ai_level
        self.my_color = 0
        self.tc = 0
        self.new_match()
        me = self.user or {"nickname": "Player 1", "pfp": 0, "flag": "UN", "elo": 1000}
        if ai_level is None:
            self.names = [me["nickname"], "Player 2"]
            self.faces = [me, {"pfp": 1, "flag": "UN", "elo": me["elo"]}]
        else:
            lvl = [self.t("easy"), self.t("normal"), self.t("expert")][ai_level]
            self.names = [me["nickname"], f"{self.t('bot')} · {lvl}"]
            self.faces = [me, {"pfp": 7, "flag": "UN", "elo": 1000 + ai_level * 250}]
        self.goto("game")

    def start_online(self, mode, tc_key):
        if not self.user:
            self.flash(self.t("nouser"))
            return
        self.flash(self.t("connecting"), MUTED)
        try:
            self.close_net()
            self.net = Net(DEFAULT_HOST, DEFAULT_PORT)
        except OSError:
            self.flash(self.t("disconnected"))
            return
        self.pending_queue = (mode, tc_key)
        self.net.send({"t": "auth", "nick": self.user["nickname"], "pw": self._pw()})
        self.goto("queue")

    def _pw(self):
        return self.inp_pw.text or "guest-pass"

    def cancel_queue(self):
        if self.net and self.net.alive:
            self.net.send({"t": "cancel"})
        self.close_net()
        self.goto("online")

    def new_match(self):
        self.g = Game()
        self.over = None
        self.wall_owner = {}
        self.wall_anim = []
        self.anim = None
        self.drag = None
        self.clocks = [self.tc, self.tc]
        self.last_tick = pygame.time.get_ticks()
        self.ai_at = 0

    def close_net(self):
        if self.net:
            try:
                self.net.send({"t": "leave"})
            except Exception:
                pass
            self.net.close()
        self.net = None

    def leave_game(self):
        self.drag = None
        if self.online:
            self.close_net()
        self.goto("menu")

    def surrender(self):
        if self.over or not self.g:
            return
        if self.online:
            self.net.send({"t": "resign"})
        else:
            self.finish(1 - self.g.turn, "resign")

    def rematch(self):
        if self.online:
            if self.net and self.net.alive:
                self.net.send({"t": "rematch"})
                self.flash(self.t("searching"), MUTED)
        else:
            self.new_match()
            self.build()

    def finish(self, winner, reason, delta=0):
        self.over = {"winner": winner, "reason": reason, "delta": delta}
        if not self.online and self.user and self.ai_level is not None:
            lvl = [self.t("easy"), self.t("normal"), self.t("expert")][self.ai_level]
            u = db.record_local(self.user["nickname"], f"{self.t('bot')} {lvl}",
                                winner == 0, "ai")
            if u:
                self.user = u
        self.build()

    # ==================================================================
    #  MOVE HANDLING
    # ==================================================================
    def my_turn(self):
        if not self.g or self.over:
            return False
        if self.online:
            return self.g.turn == self.my_color
        if self.ai_level is not None:
            return self.g.turn == 0
        return True

    def do_move(self, mv, local=True):
        p = self.g.turn
        if mv[0] == "pawn":
            self.anim = {"p": p, "from": self.g.pawn[p], "to": (mv[1], mv[2]),
                         "t0": pygame.time.get_ticks()}
        else:
            self.wall_owner[(mv[1], mv[2], mv[3])] = p
            self.wall_anim.append({"mv": mv, "t0": pygame.time.get_ticks()})
        self.g.apply(mv, p)
        if local and self.online and self.net:
            self.net.send({"t": "move", "mv": list(mv)})
        if self.g.winner is not None:
            if self.online:
                if local:
                    self.net.send({"t": "win", "color": p})
            else:
                self.finish(self.g.winner, "goal")
        elif not self.online and self.ai_level is not None and self.g.turn == 1:
            self.ai_at = pygame.time.get_ticks() + 420

    def board_click(self, pos):
        """Clicking the board (pawn or a highlighted dot) only ever moves the
        pawn. Walls are placed exclusively by dragging a tile from the tray,
        so there is no implicit 'wall mode' left active from a previous turn."""
        if not self.my_turn() or self.anim:
            return
        cell = self.cell_at(pos)
        if cell and cell in self.g.moves(self.g.turn):
            self.do_move(("pawn", cell[0], cell[1]))

    def cell_at(self, pos):
        mx, my = pos
        step = CELL + GAP
        c = int((mx - BX) // step)
        r = int((my - BY) // step)
        if 0 <= r < N and 0 <= c < N:
            rect = pygame.Rect(BX + c * step, BY + r * step, CELL, CELL)
            if rect.collidepoint(pos):
                return (r, c)
        return None

    def hover_wall(self, pos):
        if not self.g or self.over:
            return None
        mx, my = pos
        step = CELL + GAP
        c = int(round((mx - BX - CELL - GAP / 2) / step))
        r = int(round((my - BY - CELL - GAP / 2) / step))
        if not (0 <= r < N - 1 and 0 <= c < N - 1):
            return None
        cx = BX + (c + 1) * step - GAP / 2
        cy = BY + (r + 1) * step - GAP / 2
        if abs(mx - cx) > CELL * 0.58 or abs(my - cy) > CELL * 0.58:
            return None
        return (r, c)

    # ==================================================================
    #  NETWORK EVENTS
    # ==================================================================
    def pump_net(self):
        if not self.net:
            return
        while True:
            try:
                m = self.net.q.get_nowait()
            except queue.Empty:
                return
            t = m.get("t")
            if t == "auth_ok":
                self.user = m["user"]
                mode, tc_key = getattr(self, "pending_queue", ("casual", "none"))
                self.net.send({"t": "queue", "mode": mode, "tc": tc_key})
            elif t == "auth_err":
                self.flash(self.t(m.get("code", "nouser")))
                self.close_net()
                self.goto("online")
            elif t == "start":
                self.online = True
                self.ai_level = None
                self.my_color = m["color"]
                self.ranked = bool(m.get("ranked"))
                self.tc = int(m.get("tc", 0))
                me, opp = m.get("me") or {}, m.get("opp") or {}
                self.new_match()
                if self.my_color == 0:
                    self.names = [me.get("nickname", "P1"), opp.get("nickname", "P2")]
                    self.faces = [me, opp]
                else:
                    self.names = [opp.get("nickname", "P1"), me.get("nickname", "P2")]
                    self.faces = [opp, me]
                self.goto("game")
            elif t == "move":
                mv = tuple(m.get("mv") or ())
                if self.g and not self.over and mv:
                    self.do_move(mv, local=False)
            elif t == "over":
                if self.g:
                    self.over = {"winner": m.get("winner", 0),
                                 "reason": m.get("reason", "goal"),
                                 "delta": m.get("delta", 0)}
                    if m.get("user"):
                        self.user = m["user"]
                        if self.my_color == 0:
                            self.faces[0] = self.user
                        else:
                            self.faces[1] = self.user
                    self.build()
            elif t == "history":
                self.hist_rows = m.get("rows", [])
            elif t == "leaderboard":
                self.lb_kind = m.get("kind", "elo")
                self.lb_rows = m.get("rows", [])
                self.build()
            elif t == "profile":
                self.user = m.get("user") or self.user
            elif t == "opp_left":
                self.flash(self.t("opp_left"), MUTED)
            elif t == "disconnected":
                self.net = None
                if self.screen in ("queue",):
                    self.flash(self.t("disconnected"))
                    self.goto("online")
                elif self.screen == "game" and not self.over:
                    self.flash(self.t("disconnected"))

    # ==================================================================
    #  UPDATE
    # ==================================================================
    def update(self):
        now = pygame.time.get_ticks()
        self.pump_net()

        if self.anim and now - self.anim["t0"] > 200:
            self.anim = None
        self.wall_anim = [w for w in self.wall_anim if now - w["t0"] < 260]

        if self.screen == "game" and self.g and not self.over:
            # clocks
            if self.tc > 0:
                dt = (now - self.last_tick) / 1000.0
                self.last_tick = now
                turn = self.g.turn
                self.clocks[turn] = max(0.0, self.clocks[turn] - dt)
                if self.clocks[turn] <= 0:
                    if self.online:
                        if turn == self.my_color and self.net:
                            self.net.send({"t": "timeout"})
                    else:
                        self.finish(1 - turn, "timeout")
            else:
                self.last_tick = now
            # AI
            if (not self.online and self.ai_level is not None and self.g.turn == 1
                    and self.ai_at and now >= self.ai_at and not self.anim):
                self.ai_at = 0
                mv = ai_choose(self.g, 1, self.ai_level)
                if mv:
                    self.do_move(mv)
                else:
                    self.finish(0, "resign")

    # ==================================================================
    #  DRAWING — SCREENS
    # ==================================================================
    def draw(self):
        background(self.sc)
        s = self.screen
        if s == "lang":
            self.draw_lang()
        elif s == "auth":
            self.draw_auth()
        elif s == "menu":
            self.draw_menu()
        elif s == "offline":
            self.draw_simple(self.t("offline"))
        elif s == "online":
            self.draw_online()
        elif s == "queue":
            self.draw_queue()
        elif s == "profile":
            self.draw_profile()
        elif s == "history":
            self.draw_history()
        elif s == "lb":
            self.draw_lb()
        elif s == "game":
            self.draw_game()

        if self.modal == "howto":
            self.draw_howto()

        for b in self.btns:
            b.draw(self.sc)

        if self.msg and s != "game":
            text(self.sc, self.msg, (W // 2, H - 40), 18, self.msg_color, True, "center")
        pygame.display.flip()

    def title_block(self, subtitle=""):
        text(self.sc, self.t("title"), (W // 2, 110), 54, INK, True, "center")
        pygame.draw.rect(self.sc, RED, (W // 2 - 60, 142, 50, 5), border_radius=3)
        pygame.draw.rect(self.sc, BLUE, (W // 2 + 10, 142, 50, 5), border_radius=3)
        if subtitle:
            text(self.sc, subtitle, (W // 2, 185), 22, MUTED, False, "center")

    def draw_lang(self):
        self.title_block(self.t("pick_lang") if self.lang else "Choose your language")

    def draw_auth(self):
        self.title_block()
        card(self.sc, (W // 2 - 230, 230, 460, 400), 22)
        text(self.sc, self.t("nick"), (W // 2 - 180, 272), 17, MUTED, True)
        text(self.sc, self.t("pw"), (W // 2 - 180, 364), 17, MUTED, True)
        self.inp_nick.draw(self.sc)
        self.inp_pw.draw(self.sc)

    def draw_menu(self):
        self.title_block()
        if self.user:
            r = card(self.sc, (W // 2 - 230, 196, 460, 66), 18)
            draw_avatar(self.sc, (r.x + 40, r.centery), 22, self.user["pfp"], self.user["flag"])
            text(self.sc, self.user["nickname"], (r.x + 76, r.centery - 12), 20, INK, True)
            text(self.sc, f"{self.t('elo')} {self.user['elo']} · "
                          f"{self.t('matches')} {self.user['matches']} · "
                          f"{self.t('winrate')} {self.user['winrate']}%",
                 (r.x + 76, r.centery + 8), 15, MUTED)
        else:
            text(self.sc, self.t("guest"), (W // 2, 220), 18, MUTED, False, "center")

    def draw_simple(self, subtitle):
        self.title_block(subtitle)

    def draw_online(self):
        self.title_block(self.t("online"))
        text(self.sc, f"{self.t('host')}: {DEFAULT_HOST}", (W // 2, 218), 14, MUTED,
             False, "center")

    def draw_queue(self):
        self.title_block(self.t("searching"))
        cx, cy = W // 2, 380
        a = pygame.time.get_ticks() / 400.0
        for i in range(8):
            ang = a + i * math.pi / 4
            alpha = 60 + i * 22
            col = RED if i % 2 == 0 else BLUE
            pygame.draw.circle(self.sc, tuple(min(255, c + (255 - alpha) // 3) for c in col),
                               (int(cx + math.cos(ang) * 56), int(cy + math.sin(ang) * 56)),
                               8 - i // 3)

    def draw_profile(self):
        self.title_block(self.t("profile"))
        u = self.user
        r = card(self.sc, (W // 2 - 300, 200, 600, 80), 18)
        draw_avatar(self.sc, (r.x + 46, r.centery), 26, u["pfp"], u["flag"])
        text(self.sc, u["nickname"], (r.x + 88, r.centery - 14), 22, INK, True)
        text(self.sc, f"{self.t('elo')} {u['elo']}", (r.x + 88, r.centery + 10), 16, MUTED)
        text(self.sc, f"{self.t('matches')}: {u['matches']}", (r.right - 30, r.centery - 12),
             16, MUTED, False, "right")
        text(self.sc, f"{self.t('winrate')}: {u['winrate']}%", (r.right - 30, r.centery + 12),
             16, GREEN, True, "right")
        text(self.sc, self.t("avatar"), (W // 2 - 280, 272), 16, MUTED, True)
        text(self.sc, self.t("flag"), (W // 2 - 280, 472), 16, MUTED, True)
        for b in self.btns:
            if b.kind == "soft" and isinstance(b.data, int):
                draw_avatar(self.sc, b.rect.center, 22, b.data)
            elif b.kind == "soft" and isinstance(b.data, str):
                fr = pygame.Rect(0, 0, 40, 28)
                fr.center = b.rect.center
                draw_flag(self.sc, fr, b.data)

    def draw_history(self):
        self.title_block(self.t("history"))
        rows = self.hist_rows
        top = 230
        card(self.sc, (W // 2 - 380, top - 44, 760, 40), 12, SOFT, None, False)
        text(self.sc, self.t("opponent"), (W // 2 - 360, top - 24), 15, MUTED, True, "midleft")
        text(self.sc, self.t("result"), (W // 2, top - 24), 15, MUTED, True, "center")
        text(self.sc, self.t("elo"), (W // 2 + 360, top - 24), 15, MUTED, True, "right")
        if not rows:
            text(self.sc, self.t("empty"), (W // 2, 340), 18, MUTED, False, "center")
            return
        for i, row in enumerate(rows[:11]):
            y = top + i * 42
            rr = pygame.Rect(W // 2 - 380, y, 760, 38)
            card(self.sc, rr, 10, WHITE if i % 2 == 0 else (250, 251, 253), LINE, False)
            win = row["result"] == "win"
            text(self.sc, row["opponent"], (rr.x + 20, rr.centery), 17, INK, False, "midleft")
            text(self.sc, self.t("win") if win else self.t("loss"),
                 (rr.centerx, rr.centery), 16, GREEN if win else RED, True, "center")
            d = int(row["elo_delta"])
            txt = f"{'+' if d > 0 else ''}{d} {self.t('elo')}" if d else "—"
            text(self.sc, txt, (rr.right - 20, rr.centery), 16,
                 GREEN if d > 0 else (RED if d < 0 else MUTED), True, "right")
            ts = time.strftime("%Y-%m-%d", time.localtime(row.get("ts", time.time())))
            text(self.sc, ts, (rr.centerx + 180, rr.centery), 14, MUTED, False, "center")

    def draw_lb(self):
        self.title_block(self.t("lb"))
        rows = self.lb_rows
        top = 270
        if not rows:
            text(self.sc, self.t("empty"), (W // 2, 380), 18, MUTED, False, "center")
            return
        for i, row in enumerate(rows[:10]):
            y = top + i * 42
            rr = pygame.Rect(W // 2 - 380, y, 760, 38)
            card(self.sc, rr, 10, WHITE if i % 2 == 0 else (250, 251, 253), LINE, False)
            text(self.sc, f"{i + 1}", (rr.x + 24, rr.centery), 17,
                 (198, 152, 32) if i < 3 else MUTED, True, "center")
            draw_avatar(self.sc, (rr.x + 62, rr.centery), 13, row.get("pfp", 0))
            fr = pygame.Rect(0, 0, 26, 18)
            fr.center = (rr.x + 96, rr.centery)
            draw_flag(self.sc, fr, row.get("flag", "UN"))
            text(self.sc, row["nickname"], (rr.x + 120, rr.centery), 17, INK, True, "midleft")
            text(self.sc, f"{row['matches']} {self.t('matches')}",
                 (rr.right - 150, rr.centery), 15, MUTED, False, "right")
            text(self.sc, f"{row['elo']}", (rr.right - 24, rr.centery), 18, BLUE, True, "right")

    def draw_howto(self):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((16, 20, 30, 130))
        self.sc.blit(veil, (0, 0))
        r = card(self.sc, (W // 2 - 320, 140, 640, 440), 22)
        text(self.sc, self.t("howto"), (r.centerx, r.y + 46), 30, INK, True, "center")
        for i, line in enumerate(self.t("rules")):
            y = r.y + 110 + i * 52
            pygame.draw.circle(self.sc, RED if i % 2 == 0 else BLUE, (r.x + 44, y + 9), 5)
            words = line
            img = font(17).render(words, True, INK)
            if img.get_width() > r.w - 100:
                # simple wrap
                parts, cur = [], ""
                for wtok in words.split(" "):
                    if font(17).size(cur + " " + wtok)[0] > r.w - 100:
                        parts.append(cur)
                        cur = wtok
                    else:
                        cur = (cur + " " + wtok).strip()
                parts.append(cur)
                for k, part in enumerate(parts[:2]):
                    text(self.sc, part, (r.x + 64, y - 8 + k * 20), 16, INK)
            else:
                self.sc.blit(img, (r.x + 64, y - 8))

    # ==================================================================
    #  DRAWING — GAME
    # ==================================================================
    def hud_card(self, rect, p):
        col = RED if p == 0 else BLUE
        light = RED_L if p == 0 else BLUE_L
        dark = RED_D if p == 0 else BLUE_D
        active = self.g and not self.over and self.g.turn == p
        r = card(self.sc, rect, 18, col if active else light,
                 None if active else LINE, shadow=True)
        fg = WHITE if active else dark
        face = self.faces[p] if p < len(self.faces) else {}
        draw_avatar(self.sc, (r.x + 42, r.centery), 24, face.get("pfp", p),
                    face.get("flag", "UN"))
        name = self.names[p][:14]
        text(self.sc, name, (r.x + 82, r.centery - 16), 21, fg, True)
        pygame.draw.rect(self.sc, fg, (r.x + 84, r.centery + 12, 13, 4), border_radius=2)
        pygame.draw.rect(self.sc, fg, (r.x + 87, r.centery + 6, 7, 5), border_radius=2)
        text(self.sc, f"{self.g.walls[p]}", (r.x + 104, r.centery + 14), 17, fg, True, "midleft")
        if self.ranked or self.online:
            text(self.sc, f"{face.get('elo', 1000)} {self.t('elo')}",
                 (r.right - 18, r.centery - 14), 15, fg, True, "right")
        if self.tc > 0:
            mins = int(self.clocks[p]) // 60
            secs = int(self.clocks[p]) % 60
            low = self.clocks[p] < 15
            ccol = fg if not low else (255, 210, 210) if active else RED
            text(self.sc, f"{mins}:{secs:02d}", (r.right - 18, r.centery + 14), 20, ccol,
                 True, "right")

    def pawn_pos(self, p):
        step = CELL + GAP
        r, c = self.g.pawn[p]
        if self.anim and self.anim["p"] == p:
            t = min(1.0, (pygame.time.get_ticks() - self.anim["t0"]) / 200.0)
            t = 1 - (1 - t) ** 3
            fr, fc = self.anim["from"]
            tr, tc_ = self.anim["to"]
            r = fr + (tr - fr) * t
            c = fc + (tc_ - fc) * t
        return (int(BX + c * step + CELL / 2), int(BY + r * step + CELL / 2))

    def wall_rect(self, o, r, c):
        step = CELL + GAP
        if o == "h":
            return pygame.Rect(BX + c * step, BY + (r + 1) * step - GAP,
                               2 * CELL + GAP, GAP)
        return pygame.Rect(BX + (c + 1) * step - GAP, BY + r * step,
                           GAP, 2 * CELL + GAP)

    def draw_game(self):
        g = self.g
        if not g:
            return
        step = CELL + GAP

        self.hud_card((120, 44, 330, 92), 0)
        self.hud_card((W - 450, 44, 330, 92), 1)
        vs = card(self.sc, (W // 2 - 32, 56, 64, 68), 14, WHITE)
        text(self.sc, "VS", vs.center, 20, MUTED, True, "center")

        # board frame
        card(self.sc, (BX - 16, BY - 16, BOARD_PX + 32, BOARD_PX + 32), 22, WHITE)

        # goal bands
        pygame.draw.rect(self.sc, RED_L, (BX - 6, BY - 6, BOARD_PX + 12, CELL + 12),
                         border_radius=10)
        pygame.draw.rect(self.sc, BLUE_L,
                         (BX - 6, BY + 8 * step - 6, BOARD_PX + 12, CELL + 12), border_radius=10)

        legal = g.moves(g.turn) if (self.my_turn() and not self.over) else set()

        for r in range(N):
            for c in range(N):
                rect = pygame.Rect(BX + c * step, BY + r * step, CELL, CELL)
                pygame.draw.rect(self.sc, (252, 253, 255), rect, border_radius=8)
                pygame.draw.rect(self.sc, (231, 235, 242), rect, 1, border_radius=8)
                if (r, c) in legal:
                    col = RED if g.turn == 0 else BLUE
                    ball(self.sc, rect.center, 7, col)

        # placed walls
        for (r, c) in g.h:
            self.draw_wall("h", r, c)
        for (r, c) in g.v:
            self.draw_wall("v", r, c)

        # pawns
        for p in (1, 0):
            ball(self.sc, self.pawn_pos(p), 19, RED if p == 0 else BLUE)

        # wall drag preview (only while actively dragging a tray tile) —
        # drawn above the pawns so the floating wall piece stays visible
        if self.drag:
            orient = self.drag["orient"]
            drop_pos = self.drag["pos"]
            hw = self.hover_wall(drop_pos)
            if hw:
                r, c = hw
                ok = g.can_wall(orient, r, c, g.turn)
                rect = self.wall_rect(orient, r, c)
                prev = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                col = (RED if g.turn == 0 else BLUE) if ok else (170, 176, 186)
                prev.fill((*col, 140 if ok else 90))
                self.sc.blit(prev, rect.topleft)
                pygame.draw.rect(self.sc, col, rect, 2, border_radius=4)
            # the wall piece following the cursor
            gw, gh = (2 * CELL + GAP, GAP) if orient == "h" else (GAP, 2 * CELL + GAP)
            ghost = pygame.Surface((gw, gh), pygame.SRCALPHA)
            gcol = RED if g.turn == 0 else BLUE
            ghost.fill((*gcol, 170))
            self.sc.blit(ghost, (drop_pos[0] - gw // 2, drop_pos[1] - gh // 2))

        # turn strip
        turn_txt = self.t("your_turn") if self.my_turn() else self.t("opp_turn")
        if not self.online and self.ai_level is None:
            turn_txt = self.names[g.turn].upper()
        tcol = RED if g.turn == 0 else BLUE
        text(self.sc, turn_txt, (W // 2, BY - 34), 17, tcol, True, "center")
        pygame.draw.polygon(self.sc, tcol,
                            [(W // 2 - 120, BY - 34), (W // 2 - 108, BY - 40),
                             (W // 2 - 108, BY - 28)])

        # bottom wall tray — click-and-drag either tile onto the board.
        # A fresh turn always starts with no wall selected (plain pawn-move
        # mode); a wall is only ever placed by dragging one of these tiles.
        bar = card(self.sc, BAR, 18)
        text(self.sc, f"{g.walls[g.turn]} {self.t('walls')}", (bar.centerx, bar.y + 16),
             14, MUTED, True, "center")
        can_drag = self.my_turn() and not self.over and not self.anim and g.walls[g.turn] > 0
        self.draw_wall_tile(TILE_H, "h", can_drag)
        self.draw_wall_tile(TILE_V, "v", can_drag)

        if self.msg:
            text(self.sc, self.msg, (W // 2, 680), 16, self.msg_color, True, "center")

        if self.over:
            self.draw_over()

    def draw_wall_tile(self, rect, orient, can_drag):
        """One tray tile the player can press-and-drag onto the board to
        place a wall of this orientation. Highlights on hover and while
        actively being dragged; dims when it's not this player's turn or
        they have no walls left."""
        mouse = pygame.mouse.get_pos()
        dragging_this = bool(self.drag) and self.drag["orient"] == orient
        hovered = can_drag and not self.drag and rect.collidepoint(mouse)
        turn_col = RED if (self.g and self.g.turn == 0) else BLUE

        if not can_drag:
            fill, border = (245, 246, 248), LINE
        elif dragging_this:
            fill, border = (233, 238, 246), turn_col
        elif hovered:
            fill, border = (236, 240, 247), (170, 178, 196)
        else:
            fill, border = WHITE, LINE
        card(self.sc, rect, 12, fill, border, shadow=False)
        if dragging_this:
            pygame.draw.rect(self.sc, turn_col, rect, 2, border_radius=12)

        col = DARK if can_drag else MUTED
        icon_cx = rect.x + 32
        if orient == "h":
            pygame.draw.rect(self.sc, col, (icon_cx - 20, rect.centery - 5, 40, 10),
                             border_radius=5)
        else:
            pygame.draw.rect(self.sc, col, (icon_cx - 5, rect.centery - 20, 10, 40),
                             border_radius=5)
        label = self.t("horiz") if orient == "h" else self.t("vert")
        text(self.sc, label, (rect.x + 62, rect.centery), 15, col, True, "midleft")

    def draw_wall(self, o, r, c):
        owner = self.wall_owner.get((o, r, c), 0)
        col = RED if owner == 0 else BLUE
        dark = RED_D if owner == 0 else BLUE_D
        rect = self.wall_rect(o, r, c)
        scale = 1.0
        for wa in self.wall_anim:
            if tuple(wa["mv"][1:]) == (o, r, c):
                scale = min(1.0, (pygame.time.get_ticks() - wa["t0"]) / 200.0)
        if scale < 1.0:
            if o == "h":
                rect = pygame.Rect(rect.centerx - rect.w * scale / 2, rect.y,
                                   max(2, rect.w * scale), rect.h)
            else:
                rect = pygame.Rect(rect.x, rect.centery - rect.h * scale / 2,
                                   rect.w, max(2, rect.h * scale))
        pygame.draw.rect(self.sc, dark, rect, border_radius=5)
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(self.sc, col, inner, border_radius=5)

    def draw_over(self):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((16, 20, 30, 120))
        self.sc.blit(veil, (0, 0))
        r = card(self.sc, (W // 2 - 260, 290, 520, 250), 24)
        wcol = RED if self.over["winner"] == 0 else BLUE
        text(self.sc, self.t("winner"), (r.centerx, r.y + 48), 20, MUTED, True, "center")
        text(self.sc, self.names[self.over["winner"]], (r.centerx, r.y + 92), 36, wcol,
             True, "center")
        reason = self.over.get("reason")
        sub = ""
        if reason == "timeout":
            sub = self.t("timeout")
        elif reason == "resign":
            sub = self.t("surrender")
        elif reason == "disconnect":
            sub = self.t("opp_left")
        d = self.over.get("delta", 0)
        if d:
            sub = (sub + "   " if sub else "") + f"{'+' if d > 0 else ''}{d} {self.t('elo')}"
        if sub:
            text(self.sc, sub, (r.centerx, r.y + 132), 18,
                 GREEN if d > 0 else (RED if d < 0 else MUTED), True, "center")

    # ==================================================================
    #  EVENT LOOP
    # ==================================================================
    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.modal:
                self.close_modal()
                return

        if self.modal:
            for b in self.btns:
                b.handle(e)
            return

        if self.screen == "auth":
            for inp in (self.inp_nick, self.inp_pw):
                res = inp.handle(e)
                if res == "submit":
                    self.on_signin(None)
                elif res == "tab":
                    self.inp_nick.active, self.inp_pw.active = \
                        self.inp_pw.active, self.inp_nick.active

        if self.screen == "game" and self.handle_game_drag(e):
            return

        for b in list(self.btns):
            if b.handle(e):
                return

        if self.screen == "game" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.board_click(e.pos)

    def handle_game_drag(self, e):
        """Drag-and-drop wall placement: press on a tray tile to pick up a
        wall of that orientation, drag it over the board for a live preview,
        release to place it (or drop it harmlessly if the spot is invalid)."""
        g = self.g
        if not g:
            return False
        can_drag = self.my_turn() and not self.over and not self.anim and g.walls[g.turn] > 0

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if can_drag and TILE_H.collidepoint(e.pos):
                self.drag = {"orient": "h", "pos": e.pos}
                return True
            if can_drag and TILE_V.collidepoint(e.pos):
                self.drag = {"orient": "v", "pos": e.pos}
                return True

        elif e.type == pygame.MOUSEMOTION:
            if self.drag:
                self.drag["pos"] = e.pos
                return True

        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.drag:
                orient = self.drag["orient"]
                drop_pos = self.drag["pos"]
                self.drag = None
                if can_drag:
                    hw = self.hover_wall(drop_pos)
                    if hw:
                        r, c = hw
                        if g.can_wall(orient, r, c, g.turn):
                            self.do_move(("wall", orient, r, c))
                return True

        return False

    def run(self):
        while self.running:
            for e in pygame.event.get():
                self.handle(e)
            self.update()
            self.draw()
            self.clock.tick(FPS)
        self.close_net()
        pygame.quit()


def main():
    App().run()
    sys.exit(0)


if __name__ == "__main__":
    main()
