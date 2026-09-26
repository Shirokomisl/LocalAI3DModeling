# Local Image to 3D Agent

Windows + RTX 3060 12 GB local image-to-3D workbench.

## Full pipeline

source image
-> Qwen3-VL scene/geometry analysis
-> Hunyuan background removal + Vision-guided hole cleanup
-> Hunyuan3D-2.1 neural shape generation
-> Blender mesh cleanup + render
-> Qwen3-VL visual QA against the source
-> adaptive retry with higher mesh resolution when QA is weak
-> final GLB + STL

Qwen3-VL is an active planning and QA stage. It does not directly inject
text into Hunyuan's shape network; Hunyuan still receives the cleaned image.
This keeps the reconstruction neural instead of replacing it with primitives.

## Current verified setup

- Hunyuan3D-2.1: C:\AI\Hunyuan3D-2.1
- Python: C:\AI\Hunyuan3D-2.1\.venv\Scripts\python.exe
- PyTorch: 2.5.1+cu124
- GPU: RTX 3060 12 GB
- Shape checkpoint: hunyuan3d-dit-v2-1\model.fp16.ckpt
- Blender: C:\Program Files\Blender Foundation\Blender 5.2\blender.exe
- Ollama: qwen3-vl:30b-a3b-thinking-q4_K_M (vision and QA) and qwen3-coder-next:q4_K_M
## Run

Put the reference at input\source.png, then:

powershell -ExecutionPolicy Bypass -File .\run.ps1

The first Hunyuan candidate defaults to 75 diffusion steps, octree 512 and
20000 chunks. A run generates three Hunyuan candidates and, unless
`-SkipTigon` is set, three TIGON candidates; QA selects the best. Architector
may request one additional candidate. By default, a QA score below 4.0 is not
promoted to the final output; override this with `-MinimumQAScore` if needed.

For a fast smoke test:

powershell -ExecutionPolicy Bypass -File .\run.ps1 -SmokeTest -Steps 20 -Resolution 256 -Chunks 4000 -SkipVision -SkipQA

To run without the Vision stages:

powershell -ExecutionPolicy Bypass -File .\run.ps1 -SkipVision -SkipQA

## Outputs

output\vision.json             - Qwen3-VL geometry plan
output\preprocessed.png        - final cleaned input seen by Hunyuan
output\candidate_01\...       - first neural reconstruction
output\candidate_02\...       - adaptive retry, when needed
output\qa.json                 - selected candidate's Vision QA
output\model.glb               - final mesh
output\model.stl               - final printable mesh
output\model.blend             - Blender scene
output\model_preview.png       - final render

## Important quality limitation

A single stylized image does not contain true back/side geometry. Vision can
reason about likely hidden structure and can reject bad renders, but it cannot
recover information that is absent from the reference. The next major quality
upgrade is a true multi-view stage: generate consistent front/side/back views
and feed them to a multiview shape model.

Hunyuan3D-2.1 Shape remains the main generator. The official 2mv model is a
separate 1.1B multiview model, while the 2.1 Shape model is the higher-capacity
single-image model. We will add a local multiview image-generation stage only
after its model/runtime is installed and tested on the 12 GB GPU.

## OpenCode

Run opencode from this directory. The project config points at the local
qwen3-coder-next model. Use it to inspect or modify the pipeline scripts.
