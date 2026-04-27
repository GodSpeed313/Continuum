"""Pi Script v0.1 — Lark parser wrapper."""

import sys
from pathlib import Path
from lark import Lark, UnexpectedCharacters, UnexpectedToken, UnexpectedEOF

GRAMMAR_PATH = Path(__file__).parent / "pi_script.lark"

_parser: Lark | None = None


def build_parser() -> Lark:
    global _parser
    if _parser is None:
        grammar = GRAMMAR_PATH.read_text(encoding="utf-8")
        _parser = Lark(grammar, parser="lalr", propagate_positions=True)
    return _parser


def parse_file(path: str | Path) -> tuple:
    """Parse a .pi file. Returns (tree, None) on success or (None, error_str) on failure."""
    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Cannot read {path}: {e}"

    parser = build_parser()
    try:
        tree = parser.parse(source)
        return tree, None
    except UnexpectedCharacters as e:
        return None, _fmt_char_error(e, source, path)
    except UnexpectedEOF as e:
        return None, _fmt_eof_error(e, path)
    except UnexpectedToken as e:
        return None, _fmt_token_error(e, source, path)


def parse_string(source: str, source_name: str = "<string>") -> tuple:
    """Parse Pi Script source from a string. Returns (tree, None) or (None, error_str)."""
    parser = build_parser()
    try:
        tree = parser.parse(source)
        return tree, None
    except UnexpectedCharacters as e:
        return None, _fmt_char_error(e, source, source_name)
    except UnexpectedEOF as e:
        return None, _fmt_eof_error(e, source_name)
    except UnexpectedToken as e:
        return None, _fmt_token_error(e, source, source_name)


def _get_line(source: str, lineno: int) -> str:
    lines = source.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def _pointer(col: int) -> str:
    return " " * max(0, col - 1) + "^"


def _fmt_char_error(e: UnexpectedCharacters, source: str, path) -> str:
    line = _get_line(source, e.line)
    allowed = ", ".join(sorted(e.allowed or [])) or "none"
    return (
        f"Syntax error in {path} at line {e.line}, col {e.column}:\n"
        f"  {line}\n"
        f"  {_pointer(e.column)}\n"
        f"  Unexpected character {repr(e.char)}\n"
        f"  Expected: {allowed}"
    )


def _fmt_token_error(e: UnexpectedToken, source: str, path) -> str:
    line = _get_line(source, e.line)
    col = getattr(e, "column", 1)
    expected = ", ".join(sorted(str(t) for t in (e.expected or []))) or "none"
    return (
        f"Syntax error in {path} at line {e.line}, col {col}:\n"
        f"  {line}\n"
        f"  {_pointer(col)}\n"
        f"  Unexpected token {str(e.token)!r}\n"
        f"  Expected: {expected}"
    )


def _fmt_eof_error(e: UnexpectedEOF, path) -> str:
    expected = ", ".join(sorted(str(t) for t in (e.expected or []))) or "none"
    return (
        f"Unexpected end of file in {path}\n"
        f"  Expected: {expected}"
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python parser.py <file.pi>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    tree, error = parse_file(path)

    if error:
        print(error, file=sys.stderr)
        sys.exit(1)

    print(tree.pretty())
    print(f"\nOK  {path}")


if __name__ == "__main__":
    main()
