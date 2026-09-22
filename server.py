"""
server.py — Quoridor online relay server (TCP sockets + newline delimited JSON).

Deploy on Render.com / Railway.app:
    Start command:  python server.py
    The port is taken from the PORT environment variable.

Protocol (one JSON object per line, UTF-8):

  client -> server
    {"t":"auth",   "nick":"bob", "pw":"1234"}      login, registers if name is free
    {"t":"queue",  "mode":"ranked"|"casual", "tc":"bullet"|"blitz"|"rapid"|"none"}
    {"t":"cancel"}
    {"t":"move",   "mv":[...]}                     relayed verbatim to the opponent
    {"t":"resign"}
    {"t":"timeout"}                                sender's own clock hit zero
    {"t":"rematch"}
    {"t":"profile"} {"t":"history"} {"t":"leaderboard","kind":"elo"|"matches"}
    {"t":"setprofile","pfp":2,"flag":"MN"}
    {"t":"ping"}

  server -> client
    {"t":"auth_ok","user":{...}} | {"t":"auth_err","code":"taken"|"badpw"|"short"}
    {"t":"queued"} | {"t":"cancelled"}
    {"t":"start","color":0|1,"tc":180,"ranked":true,"me":{...},"opp":{...}}
    {"t":"move","mv":[...]}
    {"t":"over","winner":0|1,"reason":"goal"|"resign"|"timeout"|"disconnect",
                "delta":15,"elo":1015,"user":{...}}
    {"t":"history","rows":[...]} {"t":"leaderboard","kind":"elo","rows":[...]}
    {"t":"profile","user":{...}}
    {"t":"opp_left"} {"t":"pong"}
"""

import json
import os
import socket
import threading
import time

import database as db

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5555))

TIME_CONTROLS = {"none": 0, "bullet": 60, "blitz": 180, "rapid": 300}

_lock = threading.RLock()
_queues = {}        # key -> list[Client]
_clients = set()


# --------------------------------------------------------------------------
class Client:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.nick = None
        self.user = None
        self.room = None
        self.color = 0
        self.queue_key = None
        self.alive = True
        self._wlock = threading.Lock()

    def send(self, obj):
        if not self.alive:
            return
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            with self._wlock:
                self.sock.sendall(data)
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class Room:
    def __init__(self, a, b, ranked, tc_key):
        self.players = [a, b]
        self.ranked = ranked
        self.tc_key = tc_key
        self.tc = TIME_CONTROLS.get(tc_key, 0)
        self.over = False
        self.rematch = set()
        a.room = b.room = self
        a.color, b.color = 0, 1
        for i, p in enumerate(self.players):
            opp = self.players[1 - i]
            p.send({
                "t": "start",
                "color": i,
                "tc": self.tc,
                "ranked": self.ranked,
                "mode": self.tc_key,
                "me": p.user,
                "opp": opp.user,
            })

    def other(self, c):
        return self.players[1 - self.players.index(c)]

    def finish(self, winner_color, reason):
        with _lock:
            if self.over:
                return
            self.over = True
        w = self.players[winner_color]
        l = self.players[1 - winner_color]
        res = None
        if w.nick and l.nick and w.nick != l.nick:
            res = db.apply_result(w.nick, l.nick, self.ranked, self.tc_key)
        for p in self.players:
            side = "winner" if p is w else "loser"
            delta = res[side]["delta"] if res else 0
            elo = res[side]["elo"] if res else (p.user or {}).get("elo", 1000)
            if p.nick:
                p.user = db.get_user(p.nick) or p.user
            p.send({
                "t": "over",
                "winner": winner_color,
                "reason": reason,
                "delta": delta,
                "elo": elo,
                "user": p.user,
            })


# --------------------------------------------------------------------------
def enqueue(c, mode, tc_key):
    ranked = (mode == "ranked")
    if not ranked:
        tc_key = "none"
    key = ("ranked" if ranked else "casual", tc_key)
    with _lock:
        dequeue(c)
        q = _queues.setdefault(key, [])
        # drop dead entries
        q[:] = [x for x in q if x.alive and x.room is None]
        if q:
            opp = q.pop(0)
            Room(opp, c, ranked, tc_key)
            return
        c.queue_key = key
        q.append(c)
    c.send({"t": "queued"})


