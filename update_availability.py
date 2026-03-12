#!/usr/bin/env python3
"""
Movie & Show Watchlist - Update Availability Data
Reads watchlist.json, queries the Streaming Availability API,
and writes availability.json for the static frontend.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# --- Configuration ---
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "streaming-availability.p.rapidapi.com"
COUNTRY = os.environ.get("COUNTRY", "us")
STALE_DAYS = int(os.environ.get("STALE_DAYS", "7"))
MAX_REQUESTS = int(os.environ.get("MAX_REQUESTS", "30"))  # Free tier: 1000/month ≈ 33/day

SCRIPT_DIR = Path(__file__).parent
WATCHLIST_PATH = SCRIPT_DIR / "watchlist.json"
AVAILABILITY_PATH = SCRIPT_DIR / "docs" / "availability.json"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST,
}

# Streaming services we care about (IDs used by the API)
SERVICES_OF_INTEREST = [
    "netflix", "prime", "disney", "hulu", "hbo", "apple",
    "peacock", "paramount", "starz", "showtime", "mubi",
    "curiosity", "crunchyroll", "tubi", "pluto", "roku",
]


def load_json(path):
    """Load a JSON file, returning empty structure if not found."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(path, data):
    """Write data to a JSON file with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def search_show(title, show_type, year=None):
    """
    Search for a show by title using the Streaming Availability API.
    Returns the best-matching show object or None.
    """
    url = f"https://{RAPIDAPI_HOST}/shows/search/title"
    params = {
        "title": title,
        "country": COUNTRY,
        "show_type": show_type,
        "output_language": "en",
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return None

        # Try to match by year if provided
        if year:
            for show in results:
                release_year = show.get("releaseYear") or show.get("firstAirYear")
                if release_year and abs(release_year - year) <= 1:
                    return show
        # Fall back to first result
        return results[0] if results else None

    except requests.RequestException as e:
        print(f"  [ERROR] Search failed for '{title}': {e}")
        return None


def get_show_by_id(show_type, tmdb_id):
    """
    Fetch a specific show by its TMDB ID.
    show_type: 'movie' or 'series'
    Returns the show object or None.
    """
    url = f"https://{RAPIDAPI_HOST}/shows/{show_type}/{tmdb_id}"
    params = {
        "country": COUNTRY,
        "output_language": "en",
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  [ERROR] Fetch failed for {show_type}/{tmdb_id}: {e}")
        return None


def extract_streaming_options(show):
    """Extract streaming availability from a show object."""
    streaming = {}
    options = show.get("streamingOptions", {}).get(COUNTRY, [])

    for opt in options:
        service_id = opt.get("service", {}).get("id", "")
        if service_id not in SERVICES_OF_INTEREST:
            continue

        service_name = opt.get("service", {}).get("name", service_id)
        stream_type = opt.get("type", "")  # subscription, rent, buy, free, addon
        price_info = opt.get("price", {})
        link = opt.get("link", "")
        quality = opt.get("quality", "")

        entry = {
            "service": service_id,
            "serviceName": service_name,
            "type": stream_type,
            "link": link,
        }

        if quality:
            entry["quality"] = quality

        if price_info:
            amount = price_info.get("formatted") or price_info.get("amount")
            if amount:
                entry["price"] = str(amount)

        # Keep the best option per service (prefer subscription > free > rent > buy)
        priority = {"subscription": 0, "free": 1, "addon": 2, "rent": 3, "buy": 4}
        existing = streaming.get(service_id)
        if existing:
            if priority.get(stream_type, 5) < priority.get(existing["type"], 5):
                streaming[service_id] = entry
        else:
            streaming[service_id] = entry

    return streaming


def extract_item_data(show, watchlist_entry):
    """Build a complete availability item from API response + watchlist entry."""
    # Get poster URL
    poster = ""
    image_set = show.get("imageSet", {})
    # Prefer vertical poster
    if "verticalPoster" in image_set:
        poster = (
            image_set["verticalPoster"].get("w240")
            or image_set["verticalPoster"].get("w360")
            or image_set["verticalPoster"].get("w480")
            or ""
        )

    # Get content rating
    rating = ""
    for cert in show.get("contentRatings", []):
        if cert.get("country", "").lower() == COUNTRY:
            rating = cert.get("rating", "")
            break
    # Fallback: sometimes it's at the top level
    if not rating:
        rating = show.get("rating", "")

    # Get genres
    genres = [g.get("name", g.get("id", "")) for g in show.get("genres", [])]

    # Get overview
    overview = show.get("overview", "")
    if len(overview) > 200:
        overview = overview[:197] + "..."

    # Extract streaming options
    streaming = extract_streaming_options(show)

    # Get TMDB ID from the show
    tmdb_id = show.get("tmdbId") or watchlist_entry.get("tmdb_id")

    # Get runtime (movies) or season/episode counts (series)
    show_type = watchlist_entry.get("type", "movie")
    runtime = None
    season_count = None
    episode_count = None

    if show_type == "movie":
        runtime = show.get("runtime")  # in minutes
    else:
        # Count seasons and episodes
        seasons = show.get("seasons", [])
        if seasons:
            season_count = len(seasons)
            episode_count = sum(
                s.get("episodeCount", 0) or len(s.get("episodes", []))
                for s in seasons
            )
        # Fallback fields some API versions use
        if not season_count:
            season_count = show.get("seasonCount")
        if not episode_count:
            episode_count = show.get("episodeCount")

    result = {
        "title": show.get("title") or watchlist_entry["title"],
        "year": show.get("releaseYear") or show.get("firstAirYear") or watchlist_entry.get("year"),
        "type": show_type,
        "tmdb_id": tmdb_id,
        "lists": watchlist_entry.get("lists", ["dad"]),
        "priority": watchlist_entry.get("priority", {}),
        "poster": poster,
        "rating": rating,
        "genres": genres,
        "overview": overview,
        "streaming": streaming,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }

    # Add runtime or season/episode counts
    if runtime:
        result["runtime"] = runtime
    if season_count:
        result["season_count"] = season_count
    if episode_count:
        result["episode_count"] = episode_count

    # Pass through user-managed fields from watchlist
    if watchlist_entry.get("release_date"):
        result["release_date"] = watchlist_entry["release_date"]
    if watchlist_entry.get("watched_seasons") is not None:
        result["watched_seasons"] = watchlist_entry["watched_seasons"]

    return result


def is_stale(item, stale_days):
    """Check if an availability item needs refreshing."""
    last_checked = item.get("last_checked")
    if not last_checked:
        return True
    try:
        checked_dt = datetime.fromisoformat(last_checked)
        return datetime.now(timezone.utc) - checked_dt > timedelta(days=stale_days)
    except (ValueError, TypeError):
        return True


def main():
    if not RAPIDAPI_KEY:
        print("ERROR: RAPIDAPI_KEY environment variable is not set.")
        print("Get a free API key at: https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability")
        sys.exit(1)

    # Load watchlist
    watchlist = load_json(WATCHLIST_PATH)
    if not watchlist:
        print("ERROR: Could not load watchlist.json or it's empty.")
        sys.exit(1)

    print(f"Loaded {len(watchlist)} items from watchlist.json")

    # Load existing availability data
    existing_data = load_json(AVAILABILITY_PATH)
    existing_items = {}
    if existing_data and "items" in existing_data:
        for item in existing_data["items"]:
            key = f"{item.get('title', '').lower()}|{item.get('year', '')}|{item.get('type', '')}"
            existing_items[key] = item

    # Process each watchlist entry
    requests_made = 0
    updated_items = []
    watchlist_modified = False

    for entry in watchlist:
        title = entry.get("title", "Unknown")
        year = entry.get("year")
        show_type = entry.get("type", "movie")
        tmdb_id = entry.get("tmdb_id")

        key = f"{title.lower()}|{year or ''}|{show_type}"

        # Check if we have fresh data already
        existing = existing_items.get(key)
        if existing and not is_stale(existing, STALE_DAYS):
            # Preserve user-managed fields (may have changed in watchlist)
            existing["lists"] = entry.get("lists", existing.get("lists", ["dad"]))
            existing["priority"] = entry.get("priority", existing.get("priority", {}))
            if entry.get("release_date"):
                existing["release_date"] = entry["release_date"]
            if entry.get("watched_seasons") is not None:
                existing["watched_seasons"] = entry["watched_seasons"]
            updated_items.append(existing)
            print(f"  [FRESH] {title} ({year}) - skipping")
            continue

        # Check rate limit
        if requests_made >= MAX_REQUESTS:
            print(f"  [LIMIT] Reached {MAX_REQUESTS} requests, deferring remaining items")
            if existing:
                existing["lists"] = entry.get("lists", existing.get("lists", ["dad"]))
                existing["priority"] = entry.get("priority", existing.get("priority", {}))
                if entry.get("release_date"):
                    existing["release_date"] = entry["release_date"]
                if entry.get("watched_seasons") is not None:
                    existing["watched_seasons"] = entry["watched_seasons"]
                updated_items.append(existing)
            continue

        # Fetch from API
        show = None
        if tmdb_id:
            print(f"  [FETCH] {title} ({year}) by TMDB ID {tmdb_id}...")
            show = get_show_by_id(show_type, tmdb_id)
            requests_made += 1
            time.sleep(0.3)
            if not show:
                print(f"  [NOT IN API] {title} — TMDB ID {tmdb_id} not found in Streaming Availability API. Skipping search to avoid mismatch.")
        else:
            print(f"  [SEARCH] {title} ({year})...")
            show = search_show(title, show_type, year)
            requests_made += 1
            time.sleep(0.3)

            # Verify search result isn't a mismatch
            if show:
                result_title = (show.get("title") or "").lower()
                search_title = title.lower()
                # If the result title doesn't share any significant words, it's likely wrong
                search_words = set(w for w in search_title.split() if len(w) > 2)
                result_words = set(w for w in result_title.split() if len(w) > 2)
                if search_words and not search_words & result_words:
                    print(f"  [MISMATCH] Search returned '{show.get('title')}' for '{title}' — skipping")
                    show = None

        if show:
            item_data = extract_item_data(show, entry)
            updated_items.append(item_data)

            # Save resolved TMDB ID back to watchlist for faster future lookups
            resolved_id = show.get("tmdbId")
            if resolved_id and not tmdb_id:
                entry["tmdb_id"] = resolved_id
                watchlist_modified = True
                print(f"    -> Resolved TMDB ID: {resolved_id}")

            # Backfill year if not in watchlist
            resolved_year = show.get("releaseYear") or show.get("firstAirYear")
            if resolved_year and not entry.get("year"):
                entry["year"] = resolved_year
                watchlist_modified = True
                print(f"    -> Resolved year: {resolved_year}")

            stream_count = len(item_data["streaming"])
            print(f"    -> Found on {stream_count} service(s)")
        else:
            print(f"  [MISS] No results for '{title}' ({year})")
            # Keep existing data if we had it, or create a minimal entry
            if existing:
                existing["lists"] = entry.get("lists", existing.get("lists", ["dad"]))
                existing["priority"] = entry.get("priority", existing.get("priority", {}))
                if entry.get("release_date"):
                    existing["release_date"] = entry["release_date"]
                if entry.get("watched_seasons") is not None:
                    existing["watched_seasons"] = entry["watched_seasons"]
                updated_items.append(existing)
            else:
                miss_entry = {
                    "title": title,
                    "year": year,
                    "type": show_type,
                    "lists": entry.get("lists", ["dad"]),
                    "priority": entry.get("priority", {}),
                    "poster": "",
                    "rating": "",
                    "genres": [],
                    "overview": "",
                    "streaming": {},
                    "last_checked": datetime.now(timezone.utc).isoformat(),
                    "error": "not_found",
                }
                if entry.get("release_date"):
                    miss_entry["release_date"] = entry["release_date"]
                if entry.get("watched_seasons") is not None:
                    miss_entry["watched_seasons"] = entry["watched_seasons"]
                updated_items.append(miss_entry)

    # Write results
    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "country": COUNTRY,
        "items": updated_items,
    }
    save_json(AVAILABILITY_PATH, output)
    print(f"\nWrote {len(updated_items)} items to {AVAILABILITY_PATH}")
    print(f"API requests used: {requests_made}")

    # Save back watchlist with resolved TMDB IDs
    if watchlist_modified:
        save_json(WATCHLIST_PATH, watchlist)
        print("Updated watchlist.json with resolved TMDB IDs")


if __name__ == "__main__":
    main()
