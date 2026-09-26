import sys,os
from pathlib import Path
import torch
from PIL import Image
from diffusers import DiffusionPipeline,EulerAncestralDiscreteScheduler

MODEL="sudo-ai/zero123plus-v1.2"

def square_input(path):
    im=Image.open(path).convert("RGBA")
    side=max(im.width,im.height)
    canvas=Image.new("RGBA",(side,side),(128,128,128,255))
    canvas.alpha_composite(im,((side-im.width)//2,(side-im.height)//2))
    return canvas.convert("RGB")

def split_grid(grid):
    w,h=grid.size
    cols,rows=(3,2) if w>=h else (2,3)
    cw,ch=w//cols,h//rows
    return [grid.crop((c*cw,r*ch,(c+1)*cw,(r+1)*ch))
            for r in range(rows) for c in range(cols)]

def main():
    if len(sys.argv)<3: raise SystemExit("usage: multiview.py INPUT OUTPUT_DIR [STEPS]")
    inp=Path(sys.argv[1]); out=Path(sys.argv[2]); steps=int(sys.argv[3]) if len(sys.argv)>3 else 75
    out.mkdir(parents=True,exist_ok=True)
    cond=square_input(inp); cond.save(out/"condition_square.png")
    pipe=DiffusionPipeline.from_pretrained(MODEL,custom_pipeline="sudo-ai/zero123plus-pipeline",torch_dtype=torch.float16)
    pipe.scheduler=EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config,timestep_spacing="trailing")
    pipe.to("cuda:0")
    with torch.inference_mode(): grid=pipe(cond,num_inference_steps=steps).images[0]
    grid.save(out/"zero123_grid.png")
    views=split_grid(grid)
    for i,v in enumerate(views): v.save(out/f"view_{i:02d}.png")
    # v1.2 azimuths are 30,90,150,210,270,330 degrees.
    # Hunyuan naming: front=main, right=90, back=210, left=270.
    Image.open(out/"condition_square.png").save(out/"front.png")
    views[1].save(out/"right.png")
    views[3].save(out/"back.png")
    views[4].save(out/"left.png")
    print("MULTIVIEW_OK",out); print("VIEWS",len(views))

if __name__=="__main__": main()
