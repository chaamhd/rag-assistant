import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHARS = 1500      # environ 375 tokens
OVERLAP_CHARS = 200
MIN_CHARS = 100       # en dessous, un passage n'a pas assez de contenu

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*?)\s*#*\s*$")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
ATTR_LIST_RE = re.compile(r"\s*\{\s*[:#.][^}]*\}\s*$")
ADMONITION_RE = re.compile(r'^\s*(?:!!!|\?\?\?\+?)\s+(\w+)(?:\s+"([^"]*)")?\s*$')
TAB_RE = re.compile(r'^\s*===\s+"([^"]+)"\s*$')


@dataclass
class Chunk:
    source: str
    title: str
    section: str
    index: int
    text: str


def clean_markdown(text: str) -> str:
    """Retire le bruit (métadonnées, images, syntaxe MkDocs) sans toucher au code."""
    text = text.replace("\r\n", "\n")
    text = FRONT_MATTER_RE.sub("", text, count=1)
    text = HTML_COMMENT_RE.sub("", text)

    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line.rstrip())
            continue
        if in_fence:
            out.append(line.rstrip())
            continue
        if line.strip().startswith("--8<--"):
            continue
        m = ADMONITION_RE.match(line)
        if m:
            kind, title = m.group(1).capitalize(), m.group(2)
            out.append(f"{kind}: {title}" if title else f"{kind}:")
            continue
        m = TAB_RE.match(line)
        if m:
            out.append(f"{m.group(1)}:")
            continue
        line = IMAGE_RE.sub("", line)
        line = LINK_RE.sub(r"\1", line)
        line = ATTR_LIST_RE.sub("", line)
        out.append(line.rstrip())

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def split_sections(text: str) -> list[tuple[list[str], str]]:
    """Découpe aux titres (niveaux 1 à 3). Retourne (chemin de titres, contenu)."""
    sections, path, buf, in_fence = [], [], [], False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((list(path), body))
        buf.clear()

    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[: level - 1] + [m.group(2)]
        else:
            buf.append(line)
    flush()
    return sections


def split_blocks(body: str) -> list[str]:
    """Découpe en paragraphes, sans couper à l'intérieur d'un bloc de code."""
    blocks, cur, in_fence = [], [], False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def split_long(block: str, max_chars: int) -> list[str]:
    """Un bloc trop long (gros bloc de code, tableau) est coupé par lignes."""
    if len(block) <= max_chars:
        return [block]
    parts, cur = [], ""
    for line in block.split("\n"):
        if cur and len(cur) + len(line) + 1 > max_chars:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts


def pack(blocks: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    """Assemble les blocs en passages, avec reprise des derniers blocs en début de suivant."""
    chunks, cur, size = [], [], 0
    for block in blocks:
        if cur and size + len(block) + 2 > max_chars:
            chunks.append("\n\n".join(cur))
            carry, carry_size = [], 0
            for b in reversed(cur):
                if carry_size + len(b) > overlap_chars:
                    break
                carry.insert(0, b)
                carry_size += len(b) + 2
            cur, size = carry, carry_size
        cur.append(block)
        size += len(block) + 2
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def chunk_document(source: str, raw_text: str) -> list[Chunk]:
    text = clean_markdown(raw_text)
    sections = split_sections(text)
    title = next((p[0] for p, _ in sections if p), Path(source).stem)

    chunks, idx = [], 0
    for path, body in sections:
        blocks = [
            part for b in split_blocks(body) for part in split_long(b, MAX_CHARS)
        ]
        for piece in pack(blocks, MAX_CHARS, OVERLAP_CHARS):
            if len(piece) < MIN_CHARS:
                continue
            chunks.append(Chunk(source, title, " > ".join(path), idx, piece))
            idx += 1
    return chunks