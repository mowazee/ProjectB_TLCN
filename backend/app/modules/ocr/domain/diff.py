"""So sánh hai phiên bản text theo dòng, trong dòng thay đổi thì theo từ (P2-06). Python thuần (R3)."""

import difflib
import re
from dataclasses import dataclass, field

_TOKEN = re.compile(r"\s+|[^\s]+")


@dataclass(frozen=True)
class WordOp:
    op: str  # equal | insert | delete | replace
    old: str
    new: str


@dataclass
class Hunk:
    op: str  # equal | insert | delete | replace
    old_start: int  # số dòng (1-based) bên cũ
    new_start: int
    old_lines: list[str]
    new_lines: list[str]
    words: list[WordOp] = field(default_factory=list)  # chỉ có với replace


@dataclass
class DiffResult:
    hunks: list[Hunk]
    lines_added: int
    lines_removed: int

    @property
    def identical(self) -> bool:
        return all(h.op == "equal" for h in self.hunks)


def word_diff(old: str, new: str) -> list[WordOp]:
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        ops.append(WordOp(tag, "".join(a[i1:i2]), "".join(b[j1:j2])))
    return ops


def diff_text(old: str, new: str) -> DiffResult:
    a, b = old.splitlines(), new.splitlines()
    hunks: list[Hunk] = []
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        h = Hunk(tag, i1 + 1, j1 + 1, a[i1:i2], b[j1:j2])
        if tag == "replace":
            h.words = word_diff("\n".join(h.old_lines), "\n".join(h.new_lines))
        if tag in ("insert", "replace"):
            added += j2 - j1
        if tag in ("delete", "replace"):
            removed += i2 - i1
        hunks.append(h)
    return DiffResult(hunks, added, removed)
