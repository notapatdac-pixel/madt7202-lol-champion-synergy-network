"""Shared logic: the champion synergy network.

Node = champion. Edge = two champions on the same team in the same match (undirected). Weight = synergy lift:
the pair's win rate minus the win rate expected from the two champions alone,
    expected = sigma(logit(WR_a) + logit(WR_b))      (each WR relative to 50%; no synergy -> lift 0)
Shrinkage: individual WR uses a Beta(10, 10) prior (10 wins + 10 losses added, i.e. pulled toward 50%); the pair's
WR uses a prior centred on its expected WR worth K = 20 games, so lift = (wins - n * expected) / (n + K) shrinks
small pairs toward 0. Pairs need >= MIN_GAMES games together.
Edge sets: E-role (default) counts only role-interacting teammates (bot lane, jungle-mid, jungle-top, jungle-bot);
E-all (named alternative) counts all 10 teammate pairs.
Ban value = lift (pp) x pair pick rate (games together / matches): strong AND likely to be picked.
"""
import json
import pathlib

import networkx as nx
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA, RAW, OUT, REPORT = ROOT / "data", ROOT / "data" / "raw", ROOT / "out", ROOT / "report"
ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
ROLE_PAIRS = {frozenset(p) for p in [("BOTTOM", "UTILITY"), ("JUNGLE", "MIDDLE"), ("JUNGLE", "TOP"),
                                     ("JUNGLE", "BOTTOM")]}
SHORT = {"TOP": "Top", "JUNGLE": "Jg", "MIDDLE": "Mid", "BOTTOM": "Bot", "UTILITY": "Sup"}
PRIOR_WR = 10  # Beta(10, 10) on individual win rates
PRIOR_PAIR = 20  # pseudo-games at the expected WR for a pair
DEFAULTS = {"min_games": 30, "mode": "role", "shrink": True}
DISPLAY = {"MonkeyKing": "Wukong", "Chogath": "Cho'Gath", "Kaisa": "Kai'Sa", "Khazix": "Kha'Zix",
           "KogMaw": "Kog'Maw", "Velkoz": "Vel'Koz", "RekSai": "Rek'Sai", "KSante": "K'Sante", "Belveth": "Bel'Veth",
           "Kogmaw": "Kog'Maw", "FiddleSticks": "Fiddlesticks", "Leblanc": "LeBlanc", "JarvanIV": "Jarvan IV",
           "LeeSin": "Lee Sin", "MasterYi": "Master Yi", "MissFortune": "Miss Fortune", "TwistedFate": "Twisted Fate",
           "XinZhao": "Xin Zhao", "AurelionSol": "Aurelion Sol", "DrMundo": "Dr. Mundo", "TahmKench": "Tahm Kench",
           "RenataGlasc": "Renata Glasc", "Nunu": "Nunu & Willump"}


def name(c):
    return DISPLAY.get(c, c)


