# How to Build Your First RAG Pipeline Over Your Own PDF Documents

## Summary
1. A language model has never seen your documents, and it will still answer questions about them, because producing plausible text is what it does.

2. RAG changes the order of operations. You find the relevant pages yourself, then hand them over with the question attached.

3. Extracting text from a PDF is easy, and the text that comes out has no paragraphs, because a PDF stores lines at positions rather than structure.

4. That single fact breaks the chunking most tutorials show, since splitting on blank lines returns the whole page as one chunk.

5. Chunking on headings gives you sections that answer questions, and it takes about ten lines.

6. Keeping the page number beside each chunk is what lets an answer cite its source, and it costs nothing to carry.

7. Two instructions in the prompt do most of the work: use only this context, and say so when it does not contain the answer.

Ask a model about your own runbooks and it will answer. It sounds confident. It names commands. It cites procedures. None of it comes from your documents, because the model has never seen them.

You cannot prompt your way out of this. Producing plausible text is exactly what a language model does, and it has no way to know which parts it really knows.

RAG fixes it by changing the order. Find the relevant pages first. Hand them over with the question. Now the model answers from text you supplied rather than from memory. This post builds that over real PDF files, ending with answers that cite their page.

### What you should already have

This continues directly from the previous post How to Generate and Compare Text Embeddings With Ollama. If you followed it, you already have Ollama running and an embedding model pulled, which is everything the retrieval half needs.

#### If you are starting here, the setup is four commands:

```bash
sudo apt-get update && sudo apt-get install -y zstd python3 python3-venv
curl -fsSL https://ollama.com/install.sh | sh
curl http://localhost:11434/
ollama pull mxbai-embed-large
```

Ollama is running from that third command means the installer already started it. A connection refused means you need ollama serve & first.

Then the Python side, with one new package for reading PDFs:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install openai numpy pypdf fpdf2
```

#### Why RAG rather than a bigger model

Worth being clear about what this fixes, because it is not a quality problem.

A model is trained once, on text that existed before the training run. Your runbook from last Tuesday was not in it. Nor was your incident history, your architecture decisions, or the document somebody updated an hour ago.

So the gap is not cleverness. The information was never there. A larger model invents more fluently, which makes things worse rather than better.

| Approach | Answers from | Handles new documents |
|---|---|---|
| Ask the model directly | Training data | No |
| Fine-tune on your documents | Adjusted weights | Only by training again |
| RAG | Text you supply per question | Yes, immediat

That last row is why RAG became the default. A new document works the moment you index it. Remove one and it drops out of answers.

#### Make a PDF to practise on

You need a PDF before any of this runs. Use your own if you have one with headings. If not, this script writes the file every example below uses, so your output matches what you see here. It needs fpdf2, which the install above already covered.

```bash
from fpdf import FPDF

SECTIONS = [
    ("Restarting a stuck pod",
     "When a pod enters CrashLoopBackOff, Kubernetes is deliberately waiting "
     "longer between restarts. Delete the pod with kubectl delete pod and the "
     "controller recreates it within seconds. If it returns to the same state, "
     "the fault is in the container rather than the scheduler."),
    ("Rotating the database password",
     "Rotate the credential in the secret store first, then update the "
     "Kubernetes secret, then restart the deployment so pods reload it. Doing "
     "these in the wrong order leaves pods holding a credential that no longer works."),
    ("Certificate expiry on the edge",
     "A TLS handshake failure on the public endpoint usually means the "
     "certificate expired or the chain is incomplete. Browsers cache "
     "intermediates, so a page that loads in a browser can still fail from curl."),
    ("Memory limits and exit code 137",
     "Exit code 137 is 128 plus signal 9, which is kill. The kernel out of "
     "memory killer stopped the process. Raise the memory limit on the "
     "deployment or find the leak."),
]

pdf = FPDF()
pdf.add_page()
pdf.set_auto_page_break(True, margin=15)

