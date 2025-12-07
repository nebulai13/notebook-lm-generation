#!/usr/bin/env python3
"""
NotebookLM Generation Tool - Main Entry Point

Automated generation of learning materials from educational content.
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from .config.settings import get_settings, ProcessingStep
from .auth.google_auth import GoogleAuthenticator
from .processors.content_processor import ContentProcessor
from .processors.topic_splitter import TopicSplitter
from .generators.notebooklm import NotebookLMClient
from .generators.gemini_client import GeminiClient
from .generators.handout import HandoutGenerator
from .generators.cheatsheet import CheatsheetGenerator
from .generators.mindmap import MindmapGenerator
from .generators.audiobook import AudiobookGenerator
from .generators.story import StoryGenerator
from .generators.strategy import StrategyGenerator
from .generators.flashcards import FlashcardGenerator
from .generators.quiz import QuizGenerator
from .generators.discussion import DiscussionGenerator
from .utils.logger import setup_logger, get_logger, LogContext
from .utils.progress_reporter import ProgressReporter
from .utils.downloader import Downloader


class NotebookLMGenerator:
    """
    Main orchestrator for the NotebookLM Generation pipeline.

    Coordinates all processing steps from content input to final output.
    """

    def __init__(
        self,
        input_path: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = False,
        output_dir: Optional[Path] = None,
        gemini_api_key: Optional[str] = None
    ):
        self.input_path = Path(input_path) if not input_path.startswith("http") else input_path
        self.email = email
        self.password = password
        self.headless = headless
        self.settings = get_settings()

        # Determine output directory
        if output_dir:
            self.output_dir = output_dir
        elif isinstance(self.input_path, Path):
            self.output_dir = self.input_path.parent / f"{self.input_path.stem}_output"
        else:
            self.output_dir = Path.cwd() / "output"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger
        self.logger = setup_logger(
            log_level=self.settings.log_level,
            log_file=self.settings.log_file,
            output_dir=self.output_dir
        )

        # Initialize progress reporter
        self.progress = ProgressReporter(
            update_interval=self.settings.progress_update_interval
        )

        # Initialize downloader
        self.downloader = Downloader(self.output_dir)

        # Initialize components (will be set up in run())
        self.authenticator: Optional[GoogleAuthenticator] = None
        self.notebooklm: Optional[NotebookLMClient] = None
        self.gemini: Optional[GeminiClient] = None
        self.gemini_api_key = gemini_api_key or self.settings.gemini_api_key

    def run(self) -> bool:
        """
        Execute the full generation pipeline.

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("=" * 60)
        self.logger.info("NotebookLM Generation Tool")
        self.logger.info(f"Input: {self.input_path}")
        self.logger.info(f"Output: {self.output_dir}")
        self.logger.info("=" * 60)

        self.progress.start()

        try:
            # Step 1: Authentication
            if not self._authenticate():
                return False

            # Step 2: Load and process content
            content = self._load_content()
            if not content:
                return False

            # Step 3: Split into topics
            split_content = self._split_topics(content)
            if not split_content:
                return False

            # Step 4: Generate all materials
            self._generate_all_materials(split_content)

            # Step 5: Open Gemini at the end
            self._open_gemini_final()

            # Step 6: Final summary
            self._finalize()

            return True

        except KeyboardInterrupt:
            self.logger.warning("Process interrupted by user")
            return False
        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}")
            return False
        finally:
            self.progress.stop()
            self._cleanup()

    def _authenticate(self) -> bool:
        """Authenticate with Google."""
        self.progress.set_step(ProcessingStep.AUTHENTICATION, "Logging into Google...")

        try:
            self.authenticator = GoogleAuthenticator(
                email=self.email,
                password=self.password,
                headless=self.headless
            )

            if self.email and self.password:
                success = self.authenticator.login_google()
                if not success:
                    self.progress.fail_step(ProcessingStep.AUTHENTICATION, "Login failed")
                    return False

            # Initialize clients
            self.notebooklm = NotebookLMClient(self.authenticator)
            self.gemini = GeminiClient(
                api_key=self.gemini_api_key,
                authenticator=self.authenticator,
                use_browser=False  # Use API by default
            )

            self.progress.complete_step(ProcessingStep.AUTHENTICATION)
            return True

        except Exception as e:
            self.progress.fail_step(ProcessingStep.AUTHENTICATION, str(e))
            self.logger.error(f"Authentication failed: {e}")
            return False

    def _load_content(self):
        """Load and process input content."""
        self.progress.set_step(ProcessingStep.CONTENT_LOADING, "Processing input content...")

        try:
            processor = ContentProcessor()
            content = processor.process(self.input_path)

            self.logger.info(f"Loaded content: {content.title}")
            self.logger.info(f"Word count: {content.word_count}")

            self.progress.complete_step(ProcessingStep.CONTENT_LOADING)
            return content

        except Exception as e:
            self.progress.fail_step(ProcessingStep.CONTENT_LOADING, str(e))
            self.logger.error(f"Content loading failed: {e}")
            return None

    def _split_topics(self, content):
        """Split content into topics."""
        self.progress.set_step(ProcessingStep.TOPIC_SPLITTING, "Analyzing content and splitting into topics...")

        try:
            splitter = TopicSplitter(api_key=self.gemini_api_key)
            split_content = splitter.split(content)

            self.logger.info(f"Split into {split_content.total_topics} topics")
            for topic in split_content.topics:
                self.logger.info(f"  - {topic.title}")

            self.progress.complete_step(ProcessingStep.TOPIC_SPLITTING)
            return split_content

        except Exception as e:
            self.progress.fail_step(ProcessingStep.TOPIC_SPLITTING, str(e))
            self.logger.error(f"Topic splitting failed: {e}")
            return None

    def _generate_all_materials(self, split_content):
        """Generate all learning materials."""
        topics = split_content.topics

        # Set up generators
        handout_gen = HandoutGenerator(self.notebooklm, self.gemini, self.downloader)
        cheatsheet_gen = CheatsheetGenerator(self.notebooklm, self.gemini, self.downloader)
        mindmap_gen = MindmapGenerator(self.notebooklm, self.gemini, self.downloader)
        audiobook_gen = AudiobookGenerator(self.notebooklm, self.gemini, self.downloader)
        story_gen = StoryGenerator(self.gemini, self.downloader)
        strategy_gen = StrategyGenerator(self.gemini, self.downloader)
        flashcard_gen = FlashcardGenerator(self.notebooklm, self.gemini, self.downloader)
        quiz_gen = QuizGenerator(self.gemini, self.notebooklm, self.downloader)
        discussion_gen = DiscussionGenerator(self.gemini, self.notebooklm, self.downloader)

        # Generate for each topic
        for topic in topics:
            self.logger.info(f"\n{'='*40}")
            self.logger.info(f"Processing Topic {topic.id}: {topic.title}")
            self.logger.info(f"{'='*40}")

            # Videos (via NotebookLM)
            self.progress.set_step(
                ProcessingStep.VIDEO_GENERATION,
                f"Generating video for: {topic.title}"
            )
            try:
                if self.notebooklm:
                    self.notebooklm.create_notebook(topic.title)
                    self.notebooklm.add_text_source(topic.content, topic.title)
                    self.notebooklm.generate_audio_overview()
            except Exception as e:
                self.logger.warning(f"Video generation failed for {topic.title}: {e}")

            # Handouts
            self.progress.set_step(
                ProcessingStep.HANDOUT_GENERATION,
                f"Generating handout for: {topic.title}"
            )
            try:
                handout = handout_gen.generate(topic)
                if handout:
                    handout_gen.save(topic, handout)
            except Exception as e:
                self.logger.warning(f"Handout generation failed: {e}")

            # Cheatsheets
            self.progress.set_step(
                ProcessingStep.CHEATSHEET_GENERATION,
                f"Generating cheatsheet for: {topic.title}"
            )
            try:
                cheatsheet = cheatsheet_gen.generate(topic)
                if cheatsheet:
                    cheatsheet_gen.save(topic, cheatsheet)
            except Exception as e:
                self.logger.warning(f"Cheatsheet generation failed: {e}")

            # Mindmaps
            self.progress.set_step(
                ProcessingStep.MINDMAP_GENERATION,
                f"Generating mindmap for: {topic.title}"
            )
            try:
                mindmap = mindmap_gen.generate(topic)
                if mindmap:
                    mindmap_gen.save(topic, mindmap)
            except Exception as e:
                self.logger.warning(f"Mindmap generation failed: {e}")

            # Audiobook chapters
            self.progress.set_step(
                ProcessingStep.AUDIOBOOK_GENERATION,
                f"Generating audiobook for: {topic.title}"
            )
            try:
                script = audiobook_gen.generate_script(topic)
                if script:
                    audiobook_gen.save_script(topic, script)
            except Exception as e:
                self.logger.warning(f"Audiobook generation failed: {e}")

            # Stories (Fantasy + Sci-Fi)
            self.progress.set_step(
                ProcessingStep.STORY_GENERATION,
                f"Generating stories for: {topic.title}"
            )
            try:
                stories = story_gen.generate(topic)
                story_gen.save(topic, stories)
            except Exception as e:
                self.logger.warning(f"Story generation failed: {e}")

            # Flashcards (NotebookLM + Anki)
            self.progress.set_step(
                ProcessingStep.FLASHCARD_GENERATION,
                f"Generating flashcards for: {topic.title}"
            )
            try:
                deck = flashcard_gen.generate(topic)
                flashcard_gen.save_markdown(deck)
                flashcard_gen.save_anki(deck)  # Also creates Anki deck
            except Exception as e:
                self.logger.warning(f"Flashcard generation failed: {e}")

            # Quiz
            self.progress.set_step(
                ProcessingStep.QUIZ_GENERATION,
                f"Generating quiz for: {topic.title}"
            )
            try:
                quiz = quiz_gen.generate(topic)
                quiz_gen.save(quiz)
                quiz_gen.save_with_answers(quiz)
            except Exception as e:
                self.logger.warning(f"Quiz generation failed: {e}")

            # Podium Discussion
            self.progress.set_step(
                ProcessingStep.DISCUSSION_GENERATION,
                f"Generating discussion for: {topic.title}"
            )
            try:
                discussion = discussion_gen.generate(topic, with_video=False)
                discussion_gen.save(discussion)
            except Exception as e:
                self.logger.warning(f"Discussion generation failed: {e}")

        # Generate overall strategy paper
        self.progress.set_step(
            ProcessingStep.STRATEGY_GENERATION,
            "Generating learning strategy paper..."
        )
        try:
            strategy = strategy_gen.generate(split_content)
            if strategy:
                strategy_gen.save(split_content, strategy)
        except Exception as e:
            self.logger.warning(f"Strategy generation failed: {e}")

        self.progress.complete_step(ProcessingStep.STRATEGY_GENERATION)

    def _open_gemini_final(self):
        """Open Gemini in browser at the end."""
        self.logger.info("Opening Gemini in browser...")
        try:
            if self.authenticator:
                self.authenticator.open_gemini_in_new_tab()
                self.logger.info("Gemini opened in new tab")
        except Exception as e:
            self.logger.warning(f"Could not open Gemini: {e}")

    def _finalize(self):
        """Finalize and show summary."""
        self.progress.set_step(ProcessingStep.DOWNLOADING, "Finalizing outputs...")

        # Get download summary
        summary = self.downloader.get_summary()

        self.logger.info("\n" + "=" * 60)
        self.logger.info("GENERATION COMPLETE")
        self.logger.info("=" * 60)
        self.logger.info(f"\nOutput directory: {self.output_dir}")
        self.logger.info("\nGenerated files:")

        total_files = 0
        for content_type, info in summary.items():
            if info["count"] > 0:
                self.logger.info(f"  {content_type}: {info['count']} files")
                total_files += info["count"]

        self.logger.info(f"\nTotal files generated: {total_files}")
        self.logger.info("=" * 60)

        self.progress.complete_step(ProcessingStep.DOWNLOADING)
        self.progress.set_step(ProcessingStep.COMPLETED, "All done!")

    def _cleanup(self):
        """Clean up resources."""
        if self.authenticator:
            # Don't close browser - leave it open for user
            pass


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="NotebookLM Generation Tool - Generate learning materials from content"
    )

    parser.add_argument(
        "input",
        help="Input file path (PDF, TXT) or URL"
    )

    parser.add_argument(
        "-e", "--email",
        help="Google account email"
    )

    parser.add_argument(
        "-p", "--password",
        help="Google account password"
    )

    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: same as input)"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )

    parser.add_argument(
        "--api-key",
        help="Gemini API key (or set GEMINI_API_KEY env var)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Set up environment
    if args.api_key:
        os.environ["GEMINI_API_KEY"] = args.api_key

    output_dir = Path(args.output) if args.output else None

    # Run generator
    generator = NotebookLMGenerator(
        input_path=args.input,
        email=args.email,
        password=args.password,
        headless=args.headless,
        output_dir=output_dir,
        gemini_api_key=args.api_key
    )

    success = generator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
