# news_fetcher/topic_classifier.py

import requests
import os
import logging

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "")
MODEL       = os.environ.get("OLLAMA_MODEL", "")

VALID_TOPICS = [
    "US Headlines",
    "US Politics",
    "International Headlines",
    "Science/Technology",
    "Gaming",
    "Sports",
    "Business/Finance",
    "Other",
]


def classify_article(title, content_snippet=""):
    """
    Ask Ollama to classify an article into one or more topics.
    Returns a list of topic label strings.
    Falls back to ["Other"] if Ollama is unavailable or classification fails.
    """
    if not OLLAMA_HOST or not MODEL:
        return ["Other"]

    # Use title + first 200 chars of content for classification
    text = title
    if content_snippet:
        clean = content_snippet[:200].strip()
        if clean:
            text += f"\n{clean}"

    topics_list = "\n".join(f"- {t}" for t in VALID_TOPICS if t != "Other")

    prompt = f"""You are a news editor categorizing articles.

Article: "{text}"

Available categories:
{topics_list}

Which categories does this article belong to? An article can belong to multiple categories if relevant.

Rules:
- Only pick from the categories listed above
- Pick as many as genuinely apply, but don't over-categorize
- If it doesn't fit any category, respond with "Other"
- Respond with ONLY the category names, one per line, nothing else
- Do not include explanations or punctuation"""

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model":  MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()

        result = response.json().get("response", "").strip()
        lines  = [line.strip() for line in result.splitlines() if line.strip()]

        matched = []
        for line in lines:
            for valid in VALID_TOPICS:
                if valid.lower() in line.lower():
                    if valid not in matched:
                        matched.append(valid)

        if matched:
            logger.info(f"  [Classifier] Tagged as: {', '.join(matched)}")
            return matched

        logger.info(f"  [Classifier] No match in response '{result}', using Other")
        return ["Other"]

    except Exception as e:
        logger.info(f"  [Classifier] Error: {e}, using Other")
        return ["Other"]