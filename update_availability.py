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
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
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

# Normalize variant service IDs to canonical IDs
SERVICE_ALIASES = {
    "hbomax": "hbo", "hbo_max": "hbo", "max": "hbo",
    "appletv": "apple", "apple_tv": "apple", "apple_tv_plus": "apple",
    "paramountplus": "paramount", "paramount_plus": "paramount",
    "paramount_plus_with_showtime": "paramount",
    "amazon_prime": "prime", "amazon": "prime",
    "disneyplus": "disney", "disney_plus": "disney",
}

# Canonical display names (used everywhere instead of API-provided names)
SERVICE_NAMES = {
    "netflix": "Netflix", "prime": "Prime Video", "disney": "Disney+",
    "hulu": "Hulu", "hbo": "HBO Max", "apple": "Apple TV+",
    "peacock": "Peacock", "paramount": "Paramount+", "starz": "Starz",
    "showtime": "Showtime", "tubi": "Tubi", "roku": "Roku", "mubi": "MUBI",
    "crunchyroll": "Crunchyroll", "curiosity": "Curiosity Stream", "pluto": "Pluto TV",
}


def normalize_service_id(service_id):
    """Map variant service IDs to their canonical form."""
    return SERVICE_ALIASES.get(service_id, service_id)


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
    # Clean TMDB ID: strip any "movie/" or "series/" prefix, keep only the number
    clean_id = str(tmdb_id).split("/")[-1].strip()
    if not clean_id.isdigit():
        print(f"  [WARN] Invalid TMDB ID '{tmdb_id}' — expected a number")
        return None

    url = f"https://{RAPIDAPI_HOST}/shows/{show_type}/{clean_id}"
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


def fetch_tmdb_details(tmdb_id, show_type, title=""):
    """
    Fetch details from TMDB in a single API call using append_to_response.
    Returns a dict with any/all of: rating, release_date, poster, overview.
    For movies: /movie/{id}?append_to_response=release_dates
    For series: /tv/{id}?append_to_response=content_ratings
    """
    if not TMDB_API_KEY:
        return {}

    clean_id = str(tmdb_id).split("/")[-1].strip()
    if not clean_id.isdigit():
        return {}

    result = {}

    try:
        if show_type == "movie":
            url = f"https://api.themoviedb.org/3/movie/{clean_id}"
            params = {"api_key": TMDB_API_KEY, "append_to_response": "release_dates"}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Poster
            poster_path = data.get("poster_path", "")
            if poster_path:
                result["poster"] = f"https://image.tmdb.org/t/p/w300{poster_path}"

            # Overview
            overview = data.get("overview", "")
            if overview:
                if len(overview) > 200:
                    overview = overview[:197] + "..."
                result["overview"] = overview

            # Runtime
            runtime = data.get("runtime")
            if runtime:
                result["runtime"] = runtime

            # Parse US release dates for both certification and release date
            for country in data.get("release_dates", {}).get("results", []):
                if country.get("iso_3166_1") == "US":
                    # Find the theatrical release (type 3) or earliest with a date
                    best_date = None
                    best_cert = ""
                    for rd in country.get("release_dates", []):
                        cert = rd.get("certification", "").strip()
                        date_str = rd.get("release_date", "")[:10]  # "YYYY-MM-DD"
                        rd_type = rd.get("type", 0)

                        if cert and not best_cert:
                            best_cert = cert

                        # Prefer theatrical (3), then premiere (1), then any
                        if date_str:
                            if rd_type == 3:  # Theatrical
                                best_date = date_str
                            elif not best_date:
                                best_date = date_str

                    if best_cert:
                        result["rating"] = best_cert
                    if best_date:
                        result["release_date"] = best_date
                    break

        else:
            # TV shows
            url = f"https://api.themoviedb.org/3/tv/{clean_id}"
            params = {"api_key": TMDB_API_KEY, "append_to_response": "content_ratings"}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Poster
            poster_path = data.get("poster_path", "")
            if poster_path:
                result["poster"] = f"https://image.tmdb.org/t/p/w300{poster_path}"

            # Overview
            overview = data.get("overview", "")
            if overview:
                if len(overview) > 200:
                    overview = overview[:197] + "..."
                result["overview"] = overview

            # Season/episode counts — exclude Specials (season 0)
            # and unaired seasons (air_date in future or null)
            tmdb_seasons = data.get("seasons", [])
            if tmdb_seasons:
                from datetime import date
                today = date.today().isoformat()
                real = []
                for s in tmdb_seasons:
                    sn = s.get("season_number", -1)
                    air = s.get("air_date") or ""
                    ec = s.get("episode_count", 0)
                    if sn == 0:
                        continue  # Skip Specials
                    if not air or air > today:
                        print(f"    [SEASON SKIP] Season {sn}: air_date={air or 'none'}, episodes={ec}")
                        continue  # Skip unaired
                    real.append(s)
                if real:
                    result["season_count"] = len(real)
                    # Sum episodes only from aired seasons
                    ep_total = sum(s.get("episode_count", 0) or 0 for s in real)
                    if ep_total:
                        result["episode_count"] = ep_total
            elif data.get("number_of_seasons"):
                result["season_count"] = data["number_of_seasons"]

            num_episodes = data.get("number_of_episodes")
            if num_episodes and "episode_count" not in result:
                result["episode_count"] = num_episodes

            # Content rating
            for entry in data.get("content_ratings", {}).get("results", []):
                if entry.get("iso_3166_1") == "US":
                    rating = entry.get("rating", "")
                    if rating:
                        result["rating"] = rating
                    break

    except requests.RequestException as e:
        print(f"    [TMDB WARN] Could not fetch details for '{title}': {e}")

    return result


