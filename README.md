# AI Orbit Data Ingestion Pipeline

A modular Python pipeline that fetches AI-ecosystem entities from official
APIs, cleans/dedupes/normalizes them, finds official logos, derives
relationships, generates LLM descriptions, and exports a Google-Sheets-ready
dataset.

Workflow (matches the spec):
`Discovery → Extraction → Cleaning → Normalization → Deduplication → Classification → Relationship Mapping → Validation → Description → Export`

## Layout
```
src/sources/     one module per data source (GitHub, Hugging Face, YouTube,
                 RSS, manual seed YAML). Each exposes fetch_raw() [network]
                 and parse() [pure], so parsing is unit-testable without
                 hitting the network.
src/pipeline/    clean, normalize_urls, dedupe, logos, classify,
                 relationships, describe (LLM), validate.
src/export/      JSON + CSV writers.
data/seeds/      YAML for the categories with no single clean API
                 (companies, tools, robots, devices, personal).
data/final/      pipeline output lands here (entities.json,
                 relationships.json, ai_orbit_dataset.csv).
tests/           unit tests for every pure function, plus each source's
                 parse() against a realistic sample payload.
run.py           CLI that wires one or more modules through the pipeline.
```

## Setup
```
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill in whichever keys you have
```

## API keys (`.env`)
| Key | Needed for | Where to get it |
|---|---|---|
| `GITHUB_TOKEN` | repos / mcp / collections (works without it, capped at 60 req/hr vs 5000/hr) | github.com → Settings → Developer settings → Personal access tokens (no scopes needed, public read only) |
| `YOUTUBE_API_KEY` | videos | console.cloud.google.com → enable "YouTube Data API v3" → Credentials |
| `GEMINI_API_KEY` | Step 3 (LLM descriptions) | console.google.com / Google AI Studio |

## Running
```
python run.py --module models --limit 40
python run.py --module repos,mcp --limit 30
python run.py --module all --limit 25
python run.py --module news --check-feeds      # test RSS URLs without a full run
```
`--module` takes one preset, a comma-separated list (combine several into one
export), or `all`. **Each run overwrites `data/final/`** rather than
appending, so combine everything you want in a single invocation.

Flags: `--skip-logos` (faster iteration), `--skip-descriptions` (skip the LLM
step, e.g. while you don't have a key yet).

Output: `data/final/entities.json`, `relationships.json`,
`ai_orbit_dataset.csv` — import the CSV into Google Sheets (File → Import →
Upload) for Step 4 of the task, then set sharing to "Anyone with the link –
Viewer".

## Which module to pick
The task says to pick one module from a linked doc. These five map onto real,
official APIs and score best on the "API-first" / Discovery criterion:

| Module | Source | Notes |
|---|---|---|
| `models` | Hugging Face Hub API | license/provider/modality come straight from the API |
| `repos` | GitHub Search API | stars/language/last-updated come straight from the API |
| `mcp` | GitHub Search API (`topic:mcp-server`) | same connector as repos, different query |
| `videos` | YouTube Data API v3 | needs `YOUTUBE_API_KEY` |
| `news` | RSS (TechCrunch, VentureBeat, MIT Tech Review, The Verge, HF Blog, OpenAI) | run `--check-feeds` first |

`companies` / `tools` / `robots` / `devices` / `personal` are seed-YAML-backed
(no single clean API for these) — `data/seeds/companies.yaml` and
`tools.yaml` ship with a handful of verified real entries as a starting
point; the rest are format templates for you to fill in via your own
research.

## Technical decisions
- **Stable IDs**: `id` is `uuid5(entity_type + name + url)`, so re-running the
  pipeline never creates duplicate IDs for the same entity.
- **Dedup**: matches on a normalized name (lowercased, punctuation and legal
  suffixes stripped, spacing collapsed so "OpenAI" and "Open AI Inc" match)
  AND on normalized domain; the richer description and the union of
  categories are kept on merge.
- **Official URL**: prefers a GitHub repo's own `homepage` field over its
  `github.com` page when present, since that's usually the vendor's actual
  site, per the "replace with official URL" requirement.
- **Logos**: scrapes the official page for `<link rel="icon">` / `og:image`
  first, verifies the response is really an image via a HEAD request, and
  falls back to Google's public favicon service (unofficial but free, no
  key, confirmed working as of Sep 2026) if scraping finds nothing.
- **Descriptions**: one Gemini API call per record, grounded only in facts
  already collected (the prompt explicitly forbids inventing details),
  threaded for speed. Runs *before* validation, since several seed records
  ship with a blank description for the LLM to fill — validating first would
  reject them as incomplete before they got the chance. Falls back to the
  original description if no key is set or a call fails, so the pipeline
  degrades instead of crashing.
- **Relationships**: derived heuristically — Company→develops→(anything)
  by owner/provider/maker name matching; (anything)→solves→Task by keyword
  match against a small task taxonomy; MCP→integrates_with→Tool by name
  mention in the MCP's own text; Device→runs→Model only when declared
  explicitly in seed data (not reliably derivable otherwise). These are
  best-effort — spot-check before submitting.
- **Metadata nesting**: domain-specific fields (license, stars, provider,
  etc.) live under a nested `metadata` object rather than flattened at the
  top level, so the common schema stays stable across very different entity
  types while still carrying rich, structured detail.

## Known limitations
- GitHub topic names and RSS feed URLs drift over time. Watch the per-source
  counts the pipeline prints — a `0 results` line means a query needs
  adjusting, not that something crashed.
- Robots/devices/personal-assistant categories have no single clean API;
  `data/seeds/` holds the starting point, not the finished list.
- Logo and relationship detection are heuristic. The task explicitly asks
  for manual verification — budget time for a spot-check pass over ~10-15%
  of rows before submitting.

## Tests
```
python -m unittest tests.test_pipeline_logic -v
```
Covers schema/id stability, URL normalization, dedupe, cleaning, validation,
classification, relationship derivation, and each source's `parse()` against
a realistic sample payload (mocked — no network needed to run these).
