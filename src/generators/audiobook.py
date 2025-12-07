"""Audiobook chapter generator module."""

from typing import Optional
from pathlib import Path

from .notebooklm import NotebookLMClient
from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class AudiobookGenerator:
    """Generates audiobook chapter scripts and audio via NotebookLM."""

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

    def generate_script(self, topic: Topic) -> Optional[str]:
        """
        Generate an audiobook chapter script.

        Args:
            topic: Topic to create chapter for

        Returns:
            Chapter script as text
        """
        self.logger.info(f"Generating audiobook chapter for: {topic.title}")

        if self.gemini:
            try:
                prompt = f"""Write an audiobook chapter script for the following topic.
The script should be written to be read aloud and be engaging for listeners.

Topic: {topic.title}
Summary: {topic.summary}

Content:
{topic.content}

Requirements:
1. Start with an engaging introduction that hooks the listener
2. Use conversational but professional tone
3. Include natural pauses (marked with "...")
4. Break complex concepts into digestible parts
5. Use examples and analogies for clarity
6. Include transitions between sections
7. End with a summary and teaser for what comes next
8. Aim for ~10 minutes of reading (~1500 words)
9. Avoid visual references (this is audio-only)

Write the script:"""

                response = self.gemini.generate(prompt, temperature=0.6)
                if response:
                    return self._format_script(topic, response.text)
            except Exception as e:
                self.logger.warning(f"Script generation failed: {e}")

        return self._basic_script(topic)

    def generate_audio(self, topic: Topic) -> bool:
        """
        Generate audio using NotebookLM's audio overview feature.

        Args:
            topic: Topic to generate audio for

        Returns:
            True if audio generation started
        """
        if not self.notebooklm:
            self.logger.warning("NotebookLM client not available for audio generation")
            return False

        try:
            # Add the topic content as a source
            self.notebooklm.add_text_source(topic.content, topic.title)

            # Generate audio overview
            success = self.notebooklm.generate_audio_overview()

            if success:
                self.logger.info(f"Audio generation started for: {topic.title}")

            return success

        except Exception as e:
            self.logger.error(f"Audio generation failed: {e}")
            return False

    def _format_script(self, topic: Topic, content: str) -> str:
        """Format script with metadata."""
        return f"""# Audiobook Chapter: {topic.title}

## Chapter Information
- **Topic:** {topic.title}
- **Difficulty:** {topic.difficulty}
- **Estimated Duration:** {topic.estimated_study_time or "~10 minutes"}

---

## Script

{content}

---

## Production Notes
- Read at a measured pace (~150 words per minute)
- Emphasize key terms and concepts
- Pause at "..." marks for 1-2 seconds
- Use slight emphasis on bullet points
- Keywords to emphasize: {', '.join(topic.keywords)}
"""

    def _basic_script(self, topic: Topic) -> str:
        """Create basic script when AI unavailable."""
        return f"""# Audiobook Chapter: {topic.title}

## Script

Welcome to this chapter on {topic.title}.

{topic.summary}

...

In this chapter, we'll explore the following key concepts:

{chr(10).join(f'- {kw}' for kw in topic.keywords)}

...

Let's dive in.

{topic.content}

...

To summarize what we've covered:

{topic.summary}

Key terms to remember are: {', '.join(topic.keywords)}.

...

Thank you for listening. In the next chapter, we'll continue exploring related topics.

---

## Production Notes
- Estimated reading time: {topic.estimated_study_time or "10-15 minutes"}
- Difficulty level: {topic.difficulty}
"""

    def save_script(self, topic: Topic, content: str) -> Optional[Path]:
        """Save audiobook script to file."""
        if self.downloader:
            filename = f"audiobook_{topic.id:02d}_{self._sanitize_filename(topic.title)}"
            return self.downloader.save_text_content(
                content, filename, "audiobooks", "md"
            )
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
