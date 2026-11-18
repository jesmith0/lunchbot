import json

from flask import Flask, render_template, request

from lunchbot import process_message

app = Flask(__name__)
app.config.update(PROPAGATE_EXCEPTIONS=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/lunchbot", methods=["GET", "POST"])
def lunchbot():
    # process message from hipchat
    if request.method == "POST":
        try:
            json_dict = json.loads(request.data)
            msg = json_dict["item"]["message"]["message"]
            user = json_dict["item"]["message"]["from"]["name"]
            room = json_dict["item"]["room"]["name"]
        except ValueError as e:
            return "Invalid JSON in request : " + str(e), 400

        return process_message(msg, user, room)

    # get index page
    return render_template("lunchbot.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=80)
