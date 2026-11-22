from types import SimpleNamespace
from backend.engine import estimate_projection, simulate_players, optimize, NBA_SLOTS

def test_projection_positive():
    p=SimpleNamespace(source_avg=30,salary=6000)
    x=estimate_projection(p,"NBA")
    assert x["projection"] > 0
    assert x["ceiling"] > x["floor"]
    assert 0 <= x["ownership"] <= 100

def test_simulation_reproducible():
    p=SimpleNamespace(external_id="x",projection=30,ceiling=45,floor=20,salary=6000)
    a=simulate_players([p],1000,123)
    b=simulate_players([p],1000,123)
    assert a == b

def test_optimizer_salary_and_unique():
    pool=[]
    positions=["PG","SG","SF","PF","C","PG,SG","SF,PF","PG,SG,SF,PF,C"]
    for i,pos in enumerate(positions):
        pool.append(SimpleNamespace(id=i+1,positions=pos,salary=5000,projection=25,
          ceiling=40,floor=15,ownership=10,sport="NBA"))
    out=optimize(pool,NBA_SLOTS,50000,1)
    assert out
    assert out[0]["salary"] <= 50000
    assert len({p.id for p in out[0]["players"]}) == 8
