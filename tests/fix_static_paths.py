from pathlib import Path

p = Path(r"C:\AI_UGC_STUDIO\cloud\frontend_static\index.html")
t = p.read_text(encoding="utf-8")
t = t.replace('href="/frontend/css/style.css"', 'href="css/style.css"')
t = t.replace('src="/frontend/js/app.js"', 'src="js/app.js"')
p.write_text(t, encoding="utf-8")
print("PATHS_OK", "frontend/css" not in t and "frontend/js" not in t)
