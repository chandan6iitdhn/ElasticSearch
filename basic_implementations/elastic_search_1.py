documents = {
    "D1": "Diabetes treatment research",
    "D2": "Heart disease research",
    "D3": "Diabetes medication trial",
    "D4": "Heart treatment research",
    "D5": "Diabetes heart research"
}

inverted_index = {}
for doc_id, text in documents.items():
    tokens = text.lower().split()
    for token in tokens:
        if token not in inverted_index:
            inverted_index[token] = set()
        inverted_index[token].add(doc_id)

# print(inverted_index)

query = "Diabetes"
doc_ids = set()
tokens = query.lower().split()
for token in tokens:
    if token in inverted_index:
        doc_ids.update(inverted_index[token])

print(doc_ids)