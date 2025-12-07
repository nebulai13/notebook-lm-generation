"""Google authentication for NotebookLM and Gemini."""

import time
import pickle
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    import undetected_chromedriver as uc
    HAS_UNDETECTED = True
except ImportError:
    HAS_UNDETECTED = False

from webdriver_manager.chrome import ChromeDriverManager

from ..utils.logger import get_logger
from ..config.settings import get_settings


class GoogleAuthenticator:
    """
    Handles Google account authentication for NotebookLM and Gemini.

    Uses Selenium for browser automation to log into Google services.
    Supports both regular Chrome and undetected-chromedriver to bypass
    bot detection.
    """

    COOKIES_FILE = "google_cookies.pkl"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = False,
        cookies_dir: Optional[Path] = None
    ):
        self.email = email
        self.password = password
        self.headless = headless
        self.cookies_dir = cookies_dir or Path.home() / ".notebook_lm_gen"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

        self.logger = get_logger()
        self.settings = get_settings()
        self.driver: Optional[webdriver.Chrome] = None

    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure the Chrome WebDriver."""
        if HAS_UNDETECTED:
            # Use undetected-chromedriver to bypass bot detection
            options = uc.ChromeOptions()

            if self.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")

            driver = uc.Chrome(options=options)
        else:
            # Fallback to regular Chrome
            options = Options()

            if self.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")

            # Remove automation flags
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            # Execute script to remove webdriver property
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

        driver.set_page_load_timeout(self.settings.page_load_timeout)
        return driver

    def get_driver(self) -> webdriver.Chrome:
        """Get the WebDriver instance, creating it if necessary."""
        if self.driver is None:
            self.driver = self._create_driver()
        return self.driver

    def _save_cookies(self):
        """Save cookies to file for session persistence."""
        if self.driver:
            cookies_path = self.cookies_dir / self.COOKIES_FILE
            with open(cookies_path, "wb") as f:
                pickle.dump(self.driver.get_cookies(), f)
            self.logger.debug(f"Saved cookies to {cookies_path}")

    def _load_cookies(self) -> bool:
        """Load cookies from file if available."""
        cookies_path = self.cookies_dir / self.COOKIES_FILE

        if not cookies_path.exists():
            return False

        try:
            with open(cookies_path, "rb") as f:
                cookies = pickle.load(f)

            # First navigate to Google to set domain
            self.driver.get("https://www.google.com")
            time.sleep(1)

            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass  # Some cookies may fail due to domain mismatch

            self.logger.debug("Loaded cookies from file")
            return True

        except Exception as e:
            self.logger.warning(f"Failed to load cookies: {e}")
            return False

    def login_google(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Log into Google account.

        Args:
            email: Google account email (uses instance email if not provided)
            password: Google account password (uses instance password if not provided)

        Returns:
            True if login successful, False otherwise
        """
        email = email or self.email
        password = password or self.password

        if not email or not password:
            self.logger.error("Email and password are required for login")
            return False

        driver = self.get_driver()

        try:
            # Try to use saved cookies first
            if self._load_cookies():
                driver.get("https://accounts.google.com")
                time.sleep(2)

                # Check if already logged in
                if self._is_logged_in():
                    self.logger.info("Successfully logged in using saved session")
                    return True

            # Navigate to Google Sign In
            self.logger.info("Logging into Google account...")
            driver.get("https://accounts.google.com/signin")
            time.sleep(2)

            # Enter email
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
            )
            email_input.clear()
            email_input.send_keys(email)
            email_input.send_keys(Keys.RETURN)
            time.sleep(3)

            # Enter password
            password_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            password_input.clear()
            password_input.send_keys(password)
            password_input.send_keys(Keys.RETURN)

            # Give time for page to transition
            time.sleep(5)

            # Check for 2FA, passkey, or other verification
            # This will wait up to 2 minutes for manual verification
            self._handle_verification()

            # Additional wait in case verification just completed
            time.sleep(3)

            # Verify login success
            if self._is_logged_in():
                self._save_cookies()
                self.logger.info("Successfully logged into Google account")
                return True
            else:
                # One more check - maybe we're already on a Google page
                current_url = driver.current_url
                if any(domain in current_url for domain in ["google.com", "notebooklm", "gemini"]):
                    if "signin" not in current_url and "accounts.google.com/v3" not in current_url:
                        self._save_cookies()
                        self.logger.info("Successfully logged into Google account")
                        return True

                self.logger.error("Login failed - could not verify logged in state")
                return False

        except TimeoutException as e:
            # Check if we actually succeeded despite the timeout
            try:
                if self._is_logged_in():
                    self._save_cookies()
                    self.logger.info("Successfully logged into Google account")
                    return True
            except Exception:
                pass
            self.logger.error(f"Login timeout: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            return False

    def _is_logged_in(self) -> bool:
        """Check if currently logged into Google."""
        try:
            self.driver.get("https://myaccount.google.com")
            time.sleep(2)

            # Check for account avatar or signed-in indicators
            try:
                self.driver.find_element(By.CSS_SELECTOR, "[data-ogsr-up]")
                return True
            except NoSuchElementException:
                pass

            # Alternative check - look for sign in button absence
            try:
                self.driver.find_element(By.XPATH, "//a[contains(@href, 'signin')]")
                return False
            except NoSuchElementException:
                return True

        except Exception:
            return False

    def _handle_verification(self) -> bool:
        """Handle 2FA, passkey, or other verification steps."""
        try:
            # Wait a moment for any verification page to load
            time.sleep(3)

            # List of verification indicators to check
            verification_patterns = [
                "Verify it",
                "2-Step Verification",
                "passkey",
                "Passkey",
                "Use your passkey",
                "fingerprint",
                "Fingerprint",
                "Touch ID",
                "Face ID",
                "security key",
                "Confirm it's you",
                "Verify your identity",
                "Choose how to sign in",
            ]

            # Check if we're on a verification page
            page_source = self.driver.page_source.lower()
            needs_verification = any(
                pattern.lower() in page_source for pattern in verification_patterns
            )

            if needs_verification:
                self.logger.warning("=" * 50)
                self.logger.warning("VERIFICATION REQUIRED")
                self.logger.warning("Please complete verification in the browser window:")
                self.logger.warning("- Passkey/fingerprint")
                self.logger.warning("- 2FA code")
                self.logger.warning("- Phone verification")
                self.logger.warning("Waiting up to 2 minutes...")
                self.logger.warning("=" * 50)

                # Wait for manual completion - check multiple success indicators
                WebDriverWait(self.driver, 120).until(
                    lambda d: any([
                        "myaccount.google.com" in d.current_url,
                        "mail.google.com" in d.current_url,
                        "notebooklm" in d.current_url.lower(),
                        "gemini" in d.current_url.lower(),
                        "accounts.google.com/b/" in d.current_url,  # Account switcher (logged in)
                    ])
                )
                self.logger.info("Verification completed successfully!")
                return True

            return False

        except TimeoutException:
            self.logger.error("Verification timed out - please try again")
            return False
        except Exception as e:
            self.logger.debug(f"Verification handling: {e}")
            return False

    def navigate_to_notebooklm(self) -> bool:
        """Navigate to NotebookLM."""
        try:
            driver = self.get_driver()
            driver.get(self.settings.notebooklm_url)
            time.sleep(3)

            # Wait for page to load
            WebDriverWait(driver, 30).until(
                lambda d: "notebooklm" in d.current_url.lower()
            )

            self.logger.info("Navigated to NotebookLM")
            return True

        except Exception as e:
            self.logger.error(f"Failed to navigate to NotebookLM: {e}")
            return False

    def navigate_to_gemini(self) -> bool:
        """Navigate to Gemini."""
        try:
            driver = self.get_driver()
            driver.get(self.settings.gemini_url)
            time.sleep(3)

            # Wait for page to load
            WebDriverWait(driver, 30).until(
                lambda d: "gemini" in d.current_url.lower()
            )

            self.logger.info("Navigated to Gemini")
            return True

        except Exception as e:
            self.logger.error(f"Failed to navigate to Gemini: {e}")
            return False

    def open_gemini_in_new_tab(self) -> bool:
        """Open Gemini in a new browser tab."""
        try:
            driver = self.get_driver()

            # Open new tab
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])

            # Navigate to Gemini
            driver.get(self.settings.gemini_url)
            time.sleep(3)

            self.logger.info("Opened Gemini in new tab")
            return True

        except Exception as e:
            self.logger.error(f"Failed to open Gemini in new tab: {e}")
            return False

    def close(self):
        """Close the browser and cleanup."""
        if self.driver:
            try:
                self._save_cookies()
                self.driver.quit()
                self.logger.debug("Browser closed")
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")
            finally:
                self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
