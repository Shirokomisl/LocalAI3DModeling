import base64,json,re,sys,urllib.request
from pathlib import Path

MODEL="qwen3-vl:30b-a3b-thinking-q4_K_M"
OLLAMA="http://127.0.0.1:11434/api/chat"

def parse_json(s):
    s=s.replace(chr(96)*3+"json","").replace(chr(96)*3,"").strip()
    try:return json.loads(s)
    except:
        m=re.search(r"\{.*\}",s,re.S)
        return json.loads(m.group(0)) if m else {"raw":s}

def clamp(v,lo=0,hi=10):
    try:return max(lo,min(hi,float(v)))
    except:return 0.0

def enforce_score(result):
    """Compute final score deterministically; never trust the LLM's overall."""
    keys=["identity_match","silhouette_match","pose_match","proportion_match",
          "detail_preservation","depth_match","backside_match","artifact_penalty"]
    llm_overall=clamp(result.get("overall",0))
    for k in keys: result[k]=clamp(result.get(k,0))
    vs=result.get("view_scores",{})
    for k in ["front","left","back","right"]: vs[k]=clamp(vs.get(k,0))
    result["view_scores"]=vs
    core=(result["identity_match"]*.14+result["silhouette_match"]*.14+
          result["pose_match"]*.07+result["proportion_match"]*.10+
          result["detail_preservation"]*.15+result["depth_match"]*.18+
          result["backside_match"]*.17+sum(vs.values())*.05/4)
    score=max(0.0,core-result["artifact_penalty"]*.08)
    if vs["back"]<=3 or result["backside_match"]<=3: score=min(score,4.0)
    if min(vs["left"],vs["right"])<=3 or result["depth_match"]<=3: score=min(score,4.0)
    if result["detail_preservation"]<=3: score=min(score,5.0)
    if result["artifact_penalty"]>=7: score=min(score,4.0)
    defects=" ".join(str(x).lower() for x in result.get("critical_defects",[]))
    hard_terms=("flat sheet","flat sheets","flat body","flat wing","relief","paper-like","billboard","essentially 2d","2d shape","thin extrusion","missing back","missing backside geometry","smeared","filled hole","fused","floating")
    fatal_terms=("flat sheet","flat sheets","flat body","flat wing","relief","paper-like","billboard","essentially 2d","2d shape","missing backside geometry","thin extrusion")
    if any(t in defects for t in fatal_terms): score=min(score,3.0)
    elif any(t in defects for t in ("fused","fused wings/body","fused parts")): score=min(score,3.0)
    elif any(t in defects for t in hard_terms): score=min(score,5.0)
    if result["depth_match"]<=2 and result["backside_match"]<=2: score=min(score,3.0)
    view_range=max(vs.values())-min(vs.values())
    score-=max(0.0,view_range-3.0)*0.35
    result["overall"]=round(max(0.0,min(10.0,score)),2)
    rp=result.get("repair_plan",{})
    if not isinstance(rp,dict): rp={}
    for k in ["instructions","preserve","avoid"]:
        v=rp.get(k,[])
        rp[k]=[str(x).strip() for x in v if str(x).strip()] if isinstance(v,list) else []
    rp["priority"]=str(rp.get("priority","geometry") or "geometry")
    rp["stop_reason"]=str(rp.get("stop_reason","") or "")
    result["repair_plan"]=rp
    result["score_source"]="deterministic_postprocess"
    result["llm_overall"]=llm_overall
    return result

def ask(reference,renders,analysis=None):
    images=[base64.b64encode(Path(reference).read_bytes()).decode()]
    labels=["IMAGE 1 = ORIGINAL REFERENCE"]
    for i,p in enumerate(renders,2):
        images.append(base64.b64encode(Path(p).read_bytes()).decode())
        labels.append(f"IMAGE {i} = {Path(p).stem}")
    ctx=Path(analysis).read_text(encoding="utf-8") if analysis and Path(analysis).exists() else "{}"
    prompt="""You are the senior visual QA and reconstruction critic for a neural image-to-3D pipeline.
Compare IMAGE 1 with all four rendered views. Evaluate the actual 3D asset, not artistic preference.
A correct result must match the reference while being genuinely volumetric from every side.
Inspect front, left, back and right for silhouette, depth, thickness, proportions, topology,
rope/loops, occlusions, attachments and small high-value details. Penalize flat sheets,
thin extrusions, missing back geometry, fused/floating parts, filled holes, smearing and
loss of fine features. Do not reward a model merely because its front view looks good.
For repair_plan, produce a compact actionable specification for the NEXT TIGON attempt.
Prioritize only the highest-impact defects that are actually visible. Separate instructions,
preserve items, and avoid items. Never invent hidden details that cannot be supported by the
reference. If the result is already good enough (deterministic overall >= 8.0 and no critical defects), set stop_reason to "good_enough" and leave
instructions empty. If the problem is fundamentally unresolvable from the single reference,
use stop_reason "insufficient_reference".
Use integer scores 0-10. Return JSON only.
Schema:
{"identity_match":0,"silhouette_match":0,"pose_match":0,"proportion_match":0,"detail_preservation":0,
"depth_match":0,"backside_match":0,"artifact_penalty":0,"overall":0,
"view_scores":{"front":0,"left":0,"back":0,"right":0},
"critical_defects":[],"preserved_details":[],
"repair_plan":{"priority":"geometry","instructions":[],"preserve":[],"avoid":[],"stop_reason":""},
"recommended_retry":{"seed":0,"resolution":0,"steps":0,"guidance_scale":0,"reason":""}}
Planning context:
"""+ctx+"""
View mapping:
"""+chr(10).join(labels)
    payload={"model":MODEL,"stream":False,"think":True,"keep_alive":"30m",
             "messages":[{"role":"user","content":prompt,"images":images}],
             "options":{"temperature":0.03,"num_ctx":32768,"num_predict":4096}}
    req=urllib.request.Request(OLLAMA,data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=3600) as r:
        msg=json.loads(r.read())["message"]
        text=msg.get("content") or ""
        if not text:
            text=msg.get("thinking") or ""
        raw=parse_json(text)
    return enforce_score(raw)

if __name__=="__main__":
    if len(sys.argv)<6:
        raise SystemExit("usage: qa.py REFERENCE FRONT LEFT BACK RIGHT [ANALYSIS_JSON] [OUTPUT_JSON]")
    renders=sys.argv[2:6]
    analysis=sys.argv[6] if len(sys.argv)>6 else None
    result=ask(sys.argv[1],renders,analysis)
    if len(sys.argv)>7:
        Path(sys.argv[7]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
