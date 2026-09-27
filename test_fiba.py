import requests

GAME_ID = "2913911"
LEAGUE = "UBBF"

session = requests.Session()

html_url = f"https://fibalivestats.dcd.shared.geniussports.com/u/{LEAGUE}/{GAME_ID}/bs.html"
session.get(html_url, headers={"User-Agent": "Mozilla/5.0"})

json_url = f"https://fibalivestats.dcd.shared.geniussports.com/data/{GAME_ID}/data.json"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": html_url,
    "Accept": "application/json",
}
r = session.get(json_url, headers=headers)

print(r.status_code)
print(r.text[:1000])