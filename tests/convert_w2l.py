import os
import sys

sys.path.insert(0, r"C:\AI_UGC_STUDIO\Wav2Lip")
import torch
from models import Wav2Lip

src = r"C:\AI_UGC_STUDIO\Wav2Lip\checkpoints\wav2lip_gan.pth"
dst = r"C:\AI_UGC_STUDIO\Wav2Lip\checkpoints\wav2lip_gan_state.pth"

m = torch.jit.load(src, map_location="cpu")
sd = m.state_dict()

ref = Wav2Lip()  # solo para comparar claves
ref_keys = set(ref.state_dict().keys())
jit_keys = set(sd.keys())
print("MATCH", jit_keys == ref_keys)
print("MISSING", sorted(ref_keys - jit_keys)[:10])
print("EXTRA", sorted(jit_keys - ref_keys)[:10])

# Re-guardar en formato legacy (pickle clásico) para que el torch.load del repo
# lo lea como dict {"state_dict": ...} y no como TorchScript.
torch.save({"state_dict": sd}, dst, _use_new_zipfile_serialization=False)
print("SAVED", dst, os.path.getsize(dst))
print("MAGIC", open(dst, "rb").read(2))

chk = torch.load(dst, map_location=lambda s, l: s)
print("RELOAD_OK", type(chk), sorted(chk.keys()), len(chk["state_dict"]))
