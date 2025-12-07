"""Application settings and configuration."""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Google OAuth settings
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")

    # Gemini API
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")

    # Browser settings
    chrome_driver_path: Optional[str] = Field(default=None, alias="CHROME_DRIVER_PATH")
    headless_browser: bool = Field(default=False, alias="HEADLESS_BROWSER")

    # NotebookLM URLs
    notebooklm_url: str = "https://notebooklm.google.com"
    gemini_url: str = "https://gemini.google.com"

    # Progress reporting
    progress_update_interval: int = 15  # seconds

    # Output settings
    output_formats: list[str] = ["pdf", "txt", "md"]

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = "notebook_lm_generation.log"

    # Timeouts
    page_load_timeout: int = 60  # seconds
    element_wait_timeout: int = 30  # seconds
    generation_timeout: int = 300  # seconds (5 minutes)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Generation output types
class OutputType:
    """Constants for output types."""
    VIDEO = "video"
    HANDOUT = "handout"
    CHEATSHEET = "cheatsheet"
    MINDMAP = "mindmap"
    AUDIOBOOK = "audiobook"
    STORY = "story"
    STRATEGY = "strategy"
    FLASHCARDS = "flashcards"
    QUIZ = "quiz"
    DISCUSSION = "discussion"

    ALL = [
        VIDEO, HANDOUT, CHEATSHEET, MINDMAP, AUDIOBOOK,
        STORY, STRATEGY, FLASHCARDS, QUIZ, DISCUSSION
    ]


# Processing steps for progress reporting
class ProcessingStep:
    """Constants for processing steps."""
    AUTHENTICATION = "authentication"
    CONTENT_LOADING = "content_loading"
    TOPIC_SPLITTING = "topic_splitting"
    VIDEO_GENERATION = "video_generation"
    HANDOUT_GENERATION = "handout_generation"
    CHEATSHEET_GENERATION = "cheatsheet_generation"
    MINDMAP_GENERATION = "mindmap_generation"
    AUDIOBOOK_GENERATION = "audiobook_generation"
    STORY_GENERATION = "story_generation"
    STRATEGY_GENERATION = "strategy_generation"
    FLASHCARD_GENERATION = "flashcard_generation"
    QUIZ_GENERATION = "quiz_generation"
    DISCUSSION_GENERATION = "discussion_generation"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"

    ORDERED_STEPS = [
        AUTHENTICATION,
        CONTENT_LOADING,
        TOPIC_SPLITTING,
        VIDEO_GENERATION,
        HANDOUT_GENERATION,
        CHEATSHEET_GENERATION,
        MINDMAP_GENERATION,
        AUDIOBOOK_GENERATION,
        STORY_GENERATION,
        STRATEGY_GENERATION,
        FLASHCARD_GENERATION,
        QUIZ_GENERATION,
        DISCUSSION_GENERATION,
        DOWNLOADING,
        COMPLETED,
    ]
