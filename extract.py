from pypdf import PdfReader

reader = PdfReader("runbook.pdf")
print(f"{len(reader.pages)} pages")

text = reader.pages[0].extract_text()
print(text[:300])
