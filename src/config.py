"""Central reference for the environment variables this project reads.
Nothing here is loaded automatically — run.py calls load_dotenv() once at
startup, and individual modules read os.getenv() where they need a value.
This file exists so there's one place documenting what's required."""

REQUIRED_ENV_VARS = {
    "GITHUB_TOKEN": "optional — raises GitHub API rate limit from 60/hr to 5000/hr",
    "YOUTUBE_API_KEY": "required only for the 'videos' module (Google Cloud Console)",
    "GEMINI_API_KEY": "optional for LLM description generation via Google Gemini",
}
