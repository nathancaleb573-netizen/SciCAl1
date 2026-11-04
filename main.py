"""SciCalc - touch scientific calculator (Kivy). Build to APK with Buildozer."""
import json, os, re

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex as hx

from engine import safe_calculate, format_number

THEMES = {
    "dark": dict(bg="14151a", text="f2f2f2", sub="8a8fa3", err="ff7b7b", btn="ffffff",
                 num="2d2f3a", op="3b4a6b", fn="25343a", eq="e07a2f", clr="7a3030", on="c28a1e"),
    "light": dict(bg="f2f3f7", text="1b1c20", sub="6a6f80", err="c0392b", btn="1b1c20",
                  num="ffffff", op="c9d3ee", fn="dde8e6", eq="f08a3c", clr="f2b5b5", on="f5c542"),
}
# (label, action, [2nd label, 2nd action]); ":cmd" = command, otherwise text to insert
LAYOUT = [
    [("2nd", ":2nd"), ("DEG", ":mode"), ("MC", ":mc", "MS", ":ms"), ("MR", ":mr"), ("M+", ":m+", "M-", ":m-")],
    [("sin", "sin(", "asin", "asin("), ("cos", "cos(", "acos", "acos("), ("tan", "tan(", "atan", "atan("), ("(", "("), (")", ")")],
    [("sinh", "sinh(", "asinh", "asinh("), ("cosh", "cosh(", "acosh", "acosh("), ("tanh", "tanh(", "atanh", "atanh("), ("%", "%", ",", ","), ("|x|", "abs(", "rand", "rand()")],
    [("ln", "ln(", "e^x", "exp("), ("log", "log(", "10^x", "10^"), ("√", "sqrt(", "3√", "cbrt("), ("x²", "^2", "x³", "^3"), ("x^y", "^", "y√x", "root(")],
    [("π", "pi", "φ", "phi"), ("e", "e", "τ", "tau"), ("n!", "!", "nCr", "ncr("), ("1/x", "^(-1)", "nPr", "npr("), ("EXP", "×10^", "mod", " mod ")],
    [("C", ":c"), ("7", "7"), ("8", "8"), ("9", "9"), ("÷", "÷")],
    [("DEL", ":del"), ("4", "4"), ("5", "5"), ("6", "6"), ("×", "×")],
    [("Ans", "ans"), ("1", "1"), ("2", "2"), ("3", "3"), ("−", "−")],
    [("±", ":neg"), ("0", "0"), (".", "."), ("=", ":eq"), ("+", "+")],
]
OPS = ("+", "−", "×", "÷", "^", "%", " mod ", "!")
MODES = ["DEG", "RAD", "GRAD"]
TOKEN = re.compile(r"([a-z]+\(|\s?mod\s?|×10\^|ans|pi|phi|tau)$")


def kind_of(label):
    if label in ("C", "DEL"):
        return "clr"
    if label == "=":
        return "eq"
    if label in ("÷", "×", "−", "+", "(", ")"):
        return "op"
    return "num" if label.replace(".", "").isdigit() or label in (".", "±", "Ans") else "fn"


