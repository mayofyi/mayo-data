# Mayo Scoring Methodology — Reference Document

This file documents the methodology behind every score and metric on the Mayo platform. It is the source of truth for any scoring-related code. The full white paper lives at `mayo-scoring-methodology.html`.

---

## Engagement Rate — weighted formula

```
ER = (Likes×1 + Comments×2 + Saves×3 + Shares×4) ÷ Followers × 100
```

### Why weighted
Likes = passive acknowledgement. Comments = genuine interest. Saves = content valuable enough to return to (research shows saved content converts at significantly higher rates than liked content). Shares = audience trusted the content enough to put their own name behind it.

Saves and shares drive far greater organic distribution than likes. Platform algorithms weight them accordingly. Mayo's formula reflects this.

### Weight review policy
The ×1/×2/×3/×4 multipliers are calibrated to current platform behaviour. They are not fixed permanently — reviewed as platform dynamics and algorithm priorities shift.

### Platform variations
| Platform | Formula |
|---|---|
| Instagram | Full formula — saves available via API |
| Meta | Full formula — saves available via API |
| TikTok | Saves not available via business API — shares + video completion rate substitute |
| Substack | Open rate + reply rate substitute |
| Event channels | Attendance rate substitute |

### Important note on weighted ER values
Weighted ER figures will be higher than traditional (likes + comments) ÷ followers calculations. This is intentional — the formula surfaces genuine participation rather than passive audience size.

---

## Cross-Channel Engagement (CCE)

```
CCE = Σ (Channel ER × Channel Weight)
```

Where: `Channel Weight = Channel Reach ÷ Total Reach across all engagement channels`

### What counts as an engagement channel
Social and community platforms only: Instagram, TikTok, Substack, Discord, YouTube, etc.

**Website is explicitly excluded.** It is a data source (scraped for Cultural Impact Score inputs), not an engagement channel. Including website traffic metrics alongside social engagement would produce a meaningless blended figure.

### Single-channel communities
If a community has only one connected engagement channel, CCE equals that channel's weighted ER directly. No blending required.

### Worked example
Instagram [1,850 reach, weighted ER 10.2%] + Substack [620 subscribers, weighted ER 4.8%] = 2,470 total reach.
- Instagram weight = 1,850 ÷ 2,470 = 74.9%
- Substack weight = 620 ÷ 2,470 = 25.1%
- CCE = (10.2 × 0.749) + (4.8 × 0.251) = 7.64 + 1.20 = **8.84% ≈ 8.8%**

---

## Network Multiplier (NM)

```
NM = Σ (Member Followers × Member Weighted ER) ÷ Active Members
```

### What it measures
For every 1 person in this community, how many people outside it will you reach through organic member posting?

### Scope — all members, not just prominent ones
The calculation includes every member with a connected or verified social account. A member with 800 followers contributes proportionally just as legitimately as someone with 80,000. The formula weights by effective reach, so scale is accounted for proportionally.

### Log-normalisation
Follower counts are log-normalised before entering the calculation. This prevents a single member with a disproportionately large following (e.g. a 2M-follower member in a 300-person community) from inflating the multiplier to a point that misrepresents the community's typical reach.

### Denominator note
CCE uses social reach (total followers) as its denominator — it measures engagement relative to audience size. NM uses active members as its denominator — it measures amplification relative to actual community participation. These are different questions requiring different baselines.

### Interpreting the number
| Range | Label | Meaning |
|---|---|---|
| Below 0.5x | Tight | Inward-facing, high trust, low broadcast |
| 0.5x — 1.0x | Contained | Moderate external reach |
| 1.0x — 2.0x | Amplifying | Good organic reach beyond community |
| Above 2.0x | High reach | Strong broadcast potential |

Neither end of the scale is inherently better — it depends on the brief. A recovery product sponsorship wanting deep physical credibility may prefer a tight (0.49x) community over a high-reach one.

### Data pipeline for member verification
1. Community leader nominates members by Instagram handle
2. Mayo runs third-party audience intelligence tool lookup (referred to externally as "third-party audience intelligence tools" — do not name specific vendors in brand-facing copy)
3. Verified follower count and ER stored against the community record
4. Community leaders cannot self-report member follower counts
5. Unverified submissions are invisible to brands and do not contribute to NM

---

## Community Archetypes

Assigned based on posting behaviour, purchase signals, and member interaction patterns.

| Archetype | Best matched to | Key signals |
|---|---|---|
| Evangelists | Brand awareness, cultural association | High share rate, unsolicited advocacy, identity-linked |
| Early Adopters | Product launches, first-mover campaigns | Trend-forward, high try rate, first-to-know pride |
| Loyalists | Long-term sponsorship, retention | Repeat engagement, high attendance, low churn |
| Buyers | Direct response, product seeding | Purchase intent, conversion signal, practical focus |

---

## Cultural Impact Score (CIS) — /100

