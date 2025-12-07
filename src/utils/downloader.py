"""Download and export utilities."""

import os
import shutil
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests
from selenium.webdriver.remote.webdriver import WebDriver

from .logger import get_logger


class Downloader:
    """
    Handles downloading and organizing generated content.

    Downloads all generated materials to the same folder as the
    original input file.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.logger = get_logger()

        # Create output directory structure
        self.dirs = {
            "videos": output_dir / "videos",
            "handouts": output_dir / "handouts",
            "cheatsheets": output_dir / "cheatsheets",
            "mindmaps": output_dir / "mindmaps",
            "audiobooks": output_dir / "audiobooks",
            "stories": output_dir / "stories",
            "strategies": output_dir / "strategies",
            "flashcards": output_dir / "flashcards",
            "anki": output_dir / "anki",
            "quizzes": output_dir / "quizzes",
            "discussions": output_dir / "discussions",
        }

        self._create_directories()

    def _create_directories(self):
        """Create all output directories."""
        for name, path in self.dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {path}")

    def get_dir(self, content_type: str) -> Path:
        """Get the directory for a specific content type."""
        return self.dirs.get(content_type, self.output_dir)

    def save_text_content(
        self,
        content: str,
        filename: str,
        content_type: str,
        extension: str = "md"
    ) -> Path:
        """
        Save text content to a file.

        Args:
            content: Text content to save
            filename: Base filename (without extension)
            content_type: Type of content (handout, cheatsheet, etc.)
            extension: File extension (default: md)

        Returns:
            Path to saved file
        """
        output_path = self.get_dir(content_type) / f"{filename}.{extension}"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.logger.info(f"Saved {content_type}: {output_path}")
        return output_path

    def save_binary_content(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        extension: str
    ) -> Path:
        """
        Save binary content to a file.

        Args:
            content: Binary content to save
            filename: Base filename (without extension)
            content_type: Type of content
            extension: File extension

        Returns:
            Path to saved file
        """
        output_path = self.get_dir(content_type) / f"{filename}.{extension}"

        with open(output_path, "wb") as f:
            f.write(content)

        self.logger.info(f"Saved {content_type}: {output_path}")
        return output_path

    def download_from_url(
        self,
        url: str,
        filename: str,
        content_type: str,
        extension: str
    ) -> Optional[Path]:
        """
        Download content from a URL.

        Args:
            url: URL to download from
            filename: Base filename
            content_type: Type of content
            extension: File extension

        Returns:
            Path to downloaded file, or None if failed
        """
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            output_path = self.get_dir(content_type) / f"{filename}.{extension}"

            with open(output_path, "wb") as f:
                f.write(response.content)

            self.logger.info(f"Downloaded {content_type} from URL: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to download from {url}: {e}")
            return None

    def download_from_browser(
        self,
        driver: WebDriver,
        download_button_selector: str,
        filename: str,
        content_type: str,
        expected_extension: str,
        timeout: int = 60
    ) -> Optional[Path]:
        """
        Trigger a download from the browser and save it.

        Args:
            driver: Selenium WebDriver instance
            download_button_selector: CSS selector for download button
            filename: Desired filename
            content_type: Type of content
            expected_extension: Expected file extension
            timeout: Download timeout in seconds

        Returns:
            Path to downloaded file, or None if failed
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            # Get the browser's download directory
            download_dir = Path.home() / "Downloads"

            # Get list of files before download
            files_before = set(download_dir.glob("*"))

            # Click download button
            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, download_button_selector))
            )
            button.click()

            # Wait for new file to appear
            start_time = time.time()
            new_file = None

            while time.time() - start_time < timeout:
                files_after = set(download_dir.glob("*"))
                new_files = files_after - files_before

                # Filter out partial downloads
                complete_files = [
                    f for f in new_files
                    if not f.name.endswith(('.crdownload', '.part', '.tmp'))
                ]

                if complete_files:
                    new_file = complete_files[0]
                    break

                time.sleep(1)

            if not new_file:
                self.logger.error(f"Download timed out for {content_type}")
                return None

            # Move to output directory
            output_path = self.get_dir(content_type) / f"{filename}.{expected_extension}"
            shutil.move(str(new_file), str(output_path))

            self.logger.info(f"Downloaded {content_type}: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to download {content_type}: {e}")
            return None

    def create_anki_deck(
        self,
        flashcards: list[dict],
        deck_name: str,
        filename: str
    ) -> Optional[Path]:
        """
        Create an Anki-compatible deck file.

        Args:
            flashcards: List of dicts with 'front' and 'back' keys
            deck_name: Name for the Anki deck
            filename: Output filename

        Returns:
            Path to created Anki file
        """
        try:
            # Create a tab-separated file that Anki can import
            output_path = self.get_dir("anki") / f"{filename}.txt"

            with open(output_path, "w", encoding="utf-8") as f:
                # Anki import format: front<tab>back
                for card in flashcards:
                    front = card.get("front", "").replace("\t", " ").replace("\n", "<br>")
                    back = card.get("back", "").replace("\t", " ").replace("\n", "<br>")
                    f.write(f"{front}\t{back}\n")

            self.logger.info(f"Created Anki deck: {output_path}")

            # Also create an APKG file using genanki if available
            apkg_path = self._create_apkg(flashcards, deck_name, filename)

            return apkg_path or output_path

        except Exception as e:
            self.logger.error(f"Failed to create Anki deck: {e}")
            return None

    def _create_apkg(
        self,
        flashcards: list[dict],
        deck_name: str,
        filename: str
    ) -> Optional[Path]:
        """Create a proper .apkg file using genanki."""
        try:
            import genanki
            import random

            # Create a model (card template)
            model = genanki.Model(
                random.randrange(1 << 30, 1 << 31),
                'Simple Model',
                fields=[
                    {'name': 'Front'},
                    {'name': 'Back'},
                ],
                templates=[
                    {
                        'name': 'Card 1',
                        'qfmt': '{{Front}}',
                        'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
                    },
                ]
            )

            # Create deck
            deck = genanki.Deck(
                random.randrange(1 << 30, 1 << 31),
                deck_name
            )

            # Add cards
            for card in flashcards:
                note = genanki.Note(
                    model=model,
                    fields=[card.get("front", ""), card.get("back", "")]
                )
                deck.add_note(note)

            # Save as .apkg
            output_path = self.get_dir("anki") / f"{filename}.apkg"
            genanki.Package(deck).write_to_file(str(output_path))

            self.logger.info(f"Created Anki package: {output_path}")
            return output_path

        except ImportError:
            self.logger.warning("genanki not installed, skipping .apkg creation")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create .apkg: {e}")
            return None

    def get_summary(self) -> dict:
        """Get a summary of all downloaded files."""
        summary = {}

        for content_type, dir_path in self.dirs.items():
            files = list(dir_path.glob("*"))
            summary[content_type] = {
                "count": len(files),
                "files": [f.name for f in files],
                "total_size": sum(f.stat().st_size for f in files if f.is_file())
            }

        return summary

    def cleanup_empty_dirs(self):
        """Remove empty directories."""
        for dir_path in self.dirs.values():
            if dir_path.exists() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                self.logger.debug(f"Removed empty directory: {dir_path}")
