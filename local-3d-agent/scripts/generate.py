import argparse, sys, os, json
from pathlib import Path
import torch

ROOT=Path(__file__).resolve().parents[1]
HY=Path(r"C:\AI\Hunyuan3D-2.1")
sys.path.insert(0,str(HY/"hy3dshape"))

from hy3dshape.pipelines import Hunyuan3DDiTFlowMatchingPipeline
from hy3dshape.rembg import BackgroundRemover
from PIL import Image, ImageFilter

def load_vision(path):
    if not path or not Path(path).exists(): return {}
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return {}

def prepare_image(src,dst,vision=None):
    image=Image.open(src)
    has_alpha="A" in image.getbands()
    has_real_transparency=False
    if has_alpha:
        amin,amax=image.getchannel("A").getextrema()
        has_real_transparency=amin<250
    image=image.convert("RGBA")

    if has_real_transparency:
        print("Input already has transparency; skipping BackgroundRemover.")
        alpha=image.getchannel("A")
    else:
        print("Input has no usable transparency; applying BackgroundRemover.")
        image=BackgroundRemover()(image).convert("RGBA")
        alpha=image.getchannel("A")
        vision=vision or {}
        for region in vision.get("internal_background_regions",[]):
            box=region.get("bbox") if isinstance(region,dict) else region
            if isinstance(box,list) and len(box)==4:
                x1,y1,x2,y2=[float(v) for v in box]
                if max(abs(x1),abs(y1),abs(x2),abs(y2))<=1.5:
                    x1,x2=x1*image.width,x2*image.width
                    y1,y2=y1*image.height,y2*image.height
                box=(max(0,int(x1)),max(0,int(y1)),min(image.width,int(x2)),min(image.height,int(y2)))
                if box[2]>box[0] and box[3]>box[1]: alpha.paste(0,box=box)
        # Remove large enclosed holes only from masks created by rembg.
        try:
            import cv2,numpy as np
            mask=np.array(alpha)
            binary=(mask>16).astype(np.uint8)
            inv=(1-binary)*255
            flood=np.zeros((mask.shape[0]+2,mask.shape[1]+2),np.uint8)
            cv2.floodFill(inv,flood,(0,0),128)
            enclosed=(inv==255)
            n,labels,stats,_=cv2.connectedComponentsWithStats(enclosed.astype(np.uint8),8)
            for i in range(1,n):
                area=int(stats[i,cv2.CC_STAT_AREA])
                if area>0.008*mask.shape[0]*mask.shape[1]:
                    mask[labels==i]=0
            alpha=Image.fromarray(mask)
        except Exception:
            pass

    image.putalpha(alpha)
    bbox=alpha.getbbox()
    if bbox is None: raise RuntimeError("Background removal produced an empty mask.")
    pad=max(10,int(max(bbox[2]-bbox[0],bbox[3]-bbox[1])*0.07))
    bbox=(max(0,bbox[0]-pad),max(0,bbox[1]-pad),min(image.width,bbox[2]+pad),min(image.height,bbox[3]+pad))
    image=image.crop(bbox)
    side=max(image.width,image.height)
    canvas=Image.new("RGBA",(side,side),(255,255,255,0))
    canvas.alpha_composite(image,((side-image.width)//2,(side-image.height)//2))
    rgb=canvas.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2,percent=120,threshold=3))
    out=Image.new("RGBA",canvas.size,(255,255,255,0))
    out.paste(rgb,mask=canvas.getchannel("A"))
    out.save(dst)
    return dst

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--output",default=str(ROOT/"output"/"raw.glb"))
    ap.add_argument("--steps",type=int,default=75)
    ap.add_argument("--resolution",type=int,default=512)
    ap.add_argument("--chunks",type=int,default=20000)
    ap.add_argument("--guidance-scale",type=float,default=5.0)
    ap.add_argument("--seed",type=int,default=42)
    ap.add_argument("--vision-json",default="")
    args=ap.parse_args()
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF","expandable_segments:True")
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    prepared=Path(args.output).with_name("preprocessed.png")
    vision=load_vision(args.vision_json)
    print("Vision-guided background removal and preprocessing...")
    prepare_image(args.image,prepared,vision)
    print(f"Prepared image: {prepared}")
    print("Loading Hunyuan3D-2.1 shape model...")
    pipe=Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        str(HY),subfolder="hunyuan3d-dit-v2-1",
        use_safetensors=False,device="cuda",dtype=torch.float16)
    gen=torch.Generator(device="cuda").manual_seed(args.seed)
    print("Generating neural mesh...")
    mesh=pipe(image=str(prepared),num_inference_steps=args.steps,
              guidance_scale=args.guidance_scale,octree_resolution=args.resolution,
              num_chunks=args.chunks,generator=gen)[0]
    mesh.export(args.output)
    info={"vertices":len(mesh.vertices),"faces":len(mesh.faces),
          "steps":args.steps,"octree_resolution":args.resolution,
          "guidance_scale":args.guidance_scale,"seed":args.seed,
          "output":args.output,"prepared_image":str(prepared),
          "vision_json":args.vision_json}
    Path(args.output).with_suffix(".json").write_text(
        json.dumps(info,indent=2),encoding="utf-8")
    print(json.dumps(info,indent=2))

if __name__=="__main__":
    main()
