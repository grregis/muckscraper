# app/__init__.py
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:default1@postgres:5432/aggregator'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

from .models import Article

@app.route('/')
def index():
    return "Hello, Flask!"

@app.route('/articles')
def list_articles():
    articles = Article.query.all()
    return render_template('articles.html', articles=articles)

def create_db():
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    create_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
