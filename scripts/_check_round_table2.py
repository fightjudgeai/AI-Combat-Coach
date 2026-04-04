"""Check ALL tables and divs with fight stats from ufcstats."""
import asyncio, httpx
from bs4 import BeautifulSoup

FIGHT_URL = "http://ufcstats.com/fight-details/85e94a6c071fd9fa"  # Adesanya vs Pyfer

async def main():
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as client:
        r = await client.get(FIGHT_URL)

    print(f"Status: {r.status_code}, Content-Length: {len(r.text)}")
    soup = BeautifulSoup(r.text, "html.parser")

    # All tables
    tables = soup.find_all("table")
    print(f"\nAll <table> elements: {len(tables)}")
    for i, t in enumerate(tables[:5]):
        cls = t.get("class", [])
        rows = t.find_all("tr")
        print(f"  table {i}: class={cls}, rows={len(rows)}")
        for j, row in enumerate(rows[:3]):
            cols = [td.get_text(" ", strip=True)[:30] for td in row.find_all(["td", "th"])]
            if cols:
                print(f"    row {j}: {cols[:8]}")

    # Check if page has JS-rendered content  
    print("\n--- Key text markers ---")
    for marker in ["b-fight-details__table", "Sig. Str.", "Takedowns", "b-flag-img"]:
        count = len(soup.find_all(class_=lambda c: c and marker in c))
        direct = marker in r.text
        print(f"  {marker!r}: class_matches={count} in_html={direct}")

asyncio.run(main())
