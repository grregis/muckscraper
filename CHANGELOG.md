# Changelog

All notable changes to MuckScraper are documented here.

---

## [0.1.3] - 2026-03-17

### Added
- `python-readability` for smarter article content extraction
- Googlebot user agent fallback for soft-paywalled sites (Axios, Politico, The Atlantic, and others)
- archive.ph fallback when all other scraping strategies fail
- Per-article `[scrape]` button for articles missing full text
- Global ↻ Scrape Missing sidebar button to bulk re-scrape up to 20 articles at a time
- DB indexes on `articles.url`, `articles.date`, `articles.outlet_id`, `articles.story_id`, `articles.bias_score`, and `stories.created_at`
- Raw API payload storage with 30-day auto-cleanup
- `restart.sh` script for soft rebuilds that preserve the database

### Fixed
- Ollama catchup button breaking article links and summarization
- Re-grouping creating new stories instead of only matching existing ones
- Auto-summarization capped to 10 stories per batch to prevent timeouts
- HTML tags being sent to Ollama in summaries — content now stripped to plain text first
- Content snippet size increased from 500 to 1500 chars per article

---

## [0.1.2] - 2026-03-13

### Added
- Full article scraping with BeautifulSoup and Playwright fallback
- Sanitized HTML storage for scraped articles
- Article reader page at `/article/<id>`
- LLM story grouping using keyword pre-filter and Ollama match decision
- Smart Brevity summary format with labeled sections and bullet points
- Dark/light mode toggle with localStorage persistence
- Sticky sidebar with purple accent and drop shadow
- Ollama Catchup button — re-groups, re-rates, and re-summarizes when Ollama comes back online
- Automatic Ollama catchup when scheduler detects Ollama came back online
- Smart restart timer — skips fetch on startup if last fetch was less than 3 hours ago
- `AppSetting` model for persisting state across container restarts
- Many-to-many topic tagging for articles and stories
- GNews as a second news source alongside NewsAPI
- `destroy.sh` and `restart.sh` maintenance scripts
- `.env` support for all credentials and configuration
- `.env.example` template committed to repository

### Fixed
- Race condition causing duplicate topic creation
- Scheduler running stale cached code after restarts
- `POSTGRES_USER` typo in `docker-compose.yml`
- Removed standalone `news_fetcher` container — scheduler handles all fetching

---

## [0.1.2] - 2026-03-10

### Added
- Initial release
- Flask + PostgreSQL + Docker Compose setup
- NewsAPI integration with scheduled fetching every 3 hours
- Outlet-level political bias scoring via Ollama (1=Left to 5=Right)
- On-demand AI story summarization via Ollama
- Source blocklist for filtering unwanted domains and title patterns
- Ollama online/offline status indicator
- Per-article and per-outlet bias rating buttons
- MIT License
- README documentation
