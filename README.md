# Ban the pair, not the champion? — a LoL synergy network for tournament draft prep (Patch 26.20)

MADT 7202 mid-term applied case (network analysis). One-page report: `report/MidTerm_LoL_Synergy.pdf`.

**Decision.** Which 2–3 champion *pairs* a Thai amateur/collegiate team should ban or practise for its next
tournament on the current patch. Owner: head coach / draft analyst (generic role; no real team commissioned this).
**Flip condition:** if the top-synergy pairs were just the highest-win-rate champions together, banning single
champions by win rate would be enough and the network would add nothing.

**Answer (from the data below).** Pair synergy is weak: 43 of 638 pairs have a 90% CI above 0, but random-outcome
data gives 36 on average (max 46). The network's real signal is a **hub**: Lee Sin holds 7 of the 30 edges that pass
the CI and replicate on both servers (random max 6), has the highest betweenness (0.33) and ranks only 90th of 173
by own win rate. Recommendation: first-phase ban Lee Sin (a single ban, but chosen by the network, not by win rate);
practise Kai'Sa + Qiyana; do not adopt Caitlyn + Karma (2 of 12 pro wins on the patch).

## Run

```bash
uv venv --python 3.12 .venv
uv pip install -r requirements.txt --python .venv/Scripts/python.exe
echo RIOT_API_KEY=RGAPI-... > .env                       # development key, expires every 24 h; .env is git-ignored
.venv/Scripts/python.exe src/run_all.py                   # collect (cached) -> analyze -> robustness -> figure -> report
.venv/Scripts/python.exe src/run_all.py --skip-collect    # rebuild everything from data/ without a key
.venv/Scripts/python.exe -m pytest -q tests
```

`report.py` fails unless the PDF is exactly one page, all text ≥ 10 pt and margins ≥ 1.5 cm. Every number in the
report is read from `out/`. Author and repository link are set in `src/report.py` (`AUTHOR`, `REPO_URL`).

## Data collection (re-collect it from this section)

**Riot Games API** (official, development key, Riot developer terms), ranked solo queue `queue=420`, patch 26.20.

- **Servers.** `sg2` with match-v5 routing `sea`: TH2 no longer exists (`th2.api.riotgames.com` does not resolve);
  Riot merged TH2 and PH2 into SG2, renamed the SEA server, on 8–9 Jan 2025 (patch 25.S1.1), so Thai solo queue is
  the SEA server, shared with players from the Philippines, Singapore, Malaysia and Indonesia. `kr` with routing
  `asia`: Korea, the highest-skill solo queue, added for volume at high rank (the brief allowed KR if SEA was thin)
  and as a second sample to check SEA against. Riot enforces app rate limits per routing value, so the two servers
  were collected in parallel. Verified by test calls: SG2/KR ladders answer, and match ids carry `SG2_` / `KR_`.
- **Patch.** 26.20 = game version `16.20.*` (Data Dragon `16.20.1`), released 7 Oct 2026. `startTime` =
  2026-10-07 00:00 UTC and every match is also filtered on `gameVersion` starting with `16.20.` (4 kept games started
  at 23:32–23:53 UTC on 6 Oct, i.e. already on 16.20 in Asian time zones).
- **Frame.** league-v4 Challenger / Grandmaster / Master ladders (SEA 300 / 699 / 2,456 players; KR 300 / 700 /
  10,000) → players round-robin across the three tiers, fixed random order inside each tier (seed 7) → match-v5 ids
  (`queue=420`, `startTime`, `count=100`) until the pool holds 1.15 × the target → match details in a fixed random
  order (seed 7) until the target number of kept matches. Each match id keeps the highest tier it was reached from
  (`source_tier`, used for the tier split). Diamond was not needed.
- **Kept.** queue 420, version 16.20, 10 participants, duration ≥ 300 s, no early surrender (remakes dropped). Three
  `VN2_` games reached through SEA players' histories are dropped (frame = SG2 + KR).
- **Rate limits.** Read from `X-App-Rate-Limit` on every response (`100:120,20:1`; method limits `500:600,30:10`
  league, `2000:10` match) and obeyed one call under each window, shared by 3 worker threads; 429 → wait
  `Retry-After` (one 429 in total); timeouts / 5xx → exponential back-off; 401 / 403 → stop.
- **Collection log** (`data/collection_meta_sg2.json`, `data/collection_meta_kr.json`; times UTC, 15 Oct 2026):

| Run | Server | Window | Calls | Result |
|---|---|---|---|---|
| 1 | SEA | 15:18–15:33 | ≥ 3 league + 325 match-id + 382 match (lower bound: the run stopped on a read timeout before logging; the timeout is now retried) | 4,029 match ids, 375 kept |
| 2 | SEA | 15:34–16:38 | 3,191 match | 3,500 kept |
| 3 | SEA | 16:38–17:47 | 3 + 824 + 2,551 (+1 answered 429) | 6,000 kept |
| 1 | KR | 16:14–18:00 | 3 + 280 + 5,035 | 5,000 kept |

  Total ≥ 12,598 Riot API calls (fewer than 20 more were test calls before run 1). SEA players sampled: 1,148 (the
  first 325 reconstructed from the fixed round-robin order: run 3 resumed after them); KR: 280.
