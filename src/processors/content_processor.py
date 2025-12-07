"""Content processor for PDF, TXT, and website sources."""

import re
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import html2text

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

from ..utils.logger import get_logger


@dataclass
class ProcessedContent:
    """Container for processed content."""
    source: str  # File path or URL
    source_type: str  # pdf, txt, website
    title: str
    raw_text: str
    cleaned_text: str
    word_count: int
    metadata: dict


class ContentProcessor:
    """
    Processes content from various sources.

    Supports:
    - PDF files
    - Text files (.txt, .md)
    - Websites (HTML)
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".text"}

    def __init__(self):
        self.logger = get_logger()
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # No line wrapping

    def process(self, source: Union[str, Path]) -> ProcessedContent:
        """
        Process content from a file or URL.

        Args:
            source: File path or URL to process

        Returns:
            ProcessedContent object with extracted text
        """
        source_str = str(source)

        # Check if it's a URL
        if self._is_url(source_str):
            return self._process_website(source_str)

        # It's a file path
        path = Path(source_str)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        extension = path.suffix.lower()

        if extension == ".pdf":
            return self._process_pdf(path)
        elif extension in {".txt", ".md", ".text"}:
            return self._process_text_file(path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL."""
        try:
            result = urlparse(source)
            return all([result.scheme in ("http", "https"), result.netloc])
        except Exception:
            return False

    def _process_pdf(self, path: Path) -> ProcessedContent:
        """Process a PDF file."""
        if not HAS_PYPDF2:
            raise ImportError("PyPDF2 is required to process PDF files")

        self.logger.info(f"Processing PDF: {path}")

        try:
            reader = PdfReader(str(path))

            # Extract metadata
            metadata = {
                "pages": len(reader.pages),
                "author": reader.metadata.author if reader.metadata else None,
                "title": reader.metadata.title if reader.metadata else None,
                "creator": reader.metadata.creator if reader.metadata else None,
            }

            # Extract text from all pages
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

            raw_text = "\n\n".join(text_parts)
            cleaned_text = self._clean_text(raw_text)

            title = metadata.get("title") or path.stem

            return ProcessedContent(
                source=str(path),
                source_type="pdf",
                title=title,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                word_count=len(cleaned_text.split()),
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Failed to process PDF: {e}")
            raise

    def _process_text_file(self, path: Path) -> ProcessedContent:
        """Process a text file."""
        self.logger.info(f"Processing text file: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            cleaned_text = self._clean_text(raw_text)

            # Try to extract title from first line or filename
            lines = raw_text.strip().split("\n")
            first_line = lines[0] if lines else ""

            # Check if first line looks like a title (markdown heading or short line)
            if first_line.startswith("#"):
                title = first_line.lstrip("#").strip()
            elif len(first_line) < 100 and not first_line.endswith("."):
                title = first_line.strip()
            else:
                title = path.stem

            metadata = {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "extension": path.suffix,
            }

            return ProcessedContent(
                source=str(path),
                source_type="txt",
                title=title,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                word_count=len(cleaned_text.split()),
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Failed to process text file: {e}")
            raise

    def _process_website(self, url: str) -> ProcessedContent:
        """Process a website."""
        self.logger.info(f"Processing website: {url}")

        try:
            # Fetch the page
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Get title
            title = ""
            if soup.title:
                title = soup.title.string or ""
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
            if not title:
                title = urlparse(url).netloc

            # Convert to markdown/text
            html_content = str(soup)
            raw_text = self.html_converter.handle(html_content)
            cleaned_text = self._clean_text(raw_text)

            metadata = {
                "url": url,
                "domain": urlparse(url).netloc,
                "status_code": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
            }

            return ProcessedContent(
                source=url,
                source_type="website",
                title=title,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                word_count=len(cleaned_text.split()),
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Failed to process website: {e}")
            raise

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace multiple spaces with single space
        text = re.sub(r" {2,}", " ", text)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Remove empty lines at start and end
        text = text.strip()

        return text

    def get_preview(self, content: ProcessedContent, max_chars: int = 500) -> str:
        """Get a preview of the processed content."""
        preview = content.cleaned_text[:max_chars]
        if len(content.cleaned_text) > max_chars:
            preview += "..."
        return preview
