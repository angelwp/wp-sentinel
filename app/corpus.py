from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def load_corpus(knowledge_dir: Path = KNOWLEDGE_DIR) -> tuple[str, int]:
    """Lee todos los .md de knowledge/ en orden alfabético y los concatena.

    Sin chunking ni búsqueda semántica — ver docs/SPEC.md §4.1.
    """
    files = sorted(knowledge_dir.glob("*.md"))
    contents = [f.read_text(encoding="utf-8") for f in files]
    text = "\n\n".join(contents)
    return text, len(files)
