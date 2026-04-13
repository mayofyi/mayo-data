# Mayo Platform — Claude Code Context

This file is automatically loaded by Claude Code at the start of every session. Read it fully before making any changes to the codebase.

---

## What Mayo is

Mayo (mayo.fyi) is a B2B SaaS community partnership platform connecting brands with community leaders for authentic, measurable partnerships. Core flow: POST → PITCH → PARTNER → PROVE.

Three user types: Brand Marketers, Community Leaders, Agencies. Communities use the platform free. Brands pay a subscription plus a transaction cut. The business model combines self-serve SaaS with white-glove agency services.

Two sides of the business:
- **Community Partnerships Platform** — self-serve tool with AI matchmaking, smart contracting, project management, and measurement
- **White Glove Partnership Services** — hands-on support across strategy, discovery, management, and reporting

---

## Codebase orientation

The current prototype is a single self-contained HTML file (`mayo-prototype-updated.html`) built in React (via CDN, no build step). It covers the full brand and community user journeys including: login, community onboarding, discovery, brief creation, community profiles, project management, measurement, and case studies.

When making changes:
- All data lives in `COMMUNITIES`, `BRIEFS`, and `ACTIVE_PROJECT` constants near the top of the file
- Components are defined as functions below the data layer
- The main app shell is the `App()` function at the bottom
- Styling is in a `<style>` block in the `<head>` — CSS variables are used throughout, do not hardcode colours
- Design system uses: **Bebas Neue** (headings/display), **Barlow Condensed** (labels/UI), standard sans-serif (body)

---

## Design system — colour variables

```css
--lime: #d2ff01      /* primary accent, Fully Verified tier, CTAs */
--cyan: #b1ecf0      /* secondary accent, Verified tier */
--pink: #ff6ef2      /* Evangelists archetype, accents */
--orange: #ffab40    /* Cultural Impact Score, warnings */
--yellow: #ffea12    /* Match Score */
--green: #b3ff9e     /* success states */
--muted: #666        /* secondary text */
--surface: #080808   /* base background */
--surface2: #111     /* card backgrounds */
--surface3: #1a1a1a  /* elevated surfaces */
--border: #222       /* subtle borders */
--border2: #2a2a2a   /* stronger borders */
```

Never use hardcoded hex values in new components — always use CSS variables.

---

## Data architecture — metrics and their sources

### Active Members
- **What it is:** People who regularly attend events, meetups, or recurring activities
- **Source:** Manually entered by community leader at onboarding. Editable from profile at any time
- **Verification tier:** Always Verified (cyan) at best — never Fully Verified. It's a declaration, not a platform-confirmed figure
- **In the data model:** `community.activeMembers`

### Reach
- **What it is:** Total followers/subscribers across all connected social and community channels
- **Source:** Platform API per channel. Each channel stored separately
- **Excludes:** Website (website is a data source only, not an engagement channel — see below)
- **Currently blocked:** Instagram insights returning 403 — needs new token
- **In the data model:** `community.reach`, and per-channel `channel.reach`

### Engagement Rate (weighted, per channel)
- **Formula:** `(Likes×1 + Comments×2 + Saves×3 + Shares×4) ÷ Followers × 100`
- **Why weighted:** Saves and shares are higher-intent actions that drive greater organic distribution. Weights reflect current platform algorithm behaviour and will be reviewed over time
- **Platform variations:**
  - Instagram/Meta: full formula, saves available via API
  - TikTok: saves not available via business API — shares + video completion rate substitute
  - Substack: open rate + reply rate substitute
  - Event channels: attendance rate substitutes
- **Engagement vs Platform Avg:** Secondary context shown on hover only, not a standalone metric card

### Cross-Channel Engagement (CCE)
- **Formula:** `CCE = Σ (Channel ER × Channel Weight)` where weight = channel reach ÷ total reach
- **Only engagement channels count:** Instagram, TikTok, Substack, Discord, YouTube etc. Website is excluded entirely
- **Single-channel communities:** CCE = that channel's weighted ER directly
- **Currently blocked:** Needs cross-channel data. With only Instagram connected and insights blocked, CCE cannot be calculated

