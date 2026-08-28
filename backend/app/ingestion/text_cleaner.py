import re
import unicodedata
from typing import Iterable, List


_INVISIBLE_CHARS = "\u00ad\u200b\u200c\u200d\ufeff"


def clean_text(text: str) -> str:
	"""Normalize extracted text without changing its medical wording."""
	if not text:
		return ""

	normalized = unicodedata.normalize("NFKC", text)
	normalized = normalized.translate({ord(char): None for char in _INVISIBLE_CHARS})
	normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

	cleaned_lines = []
	for line in normalized.split("\n"):
		line = "".join(char for char in line if char == "\t" or not unicodedata.category(char).startswith("C"))
		line = line.replace("\u00a0", " ")
		line = re.sub(r"[ \t]+", " ", line).strip()
		cleaned_lines.append(line)

	cleaned = "\n".join(cleaned_lines)
	return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def clean_paragraphs(paragraphs: Iterable[str]) -> List[str]:
	"""Clean extracted paragraphs and omit paragraphs with no usable text."""
	return [cleaned for paragraph in paragraphs if (cleaned := clean_text(paragraph))]


def clean_pages(pages: Iterable[str]) -> List[str]:
	"""Clean extracted page text while preserving page boundaries."""
	return [clean_text(page) for page in pages]
