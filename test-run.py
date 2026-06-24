from ddgs import DDGS
from websitescorecard.discovery import hostnames_from_results

query = "Agriculture and Agrarian Insurance Board Sri Lanka"
with DDGS() as ddgs:
    raw = list(ddgs.text(query, max_results=30))

print([r.get("href") for r in raw])
print("unfiltered:", hostnames_from_results(raw))
print("gov.lk only:", hostnames_from_results(raw, suffixes=["gov.lk", "gov"]))