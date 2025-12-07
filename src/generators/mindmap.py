"""Mindmap generator module."""

from typing import Optional
from pathlib import Path

from .notebooklm import NotebookLMClient
from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class MindmapGenerator:
    """Generates mindmaps in text and Mermaid format."""

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
        Generate a mindmap for a topic.

        Args:
            topic: Topic to create mindmap for

        Returns:
            Mindmap in Mermaid diagram format
        """
        self.logger.info(f"Generating mindmap for: {topic.title}")

        # Try NotebookLM first
        if self.notebooklm:
            try:
                result = self.notebooklm.send_chat_message(
                    f"Create a hierarchical mindmap for: {topic.title}. "
                    f"Show main concept in center with branches for subtopics "
                    f"and sub-branches for details. Use indentation to show hierarchy."
                )
                if result:
                    return self._format_mindmap(topic, result)
            except Exception as e:
                self.logger.warning(f"NotebookLM mindmap generation failed: {e}")

        # Fallback to Gemini
        if self.gemini:
            try:
                prompt = f"""Create a mindmap for the following topic using Mermaid diagram syntax.

Topic: {topic.title}
Summary: {topic.summary}
Keywords: {', '.join(topic.keywords)}
Subtopics: {', '.join(topic.subtopics)}

Content excerpt:
{topic.content[:2000]}

Create a mindmap using Mermaid mindmap syntax:
```mermaid
mindmap
  root((Central Topic))
    Branch 1
      Sub-branch 1.1
      Sub-branch 1.2
    Branch 2
      Sub-branch 2.1
```

Include 4-6 main branches with 2-4 sub-branches each.
Make it comprehensive but not overwhelming.
Return only the Mermaid code block."""

                response = self.gemini.generate(prompt, temperature=0.4)
                if response:
                    return self._format_mindmap(topic, response.text)
            except Exception as e:
                self.logger.warning(f"Gemini mindmap generation failed: {e}")

        return self._basic_mindmap(topic)

    def _format_mindmap(self, topic: Topic, content: str) -> str:
        """Format mindmap with header and instructions."""
        # Clean up mermaid code if wrapped
        if "```mermaid" in content:
            # Extract just the mermaid diagram
            import re
            match = re.search(r'```mermaid\s*([\s\S]*?)```', content)
            if match:
                mermaid_code = match.group(1).strip()
            else:
                mermaid_code = content
        else:
            mermaid_code = content

        return f"""# Mindmap: {topic.title}

## Mermaid Diagram

Paste this code in a Mermaid-compatible viewer (like GitHub, Notion, or https://mermaid.live):

```mermaid
{mermaid_code}
```

## Text Version

{self._generate_text_version(topic)}

---
*View this mindmap at: https://mermaid.live*
"""

    def _generate_text_version(self, topic: Topic) -> str:
        """Generate a simple text-based mindmap."""
        lines = [f"**{topic.title}** (Central Topic)"]

        for i, kw in enumerate(topic.keywords[:6], 1):
            lines.append(f"├── {kw}")

        for i, st in enumerate(topic.subtopics[:4]):
            prefix = "└──" if i == len(topic.subtopics[:4]) - 1 else "├──"
            lines.append(f"{prefix} {st}")

        return "\n".join(lines)

    def _basic_mindmap(self, topic: Topic) -> str:
        """Create basic mindmap when AI unavailable."""
        # Build basic Mermaid mindmap
        safe_title = topic.title.replace('"', "'")[:30]
        mermaid_lines = [
            "mindmap",
            f'  root(("{safe_title}"))'
        ]

        # Add keywords as branches
        for kw in topic.keywords[:5]:
            safe_kw = kw.replace('"', "'")[:20]
            mermaid_lines.append(f"    {safe_kw}")

        # Add subtopics
        for st in topic.subtopics[:4]:
            safe_st = st.replace('"', "'")[:25]
            mermaid_lines.append(f"    {safe_st}")

        mermaid_code = "\n".join(mermaid_lines)

        return f"""# Mindmap: {topic.title}

## Mermaid Diagram

```mermaid
{mermaid_code}
```

## Text Structure

**{topic.title}**
├── Keywords: {', '.join(topic.keywords)}
└── Subtopics: {', '.join(topic.subtopics)}

---
*Customize this mindmap as needed*
"""

    def save(self, topic: Topic, content: str) -> Optional[Path]:
        """Save mindmap to file."""
        if self.downloader:
            filename = f"mindmap_{topic.id:02d}_{self._sanitize_filename(topic.title)}"
            return self.downloader.save_text_content(
                content, filename, "mindmaps", "md"
            )
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
