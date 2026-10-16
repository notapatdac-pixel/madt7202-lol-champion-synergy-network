"""Step 4 - one readable figure: the positive-synergy network, plus raw co-pick vs lift as an inset table.

Left: champions in the top 25 positive-synergy edges (E-role, >= 30 games), on a circle grouped by primary role.
Node colour = role, node area = pick rate, edge width = lift. The top-3 ban-value pairs are orange and labelled.
Right: top 5 by raw co-pick count vs top 5 by lift - the visual test of the flip condition.
-> out/figure.png / .svg (placed in the PDF at exactly FIG_W x FIG_H cm, so font sizes are true points)
"""
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import core  # noqa: E402

CM = 1 / 2.54
FIG_W, FIG_H = 18.0, 7.75
N_EDGES = 20
ORANGE, NAVY, INK, INK2, MUTED = "#ef6a24", "#2e3192", "#1f1f1f", "#4a4a4a", "#8a8984"
ROLE_COL = {"TOP": "#2e3192", "JUNGLE": "#2f855a", "MIDDLE": "#6b4fbb", "BOTTOM": "#0e7490", "UTILITY": "#a23b72"}
ROLE_NAME = {"TOP": "Top", "JUNGLE": "Jungle", "MIDDLE": "Mid", "BOTTOM": "Bot", "UTILITY": "Support"}
HALO = [pe.withStroke(linewidth=2.4, foreground="white")]
plt.rcParams.update({"font.family": "Arial", "font.size": 9, "svg.fonttype": "none"})


