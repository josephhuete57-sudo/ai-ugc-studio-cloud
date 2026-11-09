from pathlib import Path

p = Path(r"C:\AI_UGC_STUDIO\app\frontend\js\app.js")
t = p.read_text(encoding="utf-8")
old_src = 'src="/api/assets?path=${encodeURIComponent('
old_href = 'href="/api/assets?path=${encodeURIComponent('
new_src = 'src="${assetUrl(encodeURIComponent('
new_href = 'href="${assetUrl(encodeURIComponent('
count = t.count(old_src) + t.count(old_href)
t = t.replace(old_src, new_src).replace(old_href, new_href)
p.write_text(t, encoding="utf-8")
print("PATCHED", count)