for heading, body in SECTIONS:
    pdf.set_font("helvetica", "B", 13)
    pdf.multi_cell(0, 7, heading)
    pdf.ln(1)
    pdf.set_font("helvetica", "", 11)
    pdf.multi_cell(0, 6, body)
    pdf.ln(4)

pdf.output("runbook.pdf")
print("runbook.pdf written")
```

Four short sections about things that go wrong in a cluster. Small enough to read in full, and varied enough that retrieval has to actually choose between them rather than always returning the only option.

Swap in your own document once the pipeline works. Starting with this one means the numbers you see match the numbers here, so anything that differs is worth investigating rather than shrugging at.

#### Step 1: Get the text out of the PDF

```bash
from pypdf import PdfReader

reader = PdfReader("runbook.pdf")
print(f"{len(reader.pages)} pages")

text = reader.pages[0].extract_text()
print(text[:300])
```

```bash
python3 extract.py
```
```bash
1 pages
Restarting a stuck pod
When a pod enters CrashLoopBackOff, Kubernetes is deliberately
waiting longer between restarts. Delete the pod with kubectl
delete pod and the controller recreates it within seconds.
```

    <span style="color: green;">WHAT THIS TELLS YOU:</span>

The text came out, so this is a text based PDF. An empty string here means the file is scanned images and you need OCR before any of this applies.

That is the whole extraction step. pypdf is BSD licensed, needs no system packages, and handles text based PDFs well.

<span style="color: yellow;">WATCH OUT:</span>

The fastest PDF library, PyMuPDF, is AGPL licensed. Most tutorials use it without mentioning that. AGPL obliges you to release your source if you distribute the software or offer it over a network, unless you buy a commercial licence. For a weekend project that is fine. For anything you ship at work it is a decision your legal team should make rather than one you make by copying an import line. pypdf is BSD and pdfplumber is MIT, and both handle text based PDFs perfectly well, which is why this post uses one of them.

Two limits are worth knowing now rather than later. A scanned PDF is images of text, so extraction returns nothing and you need OCR first. And tables come out as a jumble of cells in reading order, so a table heavy document needs a library built for that.

#### Step 2: The chunking problem nobody warns you about

Here is where most tutorials quietly mislead you.

The standard advice is to split text into paragraphs on blank lines. Try that on PDF text and you get one enormous chunk containing the entire page.

```bash
python3 -c "
from pypdf import PdfReader
t = PdfReader('runbook.pdf').pages[0].extract_text()
print('blank lines:', t.count(chr(10) + chr(10)))
print('single newlines:', t.count(chr(10)))
"
```

blank lines: 0

single newlines: 14

<span style="color: green;">WHAT THIS TELLS YOU</span>

Not one blank line in the whole page. So a split on \\n\\n returns the entire page as a single chunk, which is why the usual paragraph splitting advice fails here.

There is a structural reason. A PDF does not store paragraphs. It stores characters at coordinates, and the library rebuilds lines from vertical positions. Where you see a paragraph break, the file has slightly more vertical space. That comes out as the same single newline as any other line ending.

So the blank line you are splitting on does not exist.

This matters more than it sounds. Chunk size decides retrieval quality. One chunk per page means every question retrieves that page, and the model gets four unrelated topics to work from.

#### Chunk on headings instead

Documents written for people usually have headings, and a heading reliably marks a new topic.

Detecting one is a guess rather than a parse. A heading is short, has few words, and does not end in a full stop.

```bash
def looks_like_heading(line):
    line = line.strip()
    return (bool(line)
            and len(line) < 60
            and len(line.split()) <= 8
            and not line.endswith((".", ":", ",")))