def main():
    k = pd.read_csv(core.OUT / "pairs.csv")
    champ = pd.read_csv(core.OUT / "champions.csv", index_col=0)
    s = json.loads((core.OUT / "summary.json").read_text(encoding="utf-8"))
    ban3 = k[k.ban_list.astype(bool)].sort_values("ban_value", ascending=False)  # top ban value with CI above 0
    solid = k[k.significant.astype(bool) & k.replicates.astype(bool)]  # CI above 0 and positive on both servers
    edges = pd.concat([solid.sort_values("ban_value", ascending=False).head(N_EDGES), ban3]) \
        .drop_duplicates(["a", "b"])
    hub = s["sig_hubs"][0]
    hub_key = next(c for c in champ.index if core.name(c) == hub["champion"])
    null = pd.read_csv(core.OUT / "permutation_null.csv")
    elig = champ[champ.games >= s["params"]["min_games"]]
    hub_wr_rank = int(elig.wr.rank(ascending=False, method="min")[hub_key])
    nodes = sorted(set(edges.a) | set(edges.b),
                   key=lambda c: (core.ROLES.index(champ.loc[c, "primary_role"]), -champ.loc[c, "pick_rate"]))
    gaps = 1.2
    roles = [champ.loc[c, "primary_role"] for c in nodes]
    slots, pos_s, prev = 0.0, [], None
    for r in roles:
        if prev is not None and r != prev:
            slots += gaps
        pos_s.append(slots)
        slots += 1
        prev = r
    total = slots + gaps
    cx, cy, R = 4.6, FIG_H / 2 - 0.13, 2.58
    ang = {c: math.pi / 2 - 2 * math.pi * p / total for c, p in zip(nodes, pos_s)}
    xy = {c: (cx + R * math.cos(a), cy + R * math.sin(a)) for c, a in ang.items()}

    fig = plt.figure(figsize=(FIG_W * CM, FIG_H * CM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    top_keys = set(zip(ban3.a, ban3.b))
    lmax = edges.lift_pp.max()
    for r in edges.sort_values("lift_pp").itertuples():
        hot = (r.a, r.b) in top_keys
        (x0, y0), (x1, y1) = xy[r.a], xy[r.b]
        ax.plot([x0, x1], [y0, y1], color=ORANGE if hot else "#9aa0b4", alpha=0.95 if hot else 0.55,
                lw=0.6 + 3.2 * r.lift_pp / lmax, zorder=3 if hot else 1, solid_capstyle="round")
    for i, r in enumerate(ban3.itertuples()):
        (x0, y0), (x1, y1) = xy[r.a], xy[r.b]
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"#{i + 1}", color=ORANGE, fontsize=9, fontweight="bold",
                ha="center", va="center", zorder=6, path_effects=HALO)
    pmax = champ.pick_rate.max()
    stagger = 0
    for c in nodes:
        x, y = xy[c]
        role = champ.loc[c, "primary_role"]
        ax.scatter([x], [y], s=25 + 230 * champ.loc[c, "pick_rate"] / pmax, color=ROLE_COL.get(role, MUTED),
                   edgecolors=ORANGE if c == hub_key else "white", linewidths=2.2 if c == hub_key else 0.8,
                   zorder=4)
        a = ang[c]
        centred = abs(math.cos(a)) <= 0.45  # labels above / below the circle: alternate the distance
        stagger = (stagger + 1) % 2 if centred else 0
        off = 0.3 + (0.4 if centred and stagger else 0)
        lx, ly = cx + (R + off) * math.cos(a), cy + (R + off) * math.sin(a)
        ax.text(lx, ly, core.name(c), fontsize=9 if c == hub_key else 8.5, color=INK, zorder=5, path_effects=HALO,
                fontweight="bold" if c == hub_key else "normal",
                ha="left" if math.cos(a) > 0.45 else ("right" if math.cos(a) < -0.45 else "center"),
                va="bottom" if math.sin(a) > 0.8 else ("top" if math.sin(a) < -0.8 else "center"))
    ax.text(0.15, FIG_H - 0.25, f"{N_EDGES} strongest edges by ban value: CI above 0, positive on SEA and KR",
            fontsize=8.5, color=MUTED, va="center")
    # role legend, bottom-left corner (clear of the circle)
    spots = [(0.2, 0.62), (1.0, 0.62), (2.15, 0.62), (0.2, 0.28), (1.0, 0.28)]
    for r, (lx, ly) in zip(core.ROLES, spots):
        ax.scatter([lx], [ly], s=28, color=ROLE_COL[r], edgecolors="white")
        ax.text(lx + 0.15, ly, ROLE_NAME[r], fontsize=8.5, color=INK2, va="center")
    ax.text(0.15, FIG_H - 0.6, "area = pick rate, width = lift", fontsize=8.5, color=MUTED, va="center")

    # inset tables: the ban list with CIs, the hub, then raw co-pick vs lift
    x0, y = 9.75, FIG_H - 0.35
    ax.text(x0, y, "Ban list: top ban value, 90% CI above 0", fontsize=9, fontweight="bold", color=ORANGE,
            va="center")
    ax.text(17.85, y, "games   lift", fontsize=8.5, color=MUTED, va="center", ha="right")
    y -= 0.37
    for i, r in enumerate(ban3.itertuples(), 1):
        ax.text(x0, y, f"#{i} {core.name(r.a)} + {core.name(r.b)} ({r.roles})", fontsize=9, color=INK, va="center")
        ax.text(16.55, y, f"{r.games:,}", fontsize=9, color=INK2, va="center", ha="right")
        ax.text(17.85, y, f"{r.lift_pp:+.1f}", fontsize=9, color=INK2, va="center", ha="right")
        y -= 0.34
    ci = ", ".join(f"#{i} {r.ci_lo:+.1f} to {r.ci_hi:+.1f}" for i, r in enumerate(ban3.itertuples(), 1))
    pro = ", ".join(f"#{i} " + (f"{int(r.pro_wins)} of {int(r.pro_games)}" if r.pro_games else "not played")
                    for i, r in enumerate(ban3.itertuples(), 1))
    lines = [f"90% CI: {ci}.", f"Pro games won on 26.20: {pro}.",
             f"CI above 0: {s['significant_pairs']} of {s['edges']['role_after']} pairs (random: mean "
             f"{null.ci_above_0.mean():.0f}, max {int(null.ci_above_0.max())}).",
             f"Hub {hub['champion']}: {hub['edges']} of {s['significant_and_replicated']} solid edges (random max "
             f"{int(null.max_hub_edges.max())});",
             f"betweenness {champ.loc[hub_key, 'betweenness']:.2f}; own win rate rank {hub_wr_rank} of {len(elig)}."]
    for ln in lines:
        ax.text(x0, y, ln, fontsize=8.5, color=INK2, va="center")
        y -= 0.33
    y -= 0.12
    for title, rows, col in (("Top 5 by raw co-pick count", s["top_copick"], NAVY),
                             (f"Top 5 by synergy lift (≥ {s['params']['min_games']} games)", s["top_lift"], NAVY)):
        ax.text(x0, y, title, fontsize=9, fontweight="bold", color=col, va="center")
        ax.text(17.85, y, "games   lift", fontsize=8.5, color=MUTED, va="center", ha="right")
        y -= 0.35
        for i, r in enumerate(rows, 1):
            ax.text(x0, y, f"{i}. {r['pair']}", fontsize=9, color=INK, va="center")
            ax.text(16.55, y, f"{r['games']:,}", fontsize=9, color=INK2, va="center", ha="right")
            ax.text(17.85, y, f"{r['lift_pp']:+.1f}", fontsize=9, color=INK2, va="center", ha="right")
            y -= 0.315
        y -= 0.1
    ax.plot([9.45, 9.45], [0.3, FIG_H - 0.3], color="#c9ccd6", lw=0.6)

    core.OUT.mkdir(exist_ok=True)
    fig.savefig(core.OUT / "figure.png", dpi=300)
    fig.savefig(core.OUT / "figure.svg")
    print("saved", core.OUT / "figure.png", "nodes", len(nodes), "edges", len(edges))


if __name__ == "__main__":
    main()
