import json
from lunchbot import process_message
from flask import Flask, request, render_template

app = Flask(__name__)

@app.route('/')
def index():
	return render_template('index.html')
	# 'Welcome to the homepage!\nFor lunchbot, navigate to <a href="/lunchbot">/lunchbot</a>!'

@app.route('/lunchbot', methods=['GET', 'POST'])
def lunchbot():

	#  process message from hipchat
	if request.method == 'POST':
		
		json_dict = json.loads(request.data)

		msg = json_dict['item']['message']['message']
		room = json_dict['item']['room']['name']
	
		return process_message(msg, room)

	# get index page
	else:
		return render_template('lunchbot.html')

if __name__ == '__main__':
	app.debug = True
	app.run(debug=True, host='0.0.0.0', port=80)
