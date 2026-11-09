from huggingface_hub import HfApi, get_token

api = HfApi(token=get_token())
info = api.space_info("josjshid99/ai-ugc-studio-web")
rt = info.runtime
print("STAGE", rt.stage)
print("HOST", repr(getattr(rt, "host", None)))
print("ERROR", getattr(rt, "error", None))
print("HISTORY", [h for h in getattr(rt, "history", [])][-3:])
try:
    pods = info.runtime.pods
    print("PODS", len(pods) if pods else pods)
except Exception as exc:
    print("PODS_FAIL", str(exc)[:150])
p = api.hf_hub_download(repo_id="josjshid99/ai-ugc-studio-web", filename="README.md", repo_type="space")
t = open(p, encoding="utf-8").read()
first = "\n".join(line for line in t.splitlines()[:12] if line.isascii())
print("README_TOP")
print(first)
