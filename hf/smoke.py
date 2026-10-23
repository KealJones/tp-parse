import os, platform, time, torch, transformers
lines = [f"python {platform.python_version()}, torch {torch.__version__}, transformers {transformers.__version__}",
         f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'}, bf16: {torch.cuda.is_available() and torch.cuda.is_bf16_supported()}"]
if torch.cuda.is_available():
    a = torch.randn(8192, 8192, device="cuda", dtype=torch.bfloat16); torch.cuda.synchronize(); t = time.time()
    for _ in range(20):
        a @ a
    torch.cuda.synchronize(); lines.append(f"bf16 matmul: {20 * 2 * 8192**3 / (time.time() - t) / 1e12:.0f} TFLOPS")
os.makedirs("out", exist_ok=True)
open("out/SMOKE.md", "w").write("# Hugging Face Jobs smoke test\n\n" + "\n".join(f"- {l}" for l in lines) + "\n")
print("\n".join(lines))
