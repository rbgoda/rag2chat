import os
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from flask_cors import CORS
from search import DocumentIndex
from chat_manager import ChatManager

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# 1. Add validation for critical environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
raise ValueError("OPENAI_API_KEY environment variable is not set. Please set it to run the application.")

model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
try:
max_tokens = int(os.getenv("MAX_TOKENS", "1500"))
except (ValueError, TypeError):
raise ValueError("MAX_TOKENS environment variable must be a valid integer.")

# Initialize services
client = OpenAI(api_key=openai_api_key)
doc_index = DocumentIndex()
chat_manager = ChatManager(max_history=5)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/upload", methods=["POST"])
def upload_pdf():
"""
Handles PDF file uploads, indexes the document, and then cleans up the temporary file.
"""
if "file" not in request.files:
return jsonify({"error": "No file part in the request."}), 400
file = request.files["file"]
if file.filename == "":
return jsonify({"error": "No selected file."}), 400

filename = f"{uuid.uuid4()}.pdf"
filepath = os.path.join(UPLOAD_FOLDER, filename)

try:
file.save(filepath)
doc_index.load_pdf(filepath, doc_id=filename)
return jsonify({"message": f"File uploaded and indexed as {filename}"}), 200
except Exception as e:
# 2. Return a specific error message if processing fails
print(f"Error processing PDF file: {e}")
return jsonify({"error": f"Failed to process the PDF: {str(e)}"}), 500
finally:
# 2. Use a finally block to ensure the uploaded file is always deleted
if os.path.exists(filepath):
os.remove(filepath)
print(f"Cleaned up temporary file: {filepath}")

@app.route("/chat", methods=["POST"])
def chat():
"""
Handles chat requests by finding relevant context and generating a response.
Includes robust error handling for API calls.
"""
data = request.json
if not data:
return jsonify({"error": "Invalid JSON data."}), 400

session_id = data.get("session_id") or str(uuid.uuid4())
question = data.get("question", "").strip()
if not question:
return jsonify({"error": "No question provided."}), 400

try:
# Retrieve relevant context from the document index
top_chunks = doc_index.search(question, top_k=5)
context = "\n\n".join(top_chunks)

# Get chat history for the session
history = chat_manager.get_history(session_id)

# Build the message payload for the OpenAI API
messages = [{"role": "system", "content": "You are a helpful legal assistant."}]
messages.extend(history)
user_prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
messages.append({"role": "user", "content": user_prompt})

# 4. Wrap the OpenAI API call in a try-except block
completion = client.chat.completions.create(
model=model_name,
messages=messages,
max_tokens=max_tokens,
temperature=0
)
answer = completion.choices[0].message.content

# Update chat history with the new question and answer
chat_manager.add_message(session_id, "user", question)
chat_manager.add_message(session_id, "assistant", answer)

return jsonify({"session_id": session_id, "answer": answer}), 200

except Exception as e:
# 4. Handle various API-related exceptions gracefully
print(f"An error occurred during the chat process: {e}")
return jsonify({"error": "An error occurred while generating the response."}), 500

if __name__ == "__main__":
app.run(host="0.0.0.0", port=5000, debug=True)