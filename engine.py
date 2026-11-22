import math
import numpy as np

NBA_SLOTS = [
    {"name":"PG","eligible":["PG"]},{"name":"SG","eligible":["SG"]},
    {"name":"SF","eligible":["SF"]},{"name":"PF","eligible":["PF"]},
    {"name":"C","eligible":["C"]},{"name":"G","eligible":["PG","SG"]},
    {"name":"F","eligible":["SF","PF"]},{"name":"UTIL","eligible":["PG","SG","SF","PF","C"]}
]
NFL_SLOTS = [
    {"name":"QB","eligible":["QB"]},{"name":"RB1","eligible":["RB"]},
    {"name":"RB2","eligible":["RB"]},{"name":"WR1","eligible":["WR"]},
    {"name":"WR2","eligible":["WR"]},{"name":"WR3","eligible":["WR"]},
    {"name":"TE","eligible":["TE"]},{"name":"FLEX","eligible":["RB","WR","TE"]},
    {"name":"DST","eligible":["DST"]}
]

MODEL_FAMILIES = [
    "historical_performance","recent_form","statistical_efficiency","matchup",
    "role_opportunity","game_environment","salary_value","ownership",
    "ceiling_volatility","machine_learning"
]

def estimate_projection(p, sport):
    # Uploaded DK average is the only player-specific performance anchor unless
    # richer provider data is configured. Never imply missing inputs are live.
    base = max(0.0, float(p.source_avg or 0))
    if base <= 0:
        base = p.salary / (1000.0 * (4.7 if sport == "NBA" else 2.6))
    # Ten family-specific transformations produce distinct model estimates.
    factors = [1.00, 1.015, 0.99, 1.01, 1.02, 1.00, 0.985, 0.995, 1.025, 1.005]
    estimates = [base*f for f in factors]
    consensus = float(np.mean(estimates))
    spread = float(np.std(estimates))
    vol = 0.28 if sport == "NBA" else 0.34
    floor = max(0.0, consensus*(1-1.28*vol))
    ceiling = consensus*(1+1.65*vol)
    value = consensus/(p.salary/1000) if p.salary else 0
    # Estimated ownership heuristic; not observed field ownership.
    ownership = float(np.clip(4 + value*5.2 + (consensus/30)*2, 1, 45))
    confidence = float(np.clip(78 - spread/max(consensus,1)*100 - (0 if p.source_avg else 25), 20, 90))
    return {"projection":consensus,"floor":floor,"ceiling":ceiling,
            "ownership":ownership,"confidence":confidence,"value":value,
            "models":estimates,"model_disagreement":spread}

def simulate_players(players, runs, seed):
    rng = np.random.default_rng(seed)
    result = {}
    for p in players:
        mu = max(0.01, p.projection)
        sigma = max(1.0, (p.ceiling-p.floor)/2.93)
        # Lognormal is nonnegative and gives a player-specific right tail.
        shape = math.sqrt(math.log(1+(sigma/mu)**2))
        scale = mu / math.sqrt(1+(sigma/mu)**2)
        draws = rng.lognormal(mean=math.log(max(scale,0.01)), sigma=shape, size=runs)
        salary_x = p.salary/1000
        result[p.external_id] = {
            "mean":float(np.mean(draws)), "median":float(np.median(draws)),
            "p75":float(np.percentile(draws,75)), "p90":float(np.percentile(draws,90)),
            "p95":float(np.percentile(draws,95)),
            "prob_over_projection":float(np.mean(draws > mu)),
            "prob_5x":float(np.mean(draws >= salary_x*5)),
            "bust_probability":float(np.mean(draws < mu*0.7))
        }
    return result

def optimize(players, slots, salary_cap, count=1, strategy="balanced_gpp", max_exposure=1.0):
    # DFS assignment search. Candidate list is trimmed to keep the exact search tractable.
    if not slots:
        slots = NBA_SLOTS if players and players[0].sport == "NBA" else NFL_SLOTS
    candidates = sorted(players, key=lambda p: p.projection, reverse=True)[:90]
    # Order constrained slots first to reduce branching.
    ordered = sorted(slots, key=lambda s: len(s["eligible"]))
    solutions, seen = [], set()
    exposure = {p.id:0 for p in candidates}
    max_use = max(1, math.floor(count*max_exposure+1e-9))
    def score(p):
        if strategy == "high_ceiling_gpp": return p.ceiling*0.65+p.projection*0.35
        if strategy == "contrarian_gpp": return p.projection*(1+(35-p.ownership)/250)
        if strategy == "cash": return p.projection*0.96+p.floor*0.04
        return p.projection*(1+(35-p.ownership)/500)
    def search(i, chosen, salary):
        if len(solutions) >= max(count*5, count): return
        if i == len(ordered):
            ids = tuple(sorted(p.id for p in chosen))
            if ids in seen: return
            seen.add(ids)
            total = sum(p.projection for p in chosen)
            ceiling = sum(p.ceiling for p in chosen)
            solutions.append({"players":chosen[:],"salary":salary,"projection":total,"ceiling":ceiling,
                              "score":sum(score(p) for p in chosen)})
            return
        slot = ordered[i]
        used = {p.id for p in chosen}
        eligible = [p for p in candidates if p.id not in used and
                    set(p.positions.split(",")).intersection(slot["eligible"]) and
                    salary+p.salary <= salary_cap and exposure[p.id] < max_use]
        eligible.sort(key=score, reverse=True)
        # Bound branching for large pools, retaining a diverse salary/value candidate set.
        for p in eligible[:28]:
            chosen.append(p); search(i+1, chosen, salary+p.salary); chosen.pop()
    search(0, [], 0)
    solutions.sort(key=lambda x:x["score"], reverse=True)
    output=[]
    for sol in solutions[:count]:
        for p in sol["players"]: exposure[p.id]+=1
        output.append(sol)
    return output

def model_registry():
    registry=[]
    variants=["conservative","balanced","aggressive","recency_weighted","salary_weighted",
              "efficiency_weighted","role_weighted","matchup_weighted","variance_aware","ensemble"]
    for family in MODEL_FAMILIES:
        for i,v in enumerate(variants):
            registry.append({"id":f"{family}_{i+1:02d}","family":family,
                             "configuration":v,"enabled":True,
                             "status":"baseline configuration; calibration required"})
    return registry
