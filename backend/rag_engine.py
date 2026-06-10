import os
import uuid
import chromadb
from chromadb.config import Settings

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

class RAGEngine:
    def __init__(self):
        # Create persistent ChromaDB Client
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        self.collection = self.client.get_or_create_collection(name="capabilities")
        
        # Self-healing seeding if collection is empty
        if self.collection.count() == 0:
            self._seed_from_sqlite()

    def reload_index(self):
        """
        Reloads the index by fetching new capability chunks from SQLite capability_chunks
        and upserting them into ChromaDB.
        """
        db_path = os.path.join(os.path.dirname(__file__), "engine.db")
        if not os.path.exists(db_path):
            return
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM capability_chunks")
            rows = cursor.fetchall()
            
            chunks = []
            ids = []
            metadatas = []
            
            for row in rows:
                chunk_id = row["chunk_id"]
                content = row["content"]
                source_file = row["source_file"]
                domain = row["domain"]
                meta_str = row["metadata"]
                
                meta = {
                    "source_file": source_file,
                    "domain": domain
                }
                if meta_str:
                    try:
                        extra_meta = json.loads(meta_str)
                        for k, v in extra_meta.items():
                            meta[k] = str(v)
                    except Exception:
                        pass
                
                chunks.append(content)
                ids.append(chunk_id)
                metadatas.append(meta)
                
            conn.close()
            
            if chunks:
                self.collection.upsert(
                    documents=chunks,
                    ids=ids,
                    metadatas=metadatas
                )
                print(f"Successfully reloaded ChromaDB: upserted {len(chunks)} chunks from SQLite capability_chunks.")
        except Exception as e:
            print("Error reloading ChromaDB from SQLite capability_chunks:", e)


    def _seed_from_sqlite(self):
        db_path = os.path.join(os.path.dirname(__file__), "engine.db")
        if not os.path.exists(db_path):
            return
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM capability_library")
            rows = cursor.fetchall()
            
            chunks = []
            metadata_dicts = []
            
            for row in rows:
                cap_id = row["cap_id"]
                domain = row["domain"]
                summary = row["project_summary"]
                cert = row["certification"]
                year = row["year_completed"]
                val = row["contract_value"]
                duration = row["duration_months"]
                client = row["client_type"]
                
                cap_text = (
                    f"Domain: {domain}\n"
                    f"Project Title/Summary: {summary}\n"
                    f"Certification: {cert}\n"
                    f"Year Completed: {year}\n"
                    f"Contract Value: {val}\n"
                    f"Duration: {duration} months\n"
                    f"Client Type: {client}"
                )
                chunks.append(cap_text)
                metadata_dicts.append({
                    "cap_id": cap_id,
                    "certification": cert,
                    "year_completed": year,
                    "contract_value": val,
                    "duration_months": duration,
                    "client_type": client
                })
            conn.close()
            
            if chunks:
                self.add_chunks(chunks, "dataset.xlsx", "General", metadata_dicts)
                print(f"Successfully auto-seeded {len(chunks)} records from SQLite capability_library into ChromaDB.")
        except Exception as e:
            print("Error auto-seeding ChromaDB from SQLite:", e)

    def add_chunks(self, chunks, source_file, domain, metadata_dicts=None):
        """
        Adds text chunks to the ChromaDB collection with metadata.
        """
        if not chunks:
            return
            
        ids = []
        metadatas = []
        
        for idx, chunk in enumerate(chunks):
            chunk_id = f"chunk-{source_file.replace(' ', '_')}-{str(uuid.uuid4())[:8]}-{idx}"
            ids.append(chunk_id)
            
            meta = {
                "source_file": source_file,
                "domain": domain
            }
            if metadata_dicts and idx < len(metadata_dicts):
                for k, v in metadata_dicts[idx].items():
                    meta[k] = str(v) if v is not None else ""
            metadatas.append(meta)
            
        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

    def retrieve_matches(self, query_text, limit=3):
        """
        Queries ChromaDB using cosine vector similarity.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=limit
            )
        except Exception as e:
            print("ChromaDB query error:", e)
            return []
            
        retrieved = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            
            for idx, doc in enumerate(docs):
                meta = metadatas[idx] or {}
                # Convert L2 distance to similarity score
                d = distances[idx]
                similarity = (1.0 / (1.0 + d)) * 100.0
                
                cap_id = meta.get("cap_id", ids[idx])
                domain = meta.get("domain", "General")
                cert = meta.get("certification", "N/A")
                year = meta.get("year_completed", "2025")
                val = meta.get("contract_value", "N/A")
                duration = meta.get("duration_months", "12")
                client = meta.get("client_type", "Target Client")
                
                cap_compat = {
                    "cap_id": cap_id,
                    "domain": domain,
                    "project_summary": doc,
                    "certification": cert,
                    "year_completed": int(year) if str(year).isdigit() else 2025,
                    "contract_value": val,
                    "duration_months": int(duration) if str(duration).isdigit() else 12,
                    "client_type": client
                }
                retrieved.append({
                    "score": round(similarity, 1),
                    "capability": cap_compat
                })
                
        return retrieved

if __name__ == "__main__":
    engine = RAGEngine()
    print("Testing local ChromaDB vector retrieval for 'ISO 27001':")
    matches = engine.retrieve_matches("ISO 27001 Information Security")
    for match in matches:
        print(f"[{match['score']}%] Cap ID: {match['capability']['cap_id']} - Summary: {match['capability']['project_summary'][:80]}...")
