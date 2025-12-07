"""Story generator module - Fantasy/Sci-Fi stories based on educational content."""

from typing import Optional
from pathlib import Path

from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class StoryGenerator:
    """Generates creative fantasy/sci-fi stories that teach educational content."""

    GENRES = {
        "fantasy": {
            "setting": "a magical realm with wizards, mythical creatures, and ancient powers",
            "elements": ["magic", "quests", "mythical beings", "ancient knowledge"],
        },
        "scifi": {
            "setting": "a futuristic universe with advanced technology and space exploration",
            "elements": ["technology", "space", "AI", "future societies"],
        },
        "adventure": {
            "setting": "an exciting world full of exploration and discovery",
            "elements": ["exploration", "challenges", "discoveries", "heroes"],
        },
    }

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        downloader: Optional[Downloader] = None
    ):
        self.gemini = gemini_client
        self.downloader = downloader
        self.logger = get_logger()

    def generate(
        self,
        topic: Topic,
        genre: str = "fantasy",
        include_scifi: bool = True
    ) -> dict[str, str]:
        """
        Generate both fantasy and sci-fi versions of a story.

        Args:
            topic: Topic to create story for
            genre: Primary genre (fantasy or scifi)
            include_scifi: If True, also generate a sci-fi version

        Returns:
            Dictionary with 'fantasy' and optionally 'scifi' story keys
        """
        self.logger.info(f"Generating stories for: {topic.title}")

        stories = {}

        # Generate fantasy version
        fantasy_story = self._generate_story(topic, "fantasy")
        if fantasy_story:
            stories["fantasy"] = fantasy_story

        # Generate sci-fi version
        if include_scifi:
            scifi_story = self._generate_story(topic, "scifi")
            if scifi_story:
                stories["scifi"] = scifi_story

        return stories

    def _generate_story(self, topic: Topic, genre: str) -> Optional[str]:
        """Generate a single story in the specified genre."""
        if not self.gemini:
            return self._basic_story(topic, genre)

        genre_info = self.GENRES.get(genre, self.GENRES["fantasy"])

        prompt = f"""Write an engaging {genre} story that teaches the following educational content.
The story should seamlessly weave the educational material into the narrative.

Educational Topic: {topic.title}
Key Concepts: {', '.join(topic.keywords)}
Content to teach:
{topic.content[:4000]}

Story Requirements:
1. Setting: {genre_info['setting']}
2. Elements to include: {', '.join(genre_info['elements'])}
3. Length: 2000-2500 words
4. Create memorable characters who discover or embody the educational concepts
5. Use the story's plot to explain and demonstrate the key ideas
6. Include dialogue that naturally explains concepts
7. Have a clear beginning (setup), middle (conflict/learning), and end (resolution)
8. Make complex concepts accessible through the narrative
9. Include a "moral" or "lesson learned" that reinforces the main concept
10. Make it entertaining while being educational

Story Structure:
- Opening hook that draws readers in
- Character introduction
- Inciting incident related to the topic
- Rising action where concepts are explored
- Climax where understanding is achieved
- Resolution that reinforces learning

Write the {genre} story:"""

        try:
            response = self.gemini.generate(prompt, temperature=0.8)
            if response:
                return self._format_story(topic, response.text, genre)
        except Exception as e:
            self.logger.error(f"Story generation failed: {e}")

        return self._basic_story(topic, genre)

    def _format_story(self, topic: Topic, content: str, genre: str) -> str:
        """Format story with metadata."""
        genre_emoji = "🧙" if genre == "fantasy" else "🚀" if genre == "scifi" else "🌟"

        return f"""# {genre_emoji} {topic.title}: A {genre.title()} Tale

## Story Information
- **Educational Topic:** {topic.title}
- **Genre:** {genre.title()}
- **Key Concepts:** {', '.join(topic.keywords)}
- **Difficulty:** {topic.difficulty}

---

{content}

---

## Educational Takeaways

This story was designed to teach the following concepts:

{chr(10).join(f'- **{kw}**' for kw in topic.keywords)}

### Summary
{topic.summary}

---
*This story was generated to make learning about "{topic.title}" more engaging and memorable.*
"""

    def _basic_story(self, topic: Topic, genre: str) -> str:
        """Create basic story framework when AI unavailable."""
        genre_info = self.GENRES.get(genre, self.GENRES["fantasy"])

        if genre == "fantasy":
            opening = f"In a realm where knowledge held magical power, a young apprentice named Lyra sought to understand {topic.title}..."
        else:
            opening = f"In the year 3024, aboard the research vessel Prometheus, Dr. Chen discovered something that would change everything about {topic.title}..."

        return f"""# {topic.title}: A {genre.title()} Tale

## Story

{opening}

---

*This is a story template. The full story generation requires the Gemini API.*

### Story Elements to Include:
- Setting: {genre_info['setting']}
- Key concepts: {', '.join(topic.keywords)}

### Plot Outline:
1. Introduction: Character discovers {topic.title}
2. Rising action: Learning about {', '.join(topic.keywords[:3])}
3. Climax: Using knowledge to overcome challenge
4. Resolution: Understanding the importance of these concepts

### Educational Content:
{topic.summary}

---
*Genre: {genre.title()}*
"""

    def save(
        self,
        topic: Topic,
        stories: dict[str, str]
    ) -> dict[str, Optional[Path]]:
        """Save stories to files."""
        saved_paths = {}

        if not self.downloader:
            return saved_paths

        for genre, content in stories.items():
            filename = f"story_{genre}_{topic.id:02d}_{self._sanitize_filename(topic.title)}"
            path = self.downloader.save_text_content(
                content, filename, "stories", "md"
            )
            saved_paths[genre] = path

        return saved_paths

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
