# NotebookLM Generation Tool

Automated learning material generation from educational content using Google's Gemini AI and NotebookLM.

## Features

This tool takes educational content (PDF, TXT, or website) and automatically generates:

- **Video summaries** via NotebookLM Audio Overview
- **Handouts** with keypoint summaries
- **Cheatsheets** for quick reference
- **Mindmaps** (Mermaid format) for each topic
- **Audiobook chapters** with narration scripts
- **Fantasy & Sci-Fi stories** that teach the concepts
- **Learning strategy papers** for exam preparation
- **Flashcards** (Karteikarten) - both markdown and Anki format
- **Quizzes** with answer keys
- **Podium discussions** with 3 participants

### Additional Features

- **Progress reporter** with updates every 15 seconds
- **Detailed logging** of all operations
- **Automatic topic splitting** using AI
- **Anki deck generation** (.apkg format)
- **Opens Gemini** at the end for additional interaction

## Installation

### Prerequisites

- Python 3.11 or higher
- Google Chrome browser
- Google account
- Gemini API key (optional but recommended)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/notebook-lm-generation.git
cd notebook-lm-generation

# Run the install script
./install.sh
```

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Chrome WebDriver (optional - webdriver-manager handles this)
# brew install chromedriver  # macOS
# apt-get install chromium-chromedriver  # Ubuntu
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required for full functionality
GEMINI_API_KEY=your_gemini_api_key

# Optional
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
HEADLESS_BROWSER=false
LOG_LEVEL=INFO
```

### Getting a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add it to your `.env` file or pass via command line

## Usage

### Basic Usage

```bash
# Process a PDF file
python -m src.main document.pdf

# Process a text file
python -m src.main notes.txt

# Process a website
python -m src.main https://example.com/article
```

### With Authentication

```bash
# With Google account credentials
python -m src.main document.pdf -e your.email@gmail.com -p your_password

# With Gemini API key
python -m src.main document.pdf --api-key YOUR_API_KEY
```

### Additional Options

```bash
python -m src.main document.pdf \
    -e email@gmail.com \
    -p password \
    -o ./output_folder \
    --headless \
    --api-key YOUR_API_KEY \
    -v  # verbose mode
```

### Command Line Arguments

| Argument | Description |
|----------|-------------|
| `input` | Input file path (PDF, TXT) or URL |
| `-e, --email` | Google account email |
| `-p, --password` | Google account password |
| `-o, --output` | Output directory |
| `--headless` | Run browser in headless mode |
| `--api-key` | Gemini API key |
| `-v, --verbose` | Enable verbose output |

## Output Structure

All generated files are saved to the same folder as the input file:

```
input_file_output/
├── videos/           # NotebookLM generated videos
├── handouts/         # Summary handouts
├── cheatsheets/      # Quick reference sheets
├── mindmaps/         # Mermaid diagram mindmaps
├── audiobooks/       # Narration scripts
├── stories/          # Fantasy & Sci-Fi stories
├── strategies/       # Learning strategy papers
├── flashcards/       # Markdown flashcards
├── anki/             # Anki deck files (.apkg, .txt)
├── quizzes/          # Quiz files with answer keys
├── discussions/      # Podium discussion scripts
└── notebook_lm_generation.log  # Process log
```

## Progress Tracking

The tool displays progress updates every 15 seconds showing:

- Current processing step
- Completed vs total steps
- Elapsed time
- Status of each generation task

## Troubleshooting

### Common Issues

**Browser automation fails:**
- Make sure Chrome is installed
- Try running without `--headless` first
- Check if Chrome is up to date

**Login fails:**
- Verify email and password are correct
- You may need to complete 2FA manually
- Try disabling "Less secure app access" warnings

**API errors:**
- Verify your Gemini API key is valid
- Check API quota limits
- The tool will fall back to browser automation if API fails

**NotebookLM issues:**
- NotebookLM UI may change - selectors might need updating
- Some features require manual interaction
- Audio generation can take several minutes

### Logs

Check the log file for detailed error information:

```bash
cat output_folder/notebook_lm_generation.log
```

## Development

### Project Structure

```
notebook-lm-generation/
├── src/
│   ├── main.py              # Entry point
│   ├── auth/                # Authentication
│   ├── processors/          # Content processing
│   ├── generators/          # Material generation
│   ├── utils/               # Utilities
│   └── config/              # Configuration
├── tests/                   # Test files
├── requirements.txt
├── install.sh
└── README.md
```

### Running Tests

```bash
pytest tests/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Security Notes

- Never commit credentials to version control
- Use environment variables for sensitive data
- The tool stores cookies locally for session persistence
- Consider using a separate Google account for automation

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Google Gemini AI for content generation
- Google NotebookLM for audio/video features
- Selenium for browser automation
- All open source dependencies

## Support

For issues and feature requests, please use the GitHub issue tracker.
