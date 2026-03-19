# news_fetcher/scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aggregator import create_app, db
from aggregator.models import AppSetting
from news_fetcher.fetch_and_store_articles import fetch_and_store_articles, ollama_catchup
from datetime import datetime, timedelta
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

FETCH_INTERVAL_HOURS = 3

SCHEDULED_FETCHES = [
    {
        "label":          "US and World News",
        "mode":           "top",
        "country":        "us",
        "category":       None,
        "query":          None,
        "gnews_query":    None,
        "gnews_category": "general",
    },
    {
        "label":          "World News",
        "mode":           "top",
        "country":        None,
        "category":       None,
        "query":          None,
        "gnews_query":    None,
        "gnews_category": "world",
    },
    {
        "label":          "US Politics",
        "mode":           "query",
        "country":        None,
        "category":       None,
        "query":          "US politics congress white house senate trump",
        "gnews_query":    "US politics congress",
        "gnews_category": None,
    },
    {
        "label":          "Technology",
        "mode":           "top",
        "country":        "us",
        "category":       "technology",
        "query":          None,
        "gnews_query":    None,
        "gnews_category": "technology",
    },
    {
        "label":          "Entertainment and Gaming",
        "mode":           "query",
        "country":        None,
        "category":       None,
        "query":          "video games gaming PlayStation Xbox Nintendo Steam esports",
        "gnews_query":    "video games gaming",
        "gnews_category": None,
    },
    {
        "label":          "Sports",
        "mode":           "top",
        "country":        "us",
        "category":       "sports",
        "query":          None,
        "gnews_query":    None,
        "gnews_category": "sports",
    },
    {
        "label":          "Business",
        "mode":           "top",
        "country":        "us",
        "category":       "business",
        "query":          None,
        "gnews_query":    None,
        "gnews_category": "business",
    },
]
app = create_app()


def get_last_fetch_time():
    """Get the last fetch timestamp from the database."""
    setting = AppSetting.query.filter_by(key="last_fetch").first()
    if setting and setting.value:
        try:
            return datetime.fromisoformat(setting.value)
        except Exception:
            return None
    return None


def set_last_fetch_time():
    """Store the current time as the last fetch timestamp."""
    setting = AppSetting.query.filter_by(key="last_fetch").first()
    if setting:
        setting.value = datetime.utcnow().isoformat()
    else:
        setting = AppSetting(key="last_fetch", value=datetime.utcnow().isoformat())
        db.session.add(setting)
    db.session.commit()


def should_fetch_now():
    """
    Returns True if it's been more than FETCH_INTERVAL_HOURS since the last fetch,
    or if no fetch has ever been recorded.
    """
    last_fetch = get_last_fetch_time()
    if last_fetch is None:
        logging.info("No previous fetch found, fetching now.")
        return True

    elapsed = datetime.utcnow() - last_fetch
    remaining = timedelta(hours=FETCH_INTERVAL_HOURS) - elapsed

    if elapsed >= timedelta(hours=FETCH_INTERVAL_HOURS):
        logging.info(f"Last fetch was {elapsed} ago, fetching now.")
        return True
    else:
        minutes_remaining = int(remaining.total_seconds() / 60)
        logging.info(
            f"Last fetch was {int(elapsed.total_seconds() / 60)} minutes ago. "
            f"Next fetch in {minutes_remaining} minutes, skipping startup fetch."
        )
        return False


# Track Ollama state between runs
ollama_was_online = False


def run_all_fetches():
    global ollama_was_online

    logging.info("=== Starting scheduled fetch run ===")
    with app.app_context():
        # Check if Ollama just came back online
        from news_fetcher.summarizer import check_ollama_status
        ollama_is_online = check_ollama_status()

        if ollama_is_online and not ollama_was_online:
            logging.info("Ollama just came back online — running catchup...")
            try:
                ollama_catchup()
            except Exception as e:
                logging.error(f"Ollama catchup error: {e}")

        ollama_was_online = ollama_is_online

        for fetch in SCHEDULED_FETCHES:
            logging.info(f"--- Fetching: {fetch['label']} ---")
            try:
                fetch_and_store_articles(
                    topic_name=fetch["label"],
                    mode=fetch["mode"],
                    query=fetch.get("query"),
                    country=fetch.get("country"),
                    category=fetch.get("category"),
                    gnews_query=fetch.get("gnews_query"),
                    gnews_category=fetch.get("gnews_category"),
                )
            except Exception as e:
                logging.error(f"Error fetching {fetch['label']}: {e}")

        set_last_fetch_time()

    logging.info("=== Scheduled fetch run complete ===")


if __name__ == "__main__":
    logging.info("Scheduler starting up...")

    with app.app_context():
        db.create_all()
        # Only fetch on startup if enough time has passed
        if should_fetch_now():
            run_all_fetches()
        else:
            logging.info("Skipping startup fetch.")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_all_fetches,
        trigger=IntervalTrigger(hours=FETCH_INTERVAL_HOURS),
        id="fetch_job",
        name="3-hourly news fetch",
        replace_existing=True
    )

    logging.info(f"Scheduler running. Fetching every {FETCH_INTERVAL_HOURS} hours.")
    scheduler.start()