```

Then walk the lines, starting a new chunk each time a heading appears.

```bash
def chunk_pdf(path):
    chunks = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        heading, buffer = None, []
        for line in page.extract_text().splitlines():
            if looks_like_heading(line):
                if heading and buffer:
                    chunks.append({"page": page_number,
                                   "heading": heading,
                                   "text": " ".join(buffer)})
                heading, buffer = line.strip(), []
            elif line.strip():
                buffer.append(line.strip())
        if heading and buffer:
            chunks.append({"page": page_number,
                           "heading": heading,
                           "text": " ".join(buffer)})
    return chunks
```

```bash
python3 chunk.py
```

4 chunks from heading detection

  p1  [Restarting a stuck pod]           272 chars

  p1  [Rotating the database password]   216 chars

  p1  [Certificate expiry on the edge]   202 chars

  p1  [Memory limits and exit code 137]  162 chars

<span style="color: green;">WHAT THIS TELLS YOU</span>

Four sections instead of one page, each holding a single topic. That is what lets retrieval choose between them rather than returning everything.

Four sections rather than one page. Each holds one topic, which is what makes retrieval able to pick between them.

Notice the dictionary carries the page number beside the text. That costs nothing now, and it is what lets an answer cite its source later. Add it before you need it.

<span style="color: blue;">QUICK TIP</span>

Print your chunks before you embed anything. Every chunk should read like something that could answer a question on its own. A chunk that is one line of a table, or half a sentence, or four topics at once will retrieve badly no matter which model you use. Looking at the list takes a minute and catches the problem while it is still cheap. This is the single highest return check in the whole pipeline, and it needs no code beyond a loop and a print.

#### Step 3: Embed and retrieve

This part is the embeddings post, applied to chunks instead of sentences.

```bash
import numpy as np
from openai import OpenAI

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
```

One detail in that last line does real work. The heading is prepended to the text before embedding, so the section title becomes part of what the model sees. A heading is usually the most topic dense sentence in a section. Including it improves retrieval for the cost of one string join.

Retrieval is the same sort as before, now carrying the page number through.

```bash
def retrieve(question, top_k=2):
    q = embed(question)[0]
    scored = [(cosine(q, v), c) for v, c in zip(vectors, chunks)]
    return sorted(scored, key=lambda pair: pair[0], reverse=True)[:top_k]
```

```bash
python3 retrieve.py
```

Q: why did my pod get killed with 137
  +0.706  p1  Memory limits and exit code 137
  +0.612  p1  Restarting a stuck pod

Q: what order do I rotate credentials in
  +0.770  p1  Rotating the database password
  +0.419  p1  Restarting a stuck pod

Q: the site works in chrome but not from a script
  +0.442  p1  Certificate expiry on the edge
  +0.364  p1  Memory limits and exit code 137

<span style="color: green;">WHAT THIS TELLS YOU</span>

Each question finds its section. The third one never says certificate, TLS or expiry, and still lands on the right one, which is the reason for embedding rather than grepping.

Look at the third question in that output. It never mentions certificates, TLS, or expiry. The right section comes back anyway. That is the whole reason for embedding rather than grepping.

#### Practise the retrieval layer properly

Chunking and search strategy decide more of your result than the model does, which is exactly what this post keeps running into. The Fundamentals of RAG course covers ingestion, chunking, keyword against semantic search, vector databases, and building a complete pipeline.

#### Step 4: Answer the question

Now the generation half. Retrieval found the text, and the model turns it into an answer.

```bash
chat = OpenAI(base_url=CHAT_BASE_URL, api_key=CHAT_API_KEY)

