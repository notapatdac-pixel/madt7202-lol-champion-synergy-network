"""Step 5 - the one-page A4 report (reportlab), laid out like the course's Sample C.
Every number is read from data/ and out/, not typed.

Checks after building: exactly 1 page, no text below 10 pt, 1.5 cm margins.
Exits non-zero otherwise - shorten text, never shrink the font. Set AUTHOR and REPO_URL before submitting.
"""
import json
import pathlib
import sys

import pandas as pd
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageTemplate, Paragraph, Table, TableStyle

import core
from figure import FIG_H

AUTHOR = "Notapat Dachanabhirom, Student ID 6810424021"
REPO_URL = "github.com/notapatdac-pixel/madt7202-lol-champion-synergy-network"
MARGIN = 1.5 * cm
MIN_PT = 10
NEXT_PATCH = "21 Oct 2026"  # patch 26.21 (Riot schedule)

FONT_DIR = pathlib.Path("C:/Windows/Fonts")
if (FONT_DIR / "arial.ttf").exists():
    pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "arialbd.ttf")))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold")
    BODY, BOLD = "Body", "Body-Bold"
else:  # same metrics as Arial
    BODY, BOLD = "Helvetica", "Helvetica-Bold"

ORANGE, NAVY = "#ef6a24", "#2e3192"  # Sample C palette
INK, GREY = colors.HexColor("#222222"), colors.HexColor("#555555")
GRID, SHADE = colors.HexColor("#c9ccd6"), colors.HexColor("#eceef5")

body = ParagraphStyle("body", fontName=BODY, fontSize=10, leading=11.4, textColor=INK)
cell = ParagraphStyle("cell", parent=body, leading=11.2)
label = ParagraphStyle("label", parent=cell, fontName=BOLD)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, bulletIndent=1, spaceBefore=0.6)
kicker = ParagraphStyle("kicker", parent=body, fontName=BOLD, fontSize=11, leading=13,
                        textColor=colors.HexColor(ORANGE))
title = ParagraphStyle("title", parent=body, fontName=BOLD, fontSize=12, leading=14, spaceAfter=0.5)
head = ParagraphStyle("head", parent=body, fontName=BOLD, fontSize=10.5, leading=12,
                      textColor=colors.HexColor(NAVY), spaceBefore=2.4, spaceAfter=0.4)
foot = ParagraphStyle("foot", parent=body, textColor=GREY, spaceBefore=3)


def H(n, text):
    return Paragraph(f"<font color='{ORANGE}'>{n}</font>&nbsp;&nbsp;{text}", head)


