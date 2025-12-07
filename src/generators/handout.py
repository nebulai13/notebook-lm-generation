"""Handout generator module."""

from typing import Optional
from pathlib import Path

from .notebooklm import NotebookLMClient
from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class HandoutGenerator:
    """Generates handouts with keypoint summaries."""

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
        Generate a handout for a topic.

        Args:
            topic: Topic to create handout for

        Returns:
            Handout content as markdown string
        """
        self.logger.info(f"Generating handout for: {topic.title}")

        # Try NotebookLM first
        if self.notebooklm:
            try:
                result = self.notebooklm.send_chat_message(
                    f"Create a detailed handout with key point summaries for this topic: {topic.title}. "
                    f"Include main concepts, definitions, examples, and study tips. "
                    f"Format in clear sections with bullet points."
                )
                if result:
                    return self._format_handout(topic, result)
            except Exception as e:
                self.logger.warning(f"NotebookLM handout generation failed: {e}")

        # Fallback to Gemini
        if self.gemini:
            try:
                prompt = f"""Create a comprehensive handout for the following topic.

Topic: {topic.title}
Summary: {topic.summary}

Content:
{topic.content}

The handout should include:
1. **Overview** - Brief introduction
2. **Key Concepts** - Main ideas with explanations
3. **Important Definitions** - Key terms and meanings
4. **Examples** - Practical examples where applicable
5. **Key Takeaways** - Bullet points of main points to remember
6. **Study Questions** - Questions for self-assessment
7. **Further Reading** - Suggestions for deeper learning

Format in Markdown with clear headings and bullet points."""

                response = self.gemini.generate(prompt, temperature=0.5)
                if response:
                    return self._format_handout(topic, response.text)
            except Exception as e:
                self.logger.warning(f"Gemini handout generation failed: {e}")

        # Basic fallback
        return self._basic_handout(topic)

    def _format_handout(self, topic: Topic, content: str) -> str:
        """Format handout with header."""
        return f"""# Handout: {topic.title}

{content}

---
*Keywords: {', '.join(topic.keywords)}*
*Difficulty: {topic.difficulty}*
*Estimated study time: {topic.estimated_study_time}*
"""

    def _basic_handout(self, topic: Topic) -> str:
        """Create a basic handout when AI is unavailable."""
        return f"""# Handout: {topic.title}

## Overview
{topic.summary}

## Content
{topic.content}

## Key Points
- Topic: {topic.title}
- Keywords: {', '.join(topic.keywords)}
- Subtopics: {', '.join(topic.subtopics)}

## Study Notes
(Add your own notes here)

---
*Difficulty: {topic.difficulty}*
*Estimated study time: {topic.estimated_study_time}*
"""

    def save(self, topic: Topic, content: str) -> Optional[Path]:
        """Save handout to file."""
        if self.downloader:
            filename = f"handout_{topic.id:02d}_{self._sanitize_filename(topic.title)}"
            return self.downloader.save_text_content(
                content, filename, "handouts", "md"
            )
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
