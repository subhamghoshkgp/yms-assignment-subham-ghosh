"""Retrieve only the market series and exchange disclosures used by the feature builder."""
import io
import json
import os
from datetime import datetime, time, timezone
from tempfile import NamedTemporaryFile
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile


def cached(cache, filename, fetch):
    if cache is None:
        return fetch()
    path = cache / filename
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    result = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(result, stream, separators=(",", ":"))
    os.replace(stream.name, path)
    return result


def download(url, referer):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    with urlopen(request, timeout=40) as response:
        return response.read()


def chart(symbol, start, end_exclusive, interval, cache):
    def stamp(d):
        return int(datetime.combine(d, time(), timezone.utc).timestamp())

    def fetch():
        params = urlencode({"period1": stamp(start), "period2": stamp(end_exclusive), "interval": interval})
        for host in ("query1", "query2"):
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?{params}"
            try:
                result = json.loads(download(url, "https://finance.yahoo.com/"))["chart"]["result"][0]
                if not result.get("timestamp"):
                    raise ValueError("empty series")
                return result
            except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
                if host == "query2":
                    raise RuntimeError(f"cannot read {symbol} {interval}") from error
    return cached(cache, f"quotes/{symbol}_{start}_{end_exclusive}_{interval}.json", fetch)


def announcements(symbol, start, end, cache):
    def fetch():
        params = urlencode({"symbol": symbol, "index": "equities",
                            "from_date": start.strftime("%d-%m-%Y"), "to_date": end.strftime("%d-%m-%Y")})
        url = "https://www.nseindia.com/api/corporate-announcements?" + params
        rows = json.loads(download(url, "https://www.nseindia.com/"))
        if not isinstance(rows, list):
            raise ValueError(f"invalid NSE announcements for {symbol}")
        return rows
    return cached(cache, f"filings/{symbol}_{start}_{end}.json", fetch)


def board_notices(publication_day, cache):
    """A PR archive contains that day's announcements of forthcoming board meetings."""
    def fetch():
        short = publication_day.strftime("%d%m%y")
        url = f"https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{short}.zip"
        with ZipFile(io.BytesIO(download(url, "https://www.nseindia.com/"))) as archive:
            member = "bm" + publication_day.strftime("%d%m%Y") + ".txt"
            text = archive.read(member).decode("latin-1")
        meetings = []
        for line in text.splitlines()[1:]:
            fields = line.split(" : ", 2)
            if len(fields) != 3 or not fields[0].split() or "financial result" not in fields[2].lower():
                continue
            try:
                meeting = datetime.strptime(fields[1].strip(), "%d-%b-%Y").date()
            except ValueError:
                continue
            if meeting > publication_day:
                meetings.append((fields[0].split()[-1], meeting.isoformat()))
        return meetings
    return cached(cache, f"notices/{publication_day}.json", fetch)