def extract_streaming_options(show):
    """Extract streaming availability from a show object."""
    streaming = {}
    addon_entries = []
    options = show.get("streamingOptions", {}).get(COUNTRY, [])

    # First pass: collect direct (non-addon) entries
    for opt in options:
        raw_id = opt.get("service", {}).get("id", "")
        service_id = normalize_service_id(raw_id)
        if service_id not in SERVICES_OF_INTEREST:
            continue

        service_name = SERVICE_NAMES.get(service_id, opt.get("service", {}).get("name", service_id))
        stream_type = opt.get("type", "")  # subscription, rent, buy, free, addon

        if stream_type == "addon":
            # Save for second pass
            addon_entries.append(opt)
            continue

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
        priority = {"subscription": 0, "free": 1, "rent": 2, "buy": 3}
        existing = streaming.get(service_id)
        if existing:
            if priority.get(stream_type, 5) < priority.get(existing["type"], 5):
                streaming[service_id] = entry
        else:
            streaming[service_id] = entry

    # Second pass: process addon entries
    # Only keep an addon if its service doesn't already have a direct subscription entry
    for opt in addon_entries:
        addon_info = opt.get("addon", {})
        addon_id = addon_info.get("id", "")
        host_service_id = normalize_service_id(opt.get("service", {}).get("id", ""))
        link = opt.get("link", "")

        # Normalize the addon ID to a canonical service
        mapped_service = normalize_service_id(addon_id)

        # Skip if the addon's own service already has a direct entry
        if mapped_service in streaming:
            continue

        # Also skip if it would just duplicate the host service
        if host_service_id in streaming and streaming[host_service_id]["type"] == "subscription":
            continue

        # Keep the addon, attributed to the addon's canonical service
        if mapped_service in SERVICES_OF_INTEREST:
            entry = {
                "service": mapped_service,
                "serviceName": SERVICE_NAMES.get(mapped_service, mapped_service),
                "type": "subscription",
                "link": link,
            }
            if mapped_service not in streaming:
                streaming[mapped_service] = entry

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

    # Content rating is managed via TMDB lookups in the main loop
    # and stored in watchlist.json. Just pass through what we have.
    rating = watchlist_entry.get("rating", "")

    # Get genres
    genres = [g.get("name", g.get("id", "")) for g in show.get("genres", [])]

    # Get overview
    overview = show.get("overview", "")
    if len(overview) > 200:
        overview = overview[:197] + "..."

    # Extract streaming options
    streaming = extract_streaming_options(show)

    # Merge manual streaming entries from watchlist (for API coverage gaps)
    for ms in watchlist_entry.get("manual_streaming", []):
        svc_id = ms.get("service", "")
        if svc_id and svc_id not in streaming:
            streaming[svc_id] = {
                "service": svc_id,
                "serviceName": ms.get("serviceName", svc_id),
                "type": ms.get("type", "subscription"),
                "link": ms.get("link", ""),
                "manual": True,
            }

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
        # Count seasons and episodes from SA API, excluding Specials and unaired seasons
        seasons = show.get("seasons", [])
        if seasons:
            real_seasons = [
                s for s in seasons
                if s.get("seasonNumber", s.get("season_number", -1)) != 0
                and (s.get("episodeCount", 0) or len(s.get("episodes", []))) > 0
            ]
            season_count = len(real_seasons) if real_seasons else len(seasons)
            episode_count = sum(
                s.get("episodeCount", 0) or len(s.get("episodes", []))
                for s in real_seasons or seasons
            )
        # Fallback fields some API versions use
        if not season_count:
            season_count = show.get("seasonCount")
        if not episode_count:
            episode_count = show.get("episodeCount")

    result = {
        "title": watchlist_entry["title"],
        "year": watchlist_entry.get("year") or show.get("releaseYear") or show.get("firstAirYear"),
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

    if not TMDB_API_KEY:
        print("WARNING: TMDB_API_KEY not set — content ratings, release dates, and poster backfill from TMDB will be skipped.")
        print("  Add a TMDB_API_KEY secret to enable these features.")
    else:
        print("TMDB integration enabled")

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
            if entry.get("rating"):
                existing["rating"] = entry["rating"]
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
                if entry.get("rating"):
                    existing["rating"] = entry["rating"]
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
                print(f"  [ID MISS] TMDB ID {tmdb_id} not in API, falling back to title search...")

        if not show:
            print(f"  [SEARCH] {title} ({year})...")
            show = search_show(title, show_type, year)
            requests_made += 1
            time.sleep(0.3)

            # Verify search result isn't a mismatch
            if show:
                result_title = (show.get("title") or "").lower().strip()
                search_title = title.lower().strip()

                # Strict match: titles must be very similar, not just share one word
                # Remove common articles for comparison
                def normalize(t):
                    for article in ['the ', 'a ', 'an ']:
                        if t.startswith(article):
                            t = t[len(article):]
                    return t

                norm_search = normalize(search_title)
                norm_result = normalize(result_title)

                # Check if one title contains the other, or they share most words
                search_words = set(w for w in norm_search.split() if len(w) > 1)
                result_words = set(w for w in norm_result.split() if len(w) > 1)

                if search_words and result_words:
                    overlap = search_words & result_words
                    # Require majority of the SHORTER title's words to match
                    min_words = min(len(search_words), len(result_words))
                    match_ratio = len(overlap) / min_words if min_words > 0 else 0

                    if match_ratio < 0.5 or (min_words <= 2 and overlap != search_words and overlap != result_words):
                        print(f"  [MISMATCH] Search returned '{show.get('title')}' for '{title}' (overlap: {overlap}) — skipping")
                        show = None
                    else:
                        print(f"  [MATCH] Search found '{show.get('title')}'")
                else:
                    print(f"  [MATCH] Search found '{show.get('title')}'")


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

            # Fetch details from TMDB if needed (rating, release_date, poster, overview)
            needs_rating = not entry.get("rating", "")
            needs_release = not entry.get("release_date", "")
            needs_poster = not item_data.get("poster", "")
            needs_overview = not item_data.get("overview", "")
            needs_seasons = (show_type == "series")  # Always check TMDB for accurate season counts
            lookup_id = entry.get("tmdb_id") or show.get("tmdbId")

            if (needs_rating or needs_release or needs_poster or needs_overview or needs_seasons) and lookup_id and TMDB_API_KEY:
                tmdb_data = fetch_tmdb_details(lookup_id, show_type, title)

                if tmdb_data.get("rating") and needs_rating:
                    entry["rating"] = tmdb_data["rating"]
                    item_data["rating"] = tmdb_data["rating"]
                    watchlist_modified = True
                    print(f"    -> Fetched rating: {tmdb_data['rating']}")
                elif needs_rating:
                    print(f"    -> No rating available from TMDB (will retry next run)")

                if tmdb_data.get("release_date") and needs_release:
                    entry["release_date"] = tmdb_data["release_date"]
                    item_data["release_date"] = tmdb_data["release_date"]
                    watchlist_modified = True
                    print(f"    -> Fetched release date: {tmdb_data['release_date']}")

                if tmdb_data.get("poster"):
                    if needs_poster:
                        item_data["poster"] = tmdb_data["poster"]
                        print(f"    -> Fetched poster from TMDB")
                    elif not item_data.get("poster", "").startswith("https://image.tmdb.org"):
                        # Prefer TMDB poster over Streaming Availability API poster
                        # (SA API posters can be broken for unreleased/obscure titles)
                        item_data["poster"] = tmdb_data["poster"]
                        print(f"    -> Replaced poster with TMDB version")

                if tmdb_data.get("overview") and needs_overview:
                    item_data["overview"] = tmdb_data["overview"]
                    print(f"    -> Fetched overview from TMDB")

                if tmdb_data.get("runtime") and not item_data.get("runtime"):
                    item_data["runtime"] = tmdb_data["runtime"]

                if tmdb_data.get("season_count"):
                    item_data["season_count"] = tmdb_data["season_count"]

                if tmdb_data.get("episode_count"):
                    item_data["episode_count"] = tmdb_data["episode_count"]

                time.sleep(0.15)  # Be polite to TMDB

            stream_count = len(item_data["streaming"])
            # Debug: if 0 services, show what raw options the API had
            if stream_count == 0:
                raw_options = show.get("streamingOptions", {}).get(COUNTRY, [])
                if raw_options:
                    raw_summary = [f"{o.get('service',{}).get('id','?')}:{o.get('type','?')}" for o in raw_options[:10]]
                    print(f"    [STREAM DEBUG] API had {len(raw_options)} raw options: {', '.join(raw_summary)}")
            print(f"    -> Found on {stream_count} service(s)")
        else:
            print(f"  [MISS] No results for '{title}' ({year})")

            # Try TMDB for poster, overview, rating, release_date
            tmdb_data = {}
            lookup_id = entry.get("tmdb_id") or tmdb_id
            if lookup_id and TMDB_API_KEY:
                print(f"    -> Checking TMDB for details...")
                tmdb_data = fetch_tmdb_details(lookup_id, show_type, title)
                time.sleep(0.15)

                # Write rating and release_date back to watchlist
                if tmdb_data.get("rating") and not entry.get("rating"):
                    entry["rating"] = tmdb_data["rating"]
                    watchlist_modified = True
                    print(f"    -> Fetched rating: {tmdb_data['rating']}")
                if tmdb_data.get("release_date") and not entry.get("release_date"):
                    entry["release_date"] = tmdb_data["release_date"]
                    watchlist_modified = True
                    print(f"    -> Fetched release date: {tmdb_data['release_date']}")
                if tmdb_data:
                    fields = [k for k in tmdb_data if k not in ("rating", "release_date")]
                    if fields:
                        print(f"    -> Also got from TMDB: {', '.join(fields)}")

            # Keep existing data if we had it, or create a minimal entry
            if existing:
                existing["last_checked"] = datetime.now(timezone.utc).isoformat()
                existing["lists"] = entry.get("lists", existing.get("lists", ["dad"]))
                existing["priority"] = entry.get("priority", existing.get("priority", {}))
                if entry.get("rating"):
                    existing["rating"] = entry["rating"]
                if entry.get("release_date"):
                    existing["release_date"] = entry["release_date"]
                if entry.get("watched_seasons") is not None:
                    existing["watched_seasons"] = entry["watched_seasons"]
                # Backfill poster/overview from TMDB if missing
                if tmdb_data.get("poster") and not existing.get("poster"):
                    existing["poster"] = tmdb_data["poster"]
                if tmdb_data.get("overview") and not existing.get("overview"):
                    existing["overview"] = tmdb_data["overview"]
                if tmdb_data.get("runtime") and not existing.get("runtime"):
                    existing["runtime"] = tmdb_data["runtime"]
                if tmdb_data.get("season_count") and not existing.get("season_count"):
                    existing["season_count"] = tmdb_data["season_count"]
                if tmdb_data.get("episode_count") and not existing.get("episode_count"):
                    existing["episode_count"] = tmdb_data["episode_count"]
                # Merge manual streaming entries
                existing_streaming = existing.get("streaming", {})
                for ms in entry.get("manual_streaming", []):
                    svc_id = ms.get("service", "")
                    if svc_id and svc_id not in existing_streaming:
                        existing_streaming[svc_id] = {
                            "service": svc_id,
                            "serviceName": ms.get("serviceName", svc_id),
                            "type": ms.get("type", "subscription"),
                            "link": ms.get("link", ""),
                            "manual": True,
                        }
                existing["streaming"] = existing_streaming
                updated_items.append(existing)
            else:
                miss_entry = {
                    "title": title,
                    "year": year,
                    "type": show_type,
                    "lists": entry.get("lists", ["dad"]),
                    "priority": entry.get("priority", {}),
                    "poster": tmdb_data.get("poster", ""),
                    "rating": entry.get("rating", ""),
                    "genres": [],
                    "overview": tmdb_data.get("overview", ""),
                    "streaming": {},
                    "last_checked": datetime.now(timezone.utc).isoformat(),
                }
                if tmdb_data.get("runtime"):
                    miss_entry["runtime"] = tmdb_data["runtime"]
                if tmdb_data.get("season_count"):
                    miss_entry["season_count"] = tmdb_data["season_count"]
                if tmdb_data.get("episode_count"):
                    miss_entry["episode_count"] = tmdb_data["episode_count"]
                if entry.get("release_date"):
                    miss_entry["release_date"] = entry["release_date"]
                elif tmdb_data.get("release_date"):
                    miss_entry["release_date"] = tmdb_data["release_date"]
                if entry.get("watched_seasons") is not None:
                    miss_entry["watched_seasons"] = entry["watched_seasons"]
                # Merge manual streaming entries
                for ms in entry.get("manual_streaming", []):
                    svc_id = ms.get("service", "")
                    if svc_id and svc_id not in miss_entry["streaming"]:
                        miss_entry["streaming"][svc_id] = {
                            "service": svc_id,
                            "serviceName": ms.get("serviceName", svc_id),
                            "type": ms.get("type", "subscription"),
                            "link": ms.get("link", ""),
                            "manual": True,
                        }
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