### Network Multiplier
- **What it is:** For every 1 person in this community, how many people outside it can be reached through organic member posting?
- **Formula:** `NM = Σ (Member Followers × Member Weighted ER) ÷ Active Members`
- **Includes ALL members** with connected/verified accounts, not just prominent ones. A member with 800 followers contributes proportionally alongside someone with 80,000
- **Log-normalisation:** Follower counts are log-normalised before entering the calculation to prevent a single large-audience outlier inflating the score
- **How member data gets in:**
  1. Community leader nominates members by Instagram handle via their profile
  2. Mayo runs a third-party audience intelligence tool lookup (e.g. Modash) to independently verify follower count and ER
  3. Verified data stored against the community record
  4. Community leaders cannot self-report member follower counts
  5. Unverified submissions are invisible to brands and do not contribute to NM
- **Why not via Instagram Graph API:** The community's OAuth token cannot pull another user's follower count or ER. Third-party lookup is required
- **Currently blocked:** Needs member submission flow + third-party verification pipeline

### Cultural Impact Score (CIS) — /100
- **What it is:** Cultural credibility, influence, and brand association quality. Part algorithmic, part editorial
- **Four inputs:**
  1. **Member Influence Quality (MIQ)** — type of people in community (journalists, athletes, designers etc.) assessed via third-party audience intelligence tools + Mayo manual review
  2. **Press & Media Mentions** — unsolicited editorial coverage via web monitoring + community channel history
  3. **Brand Association History (BAH)** — which brands partnered, how selective. Platform history + channel scraping + website scraping (event pages, sponsor credits)
  4. **Growth Velocity (GV)** — member + engagement growth over 90 days, from platform API
- **The Mayo Quality Stamp:** Algorithm produces raw CIS → Mayo team reviews → stamp applied. Stamp can adjust score within a defined range, cannot override entirely. Time-stamped, expires, refreshed when community is in contention for a partnership
- **In the data model:** `community.cis`
- **Currently blocked:** Needs press monitoring integration, audience intelligence tool integration, and admin stamp UI (admin panel — separate from main app in production)
- **Do not name Modash in any brand-facing copy** — refer to as "third-party audience intelligence tools"

### Match Score — /100, always brief-relative
- **Critical:** This is NOT a universal community quality score. It is always calculated relative to a specific brand brief. There is no Match Score without an active brief
- **When no brief is active:** Show `—` not a number
- **Two stages:**
  1. Hard filter — dealbreaker requirements (min active members, location, age range, interest tags). Fails = community doesn't appear against that brief
  2. Scored across four factors, weighted by the brief's campaign objective:
     - Cross-Channel Engagement (CCE) — ¼ default weight
     - Network Multiplier — ¼ default weight
     - Archetype Fit — ¼ default weight
     - Cultural Impact Score (CIS) — ¼ default weight
  - Weights shift based on campaign objective (e.g. culture-forward brief → higher CIS weight)
- **Currently blocked:** Needs brand brief input system
- **In the data model:** `community.matchScore` (currently hardcoded per community as illustrative data)

---

## Community archetypes

Each community has one primary archetype based on posting behaviour, purchase signals, interaction patterns:

| Archetype | Best matched to | Signals |
|---|---|---|
| Evangelists | Brand awareness, cultural association | High share rate, unsolicited advocacy, identity-linked |
| Early Adopters | Product launches, first-mover campaigns | Trend-forward, high try rate, first-to-know pride |
| Loyalists | Long-term sponsorship, retention | Repeat engagement, high attendance, low churn |
| Buyers | Direct response, product seeding | Purchase intent, conversion signal, practical focus |

---

## Confidence tiers

