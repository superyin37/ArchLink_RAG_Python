import random
import time

_counter = 0


def _base36(n: int) -> str:
    if n == 0:
        return "0"
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    while n:
        result.append(chars[n % 36])
        n //= 36
    return "".join(reversed(result))


def generate_node_id() -> str:
    global _counter
    _counter += 1
    ts = _base36(int(time.time() * 1000))
    cnt = _base36(_counter).zfill(4)
    rand = _base36(random.randint(0, 1295)).zfill(2)
    return f"{ts}{cnt}{rand}"


def build_path(parent_path: str, seq: int) -> str:
    segment = str(seq).zfill(4)
    return f"{parent_path}/{segment}" if parent_path else segment


def get_ancestor_paths(path: str) -> list[str]:
    parts = path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts) - 1)]


SEPARATORS = [
    "\n\n", "\n", "。", "！", "？", ".", "!", "?", "；", ";", "，", ",", " "
]


def split_by_size(text: str, max_size: int = 500) -> list[str]:
    if len(text) <= max_size:
        return [text]

    for sep in SEPARATORS:
        parts = text.split(sep)
        if len(parts) > 1:
            result = []
            buffer = ""
            for part in parts:
                candidate = buffer + sep + part if buffer else part
                if len(candidate) <= max_size:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer)
                    if len(part) > max_size:
                        result.extend(split_by_size(part, max_size))
                        buffer = ""
                    else:
                        buffer = part
            if buffer:
                result.append(buffer)
            if result:
                return result

    # Last resort: character-level split
    return [text[i : i + max_size] for i in range(0, len(text), max_size)]