- **Privacy (PDPA / Riot policy).** No summoner name, Riot ID or PUUID is written anywhere; PUUIDs exist only in
  memory while fetching. `data/raw/<match_id>.json` is a stripped cache: match id, version, duration, queue, start
  time, source tier and, per participant, team, champion, position and win.

**Leaguepedia** (Cargo API, `lol.fandom.com`, CC BY-SA 3.0): `ScoreboardPlayers` joined to `ScoreboardGames`,
`Patch = "26.20"` → 182 pro games / 1,820 player rows (LCK Academy, LCP Wildcard, EMEA Masters, VCS and others),
collected 17:01 UTC with 4 calls (2-minute spacing after an earlier rate-limit refusal). Player names are not
requested. Used only as a check on the solo-queue pairs (`data/pro_participants.csv`).

## Graph construction and every manual decision

| Choice | Default | Why / alternative |
|---|---|---|
| Node | champion (173) | |
| Edge | two champions on the same team in the same game | undirected |
| Edge set | **E-role**: bot lane (BOTTOM–UTILITY), JUNGLE–MIDDLE, JUNGLE–TOP, JUNGLE–BOTTOM | named alternative **E-all** (all 10 teammate pairs) shares 0/3 of the top 3 and puts 2 non-interacting pairs (e.g. Mid–Bot) in its top 5 |
| Weight | synergy lift = pair WR − σ(logit WR_a + logit WR_b), percentage points | raw co-pick count is shown next to it: it ranks meta pairs first (Lulu + Yunara, 393 games, −0.4 pp); 0 of its top 5 are in the lift top 5 |
| Shrinkage | individual WR: Beta(10, 10) prior; pair: prior worth 20 games at the expected WR, so lift = (wins − n·expected)/(n + 20) | turned off in robustness check 5 |
| Pruning | pairs with ≥ 30 games together: 8,787 → 638 E-role edges | 20 / 50 in check 1 |
| Ban value | lift (pp) × pair games / matches | "worth a ban" = strong and likely to be picked |
| CI | 200 bootstrap resamples of matches, individual WRs recomputed in every resample, 5th–95th percentile (seed 7) | |
| Ban list | top 3 by ban value among pairs whose CI is above 0 **and** whose lift is positive on SEA and on KR separately (≥ 10 games on each) | the replication guard against testing 638 pairs at once |
| Node metrics | pick rate, WR, weighted degree on the positive-lift graph, betweenness (unweighted) on the positive-lift graph; "hub" = most CI-and-replicated edges | |
| Pro check | same E-role pair rule on the 182 Leaguepedia games; Leaguepedia champion names mapped to Riot names | |

## Robustness (`out/robustness.md`, `out/robustness.csv`, `out/permutation_null.csv`)

1. Minimum games 20 / 30 / 50: all 3 ban-list pairs stay in the top 5 by ban value (3/3 each).
2. E-all instead of E-role: 2 of 3 stay in the top 5.
3. Bootstrap: 43 of 638 pairs have the whole 90% CI above 0.
4. Server and tier splits: lift of all 3 pairs is positive on SEA, on KR, in Challenger+GM-sourced and in
   Master-sourced matches.
5. Shrinkage off: 3/3 stay in the top 5.
6. Permutation null (winners re-drawn at random in every match, 20 rounds, 100 bootstraps each): CI-above-0 pairs
   mean 36.0, max 46 (observed 43); replicated mean 23.5, max 32 (observed 30); most edges on one champion mean 4.0,
   max 6 (observed 7, Lee Sin). Pair counts are within chance; the hub is above every null round.

No single pair survives a Bonferroni correction over 638 pairs (bootstrap z ≤ 2.9). This is why the
recommendation rests on the hub rather than on any one pair.

## Limitations that would change the recommendation

- Solo-queue synergy may not carry into coordinated 5-stack play; the pro check is small (Lee Sin + Twisted Fate was
  not played in pro on 26.20; Caitlyn + Karma won 2 of 12).
- KR players are not Thai; SEA alone agrees in direction but has fewer games per pair.
- If the 26.21 re-run (21 Oct 2026) shows the Lee Sin hub at the random level, ban by win rate instead.

## Outputs

`data/matches.csv`, `data/participants.csv` (no player ids), `data/pro_participants.csv`, `out/pairs.csv` (E-role
edges ≥ 30 games with CIs, z, Bonferroni p, per-server lifts, pro record), `out/pairs_all.csv` (E-all),
`out/champions.csv`, `out/robustness.csv`, `out/robustness.md`, `out/permutation_null.csv`, `out/summary.json`,
`out/figure.png/svg`.
