"""Parser contract shared by the TCX and GPX implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lxml import etree


class ParserError(ValueError):
    """Raised when a file cannot be parsed into a workout."""


class UnsupportedFileError(ParserError):
    """Raised when no parser recognises the file."""


@dataclass(slots=True)
class ParsedTrackPoint:
    sequence: int
    timestamp: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    heart_rate: int | None = None
    cadence: int | None = None


@dataclass(slots=True)
class ParsedWorkout:
    """Everything a parser can pull out of a file, before analysis fills the gaps."""

    source: str
    file_format: str
    name: str
    sport_type: str
    start_time: datetime
    track_points: list[ParsedTrackPoint] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    # Totals the file states itself. When absent, the analyzer derives them.
    total_distance: float | None = None
    total_time: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_cadence: int | None = None


class BaseParser(ABC):
    """Namespace-agnostic XML parsing helpers plus the parse() contract."""

    file_format: str = ""
    default_source: str = "unknown"
    #: Root tag (local name) this parser expects, used for content sniffing.
    root_tag: str = ""

    @classmethod
    def supports(cls, filename: str | None, content: bytes | None = None) -> bool:
        if filename and filename.lower().endswith(f".{cls.file_format}"):
            return True
        if content is None:
            return False
        try:
            root = cls._parse_xml(content)
        except ParserError:
            return False
        return etree.QName(root).localname == cls.root_tag

    @abstractmethod
    def parse(self, content: bytes, filename: str | None = None) -> ParsedWorkout:
        """Turn raw file bytes into a ParsedWorkout."""

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _parse_xml(content: bytes) -> etree._Element:
        if not content or not content.strip():
            raise ParserError("File is empty")
        # No network access, no entity expansion: these files come from users.
        parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
        try:
            return etree.fromstring(content, parser=parser)
        except etree.XMLSyntaxError as exc:
            raise ParserError(f"Malformed XML: {exc}") from exc

    @staticmethod
    def _nodes(element, path: str) -> list:
        """Child lookup along a slash-separated path of local names.

        Namespace-agnostic, so a Garmin TCX and a hand-written one both match.
        """
        steps = "/".join(f"*[local-name()='{name}']" for name in path.split("/"))
        return element.xpath(f"./{steps}")

    @classmethod
    def _node(cls, element, path: str):
        matches = cls._nodes(element, path)
        return matches[0] if matches else None

    @staticmethod
    def _descendants(element, name: str) -> list:
        """Descendant lookup by local name, at any depth."""
        return element.xpath(f".//*[local-name()='{name}']")

    @classmethod
    def _text(cls, element, path: str | None = None) -> str | None:
        if element is None:
            return None
        target = cls._node(element, path) if path else element
        if target is None or target.text is None:
            return None
        return target.text.strip() or None

    @classmethod
    def _float(cls, element, path: str | None = None) -> float | None:
        text = cls._text(element, path)
        if text is None:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @classmethod
    def _int(cls, element, path: str | None = None) -> int | None:
        value = cls._float(element, path)
        return int(round(value)) if value is not None else None

    @staticmethod
    def _leaf_values(element) -> dict[str, str]:
        """Map every descendant's lowercased local name to its text.

        Used for GPX extensions, where heart rate hides under a vendor
        namespace with no agreed-upon element name.
        """
        values: dict[str, str] = {}
        for node in element.iter():
            if node.text and node.text.strip():
                values.setdefault(etree.QName(node).localname.lower(), node.text.strip())
        return values

    @staticmethod
    def _parse_timestamp(text: str | None) -> datetime | None:
        """Parse an ISO-8601 timestamp, normalising to UTC."""
        if not text:
            return None
        cleaned = text.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
