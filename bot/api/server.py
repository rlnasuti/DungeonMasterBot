from flask import Flask, request, jsonify
from bot.main import process_message, reset_conversation
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_input = request.json.get('user_input')
    response = process_message(user_input)
    return jsonify({'response': response})

@app.route('/chat/reset', methods=['POST'])
def reset_endpoint():
    reset_conversation()
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(port=8000, debug=True)