def answer(question, top_k=2):
    hits = retrieve(question, top_k)
    context = "\n\n".join(
        f"[page {c['page']}, {c['heading']}]\n{c['text']}" for _, c in hits
    )
    prompt = (
        "Answer using only the context below. Cite the page number for each fact. "
        "If the context does not contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    reply = chat.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return reply.choices[0].message.content
```

```bash
python3 rag.py
```

Q: why did my pod get killed with exit code 137
  +0.720  page 1  Memory limits and exit code 137
  +0.687  page 1  Restarting a stuck pod

According to the context, exit code 137 means the kernel out of
memory killer stopped the process. [page 1] The exit code 137 is
composed of 128 plus signal 9, which is the kill signal.

To resolve this, raise the memory limit on the deployment or find
and fix a memory leak. [page 1]

<span style="color: green;">WHAT THIS TELLS YOU</span>

The answer cites its page, and every fact in it came from the retrieved section rather than from training data. That is the difference between grounded and plausible.

Three things in that function decide whether the whole pipeline is trustworthy.

The context puts the page number and heading as a label above each chunk. That makes citation possible, because the model can only cite what it can see.

Telling it to use only the context stops the model blending your documents with its training data. That blend is what produces answers which are half right and impossible to check.

And asking it to say so when the answer is absent is the line most people leave out. Without it, a question your documents cannot answer still gets a confident reply, assembled from whatever happened to be closest.

<span style="color: lightblue;">IN THE WILD</span>

Ask your pipeline something your documents definitely do not cover, and watch what happens. Retrieval always returns its nearest neighbours, because similarity search has no idea of no result. So the model receives two irrelevant chunks and a question. Without that final instruction it will answer anyway, using the chunks as loose inspiration, and the result reads exactly like a real answer. With the instruction it says the context does not cover it. That one sentence is the difference between a demo and something you would let a colleague use.

#### What the pipeline looks like end to end

Five steps, and only one of them involves a language model.

| STEP     | WHAT HAPPENS                               | RUNS WHERE            |
|----------|--------------------------------------------|-----------------------|
| Extract  | PDF becomes text, one string per page      | Local, pypdf          |
| Chunk    | Text becomes sections with page numbers    | Local, plain Python   |
| Embed    | Each section becomes a vector              | Local, Ollama         |
| Retrieve | Question becomes a vector, closest sections win | Local, numpy      |
| Generate | Sections plus question become an answer    | A chat model          |

Four of the five are ordinary code on your machine. Worth noticing, because RAG gets discussed as an AI technique and most of it is text processing, arithmetic and a sort.

It also tells you where to look when answers are poor. If the wrong sections come back, the fault sits above the generation step, and no amount of prompt work will help.

#### The complete pipeline

Everything above in one file, about ninety lines.

python

```bash
import os
import numpy as np
from openai import OpenAI
from pypdf import PdfReader

EMBED_BASE_URL = "http://localhost:11434/v1"
EMBED_MODEL = "mxbai-embed-large"
CHAT_BASE_URL = os.environ.get("CHAT_BASE_URL", "http://localhost:11434/v1")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.2")
CHAT_API_KEY = os.environ.get("CHAT_API_KEY", "ollama")

embed_client = OpenAI(base_url=EMBED_BASE_URL, api_key="ollama")
chat_client = OpenAI(base_url=CHAT_BASE_URL, api_key=CHAT_API_KEY)


def looks_like_heading(line):
    line = line.strip()
    return (bool(line)
            and len(line) < 60
            and len(line.split()) <= 8
            and not line.endswith((".", ":", ",")))


def chunk_pdf(path):
    chunks = []
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        heading, buffer = None, []
        for line in page.extract_text().splitlines():
            if looks_like_heading(line):
                if heading and buffer:
                    chunks.append({"page": page_number, "heading": heading,
                                   "text": " ".join(buffer)})
                heading, buffer = line.strip(), []
            elif line.strip():
                buffer.append(line.strip())
        if heading and buffer:
            chunks.append({"page": page_number, "heading": heading,
                           "text": " ".join(buffer)})
    return chunks


def embed(texts):
    if isinstance(texts, str):
        texts = [texts]
    response = embed_client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in response.data]


