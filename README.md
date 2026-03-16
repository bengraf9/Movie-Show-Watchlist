# Movie & Show Watchlist 🎬

A zero-cost, auto-updating watchlist tracker that shows where your movies and TV shows are streaming. Built with GitHub Pages + GitHub Actions + the [Streaming Availability API](https://www.movieofthenight.com/about/api) + [TMDB](https://www.themoviedb.org/).

**Live demo:** Once set up, your watchlist lives at `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/`

## Features

- **Automatic daily updates** — GitHub Actions checks streaming availability every day
- **Filter by streaming service** — Select a service to see what's available with that subscription; separate Rent/Buy and Theaters/Upcoming filters
- **Multiple lists** — Maintain Dad, Mom, Kids, Family, and Dad & Mom watchlists with one-click filtering
- **Priorities** — Rank titles per person and type (Dad movies, Mom series, etc.) with numbered badges and priority sorting
- **Content ratings** — Automatically fetched from TMDB; filter by age-appropriateness (G/PG for kids, up through R/TV-MA)
- **Movie posters** — Visual card grid with TMDB poster art, including for unreleased films
- **Runtime & length** — Movies show runtime (e.g., "2h 28m"); series show season/episode counts (e.g., "2s, 19e")
- **Release dates & Theaters** — Upcoming titles show "Coming Jun 5, 2026"; recent movies without streaming show "Theaters"
- **Watched progress** — Track seasons watched with a progress bar; caught-up shows are visually dimmed
- **Rental prices** — See rent/buy prices alongside subscription availability
- **Cards & Table views** — Rich card view for browsing; compact table view for scanning
- **Export** — Export filtered title lists for use in external prioritization tools
- **Manual streaming** — Fill in streaming info for titles the API misses, with visual indicators
- **Mobile-friendly** — Responsive design works on phones and tablets
- **Shared access** — Anyone with the link can view; you and your spouse manage the watchlist via GitHub
- **Totally free** — No hosting costs, no database, no subscriptions

## How It Works

```
watchlist.json          (you edit this — titles to track)
       ↓
GitHub Actions cron     (runs daily)
       ↓                   ├── Streaming Availability API (where to watch)
       ↓                   └── TMDB API (ratings, posters, release dates, runtime)
       ↓
docs/availability.json  (auto-generated — full data with posters, streaming, prices)
       ↓
docs/index.html         (static page reads the JSON, renders your watchlist)
       ↓
GitHub Pages            (serves the page for free)
```

## Setup (20 minutes)

### 1. Fork or clone this repo

```bash
# Option A: Use as template
# Click "Use this template" on GitHub, then clone your copy

# Option B: Clone directly
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
```

### 2. Get API keys (both free)

**Streaming Availability API (RapidAPI):**
1. Go to [RapidAPI — Streaming Availability](https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability)
2. Sign up for a free account (GitHub login works)
3. Subscribe to the **Basic (Free)** plan — 1,000 requests/month
4. Copy your **RapidAPI Key** from the code snippet panel or the Authorization tab

**TMDB API:**
1. Go to [themoviedb.org](https://www.themoviedb.org/) and create a free account
2. Go to Settings → API → request an API key
3. Select "Developer," accept terms, fill in the form (any URL works for Application URL)
4. Copy the **API Key (v3 auth)** — the shorter hex string, not the long "Read Access Token"

### 3. Add API keys as GitHub Secrets

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**, name it `RAPIDAPI_KEY`, paste your RapidAPI key
3. Click **New repository secret** again, name it `TMDB_API_KEY`, paste your TMDB key

### 4. Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main`, folder: `/docs`
4. Click **Save**
5. Add a `.nojekyll` file to the `docs/` folder (empty file — prevents Jekyll from interfering)

Your site will be live at `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/` within a few minutes.

### 5. Update the page config

Edit `docs/index.html` and find this line near the top of the `<script>`:

```js
const GITHUB_REPO = 'YOUR_USERNAME/YOUR_REPO_NAME';
```

Replace with your actual GitHub username and repo name. This powers the "edit watchlist" links.

### 6. Customize your watchlist

Edit `watchlist.json` to add your titles:

```json
[
  {
    "title": "The Matrix",
    "year": 1999,
    "type": "movie",
    "lists": ["dad"]
  },
  {
    "title": "Bluey",
    "type": "series",
    "lists": ["kids"]
  },
  {
    "title": "Finding Nemo",
    "year": 2003,
    "type": "movie",
    "lists": ["kids", "family"]
  },
  {
    "title": "Severance",
    "year": 2022,
    "type": "series",
    "lists": ["dad", "mom"],
    "priority": {"dad-series": 1},
    "watched_seasons": 2
  }
]
```

**Required fields:**
- `title` — Movie or show name
- `type` — `"movie"` or `"series"`
- `lists` — Array of tags: `"dad"`, `"mom"`, `"kids"`, `"family"` (a title can belong to multiple)

**Optional fields:**
- `year` — Release year (helps find the right match; auto-resolved if omitted)
- `tmdb_id` — TMDB ID like `"movie/603"` or `"tv/95396"` (auto-resolved if omitted)
- `rating` — Content rating like `"PG-13"` or `"TV-MA"` (auto-fetched from TMDB if omitted)
- `release_date` — ISO date like `"2026-06-05"` (auto-fetched from TMDB if omitted)
- `priority` — Object mapping `"person-type"` keys to rank numbers (see below)
- `watched_seasons` — Number of seasons completed, for series (see below)
- `manual_streaming` — Array of streaming entries for titles the API misses (see below)

### 7. Run the first update

Either wait for the daily cron (6:00 AM UTC), or trigger it manually:

1. Go to **Actions** tab in your repo
2. Click **Update Streaming Availability**
3. Click **Run workflow**
4. Wait ~2 minutes for it to complete

The first run will only process up to 30 titles. Subsequent daily runs will pick up the rest. After 2–3 runs, your full watchlist will be populated with posters, streaming info, ratings, and release dates.

## Managing Your Watchlist

### Adding titles

**Option A — From the web page:**
1. Click "+ Add a title" at the bottom of the page
2. Fill in title, year (optional), type, lists, priority (optional), release date (optional), and watched seasons (optional)
3. Click "Generate entry" → "Copy to clipboard"
4. Click the link to edit watchlist.json on GitHub
5. Paste the new entry into the JSON array and commit

**Option B — Edit watchlist.json directly on GitHub:**
1. Navigate to `watchlist.json` in your repo
2. Click the pencil icon to edit
3. Add your new entry to the array
4. Commit the change

Either way, the next daily run (or a manual trigger) will pick up the new title and fetch streaming data, poster, rating, and release date automatically.

**Tip:** Only `title`, `type`, and `lists` are required. Everything else (year, TMDB ID, rating, release date) gets auto-resolved by the script.

### Removing titles

Click the × on any card (or table row hover), confirm, and it opens watchlist.json on GitHub for editing. Delete the entry and commit. The item disappears from availability.json on the next run.

### Forcing a refresh on specific titles

Edit `docs/availability.json` on GitHub. For items you want re-checked, change their `last_checked` value to `"2000-01-01T00:00:00+00:00"`. The script will see those as stale and re-fetch them, while everything else stays fresh.

### Sharing with your spouse

Share the GitHub Pages URL. For edit access, add them as a collaborator on the repo (Settings → Collaborators). They can then edit `watchlist.json` through GitHub's web interface.

## Watchlist Features

### Priorities

Rank titles per person and type. The key format is `"person-type"` — e.g., `"dad-movie"`, `"mom-series"`. Lower numbers = higher priority.

```json
{
  "title": "Inception",
  "year": 2010,
  "type": "movie",
  "lists": ["dad", "mom"],
  "priority": {"dad-movie": 3, "mom-movie": 1}
}
```

On the page:
- A gold numbered badge appears next to prioritized titles
- When filtering to a specific list, that person's priority is shown
- When viewing "All," the best (lowest) priority across all people is shown
- Select "Priority" from the Sort dropdown to sort by rank
- Use **Export titles** to copy a filtered list to an external prioritization tool, then paste results back

### Upcoming Titles & Theaters

Release dates are fetched automatically from TMDB. You can also set them manually:

```json
{
  "title": "Avengers: Doomsday",
  "type": "movie",
  "lists": ["dad"],
  "release_date": "2026-12-18"
}
```

Display logic:
- **Future release date** → "Coming Dec 18, 2026"
- **Released within last 4 months, no streaming** → "Theaters"
- **Released over 4 months ago, no streaming** → "Not currently streaming"

Use the "Theaters / Upcoming" option in the Service filter to see all upcoming titles at once.

### Watched Seasons

Track your progress through a series:

```json
{
  "title": "Severance",
  "type": "series",
  "lists": ["dad", "mom"],
  "watched_seasons": 2
}
```

The card shows a progress bar ("Watched 2 of 2 seasons") and table view shows a compact "2/2." When you're caught up (watched = total aired seasons), the card dims to 45% opacity so in-progress shows stand out.

### Runtime & Length

Movies show runtime (e.g., "2h 28m") and series show season/episode counts (e.g., "2s, 19e") in both card and table views. These are fetched automatically. Announced but unaired seasons are excluded from the count.

### Manual Streaming

When the Streaming Availability API doesn't cover a title, you can specify where it streams:

```json
{
  "title": "Hamilton",
  "type": "movie",
  "lists": ["dad"],
  "manual_streaming": [
    {"service": "disney", "type": "subscription"}
  ]
}
```

Manual entries display with a dashed border and ✎ icon to remind you they may need periodic verification. If the API eventually finds the title on that service, the API data takes over automatically.

**Service IDs:** `netflix`, `prime`, `disney`, `hulu`, `hbo`, `apple`, `peacock`, `paramount`, `starz`

## Page Features

### Views
- **Cards** — Rich view with posters, descriptions, genres, and streaming badges
- **Table** — Compact view with columns for title, year, type, rating, length, progress, lists, and streaming

### Sorting
- Most services (default)
- Priority
- A–Z
- Newest first
- Oldest first

### Filters
- **List** — All, Dad, Mom, Dad & Mom, Kids, Family
- **Service** — Any subscription service in your data, plus Rent/Buy and Theaters/Upcoming
- **Rating** — Kids only (G/PG/TV-Y), Teen & under, or All
- **Type** — All, Movies, TV Shows

### Export
Click "Export titles" to get a plain text list of the currently filtered titles, one per line. Useful for pasting into external prioritization tools.

## Configuration

Environment variables (set in `.github/workflows/update.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `RAPIDAPI_KEY` | (secret) | Your RapidAPI key for the Streaming Availability API |
| `TMDB_API_KEY` | (secret) | Your TMDB API key for ratings, posters, and release dates |
| `COUNTRY` | `us` | Two-letter country code for availability data |
| `STALE_DAYS` | `7` | Days before re-checking a title |
| `MAX_REQUESTS` | `30` | Max Streaming Availability API calls per run |

## Customization

### Adding more lists

The built-in lists are Dad, Mom, Kids, and Family, plus the compound "Dad & Mom" filter. Titles can belong to multiple lists.

To add a new list:
1. In `watchlist.json`, use any tag name in the `lists` array
2. In `docs/index.html`, find the list filter pills and add a new button:
   ```html
   <button class="pill" data-filter="list" data-value="newtag">New Tag</button>
   ```
3. Optionally add a color for the tag pill in the CSS:
   ```css
   .list-tag-newtag { background: rgba(200, 100, 50, 0.15); color: #c86432; }
   ```

Compound filters use `+` — e.g., `data-value="kids+family"` shows titles on both Kids and Family lists.

### Changing the update schedule

Edit `.github/workflows/update.yml` and modify the cron expression:
```yaml
schedule:
  - cron: '0 6 * * *'  # 6:00 AM UTC daily
```

### Adding/removing streaming services

Edit `SERVICES_OF_INTEREST` in `update_availability.py` to add or remove service IDs.

## How the API Budget Works

The Streaming Availability API free tier gives you **1,000 requests per month**. The script manages this automatically:

- Items checked within the last 7 days are skipped (configurable via `STALE_DAYS`)
- Items are processed oldest-first, so everything gets refreshed within a week
- The script stops at 30 Streaming Availability API requests per run
- For 60 titles checked every 7 days, you'll use ~260 requests/month — well under 1,000
- TMDB API calls are separate and essentially unlimited (no daily/monthly cap)

**Note:** Some titles require 2 Streaming Availability API calls (ID lookup + search fallback). The script saves resolved TMDB IDs back to `watchlist.json` so subsequent runs use a single ID lookup.

## Credits

- Streaming data: [Streaming Availability API](https://www.movieofthenight.com/about/api) by Movie of the Night
- Ratings, posters, release dates, runtime: [TMDB](https://www.themoviedb.org/) — *This product uses the TMDB API but is not endorsed or certified by TMDB*
- Hosted free on [GitHub Pages](https://pages.github.com/) with [GitHub Actions](https://github.com/features/actions)
