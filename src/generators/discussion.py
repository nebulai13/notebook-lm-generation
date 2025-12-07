"""Podium discussion generator module."""

import re
from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field

from .gemini_client import GeminiClient
from .notebooklm import NotebookLMClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


@dataclass
class Participant:
    """A discussion participant."""
    name: str
    role: str
    perspective: str
    speaking_style: str = "professional"


@dataclass
class Discussion:
    """A complete discussion script."""
    topic: str
    topic_id: int
    participants: list[Participant]
    script: str
    duration_estimate: str = "10-15 minutes"


class DiscussionGenerator:
    """Generates podium discussions with 3 participants."""

    DEFAULT_PARTICIPANTS = [
        Participant(
            name="Dr. Expert",
            role="Subject Matter Expert",
            perspective="Provides deep technical knowledge and research insights",
            speaking_style="academic and thorough"
        ),
        Participant(
            name="Prof. Practical",
            role="Practitioner",
            perspective="Focuses on real-world applications and practical examples",
            speaking_style="clear and example-driven"
        ),
        Participant(
            name="Alex Student",
            role="Learner Representative",
            perspective="Asks clarifying questions from a student's perspective",
            speaking_style="curious and engaging"
        ),
    ]

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        notebooklm_client: Optional[NotebookLMClient] = None,
        downloader: Optional[Downloader] = None
    ):
        self.gemini = gemini_client
        self.notebooklm = notebooklm_client
        self.downloader = downloader
        self.logger = get_logger()

    def generate(
        self,
        topic: Topic,
        participants: list[Participant] = None,
        with_video: bool = True
    ) -> Discussion:
        """
        Generate a podium discussion for a topic.

        Args:
            topic: Topic for discussion
            participants: Custom participants (uses defaults if None)
            with_video: Generate NotebookLM video after script

        Returns:
            Discussion object with script
        """
        self.logger.info(f"Generating discussion for: {topic.title}")

        participants = participants or self.DEFAULT_PARTICIPANTS

        # Generate script with Gemini
        script = self._generate_script(topic, participants)

        discussion = Discussion(
            topic=topic.title,
            topic_id=topic.id,
            participants=participants,
            script=script
        )

        # Generate video via NotebookLM if requested
        if with_video and self.notebooklm:
            try:
                self._generate_video(topic, script)
            except Exception as e:
                self.logger.warning(f"Video generation failed: {e}")

        return discussion

    def _generate_script(
        self,
        topic: Topic,
        participants: list[Participant]
    ) -> str:
        """Generate discussion script using Gemini."""
        if not self.gemini:
            return self._basic_script(topic, participants)

        participants_desc = "\n".join(
            f"- **{p.name}** ({p.role}): {p.perspective}. Speaking style: {p.speaking_style}"
            for p in participants
        )

        prompt = f"""Write a podium discussion script about the following educational topic.

Topic: {topic.title}
Summary: {topic.summary}

Content to discuss:
{topic.content[:5000]}

Key concepts to cover: {', '.join(topic.keywords)}

Participants:
{participants_desc}

Also include a MODERATOR who guides the discussion.

Requirements:
1. Duration: 10-15 minutes when read aloud (~2000-2500 words)
2. Structure:
   - Opening by moderator (introduce topic and participants)
   - Each participant's initial perspective (1-2 min each)
   - Interactive discussion with back-and-forth exchanges
   - Audience Q&A section (3 questions)
   - Closing remarks from each participant
   - Moderator wrap-up

3. Make it educational but engaging
4. Include natural disagreements or different viewpoints
5. Use examples and analogies to explain concepts
6. Ensure all key concepts from the topic are covered
7. Keep dialogue natural and conversational

Format:
MODERATOR: [dialogue]
{chr(10).join(f'{p.name.upper()}: [dialogue]' for p in participants)}
AUDIENCE MEMBER: [question]

Write the discussion script:"""

        try:
            response = self.gemini.generate(prompt, temperature=0.7, max_tokens=5000)
            if response:
                return self._format_script(topic, participants, response.text)
        except Exception as e:
            self.logger.error(f"Script generation failed: {e}")

        return self._basic_script(topic, participants)

    def _format_script(
        self,
        topic: Topic,
        participants: list[Participant],
        script: str
    ) -> str:
        """Format script with metadata."""
        return f"""# Podium Discussion: {topic.title}

## Discussion Information
- **Topic:** {topic.title}
- **Duration:** 10-15 minutes
- **Key Concepts:** {', '.join(topic.keywords)}

## Participants

{chr(10).join(f'- **{p.name}** - {p.role}: {p.perspective}' for p in participants)}
- **MODERATOR** - Guides the discussion

---

## Script

{script}

---

## Production Notes

### For Video Creation:
1. Upload this script to NotebookLM as a source
2. Use Audio Overview feature to generate discussion audio
3. Optionally add participant images for video version

### Key Points to Emphasize:
{chr(10).join(f'- {kw}' for kw in topic.keywords)}

### Tone:
- Professional but accessible
- Educational yet engaging
- Balanced perspectives
"""

    def _basic_script(self, topic: Topic, participants: list[Participant]) -> str:
        """Create basic script when AI unavailable."""
        p1, p2, p3 = participants[0], participants[1], participants[2]

        return f"""# Podium Discussion: {topic.title}

## Script

MODERATOR: Welcome everyone to today's discussion on {topic.title}. I'm joined by three distinguished guests. {p1.name}, a {p1.role}; {p2.name}, our {p2.role}; and {p3.name}, representing the learner's perspective. Let's dive in.

MODERATOR: {p1.name}, could you start by giving us an overview of {topic.title}?

{p1.name.upper()}: Thank you. {topic.summary}

MODERATOR: Interesting. {p2.name}, from a practical standpoint, how do you see this applying?

{p2.name.upper()}: In practice, we see {topic.keywords[0] if topic.keywords else 'these concepts'} being applied in various ways...

MODERATOR: {p3.name}, what questions do students typically have about this topic?

{p3.name.upper()}: Students often wonder about the key terms like {', '.join(topic.keywords[:3]) if topic.keywords else 'the main concepts'}...

[Continue the discussion covering all key points]

MODERATOR: Thank you all for this enlightening discussion on {topic.title}.

---

*This is a basic template. Full script generation requires the Gemini API.*
"""

    def _generate_video(self, topic: Topic, script: str):
        """Generate video via NotebookLM."""
        if not self.notebooklm:
            return

        # Add script as source
        self.notebooklm.add_text_source(script, f"Discussion Script: {topic.title}")

        # Generate audio overview
        self.notebooklm.generate_audio_overview()

        self.logger.info(f"Video generation started for discussion: {topic.title}")

    def save(self, discussion: Discussion) -> Optional[Path]:
        """Save discussion script to file."""
        if not self.downloader:
            return None

        filename = f"discussion_{discussion.topic_id:02d}_{self._sanitize_filename(discussion.topic)}"

        return self.downloader.save_text_content(
            discussion.script, filename, "discussions", "md"
        )

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
