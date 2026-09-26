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

def ask(p):
    data=base64.b64encode(Path(p).read_bytes()).decode()
    prompt="""You are the geometry-analysis stage of an image-to-3D pipeline. Analyze the reference for reconstruction, not for captioning. Return JSON only. Record only evidence visible in the image; hidden geometry must be explicitly marked as inference. Analyze silhouette, relative proportions, depth/thickness cues, overlaps, holes/loops, attachments, and small high-value details. Identify risks that commonly produce flat sheets, thin extrusions, fused parts, floating parts, filled holes, or smeared detail. Explicitly fill geometry_requirements with concrete requirements for volumetric major parts, parts that must remain separate, components requiring backside geometry, openings that must remain open, attachment relationships, and high-value details that must survive reconstruction. Bboxes must be normalized [x1,y1,x2,y2]. The downstream Hunyuan3D model does NOT receive this text, so make the plan useful for preprocessing and later QA.
Schema: {"subject":"","style":"","symmetry":"","silhouette":{"description":"","bbox":[0,0,1,1]},"pose":"","major_parts":[],"anchor_points":[],"occlusion":[],"internal_background_regions":[],"detail_zones":[],"depth_cues":[],"likely_hidden_geometry":[],"topology_risks":[],"materials":[],"generation_strategy":{"detail_priority":[],"preserve_holes":true,"preserve_thin_parts":true},"geometry_requirements":{"volumetric_parts":[],"separate_parts":[],"backside_required":[],"preserve_openings":[],"attachment_requirements":[],"detail_requirements":[]}}"""
    payload={"model":MODEL,"stream":False,"think":True,"keep_alive":"30m","messages":[{"role":"user","content":prompt,"images":[data]}],"options":{"temperature":0.03,"num_ctx":32768,"num_predict":4096}}
    req=urllib.request.Request(OLLAMA,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=3600) as r:
        msg=json.loads(r.read())["message"]
        text=msg.get("content") or msg.get("thinking") or ""
        return parse_json(text)

if __name__=="__main__":
    if len(sys.argv)<2:raise SystemExit("usage: vision.py INPUT [OUTPUT_JSON]")
    result=ask(sys.argv[1])
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
