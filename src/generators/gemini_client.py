"""Gemini API client for content generation."""

import time
from typing import Optional
from dataclasses import dataclass

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..auth.google_auth import GoogleAuthenticator
from ..utils.logger import get_logger
from ..config.settings import get_settings


@dataclass
class GeminiResponse:
    """Container for Gemini response."""
    text: str
    model: str
    finish_reason: str = ""


class GeminiClient:
    """
    Client for Gemini AI, supporting both API and browser modes.

    Can use the Gemini API directly or automate the Gemini web interface.
    """

    # Selectors for Gemini web interface
    SELECTORS = {
        "chat_input": "div[contenteditable='true'], textarea[placeholder*='Enter'], .ql-editor",
        "send_btn": "button[aria-label*='Send'], button[data-test-id='send'], .send-button",
        "response": ".response-container, .model-response, [data-message-author-role='model']",
        "loading": ".loading, .spinner, [data-test-id='loading']",
        "new_chat": "button[aria-label*='New chat'], .new-chat-button",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        authenticator: Optional[GoogleAuthenticator] = None,
        use_browser: bool = False
    ):
        self.logger = get_logger()
        self.settings = get_settings()
        self.use_browser = use_browser
        self.auth = authenticator
        self.driver: Optional[WebDriver] = None

        # Initialize API client
        self.api_model = None
        if HAS_GENAI and not use_browser:
            api_key = api_key or self.settings.gemini_api_key
            if api_key:
                genai.configure(api_key=api_key)
                self.api_model = genai.GenerativeModel("gemini-1.5-pro")
                self.logger.info("Initialized Gemini API client")

        # Initialize browser if needed
        if use_browser and authenticator:
            self.driver = authenticator.get_driver()

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 8000
    ) -> Optional[GeminiResponse]:
        """
        Generate content using Gemini.

        Args:
            prompt: The prompt to send
            temperature: Generation temperature (0-1)
            max_tokens: Maximum tokens to generate

        Returns:
            GeminiResponse or None if failed
        """
        if self.api_model and not self.use_browser:
            return self._generate_via_api(prompt, temperature, max_tokens)
        elif self.driver:
            return self._generate_via_browser(prompt)
        else:
            self.logger.error("No Gemini client available")
            return None

    def _generate_via_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> Optional[GeminiResponse]:
        """Generate using the Gemini API."""
        try:
            response = self.api_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )

            return GeminiResponse(
                text=response.text,
                model="gemini-1.5-pro",
                finish_reason=str(response.candidates[0].finish_reason) if response.candidates else ""
            )

        except Exception as e:
            self.logger.error(f"Gemini API error: {e}")
            return None

    def _generate_via_browser(self, prompt: str) -> Optional[GeminiResponse]:
        """Generate using the Gemini web interface."""
        try:
            # Navigate to Gemini if not already there
            if "gemini" not in self.driver.current_url.lower():
                self.auth.navigate_to_gemini()
                time.sleep(3)

            # Find and fill chat input
            input_element = self._find_element(self.SELECTORS["chat_input"])
            if not input_element:
                self.logger.error("Could not find Gemini chat input")
                return None

            # Clear and enter prompt
            input_element.click()
            time.sleep(0.5)

            # Enter text in chunks
            chunk_size = 1000
            for i in range(0, len(prompt), chunk_size):
                input_element.send_keys(prompt[i:i + chunk_size])
                time.sleep(0.2)

            # Send message
            try:
                send_btn = self._find_element(self.SELECTORS["send_btn"])
                if send_btn:
                    send_btn.click()
            except Exception:
                input_element.send_keys(Keys.RETURN)

            time.sleep(2)

            # Wait for response
            self._wait_for_response(timeout=120)

            # Get response
            response_elements = self.driver.find_elements(
                By.CSS_SELECTOR, self.SELECTORS["response"]
            )

            if response_elements:
                response_text = response_elements[-1].text
                return GeminiResponse(
                    text=response_text,
                    model="gemini-web"
                )

            return None

        except Exception as e:
            self.logger.error(f"Browser Gemini error: {e}")
            return None

    def _find_element(self, selector: str, timeout: int = 10):
        """Find element trying multiple selectors."""
        selectors = selector.split(", ")

        for sel in selectors:
            try:
                element = WebDriverWait(self.driver, timeout // len(selectors)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel.strip()))
                )
                return element
            except Exception:
                continue

        return None

    def _wait_for_response(self, timeout: int = 60):
        """Wait for Gemini to finish responding."""
        time.sleep(2)

        # Wait for loading to disappear
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.SELECTORS["loading"])
                )
            )
        except Exception:
            pass

        # Additional wait for response to stabilize
        time.sleep(2)

    def start_new_chat(self):
        """Start a new chat session in browser mode."""
        if self.driver:
            try:
                new_chat_btn = self._find_element(self.SELECTORS["new_chat"])
                if new_chat_btn:
                    new_chat_btn.click()
                    time.sleep(2)
            except Exception as e:
                self.logger.debug(f"Could not start new chat: {e}")

    def generate_story(
        self,
        topic_content: str,
        genre: str = "fantasy",
        length: str = "short"
    ) -> Optional[str]:
        """
        Generate a creative story based on topic content.

        Args:
            topic_content: The educational content to base the story on
            genre: Story genre (fantasy, scifi, adventure)
            length: Story length (short, medium, long)

        Returns:
            Generated story text
        """
        length_words = {"short": "1000-1500", "medium": "2000-3000", "long": "4000-5000"}

        prompt = f"""Create an engaging {genre} story that teaches the following educational content.
The story should be {length_words.get(length, "1000-1500")} words long.

Educational Content:
{topic_content}

Requirements:
1. Make the educational concepts central to the plot
2. Create memorable characters that embody or discover these concepts
3. Use vivid descriptions and dialogue
4. Include a clear beginning, middle, and end
5. Make complex concepts accessible through narrative

Write the story:"""

        response = self.generate(prompt, temperature=0.8)
        return response.text if response else None

    def generate_strategy(self, topics: list[str], exam_type: str = "general") -> Optional[str]:
        """
        Generate a learning strategy paper.

        Args:
            topics: List of topic titles
            exam_type: Type of exam preparation

        Returns:
            Strategy paper text
        """
        topics_list = "\n".join(f"- {topic}" for topic in topics)

        prompt = f"""Create a comprehensive learning strategy paper for exam preparation.

Topics to cover:
{topics_list}

Exam type: {exam_type}

Include the following sections:
1. Executive Summary
2. Study Schedule Recommendations
3. For each topic:
   - Key concepts to master
   - Recommended study techniques
   - Common pitfalls to avoid
   - Self-assessment questions
4. Memory Techniques (mnemonics, visualization)
5. Practice Test Strategy
6. Day-before and Day-of Exam Tips
7. Stress Management
8. Resource Recommendations

Be specific and actionable. Format in Markdown."""

        response = self.generate(prompt, temperature=0.5)
        return response.text if response else None

    def generate_quiz(
        self,
        topic_content: str,
        num_questions: int = 10,
        difficulty: str = "mixed"
    ) -> Optional[str]:
        """
        Generate quiz questions.

        Args:
            topic_content: Content to create questions from
            num_questions: Number of questions
            difficulty: Difficulty level

        Returns:
            Quiz in JSON format
        """
        prompt = f"""Create a quiz with {num_questions} questions based on this content.
Mix question types: multiple choice, true/false, and short answer.
Difficulty: {difficulty}

Content:
{topic_content}

Format as JSON:
{{
    "quiz_title": "...",
    "questions": [
        {{
            "id": 1,
            "type": "multiple_choice",
            "question": "...",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": "..."
        }},
        {{
            "id": 2,
            "type": "true_false",
            "question": "...",
            "correct_answer": true,
            "explanation": "..."
        }},
        {{
            "id": 3,
            "type": "short_answer",
            "question": "...",
            "correct_answer": "...",
            "keywords": ["key1", "key2"]
        }}
    ]
}}

Return only valid JSON."""

        response = self.generate(prompt, temperature=0.3)
        return response.text if response else None

    def generate_discussion(
        self,
        topic: str,
        participants: list[dict]
    ) -> Optional[str]:
        """
        Generate a podium discussion script.

        Args:
            topic: Discussion topic
            participants: List of participant dicts with name and perspective

        Returns:
            Discussion script
        """
        participants_desc = "\n".join(
            f"- {p['name']}: {p['perspective']}"
            for p in participants
        )

        prompt = f"""Write a podium discussion script about: {topic}

Participants:
{participants_desc}

Requirements:
1. Write a 10-15 minute discussion (~2000 words)
2. Include an opening by a moderator
3. Each participant should make at least 3 substantive points
4. Include back-and-forth exchanges and rebuttals
5. Include audience Q&A section
6. End with concluding remarks from each participant
7. Make it engaging and educational

Format:
MODERATOR: [dialogue]
PARTICIPANT_NAME: [dialogue]

Write the script:"""

        response = self.generate(prompt, temperature=0.7)
        return response.text if response else None
