import json
from pypdf import PdfReader

def looks_like_heading(line):
    line = line.strip()
    return (bool(line)
            and len(line) < 60
            and len(line.split()) <= 8
            and not line.endswith((".", ":", ",")))

def chunk_pdf(path) -> list[dict]:
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

if __name__ == "__main__":
    chunks = chunk_pdf("runbook.pdf")
    print(json.dumps(chunks, indent=2))