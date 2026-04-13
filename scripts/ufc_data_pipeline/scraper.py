import httpx
import asyncio
from bs4 import BeautifulSoup
import json
import time
import logging
from pathlib import Path

log = logging.getLogger(__name__)

BASE_URL = "http://ufcstats.com"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # AI-Combat-Coach/
CACHE_DIR = _REPO_ROOT / "data" / "ufc_raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> httpx.Response:
    """GET with exponential-backoff retry on transient errors (5xx, timeout, network)."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await client.get(url)
            if resp.status_code < 500:
                return resp
            log.warning("HTTP %d for %s (attempt %d/%d)", resp.status_code, url, attempt + 1, max_retries)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            log.warning("Request error for %s (attempt %d/%d): %s", url, attempt + 1, max_retries, exc)
            last_exc = exc
        wait = base_delay * (2 ** attempt)
        await asyncio.sleep(wait)
    if last_exc:
        raise last_exc
    raise httpx.HTTPStatusError(f"Server error after {max_retries} retries", request=None, response=None)


class UFCStatsScraper:
    """
    Pulls event list → fight list → round-level stats
    for every UFC fight on ufcstats.com.
    Respects rate limits. Caches locally to avoid re-pulling.
    """

    def __init__(self, delay_seconds: float = 1.5):
        self.delay = delay_seconds
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    async def get_all_events(self) -> list[dict]:
        """Pull complete event list from ufcstats.com"""
        cache_path = CACHE_DIR / "events.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text())

        url = f"{BASE_URL}/statistics/events/completed?page=all"
        resp = await _get_with_retry(self.client, url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        events = []
        for row in soup.select('tr.b-statistics__table-row'):
            link = row.select_one('a.b-link')
            if link:
                date_col = row.select_one('.b-statistics__table-col_style_big-total')
                events.append({
                    'name': link.text.strip(),
                    'url': link['href'],
                    'date': date_col.text.strip() if date_col else None,
                })

        cache_path.write_text(json.dumps(events, indent=2))
        print(f"Pulled {len(events)} events")
        return events

    async def get_fights_for_event(self, event_url: str) -> list[dict]:
        """Pull all fights for a single event"""
        cache_file = CACHE_DIR / f"event_{event_url.split('/')[-1]}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        resp = await _get_with_retry(self.client, event_url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        fights = []
        for row in soup.select('tr.b-fight-details__table-row[data-link]'):
            def _cell_text(selector: str) -> str:
                el = row.select_one(selector)
                return el.text.strip() if el else ''

            fights.append({
                'url': row['data-link'],
                'fighters': [f.text.strip() for f in row.select('.b-link_style_black')[:2]],
                'result': _cell_text('.b-fight-details__table-col_type'),
                'method': _cell_text('.b-fight-details__table-col_method'),
                'round': _cell_text('.b-fight-details__table-col_round'),
                'time': _cell_text('.b-fight-details__table-col_time'),
                'weight_class': _cell_text('.b-fight-details__table-col_weight'),
            })

        cache_file.write_text(json.dumps(fights, indent=2))
        await asyncio.sleep(self.delay)
        return fights

    async def get_round_stats(self, fight_url: str) -> dict:
        """
        Pull round-by-round stats for a single fight.
        Returns: { fighter_a: [{round, SL, SA, KD, TD_F, TA_F, CTRL, sub_att}],
                   fighter_b: [...], outcome: {...} }
        """
        cache_file = CACHE_DIR / f"fight_{fight_url.split('/')[-1]}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        resp = await _get_with_retry(self.client, fight_url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        result = {
            'fight_url': fight_url,
            'fighter_a_name': None,
            'fighter_b_name': None,
            'winner': None,
            'method': None,
            'finish_round': None,
            'finish_time': None,
            'rounds_scheduled': None,
            'rounds': []  # list of per-round dicts for each fighter
        }

        # Fighter names
        names = soup.select('.b-fight-details__person-name')
        if len(names) >= 2:
            result['fighter_a_name'] = names[0].text.strip()
            result['fighter_b_name'] = names[1].text.strip()

        # Winner
        winner_el = soup.select_one('.b-fight-details__person_status_won')
        if winner_el:
            name_el = winner_el.find_next('.b-fight-details__person-name')
            if name_el:
                result['winner'] = name_el.text.strip()

        # Method, round, time
        method_els = soup.select('.b-fight-details__text-item')
        for el in method_els:
            text = el.text.strip()
            if 'Method:' in text:
                result['method'] = text.replace('Method:', '').strip()
            elif 'Round:' in text:
                try:
                    result['finish_round'] = int(text.replace('Round:', '').strip())
                except ValueError:
                    pass
            elif 'Time:' in text:
                result['finish_time'] = text.replace('Time:', '').strip()

        # Round-level stats tables
        # ufcstats has two tables per fight:
        # Table 1: Totals (per fighter, per round)
        # Table 2: Significant strike breakdown by position/type
        # We use Table 1 for RPS inputs
        round_tables = soup.select('table.b-fight-details__table')
        if round_tables:
            result['rounds'] = self._parse_round_table(round_tables[0])

        cache_file.write_text(json.dumps(result, indent=2))
        await asyncio.sleep(self.delay)
        return result

    def _parse_round_table(self, table) -> list[dict]:
        """Parse per-round stats table into structured dicts"""
        rounds = []
        rows = table.select('tbody tr')

        # ufcstats shows fighter A row then fighter B row per round
        for i in range(0, len(rows) - 1, 2):
            row_a = rows[i]
            row_b = rows[i + 1] if i + 1 < len(rows) else None

            if not row_b:
                continue

            cols_a = [c.text.strip() for c in row_a.select('td')]
            cols_b = [c.text.strip() for c in row_b.select('td')]

            # ufcstats column order in round table:
            # Round | Fighter | KD | Sig.Str. | Sig.Str.% | Total Str. | TD | TD% | Sub.Att | Rev. | Ctrl
            def parse_of(val: str) -> tuple[int, int]:
                """Parse '14 of 32' → (14, 32)"""
                parts = val.split(' of ')
                if len(parts) == 2:
                    try:
                        return int(parts[0]), int(parts[1])
                    except ValueError:
                        pass
                return 0, 0

            def parse_ctrl(val: str) -> int:
                """Parse '2:34' → 154 seconds"""
                parts = val.split(':')
                if len(parts) == 2:
                    try:
                        return int(parts[0]) * 60 + int(parts[1])
                    except ValueError:
                        pass
                return 0

            def safe_int(cols: list[str], idx: int) -> int:
                if idx < len(cols) and cols[idx].isdigit():
                    return int(cols[idx])
                return 0

            round_num = int(cols_a[0]) if cols_a and cols_a[0].isdigit() else i // 2 + 1

            sl_a, sa_a = parse_of(cols_a[3]) if len(cols_a) > 3 else (0, 0)
            sl_b, sa_b = parse_of(cols_b[3]) if len(cols_b) > 3 else (0, 0)

            td_f_a, ta_f_a = parse_of(cols_a[6]) if len(cols_a) > 6 else (0, 0)
            td_f_b, ta_f_b = parse_of(cols_b[6]) if len(cols_b) > 6 else (0, 0)

            rounds.append({
                'round': round_num,
                'fighter_a': {
                    'SL': sl_a, 'SA': sa_a,
                    'KD_F': safe_int(cols_a, 2),
                    'KD_A': safe_int(cols_b, 2),
                    'TD_F': td_f_a, 'TA_F': ta_f_a,
                    'TD_A': td_f_b, 'TA_A': ta_f_b,
                    'CTRL_F': parse_ctrl(cols_a[10]) if len(cols_a) > 10 else 0,
                    'CTRL_A': parse_ctrl(cols_b[10]) if len(cols_b) > 10 else 0,
                    'sub_att': safe_int(cols_a, 8),
                },
                'fighter_b': {
                    'SL': sl_b, 'SA': sa_b,
                    'KD_F': safe_int(cols_b, 2),
                    'KD_A': safe_int(cols_a, 2),
                    'TD_F': td_f_b, 'TA_F': ta_f_b,
                    'TD_A': td_f_a, 'TA_A': ta_f_a,
                    'CTRL_F': parse_ctrl(cols_b[10]) if len(cols_b) > 10 else 0,
                    'CTRL_A': parse_ctrl(cols_a[10]) if len(cols_a) > 10 else 0,
                    'sub_att': safe_int(cols_b, 8),
                },
            })

        return rounds


async def pull_all_ufc_data():
    async with UFCStatsScraper(delay_seconds=1.5) as scraper:
        events = await scraper.get_all_events()

        all_fights = []
        for event in events:
            fights = await scraper.get_fights_for_event(event['url'])
            for fight in fights:
                fight_data = await scraper.get_round_stats(fight['url'])
                fight_data['event_name'] = event['name']
                fight_data['event_date'] = event['date']
                fight_data['weight_class'] = fight['weight_class']
                all_fights.append(fight_data)
            print(f"Processed event: {event['name']} ({len(fights)} fights)")

        (_REPO_ROOT / "data" / "ufc_all_fights.json").write_text(json.dumps(all_fights, indent=2))
        print(f"Total fights pulled: {len(all_fights)}")


if __name__ == "__main__":
    asyncio.run(pull_all_ufc_data())