| Tier | Colour | Meaning |
|---|---|---|
| Fully Verified | Lime (#d2ff01) | Data pulled directly via API |
| Verified | Cyan (#b1ecf0) | Manually entered by community leader |
| Starter | Muted (#666) | Profile created, nothing confirmed |

Active Members is **always Verified at best** regardless of what else is connected.

---

## Channel data model

Each community has a `channels` array. Channels have an `engagementChannel` boolean:
- `engagementChannel: true` — social/community platforms (Instagram, TikTok, Substack, Discord). Feed into CCE and Reach calculations. Display with engagement stats and bar
- `engagementChannel: false` — website only. Display as reference link only. Never included in CCE or Reach

```js
// Engagement channel example
{ name: "Instagram", color: "#e1306c", reach: 1850, engagement: 10.2, vsAvg: 3.57, engagementChannel: true }

// Website example
{ name: "Website", color: "#7eb8ff", reach: null, engagement: null, vsAvg: null, engagementChannel: false, url: "https://southbound400.com" }
```

---

## Case studies — two types

### Self-reported
- Submitted by community leader via "Add Case Study" on their own profile
- Fields: brand, year, type, outcome description, campaign hashtag, quotes (up to 3), content items
- Goes into Mayo review queue on submit — not visible until approved
- Displays with grey "Self-reported" label
- No verified metrics shown — outcome description only
- `source: 'self-reported'` in the data model

### Mayo Verified
- Auto-created when a project closes on the platform
- Admin enriches via the "Publish Case Study" panel on the Project page (admin-only in production)
- Data sources:

| Field | Source |
|---|---|
| Brand, type, budget, dates | Platform-confirmed |
| Attendance | Mayo rep on ground (first 50 events), then community-reported |
| Post rate | Hashtag posts ÷ verified attendance. Via Instagram hashtag search API (public posts only, sample not guaranteed complete) |
| Impressions | Hashtag search + connected community account |
| EMV | Impressions × CPM benchmark. Formula disclosed to brands. Labelled as estimate |
| Quotes | Gathered by Mayo rep or submitted post-event |
| Content | Uploaded by Mayo rep or admin |
| Sentiment | Mayo auditor manually monitors during activation window |

- Campaign hashtag must be unique per brief (e.g. `#HypericeXS400`) — set in the brief before activation
- Displays with lime "★ Mayo Verified" stamp and full analytics view
- Admin publish panel requires attendance + impressions + post rate before publishing

---

## What's buildable now vs blocked

| Metric | Status | Reason |
|---|---|---|
| Instagram followers, ER, posts, bio, website | ✅ Ready | Live data available |
| Active Members | ✅ Ready | Manual input field |
| Instagram reach/impressions | 🔴 Blocked | 403 — needs new token |
| CCE | 🔴 Blocked | Needs cross-channel data |
| Total Reach | 🔴 Blocked | Needs insights + cross-channel |
| Network Multiplier | 🔴 Blocked | Needs member list + third-party verification pipeline |
| Cultural Impact Score | 🔴 Blocked | Needs press monitoring, audience intelligence tools, admin stamp UI |
| Match Score | 🔴 Blocked | Needs brand brief input system |
| Substack data | 🔴 Blocked | No public API — self-reported only for now |

**Approach for blocked metrics:** Show an explicit labelled placeholder stating why it's blocked — not a dash, not a zero. Brands should understand what's confirmed vs pending.

---

## Production notes

- **Data refresh:** Monthly (not nightly) to control API costs. Manual admin override available
- **Admin panel:** Separate from the main app in production. Currently simulated on the Project page in the prototype for convenience
- **Modash (or equivalent):** Used for member verification lookups. Never named in brand-facing copy — always "third-party audience intelligence tools"
- **EMV methodology:** Disclosed to brands on the case study. CPM benchmark used is documented
- **Website:** Data source only (scraped for CIS inputs). Never included in CCE or Reach calculations. Displayed as a reference link on community profiles
- **Substack connector:** Future build. Until then, self-reported/Verified tier only
- **First 50 events:** Mayo rep attends in person to verify attendance, capture content, gather quotes. Reduces margins short-term but essential for calibration