def cosine(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class Index:
    def __init__(self, path):
        self.chunks = chunk_pdf(path)
        self.vectors = embed([f"{c['heading']}. {c['text']}" for c in self.chunks])

    def retrieve(self, question, top_k=2):
        q = embed(question)[0]
        scored = [(cosine(q, v), c) for v, c in zip(self.vectors, self.chunks)]
        return sorted(scored, key=lambda pair: pair[0], reverse=True)[:top_k]

    def answer(self, question, top_k=2):
        hits = self.retrieve(question, top_k)
        context = "\n\n".join(
            f"[page {c['page']}, {c['heading']}]\n{c['text']}" for _, c in hits
        )
        prompt = (
            "Answer using only the context below. Cite the page number for each fact. "
            "If the context does not contain the answer, say so.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}"
        )
        reply = chat_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return reply.choices[0].message.content


if __name__ == "__main__":
    index = Index("runbook.pdf")
    print(f"{len(index.chunks)} chunks indexed")
    for question in ["why did my pod get killed with exit code 137",
                     "what is the capital of France"]:
        print(f"\nQ: {question}")
        for score, chunk in index.retrieve(question):
            print(f"  {score:+.3f}  page {chunk['page']}  {chunk['heading']}")
        print(f"\n{index.answer(question)}\n")
```

The Index class exists for one reason. Chunking and embedding happen once, when you build it. Every question after that is arithmetic against vectors already in memory. Doing that work per question would be slower and cost more for no gain.

### Practise on a running stack

Reading a pipeline is not the same as watching one behave when the documents are messy. The KodeKloud playgrounds give you a Linux machine where Ollama, Python and your own PDFs can sit together with nothing to install locally and nothing to clean up.

### Where this pipeline will disappoint you

Four honest limits, so you meet them knowing rather than guessing.

Scanned documents return nothing. They are images, so there is no text layer to extract. You need OCR before any of this applies.

Tables come out scrambled. Extraction gives you cells in reading order, which loses the grid. A document that is mostly tables needs a library built for tables.

Heading detection is a guess. It works on documents with real headings and fails on a wall of prose. When it fails, you fall back to fixed size chunks with overlap, which is its own topic.

Everything is in memory. Fine for a few hundred chunks. Past a few thousand you want a real store, mostly so you can filter by document or date while searching.

None of those are reasons to avoid starting. They are things to watch for, and every one shows up clearly if you print your chunks.

### Try this on your own PDFs

An afternoon, and it runs on documents you already have.

Take one real PDF with headings, like a runbook or a policy document. Run the extraction first and read what comes out. That tells you straight away whether the file is text or scanned images.

Print your chunks before embedding anything. Check each one reads like something that could answer a question. Adjust the heading rule if your document uses a different style.

Now write ten questions you would genuinely ask that document, and note which section should answer each. Run retrieval and count how often the right section lands in the top two.

That number is your pipeline quality. Generation cannot fix a miss at this stage, so measuring here tells you where you actually stand.

Then ask something the document does not cover, and confirm the answer says so. If it invents instead, the instruction in your prompt is not working. Fix that before anyone else uses it.

### What you should be able to answer now

Why does the model need your documents supplied per question? Because it was trained before they existed and has no way to know what it does not know.

Why does splitting on blank lines fail on PDF text? Because a PDF stores lines at positions rather than paragraphs, so the blank line you are splitting on was never there.

What makes citation possible? Carrying the page number alongside each chunk from the moment you create it, and putting it in the context so the model can see it.

When answers are poor, where do you look first? At what retrieval returned. If the wrong sections came back, the generation step never had a chance.

The pipeline in this post is five steps and four of them are ordinary Python. The interesting decisions are all in the middle, where a document becomes chunks, which is why the next thing worth learning is how to chunk documents properly.

### Ready to Build the Rest of the Pipeline?

A working pipeline is the start, and retrieval quality is what makes it useful. The Fundamentals of RAG course covers chunking, search strategy, and vector databases end to end. The Vector Database for GenAI course goes deeper on storage once your chunks outgrow a Python list. And the AI Learning Path sequences both alongside agents and MCP. Start with ten questions about one of your own documents.