import re
from PyPDF2 import PdfReader
from rank_bm25 import BM25Okapi
from threading import Lock

class DocumentIndex:
def __init__(self):
self.docs = {}
self.all_chunks = []
self.tokenized_chunks = []
self.bm25 = None
self.lock = Lock()

def load_pdf(self, file_path, doc_id):
text = ""
reader = PdfReader(file_path)
for page in reader.pages:
text += page.extract_text() + "\n"
chunks = re.findall(r'(.{1,3000})(?:\s+|$)', text, re.S)
with self.lock:
self.docs[doc_id] = chunks
self._rebuild_index()

def _rebuild_index(self):
self.all_chunks = []
for chunks in self.docs.values():
self.all_chunks.extend(chunks)
self.tokenized_chunks = [chunk.lower().split() for chunk in self.all_chunks]
self.bm25 = BM25Okapi(self.tokenized_chunks)

def search(self, query, top_k=5):
if not self.bm25:
return []
tokenized_query = query.lower().split()
scores = self.bm25.get_scores(tokenized_query)
ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
return [self.all_chunks[i] for i in ranked_indices]
