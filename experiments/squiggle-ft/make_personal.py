"""Candidates for the personal family: real first prompts from OpenAssistant oasst2 (Apache-2.0) and Dolly-15k
(CC BY-SA 3.0), keyword-filtered for advice / empathy about family, partners, friends, work and feelings.

  python make_personal.py > candidates.txt

The kept requests were then picked by hand from these candidates (no facts to look up, no crisis, medical, legal or
sexual topics, no writing tasks) into data/sources/personal.json, with their source ids; `ask` marks the requests where
a good reply needs one more fact from the person (who the gift is for, what happened).
"""
import gzip, json, re
from huggingface_hub import hf_hub_download

PEOPLE = (r"(mom|mum|mother|dad|father|parents?|sister|brother|family|wife|husband|girlfriend|boyfriend|partner|spouse|"
          r"friends?|roommates?|flatmates?|coworkers?|co-workers?|colleagues?|boss|manager|neighbou?rs?|kids?|son|daughter|in-laws?|ex)")
FEEL = (r"(lonely|sad|stressed|stress|burn(ed|t)? ?out|overwhelmed|exhausted|motivat\w*|procrastinat\w*|argument|angry|upset|"
        r"jealous|nervous|anxious|insecure|guilty|frustrat\w*|birthday|gift|anniversary|nag\w*|chores|dishes|break ?up|heartbr\w*)")
ASK = r"(\?|how (do|can|should|could) i|what (should|can|do) i|any (advice|tips|suggestions)|advice|should i|help me|tips|ideas)"
OFF = (r"\b(code|python|javascript|program|script|translate|summari[sz]e|poem|story|essay|song|lyrics|joke|pretend|act as|"
       r"imagine|role ?play|linux|windows|software|app|algorithm|recipe|half my age|how old|password|hack\w*|suicid\w*|kill|"
       r"self[- ]harm|abuse\w*|rape|drugs?|overdos\w*|sex\w*|porn\w*|weapon|gun|police|lawyer|legal|court|doctor|medicat\w*|"
       r"diagnos\w*|symptom\w*|cancer|died|death|weather|e-?mail|letter|speech|write)\b")


def personal(text):
    low = text.lower()
    return (re.search(r"\b(i|my|me|i'm|im)\b", low) and re.search(ASK, low) and not re.search(OFF, low)
            and (re.search(r"\bmy (\w+ )?" + PEOPLE + r"\b", low) or re.search(FEEL, low)))


def main():
    p = hf_hub_download("OpenAssistant/oasst2", "2023-11-05_oasst2_prompts.messages.jsonl.gz", repo_type="dataset")
    for line in gzip.open(p, "rt"):
        r = json.loads(line)
        t = (r.get("text") or "").strip()
        d = r.get("detoxify") or {}
        if (r.get("lang") == "en" and not r.get("parent_id") and not r.get("deleted") and not r.get("synthetic")
                and 25 <= len(t) <= 420 and "\n\n" not in t and "http" not in t and (d.get("toxicity") or 0) <= 0.3
                and (d.get("sexual_explicit") or 0) <= 0.1 and personal(t)):
            print(f"oasst2:{r['message_id']}\t{t}")
    p = hf_hub_download("databricks/databricks-dolly-15k", "databricks-dolly-15k.jsonl", repo_type="dataset")
    for i, line in enumerate(open(p)):
        r = json.loads(line)
        t = r["instruction"].strip()
        if not r["context"].strip() and r["category"] in ("brainstorming", "open_qa", "general_qa", "creative_writing") and 20 <= len(t) <= 400 and personal(t):
            print(f"dolly15k:{i}\t{t}")


if __name__ == "__main__":
    main()
