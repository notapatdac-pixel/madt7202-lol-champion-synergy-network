"""Step 2 - synergy network, node metrics, ban value, bootstrap CIs and the E-role vs E-all comparison.
Outputs: data/matches.csv, data/participants.csv, out/pairs.csv, out/pairs_all.csv, out/champions.csv,
out/summary.json
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import norm

import core

TOP = 5
REPS = 200
REPL_MIN = 10  # games a pair needs on each server for the replication check


def label(r):
    return f"{core.name(r.a)} + {core.name(r.b)}"


def hubs(g, n=3):
    """Champions on the most significant-and-replicated synergy edges (banning one removes all its edges)."""
    deg = pd.concat([g.a, g.b]).value_counts().head(n)
    return [{"champion": core.name(c), "edges": int(v),
             "partners": [core.name(o) for o in sorted(set(g[g.a == c].b) | set(g[g.b == c].a))]}
            for c, v in deg.items()]


def main():
    core.OUT.mkdir(exist_ok=True)
    n_kept = core.build_tables()
    m, p = core.load()
    n = len(m)
    d = core.DEFAULTS
    champ = core.champions(p, n)
    e_role, k_role = core.pairs(p, n, "role", d["min_games"], champ=champ)
    e_all, k_all = core.pairs(p, n, "all", d["min_games"], champ=champ)
    nodes, G = core.node_metrics(champ, k_role)

    # bootstrap every kept pair: 90% CI of the shrunk lift; only pairs whose whole CI is above 0 are findings
    boot = core.bootstrap(p, m, list(zip(k_role.a, k_role.b)), "role", REPS)
    k_role["ci_lo"] = [np.percentile(boot[(a, b)], 5) for a, b in zip(k_role.a, k_role.b)]
    k_role["ci_hi"] = [np.percentile(boot[(a, b)], 95) for a, b in zip(k_role.a, k_role.b)]
    # many pairs are tested at once: z from the bootstrap spread, one-sided p, Bonferroni over all kept pairs
    k_role["z"] = k_role.lift_pp / [boot[(a, b)].std(ddof=1) for a, b in zip(k_role.a, k_role.b)]
    k_role["p_bonferroni"] = np.minimum(1, norm.sf(k_role.z) * len(k_role))
    k_role["significant"] = k_role.ci_lo > 0
    # replication guard against the many pairs tested: lift must also be positive on each server on its own
    for sv in sorted(m.server.unique()):
        ids = set(m.match_id[m.server == sv])
        e_sv, _ = core.pairs(p[p.match_id.isin(ids)], len(ids), "role", 0)
        e_sv = e_sv.set_index(["a", "b"])
        k_role[f"lift_{sv}"] = [e_sv.lift_pp.get(t, np.nan) for t in zip(k_role.a, k_role.b)]
        k_role[f"games_{sv}"] = [int(e_sv.games.get(t, 0)) for t in zip(k_role.a, k_role.b)]
    sv_cols = [c for c in k_role.columns if c.startswith("lift_") and c not in ("lift_pp", "lift_raw_pp", "lift_rank")]
    g_cols = [c.replace("lift_", "games_") for c in sv_cols]
    k_role["replicates"] = (k_role[sv_cols] > 0).all(axis=1) & (k_role[g_cols] >= REPL_MIN).all(axis=1)
    # the ban list: top ban value among pairs with the CI above 0 that also replicate on every server
    ban = k_role[k_role.significant & k_role.replicates].head(3)
    k_role["ban_list"] = k_role.set_index(["a", "b"]).index.isin(ban.set_index(["a", "b"]).index)
    # second source: the same pairs in professional games on the patch (Leaguepedia)
    pro = core.pro_participants(champ.index)
    rec_pro = core.pro_pair_record(pro, list(zip(k_role.a, k_role.b)))
    k_role["pro_games"] = [rec_pro.get(t, (0, 0))[0] for t in zip(k_role.a, k_role.b)]
    k_role["pro_wins"] = [rec_pro.get(t, (0, 0))[1] for t in zip(k_role.a, k_role.b)]
    ban = k_role[k_role.ban_list].copy()
    k_role.assign(pair=k_role.apply(label, axis=1)).round(5).to_csv(core.OUT / "pairs.csv", index=False)
    k_all.assign(pair=k_all.apply(label, axis=1)).round(5).to_csv(core.OUT / "pairs_all.csv", index=False)
    nodes.round(5).to_csv(core.OUT / "champions.csv", encoding="utf-8")

    def rec(df, cols=("roles", "games", "lift_pp", "lift_raw_pp", "expected", "wr_pair", "pick_rate", "ban_value",
                      "copick_rank", "lift_rank", "ban_rank")):
        cols = [c for c in cols if c in df.columns]
        return [dict(pair=label(r), a=r.a, b=r.b, **{c: getattr(r, c) for c in cols}) for r in df.itertuples()]

    # flip condition: are the top synergy pairs just pairs of the highest-win-rate champions?
    eligible = nodes[nodes.games >= d["min_games"]]
    wr_rank = eligible.wr.rank(ascending=False, method="min")
    top3 = ban if len(ban) else k_role.head(3)
    members = list(top3.a) + list(top3.b)
    top10_wr = set(wr_rank[wr_rank <= 10].index)
    best_wr_pairs = k_role[k_role.a.isin(top10_wr) & k_role.b.isin(top10_wr)]
    most_picked = champ.pick_rate.idxmax()
    top_lift = k_role.sort_values("lift_pp", ascending=False).head(10)
    copick = e_role.sort_values("games", ascending=False).head(TOP)
    lift5 = k_role.sort_values("lift_pp", ascending=False).head(TOP)
    meta = {f.stem.replace("collection_meta_", ""): json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(core.DATA.glob("collection_meta_*.json"))}  # sg2, kr, pro
    tiers = m.source_tier.value_counts().to_dict()
    summary = {
        "collection": {src: {k: v for k, v in mm.items() if k != "runs"} for src, mm in meta.items()},
        "runs": {src: mm.get("runs", []) for src, mm in meta.items()}, "matches": n, "kept_in_cache": n_kept, "dropped_other_servers": int(n_kept - n),
        "api_calls": {src: sum(sum((r.get("calls") or r.get("calls_lower_bound") or {}).values())
                               for r in mm.get("runs", [])) for src, mm in meta.items() if src != "pro"},
        "patch_versions": m.game_version.str.split(".").str[:2].str.join(".").value_counts().to_dict(),
        "first_game_utc": m.game_start_utc.min(), "last_game_utc": m.game_start_utc.max(),
        "tiers": tiers, "params": d, "prior_wr": core.PRIOR_WR, "prior_pair": core.PRIOR_PAIR,
        "champions": int(len(champ)), "champions_min_games": int(len(eligible)),
        "missing_position_rows": int((p.team_position == "").sum()),
        "edges": {"role_before": int(len(e_role)), "role_after": int(len(k_role)),
                  "all_before": int(len(e_all)), "all_after": int(len(k_all)),
                  "role_positive": int((k_role.lift_pp > 0).sum()), "all_positive": int((k_all.lift_pp > 0).sum()),
                  "positive_graph_nodes": G.number_of_nodes(), "positive_graph_edges": G.number_of_edges()},
        "top_ban_role": rec(k_role.head(TOP), ("roles", "games", "lift_pp", "lift_raw_pp", "expected", "wr_pair",
                                               "pick_rate", "ban_value", "copick_rank", "lift_rank", "ban_rank",
                                               "ci_lo", "ci_hi")),
        "ban_list": rec(ban, ("roles", "games", "lift_pp", "lift_raw_pp", "expected", "wr_pair", "pick_rate",
                              "ban_value", "copick_rank", "lift_rank", "ban_rank", "ci_lo", "ci_hi", "z", "p_bonferroni", "pro_games", "lift_SG2", "lift_KR", "games_SG2", "games_KR",
                              "pro_wins")),
        "servers": m.server.value_counts().to_dict(),
        "pro": None if pro is None else {
            "games": int(pro.match_id.nunique()), "team_games": int(pro.groupby(["match_id", "team_id"]).ngroups),
            "unmatched_champions": sorted(set(pro.champion_name) - set(champ.index)),
            "kept_pairs_seen_in_pro": int((k_role.pro_games > 0).sum()),
            "significant_pairs_seen_in_pro": int((k_role[k_role.significant].pro_games > 0).sum())},
        "significant_pairs": int(k_role.significant.sum()),
        "significant_and_replicated": int((k_role.significant & k_role.replicates).sum()),
        "bonferroni_survivors": [label(r) for r in k_role[k_role.p_bonferroni < 0.05].itertuples()],
        "sig_hubs": hubs(k_role[k_role.significant & k_role.replicates]),
        "server_lift_cols": sv_cols, "replication_min_games": REPL_MIN,
        "significant_by_chance": round(0.05 * len(k_role), 1),  # one-sided 5% tail of a 90% CI under no synergy
        "top_ban_all": rec(k_all.head(TOP)),
        "role_vs_all_top3_shared": len({label(r) for r in k_role.head(3).itertuples()}
                                       & {label(r) for r in k_all.head(3).itertuples()}),
        "role_vs_all_top5_shared": len({label(r) for r in k_role.head(TOP).itertuples()}
                                       & {label(r) for r in k_all.head(TOP).itertuples()}),
        "all_top5_role_interacting": int(k_all.head(TOP).role_interacting.sum()),
        "top_copick": rec(copick, ("roles", "games", "lift_pp")),
        "top_lift": rec(lift5, ("roles", "games", "lift_pp")),
        "copick_top5_in_lift_top5": len({label(r) for r in copick.itertuples()} & {label(r) for r in lift5.itertuples()}),
        "flip": {"top3_members_wr_rank": {core.name(c): int(wr_rank.get(c, -1)) for c in members},
                 "top3_members_in_top10_wr": int(sum(c in top10_wr for c in members)),
                 "pairs_of_top10_wr_kept": int(len(best_wr_pairs)),
                 "pairs_of_top10_wr_in_top10_lift": int(len(set(zip(best_wr_pairs.a, best_wr_pairs.b))
                                                            & set(zip(top_lift.a, top_lift.b))))},
        "most_picked": {"champion": core.name(most_picked), "pick_rate": float(champ.pick_rate.max()),
                        "wr": float(champ.wr.loc[most_picked]),
                        "in_top10_lift_pair": bool(most_picked in set(top_lift.a) | set(top_lift.b)),
                        "best_lift_pp": float(k_role[(k_role.a == most_picked) | (k_role.b == most_picked)]
                                              .lift_pp.max()) if most_picked in set(k_role.a) | set(k_role.b) else None},
        "hubs": [{"champion": core.name(c), "strong_partners": int(r.strong_partners),
                  "weighted_degree_pp": float(r.weighted_degree_pp), "betweenness": float(r.betweenness),
                  "pick_rate": float(r.pick_rate), "role": r.primary_role}
                 for c, r in nodes.head(5).iterrows()],
        "top_betweenness": [{"champion": core.name(c), "betweenness": float(v)}
                            for c, v in nodes.betweenness.sort_values(ascending=False).head(3).items()],
    }
    (core.OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")
    pd.set_option("display.width", 220)
    show = ["a", "b", "roles", "games", "lift_pp", "lift_raw_pp", "pick_rate", "ban_value", "copick_rank", "ci_lo",
            "ci_hi"]
    print("E-role top ban value:\n", k_role.head(8)[show].round(3).to_string())
    print("E-all top ban value:\n", k_all.head(8)[show[:-2]].round(3).to_string())
    print("raw co-pick top:\n", copick[["a", "b", "roles", "games", "lift_pp"]].round(2).to_string())
    print("ban list:\n", ban[["a", "b", "roles", "games", "lift_pp", "ci_lo", "ci_hi", "pro_games", "pro_wins"]]
          .round(2).to_string())
    print(json.dumps({k: summary[k] for k in ("matches", "servers", "pro", "significant_pairs",
                                              "significant_by_chance", "api_calls", "tiers", "patch_versions",
                                              "champions", "edges",
                                              "role_vs_all_top3_shared", "copick_top5_in_lift_top5", "flip",
                                              "most_picked", "hubs", "top_betweenness")}, indent=1, default=float))


if __name__ == "__main__":
    main()