def table(rows, w0=3.35):
    t = Table([[Paragraph(a, label), Paragraph(b, cell)] for a, b in rows], colWidths=[w0 * cm, 18 * cm - w0 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BOX", (0, 0), (-1, -1), 0.5, GRID), ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),
                           ("BACKGROUND", (0, 0), (0, -1), SHADE),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def bullets(items):
    return [Paragraph(x, bullet, bulletText="\u2022") for x in items]


def d(iso):
    return pd.Timestamp(iso).strftime("%-d %b").lstrip("0") if sys.platform != "win32" else \
        pd.Timestamp(iso).strftime("%d %b").lstrip("0")


def story():
    s = json.loads((core.OUT / "summary.json").read_text(encoding="utf-8"))
    rb = pd.read_csv(core.OUT / "robustness.csv")
    null = pd.read_csv(core.OUT / "permutation_null.csv")
    champ = pd.read_csv(core.OUT / "champions.csv", index_col=0)
    calls = sum(s["api_calls"].values())
    servers = " + ".join(f"{v:,} {'SEA' if k == 'SG2' else k}" for k, v in s["servers"].items())
    pro = s.get("pro") or {"games": 0}
    ed, p = s["edges"], s["params"]
    ban = s["ban_list"]
    b1, b2, b3 = (ban + [None, None, None])[:3]
    cp = s["top_copick"][0]
    mp = s["most_picked"]
    fl = s["flip"]
    hub = s["sig_hubs"][0]
    hk = next(c for c in champ.index if core.name(c) == hub["champion"])
    elig = champ[champ.games >= p["min_games"]]
    hub_rank = int(elig.wr.rank(ascending=False, method="min")[hk])
    cut = rb[rb.check == 1]
    alt = rb[rb.check == 2].iloc[0]
    splits = rb[rb.check == 4]
    shrink = rb[rb.check == 5].iloc[0]
    worst_pro = min((b for b in ban if b["pro_games"] >= 5), key=lambda b: b["pro_wins"] / b["pro_games"],
                    default=None)

    def pair(b):
        return f"<b>{b['pair']}</b> ({b['roles']})"

    out = [Paragraph("MADT 7202 MID-TERM · CHAMPION SYNERGY NETWORK · HIGH-ELO SOLO QUEUE, SEA + KR", kicker),
           Paragraph("Ban the pair, not the champion? — a LoL synergy network for tournament draft prep "
                     "(Patch 26.20)", title)]
    out += [H(1, "The decision"), Paragraph(
        "Which 2–3 champion pairs a Thai amateur/collegiate team should ban or practise at its next tournament. "
        "Owner: <b>head coach / draft analyst</b>. If top-synergy pairs were just high-win-rate champions, "
        "win-rate bans would do.", body)]
    out += [H(2, "Why a network"), Paragraph(
        "A champion’s win rate is one row in a table. Synergy — winning more together than the two win "
        "rates predict — belongs to a pair, so it lives only on the edges of a champion network.", body)]

    out += [H(3, "Data"), table([
        ("Source / method", f"Riot API (league-v4 → match-v5), Challenger/GM/Master solo queue, patch 26.20, "
                            f"{d(s['first_game_utc'])}–{d(s['last_game_utc'])} 2026: SEA (Thai queue since the "
                            "2025 TH2 merge) and KR"),
        ("Permission", "Riot developer API terms; Leaguepedia CC BY-SA; no names, Riot IDs or PUUIDs kept"),
        ("Volume", f"{calls:,} API calls; {s['matches']:,} matches ({servers}), remakes out; "
                   f"{s['champions']} champions"),
        ("Sampling bias", f"Solo queue ≠ 5-stack, KR ≠ Thai: SEA and KR checked apart and against "
                          f"{pro['games']} pro games"),
    ])]

    out += [H(4, "Graph construction"), table([
        ("Node / edge", f"Champion; edge = teammates in one game; {ed['role_before']:,} → {ed['role_after']} "
                        f"edges with ≥ {p['min_games']} games"),
        ("Weight", f"Lift = pair WR − σ(logit WR(a) + logit WR(b)), pp. Raw co-pick puts meta pairs first "
                   f"({cp['pair']}: n={cp['games']}, {cp['lift_pp']:+.1f} pp); {s['copick_top5_in_lift_top5']} of "
                   "its top 5 are in the lift top 5"),
        ("E-role vs E-all", f"E-role keeps bot lane and jungle–top/mid/bot pairs; E-all (all 10) shares "
                            f"{s['role_vs_all_top3_shared']}/3 of the top 3 and puts "
                            f"{5 - s['all_top5_role_interacting']} non-interacting pairs in its top 5"),
        ("Shrinkage / score", f"WR + Beta({core.PRIOR_WR},{core.PRIOR_WR}), pair prior {core.PRIOR_PAIR} games; "
                              "ban value = lift × pair games / matches; CI = 200 bootstraps"),
    ])]

    out += [H(5, "The picture&nbsp;&nbsp;&nbsp;<font name='%s' color='#555555' size='10'>Data: Riot Games API, "
              "SEA + KR, patch 26.20</font>" % BODY),
            Image(str(core.OUT / "figure.png"), width=18 * cm, height=FIG_H * cm)]

    out += [H(6, "Findings")] + bullets([
        f"<b>Pair synergy is weak.</b> {s['significant_pairs']} of {ed['role_after']} pairs have a CI above 0, but "
        f"so do {null.ci_above_0.mean():.0f} on average (max {null.ci_above_0.max()}) when winners are re-drawn at "
        f"random. Top ban value: {pair(b1)} {b1['lift_pp']:+.1f} pp (CI {b1['ci_lo']:+.1f} to {b1['ci_hi']:+.1f}, "
        f"n={b1['games']}).",
        f"<b>The hub is real:</b> {hub['champion']} holds {hub['edges']} of the {s['significant_and_replicated']} "
        f"edges that pass on both servers (random max {null.max_hub_edges.max()}), betweenness "
        f"{champ.loc[hk, 'betweenness']:.2f}, yet ranks {hub_rank}th by own win rate; no ban-list champion is "
        f"top-10 by win rate, so a win-rate table misses them. The most-picked champion, {mp['champion']}, "
        f"{'is' if mp['in_top10_lift_pair'] else 'is not'} in a top lift pair.",
        f"<b>Robustness:</b> the 3 pairs stay top-5 at 20/30/50 games ({'/'.join(str(v) for v in cut.stays)} of 3), "
        f"without shrinkage ({shrink.stays}/3), E-all {alt.stays}/3; lift is positive in all four SEA/KR and tier "
        f"halves ({min(splits.stays)}/3)."
        + (f" But {worst_pro['pair']} won {worst_pro['pro_wins']} of {worst_pro['pro_games']} pro games."
           if worst_pro else ""),
    ])
    out += [H(7, "Recommended action")] + bullets([
        f"Scrims 19–25 Oct 2026: first-phase ban {hub['champion']} (cuts {hub['edges']} synergy edges incl. "
        "pair #1); owner: draft analyst.",
        f"Practise {b3['pair'] if b3 else b1['pair']} in 10 scrims by 31 Oct 2026, logging win rate with/without "
        f"it" + (f"; drop {worst_pro['pair']}." if worst_pro else "."),
        f"Re-run on patch day ({NEXT_PATCH}, 26.21); if the {hub['champion']} hub falls to the random level, ban "
        "by win rate.",
    ])
    out += [H(8, "What would change my mind"), Paragraph(
        "Solo-queue synergy may not carry into coordinated play. If 10 scrims show opponents win as often with "
        f"{hub['champion']} banned, or 26.21 pro games disagree, I would ban by win rate alone.", body)]
    out += [Paragraph(f"{AUTHOR} · MADT 7202 · 16 Oct 2026 · Repository: {REPO_URL}", foot)]
    return out


def check(pdf):
    """Page count, any text below MIN_PT, and the outermost text positions (margin check)."""
    r = PdfReader(str(pdf))
    sizes, xs, ys = set(), [], []

    def visit(text, ctm, tm, fd, fs):
        if text.strip():
            sizes.add(round(fs * abs(tm[0] * ctm[0]), 2) if tm[0] else fs)
            xs.append(tm[4] * ctm[0] + tm[5] * ctm[2] + ctm[4])
            ys.append(tm[4] * ctm[1] + tm[5] * ctm[3] + ctm[5])
    r.pages[0].extract_text(visitor_text=visit)
    return len(r.pages), sorted(x for x in sizes if x < MIN_PT - 0.01), min(xs), min(ys), max(ys)


def main():
    core.REPORT.mkdir(exist_ok=True)
    pdf = core.REPORT / "MidTerm_LoL_Synergy.pdf"
    w, h = A4
    doc = BaseDocTemplate(str(pdf), pagesize=A4, title="Ban the pair, not the champion? LoL synergy network",
                          author=AUTHOR)
    frame = Frame(MARGIN, MARGIN, w - 2 * MARGIN, h - 2 * MARGIN, leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="one", frames=[frame])])
    doc.build(story())
    pages, small, x0, y0, y1 = check(pdf)
    print(f"{pdf}: {pages} page(s); text below {MIN_PT} pt: {small or 'none'}; leftmost text at {x0 / cm:.2f} cm, "
          f"lowest baseline {y0 / cm:.2f} cm from bottom, highest {(h - y1) / cm:.2f} cm from top")
    if pages != 1 or small or x0 < MARGIN - 0.5:
        sys.exit("FAIL: report must be exactly one page, all text >= 10 pt, margins >= 1.5 cm - shorten the text")


if __name__ == "__main__":
    main()
