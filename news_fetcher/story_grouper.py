# news_fetcher/story_grouper.py

import requests
import os
from datetime import datetime, timedelta

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "")
MODEL = os.environ.get("OLLAMA_MODEL", "")


def get_candidate_stories(article_title, recent_stories, max_candidates=5):
    """
    Pre-filter recent stories using simple keyword overlap
    to find the most likely candidates before asking Ollama.
    Returns up to max_candidates stories.
    """
    article_words = set(
        w.lower() for w in article_title.split()
        if len(w) > 3  # skip short words
    )

    scored = []
    for story in recent_stories:
        story_words = set(
            w.lower() for w in story.title.split()
            if len(w) > 3
        )
        overlap = len(article_words & story_words)
        if overlap > 0:
            scored.append((overlap, story))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [story for _, story in scored[:max_candidates]]


def ask_ollama_for_match(article_title, candidate_stories):
    """
    Ask Ollama if the article matches any of the candidate stories.
    Returns matched Story object or None.
    """
    if not candidate_stories:
        return None

    story_list = "\n".join(
        f"{i+1}. {story.title}"
        for i, story in enumerate(candidate_stories)
    )

    prompt = f"""You are a news editor grouping articles into stories.

Article title: "{article_title}"

Existing stories:
{story_list}

Does this article cover the same event or ongoing situation as any of the stories listed above?

Rules:
- Only match if they are clearly about the same specific event or situation
- Do not match just because they share a broad topic (e.g. both about "politics")
- If it matches, respond with only the number of the matching story (e.g. "2")
- If it does not match any story, respond with only "0"
- Respond with a single number and nothing else"""

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

        # Extract the number from the response
        for token in result.split():
            if token.isdigit():
                match_index = int(token)
                if 1 <= match_index <= len(candidate_stories):
                    matched = candidate_stories[match_index - 1]
                    print(f"  [Grouper] Matched to story: '{matched.title}'")
                    return matched
                elif match_index == 0:
                    print(f"  [Grouper] No match found, will create new story")
                    return None

        print(f"  [Grouper] Unexpected response '{result}', creating new story")
        return None

    except Exception as e:
        print(f"  [Grouper] Ollama error: {e}, creating new story")
        return None


def find_or_create_story(article_title, db, Story, recent_stories):
    """
    Main entry point. Try to match article to an existing story via LLM,
    or create a new one if no match found.
    Returns a Story object.
    """
    # Step 1: keyword pre-filter
    candidates = get_candidate_stories(article_title, recent_stories)

    # Step 2: ask Ollama if Ollama is available and we have candidates
    matched_story = None
    if candidates and OLLAMA_HOST:
        matched_story = ask_ollama_for_match(article_title, candidates)

    # Step 3: return matched story or create new one
    if matched_story:
        return matched_story

    # Create a new story with a clean title
    new_title = clean_story_title(article_title)
    story = Story(title=new_title, summary=None)
    db.session.add(story)
    db.session.flush()
    print(f"  [Grouper] Created new story: '{new_title}'")
    return story


def clean_story_title(article_title):
    """
    Generate a clean story title from an article title.
    Only strips source attribution at the end, keeps the rest intact.
    """
    # Strip source attribution suffixes like " - Reuters" or " | BBC News"
    # but only if the suffix looks like a source name (short, at the end)
    for sep in [" - ", " | ", " — "]:
        if sep in article_title:
            parts = article_title.rsplit(sep, 1)
            # Only strip if the suffix is short (likely a source name)
            if len(parts[1].split()) <= 4:
                article_title = parts[0]
                break

    # Truncate to 12 words max to keep titles readable
    words = article_title.split()
    if len(words) > 12:
        return " ".join(words[:12]) + "..."

    return article_title
