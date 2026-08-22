"""Picks the parser for an uploaded file, by extension then by content."""

from app.services.parsers.base_parser import BaseParser, ParsedWorkout, UnsupportedFileError
from app.services.parsers.fit_parser import FitParser
from app.services.parsers.gpx_parser import GpxParser
from app.services.parsers.tcx_parser import TcxParser

#: FIT last: the XML parsers decide by root element, which is a cheaper and
#: stricter test than a byte signature, so let them claim a file first.
PARSERS: tuple[type[BaseParser], ...] = (TcxParser, GpxParser, FitParser)
SUPPORTED_FORMATS = tuple(parser.file_format for parser in PARSERS)


def get_parser(filename: str | None, content: bytes | None = None) -> BaseParser:
    """Return a parser instance for the file, raising if nothing matches."""
    for parser_class in PARSERS:
        if parser_class.supports(filename, content):
            return parser_class()
    raise UnsupportedFileError(
        f"Unsupported file {filename or '<unnamed>'}: expected one of "
        + ", ".join(f".{fmt}" for fmt in SUPPORTED_FORMATS)
    )


def parse_file(filename: str | None, content: bytes) -> ParsedWorkout:
    """Convenience wrapper: choose a parser and run it."""
    return get_parser(filename, content).parse(content, filename=filename)
