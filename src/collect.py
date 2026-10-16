"""Step 1 - high-elo ranked solo-queue matches on the current patch from the official Riot Games API (cached).

Frame, per server: league-v4 apex ladders (Challenger, Grandmaster, Master) -> players (PUUIDs kept in memory only)
-> match-v5 match ids (queue 420, since the patch release) -> match details. Players are taken round-robin across
tiers, in a fixed random order within each tier, so an early stop does not leave out a tier. Match ids are
deduplicated; each id remembers the highest tier it was reached from. Servers:
  sg2 / sea  - the SEA server. TH2 no longer exists (th2.api.riotgames.com does not resolve): Riot merged TH2 and
               PH2 into SG2, renamed the SEA server, on 8-9 Jan 2025 (patch 25.S1.1). Thai solo queue is SG2.
  kr / asia  - Korea, the highest-skill solo queue, added for volume at high rank and as a second server to
               check the SEA result.
Riot enforces app rate limits per routing value, so the two servers are collected in parallel by two processes.

Privacy (PDPA / Riot policy): no summoner name, Riot ID or PUUID is written anywhere. Each match is cached in
data/raw/<match_id>.json STRIPPED to: id, version, duration, queue, start time, and per participant team, champion,
position and win. Re-runs read the cache and spend no quota.

Key: RIOT_API_KEY environment variable, else a git-ignored .env file (RIOT_API_KEY=...). Never printed.
Rate limits: read from X-App-Rate-Limit on every response and obeyed (one call under each window), shared by all
worker threads; 429 -> wait Retry-After; timeouts / 5xx -> exponential back-off; 401/403 -> stop.
"""
import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import os
import pathlib
import random
import sys
import threading
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA, RAW = ROOT / "data", ROOT / "data" / "raw"
SERVERS = {"sg2": "sea", "kr": "asia"}  # platform -> match-v5 regional routing
QUEUE, PATCH = 420, "16.20"  # ranked solo/duo; Data Dragon 16.20.1 = patch 26.20
PATCH_START = dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc)  # patch 26.20 release date
LADDERS = {"CHALLENGER": "challengerleagues", "GRANDMASTER": "grandmasterleagues", "MASTER": "masterleagues"}
MIN_DURATION = 300  # seconds; shorter games are remakes
SEED = 7


