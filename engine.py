"""Safe calculation engine for SciCalc (pure Python, no GUI)."""
import ast, math, operator, random, re

BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
       ast.FloorDiv: operator.floordiv}
UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
ANGLE = {"DEG": math.pi / 180, "RAD": 1.0, "GRAD": math.pi / 200}


def _int(x):
    if x != int(x):
        raise ValueError("integer required")
    return int(x)


def _fact(x):
    if x < 0 or x > 1000:
        raise ValueError("factorial out of range")
    return math.factorial(_int(x))


def _root(x, n=2):
    if x < 0 and n == int(n) and int(n) % 2:
        return -((-x) ** (1 / n))
    return x ** (1 / n)


def functions(mode):
    k = ANGLE[mode]
    return {
        "sin": lambda x: math.sin(x * k), "cos": lambda x: math.cos(x * k),
        "tan": lambda x: math.tan(x * k),
        "sec": lambda x: 1 / math.cos(x * k), "csc": lambda x: 1 / math.sin(x * k),
        "cot": lambda x: 1 / math.tan(x * k),
        "asin": lambda x: math.asin(x) / k, "acos": lambda x: math.acos(x) / k,
        "atan": lambda x: math.atan(x) / k,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "asinh": math.asinh, "acosh": math.acosh, "atanh": math.atanh,
        "ln": math.log, "log": math.log10, "logb": math.log,
        "sqrt": math.sqrt, "cbrt": lambda x: _root(x, 3), "root": _root,
        "exp": math.exp, "abs": abs, "fact": _fact, "gamma": math.gamma,
        "ncr": lambda n, r: math.comb(_int(n), _int(r)),
        "npr": lambda n, r: math.perm(_int(n), _int(r)),
        "gcd": lambda a, b: math.gcd(_int(a), _int(b)),
        "lcm": lambda a, b: math.lcm(_int(a), _int(b)),
        "round": round, "floor": math.floor, "ceil": math.ceil,
        "pct": lambda x: x / 100, "rad": math.radians, "deg": math.degrees, "rand": random.random,
    }


CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "phi": (1 + 5 ** 0.5) / 2}


def _postfix(s, ch, fname, ok=lambda rest: True):
    """Wrap the operand before a postfix char: 5! -> fact(5), (1+2)% -> pct((1+2))."""
    i = 0
    while True:
        i = s.find(ch, i)
        if i < 0:
            return s
        if not ok(s[i + 1:]):
            i += 1
            continue
        j = i - 1
        if j >= 0 and s[j] == ")":
            depth = 0
            while j >= 0:
                depth += (s[j] == ")") - (s[j] == "(")
                if depth == 0:
                    break
                j -= 1
            if j < 0:
                raise ValueError("syntax error")
            m = re.search(r"[a-z]+$", s[:j])
            j = m.start() if m else j
        else:
            m = re.search(r"(\d+\.?\d*|[a-z]+)$", s[:i])
            j = m.start() if m else i
        s = s[:j] + fname + "(" + s[j:i] + ")" + s[i + 1:]
        i = j


def _is_postfix_percent(rest):
    """A % is a percent sign unless an operand (or 'mod') follows it."""
    return bool(re.match(r"\s*mod\b", rest)) or not re.match(r"\s*[\d(a-zA-Z.]", rest)


def preprocess(s):
    for a, b in {"×": "*", "÷": "/", "−": "-", "–": "-", "^": "**",
                 "π": "pi", "φ": "phi", "τ": "tau", "√": "sqrt"}.items():
        s = s.replace(a, b)
    s = _postfix(s, "%", "pct", _is_postfix_percent)   # 10% -> pct(10)
    s = re.sub(r"\bmod\b", "%", s)                      # what's left is modulo
    s = _postfix(s, "!", "fact")
    s = re.sub(r"(?<![\w.])(pi|e|tau|phi|ans)\s*(?=[\d(])", r"\1*", s)  # pi2, e(
    s = re.sub(r"(\d|\))\s*(?=(?![eE][+-]?\d)[a-zA-Z(])", r"\1*", s)    # 2pi, 3(4)
    s = re.sub(r"\)\s*(?=\d)", ")*", s)                                  # (2)3
    return s + ")" * max(0, s.count("(") - s.count(")"))


def evaluate(expr, mode="DEG", ans=0.0):
    src = preprocess(expr.strip())
    if not src:
        raise ValueError("empty expression")
    funcs, consts = functions(mode), dict(CONSTS, ans=ans)

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in BIN:
            a = walk(n.left)
            r = n.right
            if (isinstance(n.op, (ast.Add, ast.Sub)) and isinstance(r, ast.Call)
                    and isinstance(r.func, ast.Name) and r.func.id == "pct" and len(r.args) == 1):
                p = a * walk(r.args[0]) / 100          # 200 + 10%  ->  200 + 20
                return a + p if isinstance(n.op, ast.Add) else a - p
            b = walk(r)
            if isinstance(n.op, ast.Pow) and abs(b) > 10000:
                raise ValueError("exponent too large")
            return BIN[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in UN:
            return UN[type(n.op)](walk(n.operand))
        if isinstance(n, ast.Name) and n.id in consts:
            return consts[n.id]
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in funcs and not n.keywords):
            return funcs[n.func.id](*[walk(a) for a in n.args])
        raise ValueError("unsupported expression")

    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        raise ValueError("syntax error") from None
    r = walk(tree)
    if isinstance(r, complex):
        raise ValueError("result is not real")
    return r


def format_number(x, digits=12):
    if isinstance(x, int):
        return str(x) if abs(x) < 10 ** 15 else f"{x:.{digits}g}"
    if abs(x) < 1e-12:
        return "0"
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return f"{x:.{digits}g}"


def safe_calculate(expr, mode="DEG", ans=0.0):
    """Return (ok, value_or_error_message). Never raises."""
    try:
        return True, evaluate(expr, mode, ans)
    except ZeroDivisionError:
        return False, "Cannot divide by zero"
    except OverflowError:
        return False, "Number too large"
    except (ValueError, TypeError) as e:
        m = str(e)
        return False, "Math domain error" if "domain" in m else m.capitalize()
