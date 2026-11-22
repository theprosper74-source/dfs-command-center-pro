import csv, io, json, os
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Base, engine, get_db
from .models import Slate, Player, Lineup, SimulationRun
from .schemas import ProjectionRequest, SimulationRequest, OptimizerRequest
from .engine import estimate_projection, simulate_players, optimize, NBA_SLOTS, NFL_SLOTS, model_registry

Base.metadata.create_all(bind=engine)
app=FastAPI(title="DFS COMMAND CENTER PRO", version="0.1.0",
            description="NBA + NFL DFS research, simulation and lineup optimization API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health(db: Session=Depends(get_db)):
    try:
        db.execute(select(Slate.id).limit(1))
        database="connected"
    except Exception:
        database="error"
    return {"status":"healthy" if database=="connected" else "degraded",
            "database":database,"environment":os.getenv("APP_ENV","development"),
            "live_data":"not configured","timestamp":datetime.now(timezone.utc).isoformat()}

@app.get("/api/slates")
def slates(db: Session=Depends(get_db)):
    return [{"id":s.id,"sport":s.sport,"name":s.name,"created_at":s.created_at.isoformat()} for s in db.scalars(select(Slate).order_by(Slate.id.desc())).all()]

@app.get("/api/players")
def players(sport: str, slate_id: int, db: Session=Depends(get_db)):
    sport=sport.upper()
    if sport not in ("NBA","NFL"): raise HTTPException(400,"sport must be NBA or NFL")
    rows=db.scalars(select(Player).where(Player.slate_id==slate_id,Player.sport==sport)).all()
    return [player_dict(p) for p in rows]

def player_dict(p):
    return {"id":p.id,"external_id":p.external_id,"name":p.name,"positions":p.positions,
            "team":p.team,"opponent":p.opponent,"salary":p.salary,"game_info":p.game_info,
            "projection":p.projection,"floor":p.floor,"ceiling":p.ceiling,
            "ownership_estimate":p.ownership,"confidence":p.confidence,
            "source":p.source,"verified":p.verified,"quality_score":p.quality_score}

@app.post("/api/import/csv")
async def import_csv(sport: str=Form(...), file: UploadFile=File(...), db: Session=Depends(get_db)):
    sport=sport.upper()
    if sport not in ("NBA","NFL"): raise HTTPException(400,"sport must be NBA or NFL")
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a CSV file")
    raw=(await file.read()).decode("utf-8-sig",errors="replace")
    reader=csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames: raise HTTPException(400,"CSV has no header row")
    def keymap(row):
        return {str(k).strip().lower():v for k,v in row.items() if k}
    rows=[keymap(r) for r in reader]
    if not rows: raise HTTPException(400,"CSV contains no player rows")
    def pick(r,*names):
        for n in names:
            if n.lower() in r and r[n.lower()] not in (None,""): return str(r[n.lower()]).strip()
        return ""
    parsed=[]; seen=set(); errors=[]
    for i,r in enumerate(rows, start=2):
        pid=pick(r,"id","player id","dk id","draftkings id")
        name=pick(r,"name","nickname","player")
        pos=pick(r,"position","roster position")
        sal=pick(r,"salary")
        if not pid or not name or not pos or not sal:
            errors.append({"row":i,"reason":"missing player ID, name, position, or salary"}); continue
        if pid in seen:
            errors.append({"row":i,"reason":f"duplicate player ID {pid}"}); continue
        seen.add(pid)
        try: salary=int(float(sal.replace("$","").replace(",","")))
        except: errors.append({"row":i,"reason":"invalid salary"}); continue
        if salary<=0:
            errors.append({"row":i,"reason":"salary must be positive"}); continue
        try: avg=float(pick(r,"avgpointspergame","avg points per game","fpts","projection") or 0)
        except: avg=0
        game=pick(r,"game info","game","matchup")
        team=pick(r,"teamabbrev","team","team abbreviation")
        opp=pick(r,"opponent")
        if not opp and "@" in game:
            parts=game.replace(" ","").split("@")
            if len(parts)==2:
                if team==parts[0]: opp=parts[1]
                elif team==parts[1]: opp=parts[0]
        parsed.append({"pid":pid,"name":name,"positions":",".join(x.strip().upper() for x in pos.split("/")),
                       "salary":salary,"avg":avg,"team":team,"opponent":opp,"game":game})
    if not parsed: raise HTTPException(400,{"message":"No valid player rows","errors":errors[:30]})
    slate=Slate(sport=sport,name=f"{sport} import: {file.filename}",source="DraftKings CSV upload")
    db.add(slate); db.flush()
    now=datetime.now(timezone.utc)
    for r in parsed:
        db.add(Player(slate_id=slate.id,sport=sport,external_id=r["pid"],name=r["name"],
            positions=r["positions"],salary=r["salary"],source_avg=r["avg"],team=r["team"],
            opponent=r["opponent"],game_info=r["game"],source="DraftKings CSV upload",
            retrieved_at=now,verified=False,quality_score=0.85 if r["avg"]>0 else 0.65))
    db.commit()
    return {"slate_id":slate.id,"sport":sport,"imported":len(parsed),"rejected":len(errors),
            "errors":errors[:50],"source":"uploaded CSV","verified":False}

@app.post("/api/projections/run")
def run_projections(req: ProjectionRequest, db: Session=Depends(get_db)):
    slate=db.get(Slate,req.slate_id)
    if not slate: raise HTTPException(404,"Slate not found")
    rows=db.scalars(select(Player).where(Player.slate_id==slate.id)).all()
    for p in rows:
        out=estimate_projection(p,slate.sport)
        p.projection=out["projection"]; p.floor=out["floor"]; p.ceiling=out["ceiling"]
        p.ownership=out["ownership"]; p.confidence=out["confidence"]
    db.commit()
    return {"slate_id":slate.id,"players_updated":len(rows),
            "notice":"Estimates based on uploaded DK average or salary-derived fallback; enrich with verified stats and role data."}

@app.post("/api/simulations/run")
def run_simulations(req: SimulationRequest, db: Session=Depends(get_db)):
    slate=db.get(Slate,req.slate_id)
    if not slate: raise HTTPException(404,"Slate not found")
    rows=db.scalars(select(Player).where(Player.slate_id==slate.id)).all()
    if not rows: raise HTTPException(400,"Import a player pool first")
    results=simulate_players(rows,req.runs,req.seed)
    record=SimulationRun(slate_id=slate.id,runs=req.runs,seed=req.seed,results_json=json.dumps(results))
    db.add(record); db.commit()
    return {"run_id":record.id,"runs":req.runs,"seed":req.seed,"players":results,
            "notice":"Player-level independent baseline distributions. Correlation and game-script layers require richer inputs."}

@app.get("/api/models")
def models():
    return {"count":100,"families":10,"models":model_registry(),
            "notice":"Distinct configuration registry; historical calibration and trained ML weights are not yet connected."}

@app.post("/api/optimizer/run")
def run_optimizer(req: OptimizerRequest, db: Session=Depends(get_db)):
    slate=db.get(Slate,req.slate_id)
    if not slate: raise HTTPException(404,"Slate not found")
    rows=db.scalars(select(Player).where(Player.slate_id==slate.id)).all()
    if not rows: raise HTTPException(400,"Import a player pool first")
    slots=[s.model_dump() for s in req.slots] if req.slots else (NBA_SLOTS if slate.sport=="NBA" else NFL_SLOTS)
    sols=optimize(rows,slots,req.salary_cap,req.lineup_count,req.strategy,req.max_exposure)
    if not sols: raise HTTPException(422,"No valid lineup found. Check pool size, positions, and salary cap.")
    saved=[]
    for sol in sols:
        line=Lineup(slate_id=slate.id,sport=slate.sport,strategy=req.strategy,
                    salary=sol["salary"],projection=sol["projection"],
                    player_ids=json.dumps([p.id for p in sol["players"]]))
        db.add(line); db.flush()
        saved.append({"lineup_id":line.id,"salary":sol["salary"],"remaining_salary":req.salary_cap-sol["salary"],
            "projection":round(sol["projection"],2),"ceiling":round(sol["ceiling"],2),
            "players":[player_dict(p) for p in sol["players"]],"validated":True,
            "validation_note":"Validated against supplied slot eligibility and salary cap."})
    db.commit()
    return {"lineups":saved,"requested":req.lineup_count,"generated":len(saved),
            "notice":"Optimizer uses supplied roster rules. Confirm slate eligibility and contest settings before upload."}

@app.get("/api/lineups/{lineup_id}/export")
def export_lineup(lineup_id: int, db: Session=Depends(get_db)):
    line=db.get(Lineup,lineup_id)
    if not line: raise HTTPException(404,"Lineup not found")
    ids=json.loads(line.player_ids)
    rows=db.scalars(select(Player).where(Player.id.in_(ids))).all()
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["Player ID","Name","Position","Team","Salary"])
    for p in rows: writer.writerow([p.external_id,p.name,p.positions,p.team,p.salary])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",
        headers={"Content-Disposition":f'attachment; filename="dfs-lineup-{line.id}.csv"'})


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR/"frontend")), name="static")

@app.get("/")
def home():
    return FileResponse(str(BASE_DIR/"frontend"/"index.html"))
