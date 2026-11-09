import torch

m = torch.jit.load(
    r"C:\AI_UGC_STUDIO\Wav2Lip\checkpoints\wav2lip_gan.pth",
    map_location="cpu",
)
print("TYPE", type(m))
sd = m.state_dict()
print("PARAMS", len(sd))
keys = list(sd.keys())
for k in keys[:15]:
    print(k, tuple(sd[k].shape))
print("...")
for k in keys[-5:]:
    print(k, tuple(sd[k].shape))
has_disc = [k for k in keys if "discriminator" in k.lower()]
print("DISC_KEYS", len(has_disc))
# Guarda las claves para comparar con models.Wav2Lip
with open(r"C:\AI_UGC_STUDIO\logs\wav2lip_jit_keys.txt", "w") as f:
    f.write("\n".join(keys))
print("SAVED keys")
