"""Learning strategy paper generator module."""

from typing import Optional
from pathlib import Path

from .gemini_client import GeminiClient
from ..processors.topic_splitter import Topic, SplitContent
from ..utils.logger import get_logger
from ..utils.downloader import Downloader


class StrategyGenerator:
    """Generates comprehensive learning strategy papers for exam preparation."""

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
        split_content: SplitContent,
        exam_type: str = "general",
        study_duration: str = "2 weeks"
    ) -> Optional[str]:
        """
        Generate a learning strategy paper for all topics.

        Args:
            split_content: All topics from the content
            exam_type: Type of exam (general, multiple_choice, essay, practical)
            study_duration: Available study time

        Returns:
            Strategy paper as markdown
        """
        self.logger.info("Generating learning strategy paper...")

        topics_summary = "\n".join(
            f"- **{t.title}** ({t.difficulty}): {t.summary[:100]}..."
            for t in split_content.topics
        )

        all_keywords = []
        for topic in split_content.topics:
            all_keywords.extend(topic.keywords)
        unique_keywords = list(set(all_keywords))[:20]

        if self.gemini:
            try:
                prompt = f"""Create a comprehensive learning strategy paper for exam preparation.

## Content Overview
Title: {split_content.original_title}
Number of topics: {split_content.total_topics}
Overall summary: {split_content.overview}

## Topics to Study:
{topics_summary}

## Key Terms Across All Topics:
{', '.join(unique_keywords)}

## Exam Details:
- Type: {exam_type}
- Available study time: {study_duration}

## Create a strategy paper with these sections:

1. **Executive Summary** (200 words)
   - Overall approach
   - Key success factors

2. **Study Schedule**
   - Day-by-day breakdown for {study_duration}
   - Time allocation per topic
   - Review sessions

3. **Topic-by-Topic Strategy**
   For each topic:
   - Priority level (high/medium/low)
   - Key concepts to master
   - Recommended study techniques
   - Common mistakes to avoid
   - Self-check questions

4. **Memory Techniques**
   - Mnemonics for key terms
   - Visualization strategies
   - Connection maps between topics

5. **Practice Strategy**
   - Types of practice exercises
   - Self-assessment approach
   - Weak area identification

6. **Exam Technique**
   - Time management during exam
   - Question approach strategy
   - Common pitfalls to avoid

7. **Day-Before Checklist**
   - Final review priorities
   - Mental preparation
   - Logistics

8. **Exam Day Tips**
   - Morning routine
   - During the exam
   - If you get stuck

9. **Stress Management**
   - Study break strategies
   - Anxiety management
   - Maintaining motivation

10. **Resources**
    - Additional study materials
    - Practice test sources
    - Help resources

Format in Markdown with clear headings. Be specific and actionable."""

                response = self.gemini.generate(prompt, temperature=0.5, max_tokens=6000)
                if response:
                    return self._format_strategy(split_content, response.text, exam_type)
            except Exception as e:
                self.logger.error(f"Strategy generation failed: {e}")

        return self._basic_strategy(split_content, exam_type, study_duration)

    def _format_strategy(
        self,
        split_content: SplitContent,
        content: str,
        exam_type: str
    ) -> str:
        """Format strategy paper with metadata."""
        return f"""# Learning Strategy: {split_content.original_title}

## Document Information
- **Subject:** {split_content.original_title}
- **Topics Covered:** {split_content.total_topics}
- **Exam Type:** {exam_type}
- **Generated:** (current date)

---

{content}

---

## Quick Reference: All Topics

| # | Topic | Difficulty | Keywords |
|---|-------|------------|----------|
{chr(10).join(f"| {t.id} | {t.title} | {t.difficulty} | {', '.join(t.keywords[:3])} |" for t in split_content.topics)}

---
*This strategy paper was generated to help you effectively prepare for your exam.*
"""

    def _basic_strategy(
        self,
        split_content: SplitContent,
        exam_type: str,
        study_duration: str
    ) -> str:
        """Create basic strategy when AI unavailable."""
        topics_list = "\n".join(
            f"### {i}. {t.title}\n- Difficulty: {t.difficulty}\n- Keywords: {', '.join(t.keywords)}\n"
            for i, t in enumerate(split_content.topics, 1)
        )

        return f"""# Learning Strategy: {split_content.original_title}

## Overview
- **Topics:** {split_content.total_topics}
- **Exam Type:** {exam_type}
- **Study Duration:** {study_duration}

## Summary
{split_content.overview}

## Topics to Cover

{topics_list}

## General Study Tips

### Before Studying
- [ ] Gather all materials
- [ ] Create a quiet study space
- [ ] Set specific goals for each session

### During Study
- [ ] Use active recall (test yourself)
- [ ] Take breaks every 45-60 minutes
- [ ] Create summary notes

### After Studying
- [ ] Review notes within 24 hours
- [ ] Teach concepts to someone else
- [ ] Identify weak areas

## Exam Day
- [ ] Get enough sleep
- [ ] Eat a good breakfast
- [ ] Arrive early
- [ ] Read all questions first
- [ ] Manage your time

---
*Customize this strategy based on your learning style.*
"""

    def save(self, split_content: SplitContent, content: str) -> Optional[Path]:
        """Save strategy paper to file."""
        if self.downloader:
            filename = f"strategy_{self._sanitize_filename(split_content.original_title)}"
            return self.downloader.save_text_content(
                content, filename, "strategies", "md"
            )
        return None

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        name = re.sub(r'[^\w\s-]', '', name.lower())
        return re.sub(r'[-\s]+', '_', name).strip('_')[:50]
