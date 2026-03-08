# Movie & Show Watchlist 🎬

A zero-cost, auto-updating watchlist tracker that shows where your movies and TV shows are streaming. Built with GitHub Pages + GitHub Actions + the [Streaming Availability API](https://www.movieofthenight.com/about/api).

**Live demo:** Once set up, your watchlist lives at `https://YOUR_USERNAME.github.io/stream-finder/`

## Features

- **Automatic daily updates** — GitHub Actions checks streaming availability every day
- **Filter by streaming service** — See what's on Netflix, or Hulu, or whichever service you're considering turning on
- **Separate lists** — Maintain "ours" and "kids" watchlists with one-click filtering
- **Content ratings** — Filter by age-appropriateness (G/PG for kids, up through R/TV-MA)
- **Movie posters** — Visual grid with TMDB poster art
- **Rental prices** — See rent/buy prices alongside subscription availability
- **Mobile-friendly** — Responsive design works on phones
- **Shared access** — Anyone with the link can view; you and your spouse manage the watchlist via GitHub
- **Totally free** — No hosting costs, no database, no subscriptions

## How It Works

```
watchlist.json          (you edit this — titles to track)
       ↓
GitHub Actions cron     (runs daily, calls Streaming Availability API)
       ↓
docs/availability.json  (auto-generated — full data with posters, streaming, prices)
       ↓
docs/index.html         (static page reads the JSON, renders your watchlist)
       ↓
GitHub Pages            (serves the page for free)
```

## Setup (15 minutes)

### 1. Fork or clone this repo

```bash
# Option A: Use as template
# Click "Use this template" on GitHub, then clone your copy

# Option B: Clone directly
git clone https://github.com/YOUR_USERNAME/stream-finder.git
cd stream-finder
```

### 2. Get a free Streaming Availability API key

1. Go to [RapidAPI — Streaming Availability](https://rapidapi.com/movie-of-the-night-movie-of-the-night-default/api/streaming-availability)
2. Sign up for a free account
3. Subscribe to the **Basic (Free)** plan — 100 requests/day
4. Copy your **RapidAPI Key** from the API dashboard

### 3. Add the API key as a GitHub Secret

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `RAPIDAPI_KEY`
4. Value: paste your RapidAPI key
5. Click **Add secret**

### 4. Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main`, folder: `/docs`
4. Click **Save**

Your site will be live at `https://YOUR_USERNAME.github.io/stream-finder/` within a few minutes.

### 5. Update the page config

Edit `docs/index.html` and find this line near the top of the `<script>`:

```js
const GITHUB_REPO = 'YOUR_USERNAME/stream-finder';
```

Replace `YOUR_USERNAME` with your actual GitHub username. This powers the "edit watchlist" link in the Add form.

### 6. Customize your watchlist

Edit `watchlist.json` to add your actual titles:

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
    "year": 2018,
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
    "lists": ["dad", "mom"]
  }
]
```

Each entry needs:
- `title` — Movie or show name
- `year` — Release year (helps find the right match)
- `type` — `"movie"` or `"series"`
- `lists` — Array of one or more tags: `"dad"`, `"mom"`, `"kids"`, `"family"` (a title can belong to multiple lists)

Optional:
- `tmdb_id` — TMDB numeric ID (auto-resolved on first run if omitted)

### 7. Run the first update

Either wait for the daily cron (6:00 AM UTC), or trigger it manually:

1. Go to **Actions** tab in your repo
2. Click **Update Streaming Availability**
3. Click **Run workflow**
4. Wait ~2 minutes for it to complete

After this, `docs/availability.json` will be populated with real data and your GitHub Pages site will show your watchlist with posters and streaming info.

## Managing Your Watchlist

### Adding titles

**Option A — From the web page:**
1. Click "+ Add a title" at the bottom of your Stream Finder page
2. Fill in the title, year, type, and list
3. Click "Generate entry" → "Copy to clipboard"
4. Click the link to edit watchlist.json on GitHub
5. Paste the new entry into the JSON array and commit

**Option B — Edit directly on GitHub:**
1. Navigate to `watchlist.json` in your repo
2. Click the pencil icon to edit
3. Add your new entry to the array
4. Commit the change

Either way, the next daily run (or a manual trigger) will pick up the new title.

### Removing titles

Delete the entry from `watchlist.json` and commit. The item will disappear from `availability.json` on the next run.

### Sharing with your spouse

Share the GitHub Pages URL. For edit access, add them as a collaborator on the repo (Settings → Collaborators). They can then edit `watchlist.json` through GitHub's web interface without needing to know git.

## Configuration

Environment variables (set in `.github/workflows/update.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `RAPIDAPI_KEY` | (secret) | Your RapidAPI key for the Streaming Availability API |
| `COUNTRY` | `us` | Two-letter country code for availability data |
| `STALE_DAYS` | `7` | Days before re-checking a title |
| `MAX_REQUESTS` | `30` | Max API calls per run (free tier allows ~33/day avg) |

## Customization

### Adding more lists

The built-in lists are Dad, Mom, Kids, and Family. Titles can belong to multiple lists — for example, a movie both Dad and Mom want to watch can have `"lists": ["dad", "mom"]`.

To add a new list:
1. In `watchlist.json`, use any tag name you want in the `lists` array
2. In `docs/index.html`, find the list filter pills and add a new button:
   ```html
   <button class="pill" data-filter="list" data-value="newtag">New Tag</button>
   ```
3. Optionally add a color for the tag pill in the CSS:
   ```css
   .list-tag-newtag { background: rgba(200, 100, 50, 0.15); color: #c86432; }
   ```

### Changing the update schedule

Edit `.github/workflows/update.yml` and modify the cron expression:
```yaml
schedule:
  - cron: '0 6 * * *'  # 6:00 AM UTC daily
```

### Adding/removing streaming services

Edit `SERVICES_OF_INTEREST` in `update_availability.py` to add or remove service IDs.

## How the API Budget Works

The free tier gives you **1,000 requests per month** (~33/day). The script is smart about this:

- Items checked within the last 7 days are skipped (configurable via `STALE_DAYS`)
- Items are processed oldest-first, so everything gets refreshed within a week
- The script stops at 30 requests per run to stay well under the daily average
- For 100 titles checked every 7 days, you'll use ~430 requests/month — comfortably under 1,000

## Credits

- Streaming data: [Streaming Availability API](https://www.movieofthenight.com/about/api) by Movie of the Night
- Poster images: [TMDB](https://www.themoviedb.org/) — *This product uses the TMDB API but is not endorsed or certified by TMDB*
- Hosted free on [GitHub Pages](https://pages.github.com/) with [GitHub Actions](https://github.com/features/actions)
