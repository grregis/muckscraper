# news_fetcher/summarizer.py

import requests
import os
import re

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "")
MODEL = os.environ.get("OLLAMA_MODEL", "mannix/llama3.1-8b-lexi:latest")


def check_ollama_status():
    """Returns True if Ollama is reachable, False otherwise."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def strip_html(text):
    """Strip HTML tags and clean up whitespace for LLM input."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def summarize_story(story):
    """
    Given a Story object with related articles, ask Ollama to generate
    a detailed summary of the story based on titles and content snippets.
    Returns summary string or None if Ollama is unavailable.
    """
    if not story.articles:
        return None

    article_texts = []
    for i, article in enumerate(story.articles[:10], 1):
        text = f"{i}. Title: {article.title}"
        if article.content:
            # Strip HTML before sending to Ollama
            clean_content = strip_html(article.content)
            # Use more content now that we have full scraped articles
            snippet = clean_content[:1500].strip()
            text += f"\n   Content: {snippet}"
        article_texts.append(text)

    combined = "\n\n".join(article_texts)

    prompt = f"""You are a professional news analyst writing in the Smart Brevity style.

Below are multiple news articles covering the same story. Write a structured summary using EXACTLY this format:

The big picture: [One punchy, direct sentence summarizing what happened. No fluff.]

Why it matters: [1-2 sentences explaining the significance.]

What's happening:
- [Key fact or development]
- [Key fact or development]
- [Key fact or development]
- [Add more bullets if needed, max 6]

What's next: [One sentence on what to watch for or what comes next.]

Rules:
- Use EXACTLY the labels shown above including the colon
- Bullets must start with • 
- Keep every section tight and direct
- No markdown, no extra formatting, no commentary
- Do not add any text before or after the structure above

Articles:
{combined}

Detailed Summary:"""

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        summary = result.get("response", "").strip()

        if summary:
            print(f"  Generated summary for story: {story.title[:60]}...")
            return summary
        return None

    except Exception as e:
        print(f"  Error generating summary for '{story.title}': {e}")
        return None