"""NotebookLM browser automation client."""

import time
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.remote.webdriver import WebDriver

from ..auth.google_auth import GoogleAuthenticator
from ..utils.logger import get_logger
from ..config.settings import get_settings


@dataclass
class NotebookProject:
    """Represents a NotebookLM project/notebook."""
    name: str
    url: Optional[str] = None
    sources_count: int = 0


class NotebookLMClient:
    """
    Browser automation client for NotebookLM.

    Handles creating notebooks, uploading sources, and generating
    various outputs like audio overviews and study guides.
    """

    # CSS Selectors (may need updates if NotebookLM UI changes)
    SELECTORS = {
        "new_notebook_btn": "[data-test-id='create-notebook-button'], button[aria-label*='Create'], .create-button",
        "notebook_title_input": "[data-test-id='notebook-title'], input[placeholder*='title'], .notebook-title-input",
        "add_source_btn": "[data-test-id='add-source-button'], button[aria-label*='Add source'], .add-source-button",
        "upload_file_option": "[data-test-id='upload-file'], [aria-label*='Upload'], .upload-option",
        "file_input": "input[type='file']",
        "paste_text_option": "[data-test-id='paste-text'], [aria-label*='Paste text'], .paste-text-option",
        "text_input": "textarea[placeholder*='Paste'], .text-input-area",
        "website_option": "[data-test-id='website-url'], [aria-label*='Website'], .website-option",
        "url_input": "input[placeholder*='URL'], input[type='url']",
        "generate_audio_btn": "[data-test-id='generate-audio'], button[aria-label*='Audio Overview'], .audio-overview-button",
        "studio_tab": "[data-test-id='studio-tab'], [aria-label*='Studio'], .studio-tab",
        "chat_input": "[data-test-id='chat-input'], textarea[placeholder*='Ask'], .chat-input",
        "send_btn": "[data-test-id='send-button'], button[aria-label*='Send'], .send-button",
        "response_container": "[data-test-id='response'], .response-container, .chat-response",
        "download_btn": "[data-test-id='download'], button[aria-label*='Download'], .download-button",
        "audio_player": "audio, [data-test-id='audio-player']",
        "loading_indicator": "[data-test-id='loading'], .loading, .spinner",
    }

    def __init__(self, authenticator: GoogleAuthenticator):
        self.auth = authenticator
        self.driver = authenticator.get_driver()
        self.logger = get_logger()
        self.settings = get_settings()
        self.current_notebook: Optional[NotebookProject] = None

    def navigate_to_notebooklm(self) -> bool:
        """Navigate to NotebookLM homepage."""
        return self.auth.navigate_to_notebooklm()

    def create_notebook(self, name: str) -> NotebookProject:
        """
        Create a new notebook.

        Args:
            name: Name for the new notebook

        Returns:
            NotebookProject instance
        """
        self.logger.info(f"Creating new notebook: {name}")

        try:
            # Navigate to NotebookLM if not already there
            if "notebooklm" not in self.driver.current_url.lower():
                self.navigate_to_notebooklm()

            time.sleep(2)

            # Click create new notebook button
            self._click_element(self.SELECTORS["new_notebook_btn"])
            time.sleep(2)

            # Set notebook title if input is available
            try:
                title_input = self._find_element(self.SELECTORS["notebook_title_input"])
                if title_input:
                    title_input.clear()
                    title_input.send_keys(name)
                    title_input.send_keys(Keys.RETURN)
                    time.sleep(1)
            except Exception:
                self.logger.debug("Could not set notebook title directly")

            self.current_notebook = NotebookProject(
                name=name,
                url=self.driver.current_url
            )

            self.logger.info(f"Created notebook: {name}")
            return self.current_notebook

        except Exception as e:
            self.logger.error(f"Failed to create notebook: {e}")
            raise

    def add_text_source(self, text: str, title: str = "Source") -> bool:
        """
        Add text content as a source.

        Args:
            text: Text content to add
            title: Title for the source

        Returns:
            True if successful
        """
        self.logger.info(f"Adding text source: {title}")

        try:
            # Click add source button
            self._click_element(self.SELECTORS["add_source_btn"])
            time.sleep(1)

            # Select paste text option
            self._click_element(self.SELECTORS["paste_text_option"])
            time.sleep(1)

            # Enter text
            text_area = self._find_element(self.SELECTORS["text_input"])
            if text_area:
                text_area.clear()
                # Send text in chunks to avoid issues with large content
                chunk_size = 5000
                for i in range(0, len(text), chunk_size):
                    text_area.send_keys(text[i:i + chunk_size])
                    time.sleep(0.5)

            # Submit
            text_area.send_keys(Keys.CONTROL, Keys.RETURN)
            time.sleep(3)

            # Wait for processing
            self._wait_for_loading()

            if self.current_notebook:
                self.current_notebook.sources_count += 1

            self.logger.info(f"Added text source: {title}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add text source: {e}")
            return False

    def add_file_source(self, file_path: Path) -> bool:
        """
        Add a file as a source.

        Args:
            file_path: Path to the file to upload

        Returns:
            True if successful
        """
        self.logger.info(f"Adding file source: {file_path}")

        try:
            # Click add source button
            self._click_element(self.SELECTORS["add_source_btn"])
            time.sleep(1)

            # Select upload file option
            self._click_element(self.SELECTORS["upload_file_option"])
            time.sleep(1)

            # Find file input and upload
            file_input = self.driver.find_element(By.CSS_SELECTOR, self.SELECTORS["file_input"])
            file_input.send_keys(str(file_path.absolute()))
            time.sleep(3)

            # Wait for upload to complete
            self._wait_for_loading(timeout=60)

            if self.current_notebook:
                self.current_notebook.sources_count += 1

            self.logger.info(f"Added file source: {file_path.name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add file source: {e}")
            return False

    def add_website_source(self, url: str) -> bool:
        """
        Add a website as a source.

        Args:
            url: URL to add

        Returns:
            True if successful
        """
        self.logger.info(f"Adding website source: {url}")

        try:
            # Click add source button
            self._click_element(self.SELECTORS["add_source_btn"])
            time.sleep(1)

            # Select website option
            self._click_element(self.SELECTORS["website_option"])
            time.sleep(1)

            # Enter URL
            url_input = self._find_element(self.SELECTORS["url_input"])
            if url_input:
                url_input.clear()
                url_input.send_keys(url)
                url_input.send_keys(Keys.RETURN)
                time.sleep(3)

            # Wait for processing
            self._wait_for_loading(timeout=60)

            if self.current_notebook:
                self.current_notebook.sources_count += 1

            self.logger.info(f"Added website source: {url}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add website source: {e}")
            return False

    def generate_audio_overview(self) -> bool:
        """
        Generate an audio overview (podcast-style).

        Returns:
            True if generation started successfully
        """
        self.logger.info("Generating audio overview...")

        try:
            # Navigate to Studio tab if available
            try:
                self._click_element(self.SELECTORS["studio_tab"])
                time.sleep(2)
            except Exception:
                pass

            # Click generate audio button
            self._click_element(self.SELECTORS["generate_audio_btn"])
            time.sleep(2)

            # Wait for generation (can take several minutes)
            self._wait_for_loading(timeout=300)

            self.logger.info("Audio overview generation started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to generate audio overview: {e}")
            return False

    def send_chat_message(self, message: str) -> Optional[str]:
        """
        Send a chat message and get response.

        Args:
            message: Message to send

        Returns:
            Response text or None
        """
        self.logger.debug(f"Sending chat message: {message[:50]}...")

        try:
            # Find chat input
            chat_input = self._find_element(self.SELECTORS["chat_input"])
            if not chat_input:
                self.logger.error("Chat input not found")
                return None

            # Clear and enter message
            chat_input.clear()
            chat_input.send_keys(message)

            # Click send or press enter
            try:
                self._click_element(self.SELECTORS["send_btn"])
            except Exception:
                chat_input.send_keys(Keys.RETURN)

            time.sleep(2)

            # Wait for response
            self._wait_for_loading(timeout=120)
            time.sleep(2)

            # Get response
            response_elements = self.driver.find_elements(
                By.CSS_SELECTOR, self.SELECTORS["response_container"]
            )

            if response_elements:
                # Get the last response
                return response_elements[-1].text

            return None

        except Exception as e:
            self.logger.error(f"Failed to send chat message: {e}")
            return None

    def generate_study_guide(self) -> Optional[str]:
        """Generate a study guide using chat."""
        return self.send_chat_message(
            "Create a comprehensive study guide for this content. Include key concepts, "
            "definitions, and important points to remember."
        )

    def generate_briefing_doc(self) -> Optional[str]:
        """Generate a briefing document using chat."""
        return self.send_chat_message(
            "Create a detailed briefing document summarizing this content. "
            "Include executive summary, main points, and conclusions."
        )

    def generate_faq(self) -> Optional[str]:
        """Generate FAQ using chat."""
        return self.send_chat_message(
            "Generate a comprehensive FAQ (Frequently Asked Questions) based on this content. "
            "Include at least 10 questions and detailed answers."
        )

    def generate_timeline(self) -> Optional[str]:
        """Generate a timeline if applicable."""
        return self.send_chat_message(
            "Create a timeline of events or key milestones mentioned in this content."
        )

    def generate_flashcards(self) -> Optional[str]:
        """Generate flashcards using chat."""
        return self.send_chat_message(
            "Create flashcards (question and answer pairs) for studying this content. "
            "Format each card as 'Q: [question]' followed by 'A: [answer]'. "
            "Create at least 15 flashcards covering the main concepts."
        )

    def _find_element(self, selector: str, timeout: int = 10):
        """Find element using multiple selector strategies."""
        selectors = selector.split(", ")

        for sel in selectors:
            try:
                element = WebDriverWait(self.driver, timeout // len(selectors)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel.strip()))
                )
                return element
            except TimeoutException:
                continue

        return None

    def _click_element(self, selector: str, timeout: int = 10):
        """Click an element, trying multiple selectors."""
        selectors = selector.split(", ")

        for sel in selectors:
            try:
                element = WebDriverWait(self.driver, timeout // len(selectors)).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel.strip()))
                )
                element.click()
                return True
            except TimeoutException:
                continue

        raise TimeoutException(f"Could not click element: {selector}")

    def _wait_for_loading(self, timeout: int = 60):
        """Wait for loading indicators to disappear."""
        try:
            # First wait for loading to appear (briefly)
            time.sleep(1)

            # Then wait for it to disappear
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.SELECTORS["loading_indicator"])
                )
            )
        except TimeoutException:
            self.logger.debug("Loading wait timed out")
        except Exception:
            pass  # Loading indicator might not exist

    def get_audio_url(self) -> Optional[str]:
        """Get the URL of the generated audio."""
        try:
            audio_element = self._find_element(self.SELECTORS["audio_player"])
            if audio_element:
                return audio_element.get_attribute("src")
        except Exception:
            pass
        return None

    def download_audio(self, output_path: Path) -> bool:
        """Download the generated audio."""
        try:
            # Try to click download button
            self._click_element(self.SELECTORS["download_btn"])
            time.sleep(3)

            self.logger.info(f"Audio download initiated to: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to download audio: {e}")
            return False
