"""Check actual round table HTML structure from ufcstats."""
import asyncio, httpx
from bs4 import BeautifulSoup

FIGHT_URL = "http://ufcstats.com/fight-details/85e94a6c071fd9fa"  # Adesanya vs Pyfer

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(FIGHT_URL)

    soup = BeautifulSoup(r.text, "html.parser")

    tables = soup.select("table.b-fight-details__table")
    print(f"Found {len(tables)} tables")

    for i, table in enumerate(tables[:2]):
        print(f"\n=== TABLE {i} ===")
        headers = table.select("thead th, thead td")
        if headers:
            header_text = [h.get_text(strip=True) for h in headers]
            print(f"Headers ({len(headers)}): {header_text}")
        else:
            headers = table.select("tr:first-child th, tr:first-child td")
            print(f"First row ({len(headers)}): {[h.get_text(strip=True) for h in headers]}")

        rows = table.select("tbody tr")
        print(f"Body rows: {len(rows)}")
        for j, row in enumerate(rows[:4]):
            cols = [td.get_text(strip=True) for td in row.select("td")]
            print(f"  row {j}: {cols[:12]}")

asyncio.run(main())
