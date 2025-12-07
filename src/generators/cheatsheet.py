"""Cheatsheet generator module."""

from typing import Optional
from pathlib import Path

from .notebooklm import NotebookLMClient
from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class CheatsheetGenerator:
    """Generates condensed cheatsheets for quick reference."""

    def __init__(
        self,
        notebooklm_client: Optional[NotebookLMClient] = None,
        gemini_client: Optional[GeminiClient] = None,
        downloader: Optional[Downloader] = None
    ):
        self.notebooklm = notebooklm_client
        self.gemini = gemini_client
        self.downloader = downloader
        self.logger = get_logger()

    def generate(self, topic: Topic) -> Optional[str]:
        """
        Generate a cheatsheet for a topic.

        Args:
            topic: Topic to create cheatsheet for

        Returns:
            Cheatsheet content as markdown string
        """
        self.logger.info(f"Generating cheatsheet for: {topic.title}")

        # Try NotebookLM first
        if self.notebooklm:
            try:
                result = self.notebooklm.send_chat_message(
                    f"Create a one-page cheatsheet for: {topic.title}. "
                    f"Make it condensed with quick-reference information, "
                    f"formulas, key terms, and essential facts. "
                    f"Use tables and bullet points for easy scanning."
                )
                if result:
                    return self._format_cheatsheet(topic, result)
            except Exception as e:
                self.logger.warning(f"NotebookLM cheatsheet generation failed: {e}")

        # Fallback to Gemini
        if self.gemini:
            try:
                prompt = f"""Create a condensed one-page cheatsheet for quick reference.

Topic: {topic.title}
Content: {topic.content[:3000]}

Requirements:
1. Fit on one page when printed
2. Use tables for comparing items
3. Use bullet points, not paragraphs
4. Include all formulas/equations if applicable
5. List key terms with brief definitions
6. Include common mistakes/pitfalls
7. Add memory tricks/mnemonics if helpful

Format in Markdown. Keep it extremely concise - this is a quick reference, not a study guide."""

                response = self.gemini.generate(prompt, temperature=0.3)
                if response:
                    return self._format_cheatsheet(topic, response.text)
            except Exception as e:
                self.logger.warning(f"Gemini cheatsheet generation failed: {e}")

        return self._basic_cheatsheet(topic)

    def _format_cheatsheet(self, topic: Topic, content: str) -> str:
        """Format cheatsheet with header."""
        return f"""# {topic.title} - Cheatsheet

{content}

---
**Quick Reference Keywords:** {' | '.join(topic.keywords)}
"""

    def _basic_cheatsheet(self, topic: Topic) -> str:
        """Create basic cheatsheet when AI unavailable."""
        keywords_table = "| Term | Definition |\n|------|------------|\n"
        for kw in topic.keywords[:5]:
            keywords_table += f"| {kw} | (add definition) |\n"

        return f"""# {topic.title} - Cheatsheet

## Key Points
- {topic.summary}

## Keywords
{keywords_table}

## Subtopics
{chr(10).join(f'- {st}' for st in topic.subtopics)}

## Notes
(Add quick notes here)

---
**Difficulty:** {topic.difficulty}
"""

    def save(self, topic: Topic, content: str) -> Optional[Path]:
        """Save cheatsheet to file."""
        if self.downloader:
            filename = f"cheatsheet_{topic.id:02d}_{self._sanitize_filename(topic.title)}"
            return self.downloader.save_text_content(
                content, filename, "cheatsheets", "md"
            )
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
