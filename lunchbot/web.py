"""Flask app. Chat platforms that deliver commands over HTTP mount their routes here."""

from flask import Flask, render_template

app = Flask(__name__)
app.config.update(PROPAGATE_EXCEPTIONS=True)


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/lunchbot")
def lunchbot() -> str:
    return render_template("lunchbot.html")


if __name__ == "__main__":
    app.run(debug=True)
