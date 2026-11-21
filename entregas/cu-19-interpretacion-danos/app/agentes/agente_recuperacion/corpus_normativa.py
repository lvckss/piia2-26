"""Literal, reproducible corpus preparation for spec 32, AC-001/003/012."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

PROTOCOL = "articles-policy-sections-char1500-overlap200-title-v1"


@dataclass(frozen=True)
class Document:
    path: str
    text: str
    kind: str
    policy_id: str | None
    content_hash: str
    title: str

    @property
    def id(self):
        return hashlib.sha256((self.path + "\0" + self.content_hash).encode()).hexdigest()


@dataclass(frozen=True)
class Fragment:
    id: str
    document: Document
    section: str
    section_index: int
    window_index: int
    start: int
    end: int
    text: str
    embedding_input: str
    input_hash: str
    source: str


@dataclass(frozen=True)
class Corpus:
    documents: tuple[Document, ...]
    fragments: tuple[Fragment, ...]
    hash: str
    protocol: str = PROTOCOL


def fragment_document(document: Document) -> tuple[Fragment, ...]:
    pattern = r"(?m)^##[ \t]+[^\r\n]+" if document.kind == "poliza" else r"(?mi)^[ \t]*Art[ií]culo[ \t]+(?:\d+|[a-záéíóúüñ]+)[^\r\n]*"
    headings = list(re.finditer(pattern, document.text))
    blocks = []
    if not headings:
        blocks.append((0, len(document.text), "Documento completo"))
    else:
        if headings[0].start() > 0:
            blocks.append((0, headings[0].start(), "Preámbulo"))
        for index, match in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(document.text)
            blocks.append((match.start(), end, match.group().lstrip("# \t").strip()))
    fragments = []
    for section_index, (start, end, section) in enumerate(blocks):
        cursor, window = start, 0
        while cursor < end:
            stop = min(cursor + 1500, end) if document.kind == "legal" else end
            piece = document.text[cursor:stop]
            left = cursor + len(piece) - len(piece.lstrip())
            right = stop - (len(piece) - len(piece.rstrip()))
            text = document.text[left:right]
            if text:
                embedding_input = f"Documento: {document.title}\nSección: {section}\n\n{text}"
                input_hash = hashlib.sha256(embedding_input.encode()).hexdigest()
                identity = f"{document.id}\0{PROTOCOL}\0{section_index}\0{window}\0{left}\0{right}"
                first_line = document.text.count("\n", 0, left) + 1
                last_line = document.text.count("\n", 0, max(left, right - 1)) + 1
                source = f"{document.path}#seccion-{section_index}-ventana-{window};L{first_line}-L{last_line}"
                fragments.append(Fragment(hashlib.sha256(identity.encode()).hexdigest(), document,
                    section, section_index, window, left, right, text, embedding_input, input_hash, source))
            if stop == end:
                break
            cursor, window = stop - 200, window + 1
    return tuple(fragments)


def load_corpus(package: Path) -> Corpus:
    package = Path(package)
    files = sorted([*(package / "docs/polizas_sinteticas").glob("*.md"),
                    *(package / "docs/legal").glob("*.txt")], key=lambda p: p.relative_to(package).as_posix())
    if not files:
        raise ValueError("No hay documentos de póliza o legislación en el paquete indicado")
    digest, documents, fragments = hashlib.sha256(), [], []
    for path in files:
        relative = path.relative_to(package).as_posix()
        raw = path.read_bytes()
        digest.update(relative.encode()); digest.update(b"\0"); digest.update(raw); digest.update(b"\0")
        text = raw.decode("utf-8-sig")
        if not text.strip():
            raise ValueError(f"Documento vacío: {relative}")
        kind = "poliza" if path.suffix == ".md" else "legal"
        title = next(line.lstrip("# \t").strip() for line in text.splitlines() if line.strip())[:200]
        doc = Document(relative, text, kind, path.stem if kind == "poliza" else None,
                       hashlib.sha256(raw).hexdigest(), title)
        documents.append(doc)
        fragments.extend(fragment_document(doc))
    return Corpus(tuple(documents), tuple(fragments), digest.hexdigest())
