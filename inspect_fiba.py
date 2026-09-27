import requests, json

GAME_ID = "2913911"
LEAGUE = "UBBF"

s = requests.Session()
html = f"https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE}/{GAME_ID}/bs.html"
s.get(html, headers={"User-Agent": "Mozilla/5.0"})
r = s.get(
    f"https://fibalivestats.dcd.shared.geniussports.com/data/{GAME_ID}/data.json",
    headers={"User-Agent": "Mozilla/5.0", "Referer": html, "Accept": "application/json"},
)
data = r.json()

print("Top-level keys:", list(data.keys()))
print()
print("tm.1 keys:", list(data["tm"]["1"].keys()))
print()
print("tm.1 box totals:")
for k, v in data["tm"]["1"].items():
    if k.startswith("tot_"):
        print(f"  {k}: {v}")

# Peek at play-by-play if present
for candidate in ["pbp", "playbyplay", "actions", "events"]:
    if candidate in data:
        print(f"\n'{candidate}' exists with {len(data[candidate])} entries")
        print("First entry:", json.dumps(data[candidate][0], indent=2)[:800])
        break
else:
    print("\nNo obvious PBP key — check other top-level keys above.")