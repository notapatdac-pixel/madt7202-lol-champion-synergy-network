# Robustness checks

Ban list (E-role, >= 30 games, shrunk, CI above 0): Lee Sin + Twisted Fate; Caitlyn + Karma; Kai'Sa + Qiyana.

- **1 min games 20**: 3 of 3 ban-list pairs in this variant's top 5 by ban value. Top 3 / detail: Lee Sin + Twisted Fate; Aphelios + Thresh; Caitlyn + Karma (1199 pairs)
- **1 min games 30**: 3 of 3 ban-list pairs in this variant's top 5 by ban value. Top 3 / detail: Lee Sin + Twisted Fate; Aphelios + Thresh; Caitlyn + Karma (638 pairs)
- **1 min games 50**: 3 of 3 ban-list pairs in this variant's top 5 by ban value. Top 3 / detail: Lee Sin + Twisted Fate; Aphelios + Thresh; Caitlyn + Karma (266 pairs)
- **2 E-all (all 10 teammate pairs)**: 2 of 3 ban-list pairs in this variant's top 5 by ban value. Top 3 / detail: Kai'Sa + Qiyana; Kai'Sa + Pantheon; Qiyana + Thresh (1939 pairs)
- **3 bootstrap 200x, 90% CI of lift**: 43 of 638 pairs with the whole CI above 0; 31.9 expected by chance. Top 3 / detail: Lee Sin + Twisted Fate [+3.3, +15.6]; Caitlyn + Karma [+1.9, +14.1]; Kai'Sa + Qiyana [+0.6, +12.2] (638 pairs)
- **4 KR server matches (5000)**: 3 of 3 ban-list pairs with positive lift in this half. Top 3 / detail: Lee Sin + Twisted Fate +8.1 pp (n=70); Caitlyn + Karma +10.1 pp (n=50); Kai'Sa + Qiyana +6.1 pp (n=71) (6124 pairs)
- **4 SG2 server matches (5997)**: 3 of 3 ban-list pairs with positive lift in this half. Top 3 / detail: Lee Sin + Twisted Fate +6.5 pp (n=22); Caitlyn + Karma +4.4 pp (n=62); Kai'Sa + Qiyana +5.6 pp (n=62) (7793 pairs)
- **4 Challenger+GM-sourced matches (6783)**: 3 of 3 ban-list pairs with positive lift in this half. Top 3 / detail: Lee Sin + Twisted Fate +4.3 pp (n=50); Caitlyn + Karma +8.9 pp (n=71); Kai'Sa + Qiyana +5.8 pp (n=82) (7650 pairs)
- **4 Master-sourced matches (4214)**: 3 of 3 ban-list pairs with positive lift in this half. Top 3 / detail: Lee Sin + Twisted Fate +13.9 pp (n=42); Caitlyn + Karma +4.1 pp (n=41); Kai'Sa + Qiyana +5.4 pp (n=51) (6961 pairs)
- **5 shrinkage off (raw win rates, no pair prior)**: 3 of 3 ban-list pairs in this variant's top 5 by ban value. Top 3 / detail: Lee Sin + Twisted Fate; Caitlyn + Karma; Nautilus + Tristana (638 pairs)
- **6 permutation null: winners re-drawn at random, 20 rounds**: 1 of 3 observed counts above every null round. Top 3 / detail: observed 43 / 30 / 7 (CI>0 / +replicated / Lee Sin edges); null mean 36.0 / 23.5 / 4.0, null max 46 / 32 / 6 (638 pairs)
