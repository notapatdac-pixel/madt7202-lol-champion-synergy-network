"""Unit tests on small synthetic matches (named test_*): pair building, lift, shrinkage, ban value, privacy strip."""
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import collect  # noqa: E402
import core  # noqa: E402

LINEUP = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def make_matches(n, seed=1):
    """test_ data: champions A..E on team 100 vs F..J on team 200; the A+B duo (TOP+JUNGLE) wins 70%, others 50%."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        blue_win = rng.random() < 0.7
        blue = list("ABCDE") if i % 2 == 0 else list("AKCDE")  # B only in even games
        red = list("FGHIJ")
        for team, champs, w in ((100, blue, blue_win), (200, red, not blue_win)):
            rows += [{"match_id": f"test_{i}", "team_id": team, "champion_name": c, "team_position": r, "win": w}
                     for c, r in zip(champs, LINEUP)]
    return pd.DataFrame(rows)


make_matches.__test__ = False


def test_pair_rows_counts_ten_or_four_pairs_per_team():
    p = make_matches(2)
    assert len(core.pair_rows(p, "all")) == 2 * 2 * 10
    role = core.pair_rows(p, "role")
    assert len(role) == 2 * 2 * 4
    assert {frozenset((a, b)) for a, b in zip(role.role_a, role.role_b)} == core.ROLE_PAIRS


def test_lift_is_zero_without_synergy_and_shrinks_small_samples():
    p = make_matches(400)
    champ = core.champions(p, 400)
    _, k = core.pairs(p, 400, mode="all", min_games=30, champ=champ)
    # the logit model: two 50% champions -> expected 50%; a 60% and a 50% champion -> 60%
    assert abs(core.sigma(core.logit(0.6) + core.logit(0.5)) - 0.6) < 1e-12
    ab = k[(k.a == "A") & (k.b == "B")].iloc[0]
    assert ab.games == 200 and abs(ab.lift_pp) < abs(ab.lift_raw_pp)  # shrinkage pulls toward 0
    assert abs(ab.ban_value - ab.lift_pp * ab.games / 400) < 1e-9


def test_min_games_prunes_rare_pairs():
    p = make_matches(40)
    e, k = core.pairs(p, 40, mode="all", min_games=30)
    assert (k.games >= 30).all() and len(e) > len(k)


def test_bootstrap_matches_point_estimate_on_average():
    p = make_matches(300)
    m = pd.DataFrame({"match_id": p.match_id.unique()})
    _, k = core.pairs(p, len(m), mode="role")
    boot = core.bootstrap(p, m, [("A", "B")], mode="role", reps=100)  # TOP-JUNGLE
    point = k[(k.a == "A") & (k.b == "B")].lift_pp.iloc[0]
    assert abs(np.median(boot[("A", "B")]) - point) < 2.0


def test_strip_drops_player_identifiers():
    raw = {"metadata": {"matchId": "SG2_1", "participants": ["puuid-x"] * 10},
           "info": {"gameVersion": "16.20.1", "gameDuration": 1500, "queueId": 420, "gameStartTimestamp": 0,
                    "participants": [{"puuid": "puuid-x", "riotIdGameName": "someone", "summonerName": "someone",
                                      "teamId": 100, "championName": "Ahri", "teamPosition": "MIDDLE", "win": True}
                                     ] * 10}}
    s = collect.strip(raw, "MASTER")
    text = str(s)
    assert "puuid" not in text and "someone" not in text and collect.keep(s)
    assert not collect.keep({**s, "game_duration": 200})  # remake
