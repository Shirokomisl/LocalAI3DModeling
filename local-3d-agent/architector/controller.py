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
    for obj in candidates:
        if isinstance(obj, dict):
            if isinstance(obj.get("text"), str):
                texts.append(obj["text"])
            if isinstance(obj.get("message"), dict):
                content = obj["message"].get("content")
                if isinstance(content, str):
                    texts.append(content)
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
    raise RuntimeError("Controller did not return a valid JSON decision.")

def run_controller(state_path, stage):
    state = Path(state_path)
    prompt = (
        "You are controlling the local image-to-3D pipeline.\n"
        f"Stage: {stage}\n"
        "Read the attached project state JSON. Use only facts present there.\n"
        "Use existing Architector specialist roles when they materially reduce uncertainty.\n"
        "Return ONLY the required decision JSON from your system prompt.\n"
        "Do not edit files. The caller will execute your decision.\n"
    )
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = str(CONFIG)
    env["OPENCODE_CONFIG_DIR"] = str(CONFIG_DIR)
    cmd = [OPEN, "run", "--agent", "3d-orchestrator", "--format", "json",
           "--auto", prompt, "--file", str(state)]
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