def dequeue(c):
    with _lock:
        if c.queue_key and c.queue_key in _queues:
            try:
                _queues[c.queue_key].remove(c)
            except ValueError:
                pass
        c.queue_key = None


# --------------------------------------------------------------------------
def handle_message(c, msg):
    t = msg.get("t")

    if t == "ping":
        c.send({"t": "pong"})
        return

    if t == "auth":
        ok, res = db.login_or_create(msg.get("nick", ""), msg.get("pw", ""))
        if ok:
            with _lock:
                for other in list(_clients):
                    if other is not c and other.nick and other.nick.lower() == res["nickname"].lower():
                        other.send({"t": "kicked"})
                        other.close()
            c.nick = res["nickname"]
            c.user = res
            c.send({"t": "auth_ok", "user": res})
        else:
            c.send({"t": "auth_err", "code": res})
        return

    if c.nick is None:
        c.send({"t": "auth_err", "code": "nouser"})
        return

    if t == "queue":
        enqueue(c, msg.get("mode", "casual"), msg.get("tc", "none"))

    elif t == "cancel":
        dequeue(c)
        c.send({"t": "cancelled"})

    elif t == "move":
        if c.room and not c.room.over:
            c.room.other(c).send({"t": "move", "mv": msg.get("mv")})

    elif t == "win":
        # sender reports that a pawn reached its goal row
        if c.room and not c.room.over:
            c.room.finish(int(msg.get("color", c.color)), "goal")

    elif t == "resign":
        if c.room and not c.room.over:
            c.room.finish(1 - c.color, "resign")

    elif t == "timeout":
        if c.room and not c.room.over:
            c.room.finish(1 - c.color, "timeout")

    elif t == "rematch":
        room = c.room
        if room and room.over:
            room.rematch.add(c.color)
            if len(room.rematch) == 2:
                a, b = room.players
                Room(a, b, room.ranked, room.tc_key)
            else:
                room.other(c).send({"t": "rematch_offer"})

    elif t == "leave":
        room = c.room
        if room:
            if not room.over:
                room.finish(1 - c.color, "disconnect")
            room.other(c).send({"t": "opp_left"})
            for p in room.players:
                p.room = None

    elif t == "profile":
        c.user = db.get_user(c.nick) or c.user
        c.send({"t": "profile", "user": c.user})

    elif t == "setprofile":
        c.user = db.set_profile(c.nick, int(msg.get("pfp", 0)), msg.get("flag", "UN"))
        c.send({"t": "profile", "user": c.user})

    elif t == "history":
        c.send({"t": "history", "rows": db.history(c.nick, 50)})

    elif t == "leaderboard":
        kind = msg.get("kind", "elo")
        c.send({"t": "leaderboard", "kind": kind, "rows": db.leaderboard(kind, 20)})


def client_thread(c):
    buf = b""
    try:
        while c.alive:
            data = c.sock.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                try:
                    handle_message(c, msg)
                except Exception as exc:           # never kill the server
                    print("handler error:", exc)
    except OSError:
        pass
    finally:
        disconnect(c)


def disconnect(c):
    dequeue(c)
    room = c.room
    if room and not room.over:
        room.finish(1 - c.color, "disconnect")
    if room:
        try:
            room.other(c).send({"t": "opp_left"})
        except Exception:
            pass
        for p in room.players:
            p.room = None
    with _lock:
        _clients.discard(c)
    c.close()
    print("-- disconnected", c.addr, c.nick)


def serve():
    db.init_db()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(64)
    print(f"Quoridor server listening on {HOST}:{PORT}")
    try:
        while True:
            sock, addr = srv.accept()
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            c = Client(sock, addr)
            with _lock:
                _clients.add(c)
            print("++ connected", addr)
            threading.Thread(target=client_thread, args=(c,), daemon=True).start()
    except KeyboardInterrupt:
        print("shutting down")
    finally:
        srv.close()


if __name__ == "__main__":
    serve()
