# CLAUDE.md - Project Guidelines

## Project Overview
NotebookLM Generation Tool - A comprehensive automation tool that processes educational content and generates various learning materials using Google's Gemini AI and NotebookLM.

## Tech Stack
- **Language**: Python 3.11+
- **Authentication**: Google OAuth 2.0
- **AI Services**: Google Gemini API, NotebookLM (via Selenium automation)
- **Content Processing**: PyPDF2, BeautifulSoup, requests
- **Automation**: Selenium WebDriver
- **Progress Tracking**: Threading with periodic updates

## Project Structure
```
notebook-lm-generation/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── auth/
│   │   ├── __init__.py
│   │   └── google_auth.py      # Google/Gemini authentication
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── content_processor.py # PDF/TXT/Website processing
│   │   └── topic_splitter.py    # Split content by topics
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── notebooklm.py       # NotebookLM automation
│   │   ├── gemini_client.py    # Gemini API client
│   │   ├── handout.py          # Handout generation
│   │   ├── cheatsheet.py       # Cheatsheet generation
│   │   ├── mindmap.py          # Mindmap generation
│   │   ├── audiobook.py        # Audiobook chapters
│   │   ├── story.py            # Fantasy/Sci-Fi stories
│   │   ├── strategy.py         # Learning strategy papers
│   │   ├── flashcards.py       # Karteikarten generation
│   │   ├── quiz.py             # Quiz generation
│   │   └── discussion.py       # Podium discussion videos
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── progress_reporter.py # Progress tracking
│   │   ├── logger.py           # Logging utilities
│   │   └── downloader.py       # Download/export utilities
│   └── config/
│       ├── __init__.py
│       └── settings.py         # Configuration settings
├── tests/
│   └── ...
├── requirements.txt
├── install.sh
├── README.md
├── JOURNAL.md
└── CLAUDE.md
```

## Key Commands
- `python -m src.main <input_file>` - Run the generation pipeline
- `pip install -r requirements.txt` - Install dependencies
- `./install.sh` - Full installation script

## Coding Standards
- Use type hints for all functions
- Docstrings for all public functions
- Error handling with proper logging
- Progress updates every 15 seconds
- All output files saved to input file's directory

## Important Notes
- NotebookLM requires browser automation (no official API)
- Gemini API key required for story generation
- Google OAuth for account authentication
- All operations should be idempotent where possible
- Failed operations should be logged and retried where appropriate

## Environment Variables
- `GOOGLE_CLIENT_ID` - OAuth client ID
- `GOOGLE_CLIENT_SECRET` - OAuth client secret
- `GEMINI_API_KEY` - Gemini API key

## Testing
- Run tests with: `pytest tests/`
- Integration tests require valid credentials