class SciCalc(App):
    title = "SciCalc"

    # ---------- setup ---------- #
    def build(self):
        self.st = dict(theme="dark", mode="DEG", mem=0.0, ans=0.0, history=[])
        try:
            with open(self._path()) as f:
                self.st.update(json.load(f))
        except Exception:
            pass
        self.expr, self.fresh, self.second, self.keys, self.styled = "", False, False, {}, []

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        bar = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.info = self._label(bar, 0.4, 14, "left")
        for txt, fn in (("History", self.show_history), ("Copy", self.copy), ("Theme", self.toggle_theme)):
            b = Button(text=txt, font_size=sp(14), background_normal="", on_release=fn)
            self.styled.append((b, "op"))
            bar.add_widget(b)
        root.add_widget(bar)
        self.disp = self._label(root, None, 40, "right", valign="bottom", hint_y=0.2)
        self.prev = self._label(root, None, 20, "right", hint_y=None, h=dp(30))
        grid = GridLayout(cols=5, spacing=dp(4), size_hint_y=0.66)
        for row in LAYOUT:
            for item in row:
                b = Button(text=item[0], font_size=sp(17), background_normal="")
                b.bind(on_release=self.on_key)
                self.keys[b] = item
                self.styled.append((b, kind_of(item[0])))
                grid.add_widget(b)
        root.add_widget(grid)
        Window.bind(on_key_down=self.on_kbd)
        self.apply_theme()
        self.refresh()
        return root

    def _label(self, parent, hx_w, size, halign, valign="middle", hint_y=1, h=None):
        kw = dict(font_size=sp(size), halign=halign, valign=valign, markup=False)
        if hx_w:
            kw["size_hint_x"] = hx_w
        if h:
            kw.update(size_hint_y=None, height=h)
        else:
            kw["size_hint_y"] = hint_y
        lb = Label(**kw)
        lb.bind(size=lambda w, s: setattr(w, "text_size", s))
        parent.add_widget(lb)
        return lb

    def _path(self):
        return os.path.join(self.user_data_dir, "state.json")

    def save(self):
        self.st["history"] = self.st["history"][-100:]
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self._path(), "w") as f:
                json.dump(self.st, f)
        except Exception:
            pass

    def on_stop(self):
        self.save()

    on_pause = lambda self: (self.save(), True)[1]

    # ---------- theme / display ---------- #
    def apply_theme(self):
        t = THEMES[self.st["theme"]]
        Window.clearcolor = hx(t["bg"])
        for b, k in self.styled:
            b.background_color = hx(t[k])
            b.color = hx("ffffff" if k in ("eq", "clr") else t["btn"])
        for lb, c in ((self.disp, "text"), (self.info, "sub")):
            lb.color = hx(t[c])
        self.refresh()

    def toggle_theme(self, *_):
        self.st["theme"] = "light" if self.st["theme"] == "dark" else "dark"
        self.apply_theme()

    def refresh(self, err=None):
        t = THEMES[self.st["theme"]]
        n = len(self.expr)
        self.disp.font_size = sp(40 if n < 12 else 30 if n < 20 else 22)
        self.disp.text = self.expr or "0"
        self.info.text = self.st["mode"] + ("   •  M" if self.st["mem"] else "")
        ok, v = safe_calculate(self.expr, self.st["mode"], self.st["ans"]) if self.expr else (False, "")
        if err:
            self.prev.text, self.prev.color = err, hx(t["err"])
        elif ok and not self.fresh and format_number(v) != self.expr.strip():
            self.prev.text, self.prev.color = "= " + format_number(v), hx(t["sub"])
        else:
            self.prev.text = ""
        for b, item in self.keys.items():
            use2 = self.second and len(item) > 2
            b.text = item[2] if use2 else item[0]
            if item[0] == "DEG":
                b.text = self.st["mode"]
            if item[0] == "2nd":
                b.background_color = hx(t["on"] if self.second else t["fn"])

    # ---------- input handling ---------- #
    def on_key(self, btn):
        item = self.keys[btn]
        act = item[3] if self.second and len(item) > 2 else item[1]
        self.press(act)
        if self.second and item[0] != "2nd":
            self.second = False
            self.refresh()

    def press(self, act):
        if act.startswith(":"):
            return self.command(act[1:])
        if self.fresh:
            if not act.startswith(OPS):
                self.expr = ""
            self.fresh = False
        self.expr += act
        self.refresh()

    def command(self, c):
        s = self.st
        if c == "c":
            self.expr, self.fresh = "", False
        elif c == "del":
            m = TOKEN.search(self.expr)
            self.expr = self.expr[:m.start()] if m else self.expr[:-1]
            self.fresh = False
        elif c == "neg":
            e = self.expr
            self.expr = e[2:-1] if e.startswith("-(") and e.endswith(")") else ("-(" + e + ")" if e else "-")
        elif c == "2nd":
            self.second = not self.second
        elif c == "mode":
            s["mode"] = MODES[(MODES.index(s["mode"]) + 1) % 3]
        elif c == "mc":
            s["mem"] = 0.0
        elif c == "mr":
            return self.press(format_number(s["mem"]))
        elif c in ("ms", "m+", "m-"):
            ok, v = safe_calculate(self.expr or "0", s["mode"], s["ans"])
            if not ok:
                return self.refresh(v)
            s["mem"] = v if c == "ms" else s["mem"] + (v if c == "m+" else -v)
        elif c == "eq":
            return self.equals()
        self.refresh()

    def equals(self):
        if not self.expr:
            return
        ok, v = safe_calculate(self.expr, self.st["mode"], self.st["ans"])
        if not ok:
            return self.refresh(v)
        text = format_number(v)
        self.st["history"].append([self.expr, text])
        self.st["ans"], self.expr, self.fresh = v, text, True
        self.save()
        self.refresh()

    def on_kbd(self, win, key, scan, char, mods):
        if key in (13, 271):
            self.press(":eq")
        elif key == 8:
            self.press(":del")
        elif key == 27:
            self.press(":c")
        elif char and char in "0123456789.+-*/()^%!":
            self.press({"*": "×", "/": "÷", "-": "−"}.get(char, char))
        elif char and char.isalpha():
            self.press(char)
        return True

    # ---------- history / clipboard ---------- #
    def copy(self, *_):
        Clipboard.copy(self.expr or format_number(self.st["ans"]))
        self.refresh("Copied to clipboard")

    def show_history(self, *_):
        t = THEMES[self.st["theme"]]
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        pop = Popup(title="History (tap to reuse)", content=box, size_hint=(0.92, 0.8))
        lst = GridLayout(cols=1, size_hint_y=None, spacing=dp(4))
        lst.bind(minimum_height=lst.setter("height"))
        for e, r in reversed(self.st["history"]):
            b = Button(text=f"{e}\n= {r}", size_hint_y=None, height=dp(62), background_normal="",
                       background_color=hx(t["num"]), color=hx(t["btn"]), halign="right")
            b.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - dp(16), s[1])))
            b.bind(on_release=lambda _b, r=r: (pop.dismiss(), self.press(r)))
            lst.add_widget(b)
        if not self.st["history"]:
            lst.add_widget(Label(text="No calculations yet", size_hint_y=None, height=dp(60)))
        sv = ScrollView()
        sv.add_widget(lst)
        box.add_widget(sv)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        clr = Button(text="Clear history", background_normal="", background_color=hx(t["clr"]),
                     on_release=lambda *_: (self.st["history"].clear(), self.save(), pop.dismiss()))
        row.add_widget(clr)
        row.add_widget(Button(text="Close", on_release=pop.dismiss))
        box.add_widget(row)
        pop.open()


if __name__ == "__main__":
    SciCalc().run()
