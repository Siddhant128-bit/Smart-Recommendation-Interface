import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import pickle
import os
import chatbot_engine as cbe

# Load the embedder once
embedder = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding(text):
    emb = embedder.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return emb.astype("float32")

def manage_faiss_index(corpus_list=None, flag="save", index_file="movies.index", meta_file="movies.pkl"):
    """
    Manage FAISS index: save, load, or append
    corpus_list: list of text corpus (required if flag='save')
    flag: 'save' or 'load'
    index_file: FAISS index file
    meta_file: metadata pickle file
    """

    if flag == "save":
        if corpus_list is None:
            raise ValueError("corpus_list must be provided when saving index.")

        # Generate embeddings
        embeddings = np.array([get_embedding(c) for c in corpus_list]).astype("float32")
        dim = embeddings.shape[1]

        if os.path.exists(index_file) and os.path.exists(meta_file):
            # Load existing index and metadata
            index = faiss.read_index(index_file)
            with open(meta_file, "rb") as f:
                old_corpus = pickle.load(f)

            # Prepend new embeddings and metadata
            combined_embeddings = np.vstack((embeddings, index.reconstruct_n(0, index.ntotal)))
            index = faiss.IndexFlatL2(dim)
            index.add(combined_embeddings)

            combined_corpus = corpus_list + old_corpus

            # Save combined metadata
            with open(meta_file, "wb") as f:
                pickle.dump(combined_corpus, f)
        else:
            # No existing index: create new
            index = faiss.IndexFlatL2(dim)
            index.add(embeddings)

            with open(meta_file, "wb") as f:
                pickle.dump(corpus_list, f)

        # Save FAISS index
        faiss.write_index(index, index_file)
        return index, combined_corpus if 'combined_corpus' in locals() else corpus_list

    elif flag == "load":
        if not os.path.exists(index_file) or not os.path.exists(meta_file):
            raise FileNotFoundError("No saved FAISS index/metadata found. Run with flag='save' first.")

        # Load FAISS index
        index = faiss.read_index(index_file)

        # Load metadata
        with open(meta_file, "rb") as f:
            corpus_list = pickle.load(f)

        return index, corpus_list

    else:
        raise ValueError("flag must be 'save' or 'load'")

def recommend(query, top_n=2):
    index,corpus_list=manage_faiss_index(flag="load")
    query_text=cbe.ask_gemini_similarity(query)
    query_emb = get_embedding(query_text).reshape(1, -1)
    distances, indices = index.search(query_emb, top_n)
    results = []
    for idx, dist in zip(indices[0], distances[0]):
        title = corpus_list[idx].split("\n")[0]  # first line = movie title
        results.append((title, dist))
    return results

if __name__=='__main__':
    query = "Batman"
    print(recommend(query,top_n=15))