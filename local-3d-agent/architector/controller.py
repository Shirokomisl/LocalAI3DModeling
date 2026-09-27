import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "architector"
CONFIG = ARCH / "opencode.jsonc"
CONFIG_DIR = ARCH
OPEN = r"C:\Users\Данил\AppData\Roaming\npm\opencode.cmd"

def extract_json(text):
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            candidates.append(json.loads(line))
        except Exception:
            pass
    texts = []

    def collect_text(value):
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                texts.append(value["text"])
            if isinstance(value.get("content"), str):
                texts.append(value["content"])
            for key in ("part", "message", "data", "result", "content"):
                nested = value.get(key)
                if isinstance(nested, (dict, list)):
                    collect_text(nested)
        elif isinstance(value, list):
            for item in value:
                collect_text(item)

    for obj in candidates:
        if isinstance(obj, dict):
            if "action" in obj:
                return obj
            if isinstance(obj.get("text"), str):
                texts.append(obj["text"])
            if isinstance(obj.get("message"), dict):
                content = obj["message"].get("content")
                if isinstance(content, str):
                    texts.append(content)
            collect_text(obj)
    texts = list(dict.fromkeys(texts))
    texts.append(text)
    for block in reversed(texts):
        block = block.strip()
        try:
            obj = json.loads(block)
            if isinstance(obj, dict) and "action" in obj:
                return obj
        except Exception:
            pass
        m = re.search(r'\{\s*"action".*\}\s*$', block, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    output_tail = text[-3000:].encode("ascii", "backslashreplace").decode("ascii")
    raise RuntimeError(
        "Controller did not return a valid JSON decision. "
        f"OpenCode output tail:\n{output_tail}"
    )

def run_controller(state_path, stage):
    state = Path(state_path)
    state_data = json.loads(state.read_text(encoding="utf-8-sig"))

    def brief_list(value):
        if not isinstance(value, list):
            return []
        return [str(item)[:240] for item in value[:8]]

    candidates = []
    for candidate in state_data.get("candidates", [])[:8]:
        if not isinstance(candidate, dict):
            continue
        qa = candidate.get("qa")
        if not isinstance(qa, dict):
            qa = {}
        repair_plan = qa.get("repair_plan")
        if not isinstance(repair_plan, dict):
            repair_plan = {}
        candidates.append({
            "name": candidate.get("name"),
            "kind": candidate.get("kind"),
            "score": candidate.get("score", qa.get("overall")),
            "critical_defects": brief_list(qa.get("critical_defects")),
            "repair_instructions": brief_list(repair_plan.get("instructions")),
            "stop_reason": repair_plan.get("stop_reason", ""),
        })
    vision = state_data.get("vision")
    if not isinstance(vision, dict):
        vision = {}
    geometry = vision.get("geometry_requirements")
    if not isinstance(geometry, dict):
        geometry = {}
    state_summary = {
        "stage": stage,
        "best_model": state_data.get("best_model"),
        "best_score": state_data.get("best_score"),
        "minimum_qa_score": state_data.get("minimum_qa_score", 4.0),
        "candidates": candidates,
        "subject": vision.get("subject", ""),
        "topology_risks": brief_list(vision.get("topology_risks")),
        "volumetric_parts": brief_list(geometry.get("volumetric_parts")),
        "separate_parts": brief_list(geometry.get("separate_parts")),
        "backside_required": brief_list(geometry.get("backside_required")),
    }
    prompt = (
        "Use this state summary to choose one allowed next action. Facts: "
        f"{json.dumps(state_summary, ensure_ascii=True, separators=(',', ':'))}. "
        f"A best score below {state_summary['minimum_qa_score']} is not acceptable; "
        "do not choose stop when QA reports critical defects and actionable repair instructions. "
        "Return one JSON object matching the full required schema only."
    )
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(CONFIG)
    env["OPENCODE_CONFIG_DIR"] = str(CONFIG_DIR)
    cmd = [OPEN, "run", "--agent", "3d-orchestrator", "--format", "json",
           "--auto", prompt]
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"OpenCode controller failed ({proc.returncode}):\n{proc.stdout}"
        )
    decision = extract_json(proc.stdout)
    decision["_stage"] = stage
    decision["_raw_output"] = proc.stdout[-12000:]
    return decision

if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: controller.py STATE_JSON STAGE [OUTPUT_JSON]")
    result = run_controller(sys.argv[1], sys.argv[2])
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(sys.argv[1]).with_name("controller_decision.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))
