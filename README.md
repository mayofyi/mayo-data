# Mayo Data Pipeline

Pulls data from Instagram, Substack, and community websites. Assigns a behavioural archetype (Evangelist, Early Adopter, Buyer, Loyalist, Culturally Impactful) and generates a Match Score against a brand brief. Built in Python. Requires a `.env` file with Meta API credentials.

## Setup

1. Clone the repo and navigate to the project directory.
2. Create a `.env` file (see `.env` for the required keys):
   ```
   META_APP_ID=your_meta_app_id_here
   META_APP_SECRET=your_meta_app_secret_here
   IG_ACCESS_TOKEN=your_instagram_access_token_here
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the pipeline:
   ```bash
   python run.py
   ```

## Project Structure

```
mayo-data/
├── connectors/         # Data connectors for each platform
│   ├── instagram.py    # Instagram Graph API
│   ├── substack.py     # Substack RSS/web scraping
│   └── website.py      # Community website scraping
├── scoring/            # Scoring and matching logic
│   ├── aggregator.py   # Combines signals across platforms
│   ├── archetype.py    # Behavioural archetype classification
│   ├── match.py        # Brand-community match scoring
│   └── weights.py      # Scoring weights configuration
├── data/
│   └── communities/    # Cached raw API responses (gitignored)
├── output/             # Final scored profiles (gitignored)
└── run.py              # Main pipeline entry point
```

## Archetypes

| Archetype | Description |
|---|---|
| Evangelist | Highly engaged advocates who actively promote and recruit |
| Early Adopter | First movers who embrace new products and trends |
| Buyer | Purchase-intent driven, responsive to offers and deals |
| Loyalist | Long-term brand faithful with high retention signals |
| Culturally Impactful | Taste-makers with strong cultural influence and reach |

## Data Sources

- **Instagram** — follower count, engagement rate, post captions, reach/impressions via Meta Graph API
- **Substack** — subscriber signals, post engagement, content themes via RSS
- **Website** — community size, description, content topics via web scraping
