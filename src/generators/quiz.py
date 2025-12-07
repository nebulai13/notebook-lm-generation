"""Quiz generator module."""

import json
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
class QuizQuestion:
    """A single quiz question."""
    id: int
    type: str  # multiple_choice, true_false, short_answer
    question: str
    options: list[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    difficulty: str = "medium"


@dataclass
class Quiz:
    """A complete quiz."""
    title: str
    topic_id: int
    questions: list[QuizQuestion]
    total_points: int = 0


class QuizGenerator:
    """Generates quizzes for each topic."""

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
        num_questions: int = 10,
        question_types: list[str] = None
    ) -> Quiz:
        """
        Generate a quiz for a topic.

        Args:
            topic: Topic to create quiz for
            num_questions: Number of questions
            question_types: Types to include (multiple_choice, true_false, short_answer)

        Returns:
            Quiz object with questions
        """
        self.logger.info(f"Generating quiz for: {topic.title}")

        if question_types is None:
            question_types = ["multiple_choice", "true_false", "short_answer"]

        questions = []

        # Try Gemini for quiz generation
        if self.gemini:
            try:
                questions = self._generate_via_gemini(topic, num_questions, question_types)
            except Exception as e:
                self.logger.warning(f"Gemini quiz generation failed: {e}")

        # Fallback to basic questions
        if len(questions) < num_questions:
            basic = self._generate_basic_questions(
                topic, num_questions - len(questions), question_types
            )
            questions.extend(basic)

        quiz = Quiz(
            title=f"Quiz: {topic.title}",
            topic_id=topic.id,
            questions=questions[:num_questions],
            total_points=sum(
                3 if q.type == "short_answer" else 2 if q.type == "multiple_choice" else 1
                for q in questions[:num_questions]
            )
        )

        return quiz

    def _generate_via_gemini(
        self,
        topic: Topic,
        num_questions: int,
        question_types: list[str]
    ) -> list[QuizQuestion]:
        """Generate quiz questions using Gemini."""
        types_desc = ", ".join(question_types)

        prompt = f"""Create a quiz with {num_questions} questions about the following topic.
Include these question types: {types_desc}

Topic: {topic.title}
Content: {topic.content[:4000]}

Return as JSON:
{{
    "questions": [
        {{
            "id": 1,
            "type": "multiple_choice",
            "question": "Question text?",
            "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
            "correct_answer": "A",
            "explanation": "Why this is correct",
            "difficulty": "medium"
        }},
        {{
            "id": 2,
            "type": "true_false",
            "question": "Statement to evaluate.",
            "correct_answer": "True",
            "explanation": "Why true/false",
            "difficulty": "easy"
        }},
        {{
            "id": 3,
            "type": "short_answer",
            "question": "Question requiring written answer?",
            "correct_answer": "Expected answer",
            "explanation": "Key points to include",
            "difficulty": "hard"
        }}
    ]
}}

Guidelines:
1. Mix difficulty levels (easy, medium, hard)
2. Cover different aspects of the topic
3. Make multiple choice distractors plausible
4. Explanations should be educational
5. Short answer questions should have clear criteria

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

            data = json.loads(text)
            questions = []

            for q_data in data.get("questions", []):
                questions.append(QuizQuestion(
                    id=q_data.get("id", len(questions) + 1),
                    type=q_data.get("type", "multiple_choice"),
                    question=q_data.get("question", ""),
                    options=q_data.get("options", []),
                    correct_answer=str(q_data.get("correct_answer", "")),
                    explanation=q_data.get("explanation", ""),
                    difficulty=q_data.get("difficulty", "medium")
                ))

            return questions

        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse quiz JSON: {e}")
            return []

    def _generate_basic_questions(
        self,
        topic: Topic,
        num_questions: int,
        question_types: list[str]
    ) -> list[QuizQuestion]:
        """Generate basic questions when AI unavailable."""
        questions = []

        # Generate from keywords
        for i, keyword in enumerate(topic.keywords[:num_questions]):
            if i % 3 == 0 and "multiple_choice" in question_types:
                questions.append(QuizQuestion(
                    id=len(questions) + 1,
                    type="multiple_choice",
                    question=f"Which of the following best describes {keyword}?",
                    options=[
                        f"A) Definition related to {keyword}",
                        "B) An unrelated concept",
                        "C) A different term",
                        "D) None of the above"
                    ],
                    correct_answer="A",
                    explanation=f"Review the definition of {keyword}",
                    difficulty="medium"
                ))
            elif i % 3 == 1 and "true_false" in question_types:
                questions.append(QuizQuestion(
                    id=len(questions) + 1,
                    type="true_false",
                    question=f"{keyword} is an important concept in {topic.title}.",
                    correct_answer="True",
                    explanation=f"{keyword} is covered in this topic",
                    difficulty="easy"
                ))
            elif "short_answer" in question_types:
                questions.append(QuizQuestion(
                    id=len(questions) + 1,
                    type="short_answer",
                    question=f"Explain the concept of {keyword} in your own words.",
                    correct_answer=f"Answer should explain {keyword}",
                    explanation="Key points to include",
                    difficulty="hard"
                ))

        return questions[:num_questions]

    def save(self, quiz: Quiz) -> Optional[Path]:
        """Save quiz to file."""
        if not self.downloader:
            return None

        content = self._format_quiz_md(quiz)
        filename = f"quiz_{quiz.topic_id:02d}_{self._sanitize_filename(quiz.title)}"

        return self.downloader.save_text_content(content, filename, "quizzes", "md")

    def save_with_answers(self, quiz: Quiz) -> Optional[Path]:
        """Save quiz with answer key."""
        if not self.downloader:
            return None

        content = self._format_quiz_md(quiz, include_answers=True)
        filename = f"quiz_answers_{quiz.topic_id:02d}_{self._sanitize_filename(quiz.title)}"

        return self.downloader.save_text_content(content, filename, "quizzes", "md")

    def _format_quiz_md(self, quiz: Quiz, include_answers: bool = False) -> str:
        """Format quiz as markdown."""
        lines = [
            f"# {quiz.title}",
            "",
            f"**Total Questions:** {len(quiz.questions)}",
            f"**Total Points:** {quiz.total_points}",
            "",
            "---",
            ""
        ]

        for q in quiz.questions:
            points = 3 if q.type == "short_answer" else 2 if q.type == "multiple_choice" else 1
            lines.append(f"## Question {q.id} ({points} points) - {q.difficulty.title()}")
            lines.append("")
            lines.append(q.question)
            lines.append("")

            if q.type == "multiple_choice" and q.options:
                for option in q.options:
                    lines.append(f"- {option}")
                lines.append("")

            if include_answers:
                lines.append(f"**Answer:** {q.correct_answer}")
                if q.explanation:
                    lines.append(f"**Explanation:** {q.explanation}")
                lines.append("")

            lines.append("---")
            lines.append("")

        if not include_answers:
            lines.extend([
                "",
                "## Answer Space",
                "",
                "| Question | Answer |",
                "|----------|--------|",
            ])
            for q in quiz.questions:
                lines.append(f"| {q.id} | |")

        return "\n".join(lines)

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
