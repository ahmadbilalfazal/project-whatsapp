import os
import faiss
import numpy as np
from app import db
from app.models import Chunk

INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'faiss.index')


class VectorStore:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.dim = None
        self.index = None
        self._load_index()

    def _ensure_model(self):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            self.dim = self.model.get_sentence_embedding_dimension()
            if self.index is None:
                self._load_index()

    def _load_index(self):
        # Load an existing FAISS index if available; otherwise defer creation until we know the embedding dimension.
        if os.path.exists(INDEX_PATH):
            try:
                self.index = faiss.read_index(INDEX_PATH)
            except Exception:
                self.index = None
        else:
            self.index = None

    def _ensure_index(self):
        if self.index is None:
            self._ensure_model()
            self.index = faiss.IndexFlatL2(self.dim)

    def save(self):
        if self.index is None:
            return
        faiss.write_index(self.index, INDEX_PATH)

    def add(self, texts, metadatas):
        self._ensure_model()
        self._ensure_index()
        embs = self.model.encode(texts, convert_to_numpy=True)
        if embs.ndim == 1:
            embs = np.expand_dims(embs, axis=0)
        start_id = int(self.index.ntotal)
        self.index.add(embs.astype('float32'))
        self.save()
        # persist metadata mapping in DB
        for i, m in enumerate(metadatas):
            ch = Chunk(
                business_id=m.get('business_id'),
                doc_id=m.get('doc_id'),
                page=m.get('page'),
                text=m.get('text'),
                vector_id=start_id + i,
            )
            db.session.add(ch)
        db.session.commit()

    def embed(self, texts):
        self._ensure_model()
        return self.model.encode(texts, convert_to_numpy=True)

    def search(self, query, top_k=3, business_id=None):
        self._ensure_model()
        if self.index is None:
            self._load_index()
        if self.index is None:
            return []
        q_emb = self.embed([query]).astype('float32')
        if self.index.ntotal == 0:
            return []
        search_k = top_k * 5 if business_id is not None else top_k
        D, I = self.index.search(q_emb, search_k)
        # convert distances to similarity-like scores
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            # similarity proxy
            score = 1.0 / (1.0 + float(dist))
            chunk = Chunk.query.filter_by(vector_id=int(idx)).first()
            if chunk and (business_id is None or chunk.business_id == business_id):
                results.append({'chunk': chunk, 'score': score})
            if len(results) >= top_k:
                break
        return results
