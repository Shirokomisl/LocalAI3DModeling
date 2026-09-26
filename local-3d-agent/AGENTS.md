# Local 3D Agent instructions

You are maintaining a local image-to-3D pipeline.
Never replace the neural reconstruction stage with collections of primitive spheres/cones.
The core generator is Hunyuan3D-2.1 shape generation.
Use Blender only for post-processing, validation, camera/render setup and optional print preparation.
Use Ollama qwen3-vl for visual inspection and qwen3-coder-next for code changes.
All generated assets must remain under output/ unless explicitly requested otherwise.
Prefer reproducible scripts over manual Blender GUI operations.
When changing generation quality, preserve a working low-VRAM preset for RTX 3060 12GB.
