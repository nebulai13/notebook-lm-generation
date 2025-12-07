"""Topic splitter using Gemini AI."""

import json
import re
from typing import Optional
from dataclasses import dataclass, field

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from .content_processor import ProcessedContent
from ..utils.logger import get_logger
from ..config.settings import get_settings


@dataclass
class Topic:
    """Represents a single topic extracted from content."""
    id: int
    title: str
    summary: str
    content: str
    keywords: list[str] = field(default_factory=list)
    subtopics: list[str] = field(default_factory=list)
    difficulty: str = "medium"  # easy, medium, hard
    estimated_study_time: str = ""


@dataclass
class SplitContent:
    """Container for split content with topics."""
    original_title: str
    topics: list[Topic]
    total_topics: int
    overview: str


class TopicSplitter:
    """
    Splits content into topics using Gemini AI.

    Analyzes the content and identifies distinct topics that can
    be processed individually by NotebookLM.
    """

    SPLIT_PROMPT = """Analyze the following educational content and split it into distinct topics.
Each topic should be self-contained enough to create a short educational video (5-10 minutes).

For each topic, provide:
1. A clear, concise title
2. A brief summary (2-3 sentences)
3. The relevant content excerpt
4. Key keywords (5-10)
5. Any subtopics
6. Difficulty level (easy, medium, hard)
7. Estimated study time

Return the result as a JSON object with this structure:
{
    "overview": "Brief overview of the entire content",
    "topics": [
        {
            "id": 1,
            "title": "Topic Title",
            "summary": "Brief summary of the topic",
            "content": "The actual content for this topic",
            "keywords": ["keyword1", "keyword2"],
            "subtopics": ["subtopic1", "subtopic2"],
            "difficulty": "medium",
            "estimated_study_time": "15 minutes"
        }
    ]
}

Content to analyze:

{content}

Return ONLY valid JSON, no additional text."""

    def __init__(self, api_key: Optional[str] = None):
        self.logger = get_logger()
        self.settings = get_settings()

        if not HAS_GENAI:
            self.logger.warning("google-generativeai not installed")
            self.model = None
        else:
            api_key = api_key or self.settings.gemini_api_key
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
            else:
                self.logger.warning("No Gemini API key provided")
                self.model = None

    def split(self, content: ProcessedContent, max_topics: int = 10) -> SplitContent:
        """
        Split content into topics.

        Args:
            content: Processed content to split
            max_topics: Maximum number of topics to extract

        Returns:
            SplitContent with extracted topics
        """
        if not self.model:
            # Fallback to simple splitting if no API
            return self._fallback_split(content, max_topics)

        self.logger.info(f"Splitting content into topics using Gemini AI...")

        try:
            # Prepare the prompt
            prompt = self.SPLIT_PROMPT.format(content=content.cleaned_text[:30000])

            # Generate response
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=8000,
                )
            )

            # Parse JSON response
            result_text = response.text.strip()

            # Clean up response if needed
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            result = json.loads(result_text)

            # Create Topic objects
            topics = []
            for i, topic_data in enumerate(result.get("topics", [])[:max_topics]):
                topic = Topic(
                    id=topic_data.get("id", i + 1),
                    title=topic_data.get("title", f"Topic {i + 1}"),
                    summary=topic_data.get("summary", ""),
                    content=topic_data.get("content", ""),
                    keywords=topic_data.get("keywords", []),
                    subtopics=topic_data.get("subtopics", []),
                    difficulty=topic_data.get("difficulty", "medium"),
                    estimated_study_time=topic_data.get("estimated_study_time", "")
                )
                topics.append(topic)

            split_content = SplitContent(
                original_title=content.title,
                topics=topics,
                total_topics=len(topics),
                overview=result.get("overview", "")
            )

            self.logger.info(f"Successfully split content into {len(topics)} topics")
            return split_content

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Gemini response: {e}")
            return self._fallback_split(content, max_topics)
        except Exception as e:
            self.logger.error(f"Failed to split content: {e}")
            return self._fallback_split(content, max_topics)

    def _fallback_split(self, content: ProcessedContent, max_topics: int) -> SplitContent:
        """
        Fallback splitting when API is unavailable.

        Uses simple heuristics to split content by headings or paragraphs.
        """
        self.logger.info("Using fallback topic splitting...")

        text = content.cleaned_text
        topics = []

        # Try to split by markdown headings
        heading_pattern = r"^(#{1,3})\s+(.+)$"
        sections = re.split(r"\n(?=#{1,3}\s)", text)

        if len(sections) > 1:
            # Content has headings
            for i, section in enumerate(sections[:max_topics]):
                lines = section.strip().split("\n")
                title_match = re.match(heading_pattern, lines[0])

                if title_match:
                    title = title_match.group(2).strip()
                    section_content = "\n".join(lines[1:]).strip()
                else:
                    title = f"Section {i + 1}"
                    section_content = section.strip()

                if section_content:
                    topics.append(Topic(
                        id=i + 1,
                        title=title,
                        summary=section_content[:200] + "..." if len(section_content) > 200 else section_content,
                        content=section_content,
                        keywords=self._extract_keywords(section_content),
                    ))
        else:
            # Split by paragraphs or fixed chunks
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

            # Group paragraphs into topics
            chunk_size = max(1, len(paragraphs) // max_topics)

            for i in range(0, len(paragraphs), chunk_size):
                chunk = paragraphs[i:i + chunk_size]
                chunk_text = "\n\n".join(chunk)

                # Get first sentence as title
                first_sentence = chunk_text.split(".")[0][:100]

                topics.append(Topic(
                    id=len(topics) + 1,
                    title=f"Part {len(topics) + 1}: {first_sentence}",
                    summary=chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                    content=chunk_text,
                    keywords=self._extract_keywords(chunk_text),
                ))

                if len(topics) >= max_topics:
                    break

        return SplitContent(
            original_title=content.title,
            topics=topics,
            total_topics=len(topics),
            overview=f"Content split into {len(topics)} parts based on structure."
        )

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Extract simple keywords from text."""
        # Remove common words and get unique words
        common_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "this", "that", "these",
            "those", "it", "its", "they", "them", "their", "we", "you", "he",
            "she", "him", "her", "his", "as", "if", "then", "than", "so", "such",
            "can", "not", "no", "more", "most", "other", "some", "any", "all",
        }

        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        word_freq = {}

        for word in words:
            if word not in common_words:
                word_freq[word] = word_freq.get(word, 0) + 1

        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]