CIS is calculated **before** Match Score and feeds into it as one of four factors. It is calculated independently, reviewed by the Mayo team, stamped, and then enters the Match Score calculation weighted according to the brief's campaign objective.

### Four inputs

**1. Member Influence Quality (MIQ)**
Type of people in the community, not just count. Journalists, designers, athletes, other community leaders — people whose opinion shapes others' behaviour carry more CIS weight than general-interest accounts. Assessed via third-party audience intelligence tools + Mayo manual review.

**2. Press & Media Mentions**
Unsolicited editorial coverage is one of the clearest signals of genuine cultural weight. Also tracked via the community's own channel history — brand tags and partnership posts surface previous associations without requiring self-reporting.
- Source: web monitoring tools + channel data

**3. Brand Association History (BAH)**
Which brands has this community partnered with, and have they been selective? A community that turns down misaligned partnerships is more credible than one that takes everything.
- Platform-facilitated partnerships: tracked on-platform
- Pre-Mayo partnerships: surfaced from channel post history, press mentions, and website scraping (event pages, sponsor credits, past campaign content)
- Source: platform history + channel data + website

**4. Growth Velocity (GV)**
Cultural relevance compounds when communities are on the rise. Measured as active member and engagement growth rate over the previous 90 days.
- Source: platform API

### The Mayo Quality Stamp
- Algorithm produces raw CIS
- Mayo team member reviews and validates against direct knowledge of the community
- Stamp applied — can adjust raw score within a defined range, cannot override entirely
- Stamps are time-stamped and expire
- A community in contention for a partnership triggers a fresh review
- The stamp is Mayo's editorial credibility — not cosmetic

### CIS and the admin panel
The stamp interface lives in the admin-only panel (separate from the main app in production). In the prototype it is simulated. Do not expose the CIS raw calculation or stamp controls to community leaders or brands.

---

## Match Score — /100, always brief-relative

**There is no universal Match Score.** It is always calculated relative to a specific brand brief. The same community will score differently against different briefs.

When no brief is active, Match Score should display as `—`.

### Stage 1 — Hard filter (pass/fail)
Brand sets dealbreaker requirements at brief creation:
- Minimum active members
- Location
- Age demographic range
- Interest tags

Communities that fail dealbreakers do not appear against that brief and receive no score.

### Stage 2 — Scored across four factors

Default weighting (equal quarters):
| Factor | Default weight |
|---|---|
| Cross-Channel Engagement (CCE) | ¼ |
| Network Multiplier | ¼ |
| Archetype Fit | ¼ |
| Cultural Impact Score (CIS) | ¼ |

Weightings shift based on the brief's declared campaign objective:
- Distribution-focused brief → higher CCE and NM weight, lower CIS weight
- Culture-forward brief → higher CIS weight
- Depth/loyalty brief → lower NM weight

**Note:** The full weighting matrix (exact weight values per campaign objective) is a pending item — not yet formally defined.

### Archetype Fit scoring
Scored as a categorical match against the brief's declared campaign objective:
- Evangelists + Brand Awareness = perfect fit
- Buyers + Direct Response = perfect fit
- Mismatch (e.g. Loyalists + Product Launch) = low fit score

### Score normalisation
Each factor is scored by normalising against all communities in the filtered set (those that passed the hard filter for that brief). Scores are relative to available options, not absolute.

---

## Active Members vs Reach — why both matter

These are distinct concepts that answer different questions:

| Metric | What it is | Source | Verification |
|---|---|---|---|
| Active Members | People who physically participate — events, meetups, recurring activities | Community-reported | Always Verified (cyan) at best |
| Reach | Total social followers and subscribers across all connected channels | Platform API | Fully Verified (lime) when API-connected |

**NM denominator uses Active Members** — measures amplification relative to actual community participation.

**CCE denominator uses Reach (followers)** — measures engagement relative to audience size.

These are intentionally different baselines because they answer different questions.

---

## EMV — Estimated Media Value

```
EMV = Impressions × CPM benchmark
```

- Formula is disclosed to brands on every case study
- CPM benchmark used is documented (currently $8.50 default, adjustable by admin)
- Labelled clearly as an estimate — not presented as a confirmed figure
- Industry-standard calculation used because it is widely understood, not because it is precise
- EMV is only generated for Mayo Verified case studies, not self-reported ones

---

## Confidence tiers — full definitions

| Tier | Colour | Hex | Definition |
|---|---|---|---|
| Fully Verified | Lime | #d2ff01 | Data pulled directly via platform API |
| Verified | Cyan | #b1ecf0 | Data manually entered by community leader |
| Starter | Muted | #666 | Profile exists, no data confirmed |

**Active Members is always Verified at best.** No API can confirm physical participation. Brands must understand this is a declaration from the community leader. This distinction must be communicated clearly in the UI — a sub-label reading "community-reported" on the Active Members metric card.