def build_tables():
    """Kept matches in the stripped cache -> data/matches.csv and data/participants.csv (no player identifiers)."""
    ms, ps = [], []
    for f in sorted(RAW.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # a file the collector is still writing
            continue
        if not m.get("kept"):
            continue
        ms.append({**{k: m[k] for k in ("match_id", "game_version", "game_duration", "game_start_utc",
                                        "source_tier")}, "server": m["match_id"].split("_")[0]})
        ps += [{"match_id": m["match_id"], **p} for p in m["participants"]]
    pd.DataFrame(ms).to_csv(DATA / "matches.csv", index=False, encoding="utf-8")
    pd.DataFrame(ps).to_csv(DATA / "participants.csv", index=False, encoding="utf-8")
    return len(ms)


SERVERS_KEPT = ("SG2", "KR")  # the frame; a few SEA players' histories also hold VN2 games, which are dropped


def load():
    m = pd.read_csv(DATA / "matches.csv")
    m = m[m.server.isin(SERVERS_KEPT)]
    p = pd.read_csv(DATA / "participants.csv", keep_default_na=False)
    p = p[p.match_id.isin(set(m.match_id))]
    p["win"] = p.win.astype(str).str.lower().isin(["true", "1"])
    return m.reset_index(drop=True), p.reset_index(drop=True)


def logit(p):
    return np.log(p / (1 - p))


def sigma(z):
    return 1 / (1 + np.exp(-z))


def champions(p, n_matches):
    c = p.groupby("champion_name").agg(games=("win", "size"), wins=("win", "sum"))
    c["pick_rate"] = c.games / n_matches
    c["wr_raw"] = c.wins / c.games
    c["wr"] = (c.wins + PRIOR_WR) / (c.games + 2 * PRIOR_WR)
    c["primary_role"] = p.groupby("champion_name").team_position.agg(lambda s: s.value_counts().index[0])
    return c


def pair_rows(p, mode="role"):
    """One row per teammate pair per team-game: (match_id, a, b, role_a, role_b, win), a < b."""
    q = p[["match_id", "team_id", "champion_name", "team_position", "win"]]
    x = q.merge(q, on=["match_id", "team_id"], suffixes=("_a", "_b"))
    x = x[x.champion_name_a < x.champion_name_b]
    if mode == "role":
        ok = [frozenset((r1, r2)) in ROLE_PAIRS for r1, r2 in zip(x.team_position_a, x.team_position_b)]
        x = x[ok]
    return x.rename(columns={"champion_name_a": "a", "champion_name_b": "b", "team_position_a": "role_a",
                             "team_position_b": "role_b", "win_a": "win"})[
        ["match_id", "a", "b", "role_a", "role_b", "win"]]


def pairs(p, n_matches, mode="role", min_games=30, shrink=True, champ=None):
    """Edge table: games together, wins, expected WR, lift (pp, shrunk and raw), ban value, ranks."""
    champ = champions(p, n_matches) if champ is None else champ
    x = pair_rows(p, mode)
    e = x.groupby(["a", "b"]).agg(games=("win", "size"), wins=("win", "sum")).reset_index()
    roles = x.assign(rp=x.role_a + "-" + x.role_b).groupby(["a", "b"]).rp.agg(lambda s: s.value_counts().index[0])
    e = e.merge(roles.rename("role_pair").reset_index(), on=["a", "b"])  # most common roles, e.g. BOTTOM-UTILITY
    e["roles"] = e.role_pair.map(lambda s: "-".join(SHORT.get(r, r or "?") for r in s.split("-")))
    e["role_interacting"] = e.role_pair.map(lambda s: frozenset(s.split("-")) in ROLE_PAIRS)
    wr = champ.wr if shrink else champ.wr_raw.clip(0.01, 0.99)
    e["expected"] = sigma(logit(e.a.map(wr)) + logit(e.b.map(wr)))
    e["wr_pair"] = e.wins / e.games
    e["lift_raw_pp"] = 100 * (e.wr_pair - e.expected)
    e["lift_pp"] = 100 * (e.wins - e.games * e.expected) / (e.games + (PRIOR_PAIR if shrink else 0))
    e["pick_rate"] = e.games / n_matches
    e["ban_value"] = e.lift_pp * e.pick_rate
    e["copick_rank"] = e.games.rank(ascending=False, method="min").astype(int)
    k = e[e.games >= min_games].copy()
    k["lift_rank"] = k.lift_pp.rank(ascending=False, method="min").astype(int)
    k["ban_rank"] = k.ban_value.rank(ascending=False, method="min").astype(int)
    return e, k.sort_values("ban_value", ascending=False)


def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


PRO_ROLE = {"Top": "TOP", "Jungle": "JUNGLE", "Mid": "MIDDLE", "Bot": "BOTTOM", "Support": "UTILITY"}


def pro_participants(champions_seen):
    """Leaguepedia pro games on the patch, champion names mapped to Riot's internal names (Kai'Sa -> Kaisa,
    Wukong -> MonkeyKing) so pairs can be looked up in both sources."""
    f = DATA / "pro_participants.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    to_riot = {norm(name(c)): c for c in champions_seen}
    d["champion_name"] = d.champion.map(lambda c: to_riot.get(norm(c), c))
    d["team_position"] = d.role.map(PRO_ROLE).fillna("")
    d["win"] = d.win.astype(str).str.lower().isin(["yes", "1", "true"])
    d["team_id"] = d.side.astype(str)
    return d.rename(columns={"game_id": "match_id"})[["match_id", "team_id", "champion_name", "team_position", "win"]]


def pro_pair_record(pro, targets, mode="role"):
    """Team-games and wins in pro play for each target pair (same edge rule as the solo-queue network)."""
    if pro is None:
        return {}
    x = pair_rows(pro, mode)
    g = x.groupby(["a", "b"]).win.agg(["size", "sum"])
    return {t: (int(g.loc[t, "size"]), int(g.loc[t, "sum"])) if t in g.index else (0, 0) for t in targets}


def positive_graph(k):
    """Champions joined by kept edges with positive synergy; weight = lift (pp)."""
    G = nx.Graph()
    for r in k[k.lift_pp > 0].itertuples():
        G.add_edge(r.a, r.b, weight=r.lift_pp, games=r.games)
    return G


def node_metrics(champ, k):
    G = positive_graph(k)
    bet = nx.betweenness_centrality(G) if G.number_of_edges() else {}
    t = champ.copy()
    t["strong_partners"] = pd.Series(dict(G.degree())).reindex(t.index).fillna(0).astype(int)
    t["weighted_degree_pp"] = pd.Series(dict(G.degree(weight="weight"))).reindex(t.index).fillna(0)
    t["betweenness"] = pd.Series(bet).reindex(t.index).fillna(0)
    t["wr_rank"] = t.wr.rank(ascending=False, method="min").astype(int)
    return t.sort_values("weighted_degree_pp", ascending=False), G


def bootstrap(p, m, targets, mode="role", reps=200, seed=7):
    """Resample matches with replacement (reps times); shrunk lift (pp) of every target pair in each resample,
    with the individual win rates recomputed inside every resample. Returns {(a, b): array of reps lifts}."""
    rng = np.random.default_rng(seed)
    mid = {k: i for i, k in enumerate(m.match_id)}
    champs = sorted(p.champion_name.unique())
    ic = {c: i for i, c in enumerate(champs)}
    pm, pc, pw = p.match_id.map(mid).to_numpy(), p.champion_name.map(ic).to_numpy(), p.win.to_numpy(float)
    targets = list(targets)
    it = {t: i for i, t in enumerate(targets)}
    x = pair_rows(p, mode)
    key = list(zip(x.a, x.b))
    sel = np.array([k in it for k in key])
    xm = x.match_id.map(mid).to_numpy()[sel]
    xp = np.array([it[k] for k, s in zip(key, sel) if s], dtype=int)
    xw = x.win.to_numpy(float)[sel]
    ta = np.array([ic[a] for a, _ in targets], dtype=int)
    tb = np.array([ic[b] for _, b in targets], dtype=int)
    res = np.empty((reps, len(targets)))
    for r in range(reps):
        w = np.bincount(rng.integers(0, len(m), len(m)), minlength=len(m)).astype(float)
        g = np.bincount(pc, weights=w[pm], minlength=len(champs))
        wn = np.bincount(pc, weights=w[pm] * pw, minlength=len(champs))
        wr = (wn + PRIOR_WR) / (g + 2 * PRIOR_WR)
        n = np.bincount(xp, weights=w[xm], minlength=len(targets))
        wv = np.bincount(xp, weights=w[xm] * xw, minlength=len(targets))
        exp = sigma(logit(wr[ta]) + logit(wr[tb]))
        res[r] = 100 * (wv - n * exp) / (n + PRIOR_PAIR)
    return {t: res[:, i] for i, t in enumerate(targets)}
