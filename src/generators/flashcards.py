"""Flashcard generator module - for NotebookLM and Anki."""

import json
import re
from typing import Optional
from pathlib import Path
from dataclasses import dataclass, field

from .notebooklm import NotebookLMClient
from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


@dataclass
class Flashcard:
    """A single flashcard."""
    front: str
    back: str
    topic: str = ""
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"


@dataclass
class FlashcardDeck:
    """A collection of flashcards."""
    name: str
    cards: list[Flashcard]
    topic_id: int = 0


class FlashcardGenerator:
    """Generates flashcards (Karteikarten) for NotebookLM and Anki."""

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

    def generate(
        self,
        topic: Topic,
        num_cards: int = 15,
        include_notebooklm: bool = True
    ) -> FlashcardDeck:
        """
        Generate flashcards for a topic.

        Args:
            topic: Topic to create flashcards for
            num_cards: Number of cards to generate
            include_notebooklm: Also generate via NotebookLM

        Returns:
            FlashcardDeck with generated cards
        """
        self.logger.info(f"Generating flashcards for: {topic.title}")

        cards = []

        # Try NotebookLM first
        if include_notebooklm and self.notebooklm:
            try:
                nlm_cards = self._generate_via_notebooklm(topic)
                cards.extend(nlm_cards)
            except Exception as e:
                self.logger.warning(f"NotebookLM flashcard generation failed: {e}")

        # Generate additional cards via Gemini
        if self.gemini:
            remaining = max(0, num_cards - len(cards))
            if remaining > 0:
                try:
                    gemini_cards = self._generate_via_gemini(topic, remaining)
                    cards.extend(gemini_cards)
                except Exception as e:
                    self.logger.warning(f"Gemini flashcard generation failed: {e}")

        # If still not enough cards, use basic generation
        if len(cards) < num_cards:
            basic_cards = self._generate_basic_cards(topic, num_cards - len(cards))
            cards.extend(basic_cards)

        return FlashcardDeck(
            name=f"Flashcards: {topic.title}",
            cards=cards[:num_cards],
            topic_id=topic.id
        )

    def _generate_via_notebooklm(self, topic: Topic) -> list[Flashcard]:
        """Generate flashcards using NotebookLM."""
        response = self.notebooklm.generate_flashcards()
        if not response:
            return []

        return self._parse_flashcard_text(response, topic)

    def _generate_via_gemini(self, topic: Topic, num_cards: int) -> list[Flashcard]:
        """Generate flashcards using Gemini."""
        prompt = f"""Create {num_cards} flashcards for studying this topic.

Topic: {topic.title}
Content: {topic.content[:4000]}

Return as JSON array:
[
    {{
        "front": "Question or term",
        "back": "Answer or definition",
        "difficulty": "easy|medium|hard"
    }}
]

Guidelines:
1. Mix question types: definitions, concepts, applications
2. Front should be a clear question or term
3. Back should be a concise but complete answer
4. Cover the most important concepts
5. Vary difficulty levels
6. Make answers self-contained (understandable without context)

Return only valid JSON."""

        response = self.gemini.generate(prompt, temperature=0.4)
        if not response:
            return []

        try:
            # Clean up response
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            cards_data = json.loads(text)

            cards = []
            for card_data in cards_data:
                cards.append(Flashcard(
                    front=card_data.get("front", ""),
                    back=card_data.get("back", ""),
                    topic=topic.title,
                    tags=topic.keywords[:3],
                    difficulty=card_data.get("difficulty", "medium")
                ))

            return cards

        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse flashcard JSON: {e}")
            return self._parse_flashcard_text(response.text, topic)

    def _parse_flashcard_text(self, text: str, topic: Topic) -> list[Flashcard]:
        """Parse flashcards from text format (Q: ... A: ...)."""
        cards = []

        # Pattern for Q: ... A: ... format
        qa_pattern = r"Q:\s*(.+?)\s*A:\s*(.+?)(?=Q:|$)"
        matches = re.findall(qa_pattern, text, re.DOTALL | re.IGNORECASE)

        for question, answer in matches:
            cards.append(Flashcard(
                front=question.strip(),
                back=answer.strip(),
                topic=topic.title,
                tags=topic.keywords[:3]
            ))

        # Alternative pattern: numbered questions
        if not cards:
            num_pattern = r"\d+\.\s*(?:Question|Q)?[:\s]*(.+?)\s*(?:Answer|A)?[:\s]*(.+?)(?=\d+\.|$)"
            matches = re.findall(num_pattern, text, re.DOTALL | re.IGNORECASE)

            for question, answer in matches:
                if question.strip() and answer.strip():
                    cards.append(Flashcard(
                        front=question.strip(),
                        back=answer.strip(),
                        topic=topic.title,
                        tags=topic.keywords[:3]
                    ))

        return cards

    def _generate_basic_cards(self, topic: Topic, num_cards: int) -> list[Flashcard]:
        """Generate basic flashcards from keywords when AI unavailable."""
        cards = []

        # Create cards from keywords
        for i, keyword in enumerate(topic.keywords[:num_cards]):
            cards.append(Flashcard(
                front=f"What is {keyword}?",
                back=f"(Define {keyword} in the context of {topic.title})",
                topic=topic.title,
                tags=[keyword],
                difficulty="medium"
            ))

        # Create card from summary
        if len(cards) < num_cards:
            cards.append(Flashcard(
                front=f"Summarize the main points of {topic.title}",
                back=topic.summary,
                topic=topic.title,
                difficulty="hard"
            ))

        return cards[:num_cards]

    def save_markdown(self, deck: FlashcardDeck) -> Optional[Path]:
        """Save flashcards as markdown file."""
        if not self.downloader:
            return None

        content = f"""# {deck.name}

## Flashcards

{chr(10).join(self._format_card_md(i, card) for i, card in enumerate(deck.cards, 1))}

---
**Total Cards:** {len(deck.cards)}
"""

        filename = f"flashcards_{deck.topic_id:02d}_{self._sanitize_filename(deck.name)}"
        return self.downloader.save_text_content(content, filename, "flashcards", "md")

    def save_anki(self, deck: FlashcardDeck) -> Optional[Path]:
        """Save flashcards as Anki-compatible file."""
        if not self.downloader:
            return None

        cards_data = [{"front": c.front, "back": c.back} for c in deck.cards]
        filename = f"anki_{deck.topic_id:02d}_{self._sanitize_filename(deck.name)}"

        return self.downloader.create_anki_deck(
            cards_data,
            deck.name,
            filename
        )

    def _format_card_md(self, num: int, card: Flashcard) -> str:
        """Format a single card as markdown."""
        return f"""### Card {num}
**Front:** {card.front}

**Back:** {card.back}

*Difficulty: {card.difficulty}* | *Tags: {', '.join(card.tags)}*

---
"""

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