def api_key():
    key = os.environ.get("RIOT_API_KEY", "").strip()
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("RIOT_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
    if not key:
        sys.exit("STOP: RIOT_API_KEY is missing. Set the environment variable or put RIOT_API_KEY=... in .env")
    return key


class Riot:
    """Requests with the app rate limits obeyed (sliding windows shared by all threads) and back-off."""

    def __init__(self, key):
        self.s = requests.Session()
        self.s.headers.update({"X-Riot-Token": key, "User-Agent": "MADT7202-coursework/1.0"})
        self.limits = [(20, 1.0), (100, 120.0)]  # development-key default until the first response says otherwise
        self.stamps = collections.deque()
        self.calls = collections.Counter()
        self.headers_seen = {}
        self.lock = threading.Lock()

    def _wait(self):
        while True:
            now = time.monotonic()
            while self.stamps and now - self.stamps[0] > max(w for _, w in self.limits):
                self.stamps.popleft()
            delay = 0.0
            for n, w in self.limits:
                recent = [t for t in self.stamps if now - t < w]
                if len(recent) >= n - 1:  # stay one call under each limit
                    delay = max(delay, w - (now - recent[-(n - 1)]) + 0.05)
            if delay <= 0:
                return
            time.sleep(delay)

    def get(self, url, params=None, kind="other"):
        for attempt in range(10):
            with self.lock:  # one thread at a time reserves a slot; the requests themselves run in parallel
                self._wait()
                self.stamps.append(time.monotonic())
                self.calls[kind] += 1
            try:
                r = self.s.get(url, params=params, timeout=30)
            except (requests.Timeout, requests.ConnectionError):
                with self.lock:
                    self.calls["timeouts"] += 1
                time.sleep(min(2 ** attempt, 60))
                continue
            with self.lock:
                for h in ("X-App-Rate-Limit", "X-Method-Rate-Limit"):
                    if h in r.headers:
                        self.headers_seen[f"{h} ({kind})" if "Method" in h else h] = r.headers[h]
                if "X-App-Rate-Limit" in r.headers:
                    self.limits = [(int(n), float(w)) for n, w in
                                   (p.split(":") for p in r.headers["X-App-Rate-Limit"].split(","))]
            if r.status_code == 200:
                return r.json()
            if r.status_code in (401, 403):
                sys.exit(f"STOP: Riot API answered {r.status_code} - the key is missing, invalid or expired.")
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                with self.lock:
                    self.calls["429"] += 1
                time.sleep(float(r.headers.get("Retry-After", 10)) + 1)
                continue
            time.sleep(min(2 ** attempt, 60))  # 5xx: back off
        raise RuntimeError(f"giving up on {url}")


def players(api, platform):
    """Round-robin over tiers, fixed random order inside each tier. Returns [(puuid, tier)] - memory only."""
    rng = random.Random(SEED)
    by_tier = {}
    for tier, path in LADDERS.items():
        d = api.get(f"https://{platform}.api.riotgames.com/lol/league/v4/{path}/by-queue/RANKED_SOLO_5x5",
                    kind="league")
        by_tier[tier] = [e["puuid"] for e in d["entries"] if e.get("puuid")]
    for t in by_tier:
        rng.shuffle(by_tier[t])
    order, i = [], 0
    while any(i < len(v) for v in by_tier.values()):
        order += [(v[i], t) for t, v in by_tier.items() if i < len(v)]
        i += 1
    return order, {t: len(v) for t, v in by_tier.items()}


def strip(m, source_tier):
    i = m["info"]
    return {"match_id": m["metadata"]["matchId"], "game_version": i.get("gameVersion", ""),
            "game_duration": i.get("gameDuration", 0), "queue_id": i.get("queueId"),
            "game_start_utc": dt.datetime.fromtimestamp(i.get("gameStartTimestamp", 0) / 1000, dt.timezone.utc)
            .isoformat(timespec="seconds"), "source_tier": source_tier,
            "early_surrender": any(p.get("gameEndedInEarlySurrender") for p in i["participants"]),
            "participants": [{"team_id": p["teamId"], "champion_name": p["championName"],
                              "team_position": p.get("teamPosition", ""), "win": bool(p["win"])}
                             for p in i["participants"]]}


def keep(m):
    return (m["queue_id"] == QUEUE and m["game_version"].startswith(PATCH + ".") and len(m["participants"]) == 10
            and m["game_duration"] >= MIN_DURATION and not m["early_surrender"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=sorted(SERVERS), default="sg2")
    ap.add_argument("--target", type=int, default=3500, help="kept matches to reach on this server")
    ap.add_argument("--pool", type=float, default=1.15, help="collect target x pool match ids before details")
    ap.add_argument("--workers", type=int, default=3, help="parallel requests (one shared rate limiter)")
    args = ap.parse_args()
    platform, region = args.platform, SERVERS[args.platform]
    prefix = platform.upper() + "_"
    RAW.mkdir(parents=True, exist_ok=True)
    meta_f, ids_f = DATA / f"collection_meta_{platform}.json", DATA / f"match_ids_{platform}.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8")) if meta_f.exists() else {"runs": []}
    t0 = dt.datetime.now(dt.timezone.utc)
    api = Riot(api_key())

    ids = json.loads(ids_f.read_text(encoding="utf-8")) if ids_f.exists() else {}  # match_id -> source tier
    if len(ids) < args.target * args.pool:
        order, meta["players_per_tier"] = players(api, platform)
        rank = {t: i for i, t in enumerate(LADDERS)}
        start = int(PATCH_START.timestamp())
        used = collections.Counter(meta.get("players_sampled_per_tier", {}))
        skip = sum(used.values())  # players already used by an earlier run (same deterministic order)
        for puuid, tier in order[skip:]:
            if len(ids) >= args.target * args.pool:
                break
            got = api.get(f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids",
                          params={"queue": QUEUE, "startTime": start, "start": 0, "count": 100}, kind="match_ids")
            used[tier] += 1
            for mid in got or []:
                if mid not in ids or rank[tier] < rank[ids[mid]]:
                    ids[mid] = tier
            if sum(used.values()) % 25 == 0:
                ids_f.write_text(json.dumps(ids), encoding="utf-8")
                meta["players_sampled_per_tier"] = dict(used)
                print(f"players {sum(used.values())}, match ids {len(ids)}", flush=True)
        ids_f.write_text(json.dumps(ids), encoding="utf-8")
        meta["players_sampled_per_tier"] = dict(used)

    rng = random.Random(SEED)
    todo = sorted(ids)
    rng.shuffle(todo)  # random order, so stopping at the target does not favour one tier
    todo = [mid for mid in todo if not (RAW / f"{mid}.json").exists()]
    kept = sum(1 for f in RAW.glob(f"{prefix}*.json") if json.loads(f.read_text(encoding="utf-8")).get("kept"))
    done = 0

    def fetch(mid):
        m = api.get(f"https://{region}.api.riotgames.com/lol/match/v5/matches/{mid}", kind="match")
        if m is None:
            return False
        s = strip(m, ids[mid])
        s["kept"] = keep(s)
        (RAW / f"{mid}.json").write_text(json.dumps(s), encoding="utf-8")
        return s["kept"]

    try:
        with cf.ThreadPoolExecutor(args.workers) as pool:
            it = iter(todo)
            running = set()
            while True:
                while len(running) < 2 * args.workers and kept + len(running) < args.target:
                    mid = next(it, None)
                    if mid is None:
                        break
                    running.add(pool.submit(fetch, mid))
                if not running:
                    break
                finished, running = cf.wait(running, return_when=cf.FIRST_COMPLETED)
                for f in finished:
                    kept += bool(f.result())
                    done += 1
                    if done % 100 == 0:
                        print(f"details {done}, kept {kept}", flush=True)
    finally:  # the call log is written even if the run stops early
        t1 = dt.datetime.now(dt.timezone.utc)
        meta["runs"].append({"start_utc": t0.isoformat(timespec="seconds"),
                             "end_utc": t1.isoformat(timespec="seconds"), "calls": dict(api.calls),
                             "rate_limit_headers": api.headers_seen, "target": args.target,
                             "workers": args.workers})
        meta.update({"platform": platform, "region": region, "queue": QUEUE, "patch_prefix": PATCH,
                     "patch_start_utc": PATCH_START.isoformat(), "match_ids": len(ids), "kept_matches": kept,
                     "cached_matches": len(list(RAW.glob(f"{prefix}*.json")))})
        meta_f.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "runs"}, indent=1))
    print("this run:", json.dumps(meta["runs"][-1], indent=1))


if __name__ == "__main__":
    main()
