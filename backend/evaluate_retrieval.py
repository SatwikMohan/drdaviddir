"""Run labelled retrieval evaluation without a conversational generation call."""
import argparse
import json
from pathlib import Path
from services.retrieval import active_store, retrieve_from_store

def load_cases(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]

def evaluate(path, top_k=5):
    cases=load_cases(path)
    if not cases: raise ValueError("No evaluation cases")
    store=active_store()
    scores=[]
    for case in cases:
        docs=retrieve_from_store(store,case["question"],top_k)
        sources=[d.metadata.get("source","") for d in docs]
        expected=case["expected_sources"]
        scores.append(sum(any(name.casefold() in source.casefold() for source in sources) for name in expected)/len(expected))
    result={"cases":len(cases),"recall_at_k":sum(scores)/len(scores),"top_k":top_k}
    print(json.dumps(result));return result

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("cases",type=Path);parser.add_argument("--top-k",type=int,default=5)
    args=parser.parse_args();evaluate(args.cases,args.top_k)
