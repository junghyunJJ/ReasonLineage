"""A small hand-written run log and a PubMed reply, shared by the J2, PMID, and CLI tests."""

import json


def entry(item, pmids):
    return {"item": item, "promisingness": 0.5, "confidence": 0.5, "pmids": pmids}


EVENTS = [
    {"event": "candidate.created", "id": "c001", "author": "opus", "operator": "seed", "parents": [], "generation": 0,
     "answer": {"answer": "metformin reverses fibrosis", "ranking": [entry("metformin", ["29967351"]), entry("imatinib", [])]}},
    {"event": "judge.scored", "candidate": "c001", "judge": "gpt", "author": "opus", "critique": ["cite a trial"]},
    {"event": "candidate.created", "id": "c005", "author": "opus", "operator": "mutation", "parents": ["c001"], "generation": 1,
     "answer": {"answer": "metformin and imatinib",
                "ranking": [entry("metformin", ["29967351", "20866024"]), entry("imatinib", ["11111111"])]}},
]

EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
 <PubmedArticle><MedlineCitation><PMID>29967351</PMID><Article>
  <ArticleTitle>Metformin reverses established lung fibrosis in a bleomycin model.</ArticleTitle>
  <Abstract><AbstractText>AMPK activation ...</AbstractText></Abstract></Article>
  <MeshHeadingList><MeshHeading><DescriptorName>Pulmonary Fibrosis</DescriptorName></MeshHeading></MeshHeadingList>
 </MedlineCitation></PubmedArticle>
 <PubmedArticle><MedlineCitation><PMID>20866024</PMID><Article>
  <ArticleTitle>Legal briefing: conscience clauses and conscientious refusal.</ArticleTitle></Article>
 </MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


def write_events(run_dir):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in EVENTS))
