import argparse,json,sys
from pathlib import Path
import torch
from PIL import Image
sys.path.insert(0,r"C:\AI\Hunyuan3D-2")
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

def load(p):
    return Image.open(p).convert("RGBA")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--views",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--steps",type=int,default=50)
    ap.add_argument("--resolution",type=int,default=512)
    ap.add_argument("--chunks",type=int,default=20000)
    ap.add_argument("--guidance-scale",type=float,default=5.0)
    ap.add_argument("--seed",type=int,default=42)
    a=ap.parse_args()
    v=Path(a.views)
    images={k:load(v/f"{k}.png") for k in ("front","left","back","right")}
    root=Path(r"C:\AI\Hunyuan3D-2mv\hunyuan3d-dit-v2-mv")
    pipe=Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        str(root),subfolder="hunyuan3d-dit-v2-mv",
        use_safetensors=False,device="cuda",dtype=torch.float16)
    gen=torch.Generator(device="cuda").manual_seed(a.seed)
    mesh=pipe(image=images,num_inference_steps=a.steps,
        octree_resolution=a.resolution,num_chunks=a.chunks,
        guidance_scale=a.guidance_scale,generator=gen,output_type="trimesh")[0]
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    mesh.export(str(out))
    meta={"steps":a.steps,"resolution":a.resolution,"chunks":a.chunks,
          "guidance_scale":a.guidance_scale,"seed":a.seed,"views":list(images)}
    out.with_suffix(".json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    print("HUNYUAN_MV_OK",out)
    print("VERTICES",len(mesh.vertices),"FACES",len(mesh.faces))

if __name__=="__main__":
    main()
