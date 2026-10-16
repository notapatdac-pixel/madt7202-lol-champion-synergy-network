"""Step 3 - does the ban list survive other choices? -> out/robustness.csv, out/robustness.md
The ban list = top 3 by ban value among E-role pairs (>= 30 games) whose bootstrap 90% CI is above 0.
1 minimum games 20 / 30 / 50; 2 E-role vs E-all; 3 bootstrap 90% CI (200 match resamples), against the number of
pairs expected above 0 by chance; 4 server split (SEA vs KR) and tier split (matches reached from Challenger/Grandmaster vs Master players);
5 shrinkage on vs off. Checks 1, 2, 5 count how many ban-list pairs stay in that variant's top 5 by ban value.
"""
import json

import numpy as np

import pandas as pd

import core


def passing(m, p, k, reps):
    """Counts for the ban-list filter on (m, p): pairs with the CI above 0, those that also replicate on every
    server (>= 10 games each), and the most such edges on one champion."""
    boot = core.bootstrap(p, m, list(zip(k.a, k.b)), "role", reps)
    sig = np.array([np.percentile(boot[t], 5) > 0 for t in zip(k.a, k.b)])
    rep = np.ones(len(k), bool)
    for sv in sorted(m.server.unique()):
        ids = set(m.match_id[m.server == sv])
        e, _ = core.pairs(p[p.match_id.isin(ids)], len(ids), "role", 0)
        e = e.set_index(["a", "b"])
        rep &= np.array([e.lift_pp.get(t, -1) > 0 and e.games.get(t, 0) >= 10 for t in zip(k.a, k.b)])
    g = k[sig & rep]
    hub = int(pd.concat([g.a, g.b]).value_counts().max()) if len(g) else 0
    return int(sig.sum()), int((sig & rep).sum()), hub


def permutation_null(m, p, rounds=20, reps=100, seed=11):
    """Null world: in every match the winner is re-drawn at random (who played with whom is kept), 20 times."""
    rng = np.random.default_rng(seed)
    mid = {x: i for i, x in enumerate(m.match_id)}
    pm = p.match_id.map(mid).to_numpy()
    out = []
    for _ in range(rounds):
        flip = rng.random(len(m)) < 0.5
        q = p.assign(win=p.win.to_numpy() ^ flip[pm])
        _, k = core.pairs(q, len(m), "role", 30)
        out.append(passing(m, q, k, reps))
    return np.array(out)


def names(k, n=3):
    return [f"{core.name(a)} + {core.name(b)}" for a, b in zip(k.a.head(n), k.b.head(n))]


def main():
    m, p = core.load()
    n = len(m)
    s = json.loads((core.OUT / "summary.json").read_text(encoding="utf-8"))
    ban = pd.DataFrame(s["ban_list"])
    base = [(a, b) for a, b in zip(ban.a, ban.b)] if len(ban) else []
    base_names = [f"{core.name(a)} + {core.name(b)}" for a, b in base]
    rows = []

    def add(check, variant, k):
        top5 = set(zip(k.a.head(5), k.b.head(5)))
        rows.append({"check": check, "variant": variant, "pairs_kept": len(k), "top3": "; ".join(names(k)),
                     "stays": sum(t in top5 for t in base), "of": len(base),
                     "note": "ban-list pairs in this variant's top 5 by ban value"})

    champ = core.champions(p, n)
    for g in (20, 30, 50):
        add("1", f"min games {g}", core.pairs(p, n, "role", g, champ=champ)[1])
    add("2", "E-all (all 10 teammate pairs)", core.pairs(p, n, "all", 30, champ=champ)[1])
    rows.append({"check": "3", "variant": "bootstrap 200x, 90% CI of lift", "pairs_kept": s["edges"]["role_after"],
                 "top3": "; ".join(f"{r.pair} [{r.ci_lo:+.1f}, {r.ci_hi:+.1f}]" for r in ban.itertuples()),
                 "stays": s["significant_pairs"], "of": s["edges"]["role_after"],
                 "note": f"pairs with the whole CI above 0; {s['significant_by_chance']} expected by chance"})
    hi = m.source_tier.isin(["CHALLENGER", "GRANDMASTER"])
    splits = [(f"{sv} server", m.server == sv) for sv in sorted(m.server.unique())] if m.server.nunique() > 1 else []
    splits += [("Challenger+GM-sourced", hi), ("Master-sourced", ~hi)]
    for label, mask in splits:
        ids = set(m.match_id[mask])
        e, _ = core.pairs(p[p.match_id.isin(ids)], len(ids), "role", 0)
        e = e.set_index(["a", "b"])
        vals = [(e.lift_pp.get(t, float("nan")), int(e.games.get(t, 0))) for t in base]
        rows.append({"check": "4", "variant": f"{label} matches ({len(ids)})", "pairs_kept": len(e),
                     "top3": "; ".join(f"{nm} {v:+.1f} pp (n={g})" for nm, (v, g) in zip(base_names, vals)),
                     "stays": sum(v > 0 for v, _ in vals), "of": len(base),
                     "note": "ban-list pairs with positive lift in this half"})
    add("5", "shrinkage off (raw win rates, no pair prior)", core.pairs(p, n, "role", 30, shrink=False)[1])
    null = permutation_null(m, p)
    hub = s["sig_hubs"][0] if s["sig_hubs"] else {"champion": "-", "edges": 0}
    obs = (s["significant_pairs"], s["significant_and_replicated"], hub["edges"])
    rows.append({"check": "6", "variant": "permutation null: winners re-drawn at random, 20 rounds",
                 "pairs_kept": s["edges"]["role_after"],
                 "top3": f"observed {obs[0]} / {obs[1]} / {obs[2]} (CI>0 / +replicated / {hub['champion']} edges); "
                         f"null mean {null[:, 0].mean():.1f} / {null[:, 1].mean():.1f} / {null[:, 2].mean():.1f}, "
                         f"null max {null[:, 0].max()} / {null[:, 1].max()} / {null[:, 2].max()}",
                 "stays": int(sum(obs[i] > null[:, i].max() for i in range(3))), "of": 3,
                 "note": "observed counts above every null round"})
    pd.DataFrame(null, columns=["ci_above_0", "replicated", "max_hub_edges"]).to_csv(
        core.OUT / "permutation_null.csv", index=False)

    t = pd.DataFrame(rows)
    t.to_csv(core.OUT / "robustness.csv", index=False, encoding="utf-8")
    md = ["# Robustness checks", "", f"Ban list (E-role, >= 30 games, shrunk, CI above 0): {'; '.join(base_names)}.",
          ""]
    md += [f"- **{r.check} {r.variant}**: {r.stays} of {r.of} {r.note}. Top 3 / detail: {r.top3} "
           f"({r.pairs_kept} pairs)" for r in t.itertuples()]
    (core.OUT / "robustness.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
