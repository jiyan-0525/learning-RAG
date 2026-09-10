import numpy as np
from openai import OpenAI
from chunk import chunk_pdf

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "mxbai-embed-large"

def embed(texts):
    if isinstance(texts, str):
        texts = [texts]
    return [d.embedding for d in client.embeddings.create(model=MODEL, input=texts).data]

def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

chunks = chunk_pdf("runbook.pdf")
vectors = embed([f"{c['heading']}. {c['text']}" for c in chunks])

def retrieve(question, top_k=2):
    q = embed(question)[0]
    scored = [(cosine(q, v), c) for v, c in zip(vectors, chunks)]
    return sorted(scored, key=lambda pair: pair[0], reverse=True)[:top_k]

if __name__ == "__main__":
    questions = [
        "why did my pod get killed with 137",
        "what order do I rotate credentials in",
        "the site works in chrome but not from a script",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        for score, chunk in retrieve(question):
            print(f"  {score:+.3f}  p{chunk['page']}  {chunk['heading']}")