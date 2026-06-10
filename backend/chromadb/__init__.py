import os
import sqlite3
import json
import re
import math

def stem(word):
    word = word.lower()
    # Vocabulary mapping for common proposal terms
    if word.startswith("certif") or word.startswith("cert"):
        return "cert"
    if word.startswith("implement"):
        return "implement"
    if word.startswith("manag"):
        return "manag"
    if word.startswith("compli"):
        return "compli"
    if word.startswith("secur"):
        return "secur"
    if word.startswith("experi"):
        return "experi"
    # General light suffix stripping
    for suffix in ["s", "es", "ed", "ing", "er", "ers", "ment", "ments", "tion", "tions", "ive", "al", "ly"]:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word

def tokenize(text):
    words = re.findall(r'\w+', str(text).lower())
    return [stem(w) for w in words]

class MockCollection:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._init_db()

    def _init_db(self):
        # Store mock database inside the persistent directory
        self.db_path = os.path.join(self.client.path, "chroma_mock.db")
        os.makedirs(self.client.path, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mock_collection (
            id TEXT PRIMARY KEY,
            document TEXT,
            metadata TEXT
        )
        """)
        conn.commit()
        conn.close()

    def count(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mock_collection")
        cnt = cursor.fetchone()[0]
        conn.close()
        return cnt

    def add(self, documents, ids, metadatas=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for idx, doc in enumerate(documents):
            doc_id = ids[idx]
            meta = metadatas[idx] if metadatas and idx < len(metadatas) else {}
            meta_json = json.dumps(meta)
            cursor.execute("""
            INSERT OR REPLACE INTO mock_collection (id, document, metadata)
            VALUES (?, ?, ?)
            """, (doc_id, doc, meta_json))
        conn.commit()
        conn.close()

    def upsert(self, documents, ids, metadatas=None):
        self.add(documents, ids, metadatas)

    def query(self, query_texts, n_results=3):
        # Retrieve all records from local mock database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, document, metadata FROM mock_collection")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"documents": [[]], "ids": [[]], "metadatas": [[]], "distances": [[]]}

        all_docs = []
        doc_ids = []
        doc_metas = []

        for row in rows:
            doc_ids.append(row[0])
            all_docs.append(row[1])
            try:
                meta = json.loads(row[2])
            except Exception:
                meta = {}
            doc_metas.append(meta)

        # Build TF-IDF
        df = {}
        for doc in all_docs:
            terms = set(tokenize(doc))
            for term in terms:
                df[term] = df.get(term, 0) + 1

        N = len(all_docs)
        idf = {}
        for term, val in df.items():
            idf[term] = math.log((1 + N) / (1 + val)) + 1

        doc_vectors = []
        for doc in all_docs:
            tokens = tokenize(doc)
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            vec = {term: count * idf.get(term, 1.0) for term, count in tf.items()}
            doc_vectors.append(vec)

        res_docs = []
        res_ids = []
        res_metas = []
        res_distances = []

        for q_text in query_texts:
            q_tokens = tokenize(q_text)
            q_tf = {}
            for token in q_tokens:
                q_tf[token] = q_tf.get(token, 0) + 1
            q_vec = {term: count * idf.get(term, 1.0) for term, count in q_tf.items()}

            q_mag = math.sqrt(sum(v**2 for v in q_vec.values()))

            scores = []
            for idx, doc_vec in enumerate(doc_vectors):
                # Calculate Cosine Similarity
                dot_product = sum(q_vec[t] * doc_vec.get(t, 0.0) for t in q_vec if t in doc_vec)
                doc_mag = math.sqrt(sum(v**2 for v in doc_vec.values()))

                if q_mag > 0 and doc_mag > 0:
                    # Soft normalization: use doc_mag ** 0.75 to reduce length penalty for rich documents
                    sim = dot_product / (q_mag * (doc_mag ** 0.75))
                    sim = min(1.0, max(0.0, sim))
                else:
                    sim = 0.0

                # Map Cosine Similarity [0, 1] to L2 distance compatible with rag_engine.py
                # rag_engine.py similarity = 1.0 / (1.0 + d) * 100
                # sim = 1.0 / (1.0 + d) => d = (1.0 / sim) - 1.0
                distance = (1.0 / sim) - 1.0 if sim > 0.01 else 99.0
                scores.append((distance, idx))

            scores.sort(key=lambda x: x[0])
            top_scores = scores[:n_results]

            q_docs = []
            q_ids = []
            q_metas = []
            q_dists = []

            for dist, idx in top_scores:
                q_docs.append(all_docs[idx])
                q_ids.append(doc_ids[idx])
                q_metas.append(doc_metas[idx])
                q_dists.append(dist)

            res_docs.append(q_docs)
            res_ids.append(q_ids)
            res_metas.append(q_metas)
            res_distances.append(q_dists)

        return {
            "documents": res_docs,
            "ids": res_ids,
            "metadatas": res_metas,
            "distances": res_distances
        }

class MockClient:
    def __init__(self, path):
        self.path = path

    def get_or_create_collection(self, name):
        return MockCollection(self, name)

def PersistentClient(path):
    return MockClient(path)
