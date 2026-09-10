import os
from openai import OpenAI
from retrieve import retrieve

CHAT_BASE_URL = os.environ.get("CHAT_BASE_URL", "http://localhost:11434/v1")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.2")
CHAT_API_KEY = os.environ.get("CHAT_API_KEY", "ollama")

chat = OpenAI(base_url=CHAT_BASE_URL, api_key=CHAT_API_KEY)

def answer(question, top_k=2):
    hits = retrieve(question, top_k)
    context = "\n\n".join(
        f"[page {c['page']}, {c['heading']}]\n{c['text']}" for _, c in hits
    )
    prompt = (
        "Answer using only the context below. Cite the page number for each fact (e.g. [page 1]). "
        "If the context does not contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    reply = chat.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return reply.choices[0].message.content

if __name__ == "__main__":
    question = "why did my pod get killed with exit code 137"
    print(f"Q: {question}")
    for score, chunk in retrieve(question):
        print(f"  {score:+.3f}  page {chunk['page']}  {chunk['heading']}")
    print()
    print(answer(question))