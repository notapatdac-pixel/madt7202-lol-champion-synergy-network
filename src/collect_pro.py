"""Step 1b - professional games on the same patch (second source, a sanity check on the solo-queue result).

Leaguepedia Cargo API (lol.fandom.com, content CC BY-SA 3.0), table ScoreboardPlayers joined to ScoreboardGames,
Patch = 26.20: per player-game the game id, tournament page, team, side, role, champion and win. Player names are
not requested. Leaguepedia rate-limits anonymous use hard: the script waits 10 minutes before the first request,
keeps pages 2 minutes apart and waits 5 minutes after each 'ratelimited' answer. -> data/pro_participants.csv, data/collection_meta_pro.json
"""
import datetime as dt
import json
import sys
import time

import pandas as pd
import requests

import core

URL = "https://lol.fandom.com/api.php"
HEADERS = {"User-Agent": "MADT7202-coursework/1.0 (student network-analysis project; cached, low volume)"}
PATCH = "26.20"
PAGE = 500


def query(offset):
    params = {"action": "cargoquery", "format": "json", "limit": PAGE, "offset": offset,
              "tables": "ScoreboardPlayers=SP,ScoreboardGames=SG", "join_on": "SP.GameId=SG.GameId",
              "fields": "SP.GameId=game_id,SG.OverviewPage=tournament,SP.Team=team,SP.Side=side,SP.Role=role,"
                        "SP.Champion=champion,SP.PlayerWin=win,SG.DateTime_UTC=date_utc",
              "where": f'SG.Patch="{PATCH}"', "order_by": "SP.GameId,SP.Side,SP.Role"}
    for attempt in range(8):
        r = requests.get(URL, params=params, headers=HEADERS, timeout=60).json()
        if "cargoquery" in r:
            return [row["title"] for row in r["cargoquery"]]
        time.sleep(300)  # 'ratelimited': wait and retry
    raise RuntimeError(f"Leaguepedia kept refusing: {r}")


def main():
    if (core.DATA / "pro_participants.csv").exists() and "--refresh" not in sys.argv:
        print("cached:", core.DATA / "pro_participants.csv")
        return
    time.sleep(600)  # let an earlier rate-limit window expire
    t0 = dt.datetime.now(dt.timezone.utc)
    rows, offset, calls = [], 0, 0
    while True:
        got = query(offset)
        calls += 1
        rows += got
        print(f"rows {len(rows)}", flush=True)
        if len(got) < PAGE:
            break
        offset += PAGE
        time.sleep(120)
    d = pd.DataFrame(rows)
    d.to_csv(core.DATA / "pro_participants.csv", index=False, encoding="utf-8")
    meta = {"source": URL, "licence": "CC BY-SA 3.0 (Leaguepedia)", "patch": PATCH, "rows": len(d),
            "games": int(d.game_id.nunique()) if len(d) else 0,
            "tournaments": d.tournament.value_counts().to_dict() if len(d) else {},
            "collected_utc": t0.isoformat(timespec="seconds"), "calls": calls}
    (core.DATA / "collection_meta_pro.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
