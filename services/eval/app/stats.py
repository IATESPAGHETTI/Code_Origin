"""Small, dependency-free statistics: bootstrap CIs, paired tests, agreement."""
import itertools
import math
import random


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def bootstrap_ci(xs, n_boot=2000, alpha=0.05, seed=0):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    if len(xs) == 1:
        return xs[0], xs[0]
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return means[int((alpha / 2) * n_boot)], means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]


def permutation_pvalue(diffs, n_perm=5000, seed=0):
    """Two-sided sign-flip test on the mean paired difference (exact for n <= 12)."""
    diffs = [d for d in diffs if d is not None]
    if not diffs or all(d == 0 for d in diffs):
        return 1.0
    observed = abs(sum(diffs))
    n = len(diffs)
    if n <= 12:
        signs = itertools.product((1, -1), repeat=n)
        total = ge = 0
        for s in signs:
            total += 1
            ge += abs(sum(si * d for si, d in zip(s, diffs))) >= observed - 1e-12
        return ge / total
    rng = random.Random(seed)
    ge = sum(abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= observed - 1e-12 for _ in range(n_perm))
    return (ge + 1) / (n_perm + 1)


def cohens_dz(diffs):
    diffs = [d for d in diffs if d is not None]
    if len(diffs) < 2:
        return None
    m = sum(diffs) / len(diffs)
    sd = math.sqrt(sum((d - m) ** 2 for d in diffs) / (len(diffs) - 1))
    return round(m / sd, 3) if sd > 0 else (0.0 if m == 0 else None)


def paired_compare(a_by_key, b_by_key, seed=0):
    """Compare b - a over items present in both. Returns dict or None when no overlap."""
    keys = sorted(set(a_by_key) & set(b_by_key))
    pairs = [(a_by_key[k], b_by_key[k]) for k in keys if a_by_key[k] is not None and b_by_key[k] is not None]
    if not pairs:
        return None
    diffs = [b - a for a, b in pairs]
    lo, hi = bootstrap_ci(diffs, seed=seed)
    return {
        "n": len(diffs), "mean_a": round(mean([a for a, _ in pairs]), 3), "mean_b": round(mean([b for _, b in pairs]), 3),
        "mean_diff": round(mean(diffs), 3), "ci_low": round(lo, 3), "ci_high": round(hi, 3),
        "p_value": round(permutation_pvalue(diffs, seed=seed), 4), "effect_size_dz": cohens_dz(diffs),
    }


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x, y):
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 3) if den else None


def weighted_kappa(a, b, categories=(0, 1, 2)):
    """Quadratic-weighted Cohen's kappa for ordinal ratings."""
    if len(a) != len(b) or not a:
        return None
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    n = len(a)
    row = [sum(r) for r in obs]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2)
            num += w * obs[i][j] / n
            den += w * row[i] * col[j] / (n * n)
    return round(1 - num / den, 3) if den else None
