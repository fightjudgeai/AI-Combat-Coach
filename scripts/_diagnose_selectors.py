"""Diagnose and fix ufcstats.com CSS selectors for winner/method parsing."""
import asyncio, httpx
from bs4 import BeautifulSoup

FIGHT_URL = "http://ufcstats.com/fight-details/85e94a6c071fd9fa"  # Adesanya vs Pyfer

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(FIGHT_URL)
        soup = BeautifulSoup(r.text, "html.parser")

    # Try different selectors to find winner
    print("=== WINNER SELECTORS ===")
    # Method 1: original
    el = soup.select_one('.b-fight-details__person_status_won')
    print(f"  .b-fight-details__person_status_won: {el}")

    # Method 2: check all person elements
    persons = soup.select('.b-fight-details__person')
    print(f"\n  Person elements ({len(persons)}):")
    for p in persons[:2]:
        status = p.select_one('.b-fight-details__person-status')
        name = p.select_one('.b-fight-details__person-name')
        print(f"    status={status.text.strip() if status else None!r} name={name.text.strip() if name else None!r}")

    # Method 3: check for 'W' indicator
    status_els = soup.select('.b-fight-details__person-status')
    print(f"\n  All status elements: {[e.text.strip() for e in status_els]}")

    # Check all class names near person info
    print("\n  Classes near person divs:")
    for el in soup.select('[class*="person"]')[:8]:
        print(f"    class={el.get('class')} text={el.text.strip()[:50]!r}")

    print("\n=== METHOD SELECTORS ===")
    # Method 1: original
    text_items = soup.select('.b-fight-details__text-item')
    print(f"\n  .b-fight-details__text-item ({len(text_items)} items):")
    for item in text_items[:10]:
        print(f"    {item.text.strip()[:80]!r}")

    # Method 2: check text content items
    content_items = soup.select('.b-fight-details__content')
    print(f"\n  .b-fight-details__content ({len(content_items)}):")
    for item in content_items[:3]:
        print(f"    {item.text.strip()[:120]!r}")

    # Check all divs with fight-details class
    print("\n  Divs containing 'Method':")
    for el in soup.find_all(text=lambda t: t and 'Method' in t):
        print(f"    {el.strip()[:80]!r} -- parent: {el.parent.get('class')}")

    print("\n=== ROUNDS SCHEDULED ===")
    for el in soup.find_all(text=lambda t: t and 'Time format' in t):
        print(f"  text={el.strip()!r} parent_class={el.parent.get('class')}")

asyncio.run(main())
