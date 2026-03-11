# aggregator/__init__.py
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import requests

db = SQLAlchemy()

TOPICS = [
    {"label": "US Headlines",    "mode": "top",   "query": None,                               "country": "us",  "category": None},
    {"label": "World Headlines", "mode": "top",   "query": None,                               "country": None,  "category": None},
    {"label": "US Politics",     "mode": "query", "query": "US politics congress white house", "country": None,  "category": None},
    {"label": "Technology",      "mode": "top",   "query": None,                               "country": "us",  "category": "technology"},
    {"label": "Gaming",          "mode": "top",   "query": None,                               "country": "us",  "category": "entertainment"},
    {"label": "Linux",           "mode": "query", "query": "linux open source",                "country": None,  "category": None},
]


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        ""
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    db.init_app(app)

    from .models import Article, Story, Outlet

    @app.route("/")
    def index():
        return redirect(url_for("list_articles"))

    @app.route("/articles")
    def list_articles():
        active_label = request.args.get("topic", None)

        if active_label:
            active_topic = next(
                (t for t in TOPICS if t["label"] == active_label), None
            )
            if active_topic and active_topic["mode"] == "query":
                keywords = active_topic["query"].split()[:3]
                query_filter = Article.title.ilike(f"%{keywords[0]}%")
                stories = (
                    Story.query
                    .join(Story.articles)
                    .filter(query_filter)
                    .order_by(Story.created_at.desc())
                    .distinct()
                    .limit(50)
                    .all()
                )
            else:
                stories = Story.query.order_by(Story.created_at.desc()).limit(50).all()
        else:
            stories = Story.query.order_by(Story.created_at.desc()).limit(50).all()

        return render_template(
            "articles.html",
            stories=stories,
            topics=TOPICS,
            active_label=active_label
        )

    @app.route("/fetch", methods=["POST"])
    def fetch_articles():
        mode     = request.form.get("mode", "top").strip()
        query    = request.form.get("query", "").strip() or None
        country  = request.form.get("country", "").strip() or None
        category = request.form.get("category", "").strip() or None
        label    = request.form.get("label", "").strip() or None

        try:
            from news_fetcher.fetch_and_store_articles import fetch_and_store_articles
            fetch_and_store_articles(
                mode=mode,
                query=query,
                country=country,
                category=category
            )
        except Exception as e:
            print(f"Fetch error: {e}")

        if label:
            return redirect(url_for("list_articles", topic=label))
        return redirect(url_for("list_articles"))

    @app.route("/summarize/<int:story_id>", methods=["POST"])
    def summarize_story_route(story_id):
        story = Story.query.get_or_404(story_id)
        label = request.form.get("label", "")

        try:
            from news_fetcher.summarizer import summarize_story, check_ollama_status
            if not check_ollama_status():
                print("Ollama is not reachable for manual summarization.")
            else:
                summary = summarize_story(story)
                if summary:
                    story.summary = summary
                    db.session.commit()
        except Exception as e:
            print(f"Summarization error: {e}")

        if label:
            return redirect(url_for("list_articles", topic=label))
        return redirect(url_for("list_articles"))

    @app.route("/rerank-outlet/<int:outlet_id>", methods=["POST"])
    def rerank_outlet(outlet_id):
        """Re-score an outlet's bias via Ollama."""
        outlet = Outlet.query.get_or_404(outlet_id)
        label  = request.form.get("label", "")

        try:
            from news_fetcher.outlet_bias_llm import get_outlet_bias_from_llm
            bias_score = get_outlet_bias_from_llm(outlet.name)
            if bias_score is not None:
                outlet.bias_score = bias_score
                # Update all articles from this outlet too
                Article.query.filter_by(outlet_id=outlet.id).update(
                    {"bias_score": bias_score}
                )
                db.session.commit()
                print(f"Re-ranked outlet '{outlet.name}' to {bias_score}")
            else:
                print(f"Ollama could not re-rank outlet '{outlet.name}'")
        except Exception as e:
            print(f"Re-rank error: {e}")

        if label:
            return redirect(url_for("list_articles", topic=label))
        return redirect(url_for("list_articles"))

    @app.route("/rate-article/<int:article_id>", methods=["POST"])
    def rate_article(article_id):
        """Score an individual article's bias via Ollama."""
        article = Article.query.get_or_404(article_id)
        label   = request.form.get("label", "")

        try:
            from news_fetcher.outlet_bias_llm import get_article_bias_from_llm
            bias_score = get_article_bias_from_llm(article.title, article.content)
            if bias_score is not None:
                article.bias_score = bias_score
                db.session.commit()
                print(f"Rated article '{article.title[:60]}' to {bias_score}")
            else:
                print(f"Ollama could not rate article '{article.title[:60]}'")
        except Exception as e:
            print(f"Article rating error: {e}")

        if label:
            return redirect(url_for("list_articles", topic=label))
        return redirect(url_for("list_articles"))

    @app.route("/ollama-status")
    def ollama_status():
        ollama_host = os.environ.get("OLLAMA_HOST", "http://192.168.3.9:11434")
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            online = response.status_code == 200
        except Exception:
            online = False
        return jsonify({"online": online})

    return app


def create_db(app):
    with app.app_context():
        db.create_all()