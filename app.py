from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
import cv2, numpy as np, os, json, base64, uuid
from pathlib import Path

app = FastAPI(title="PokémonGrader")

VAULT = Path("vault.json")
if not VAULT.exists():
    VAULT.write_text("[]", encoding="utf-8")

def grade_image(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error":"Geen geldige afbeelding."}
    h,w = img.shape[:2]
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    blur=cv2.GaussianBlur(gray,(5,5),0)
    edges=cv2.Canny(blur,60,160)
    contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    largest=max(contours,key=cv2.contourArea) if contours else None
    card_area=cv2.contourArea(largest) if largest is not None else 0
    image_area=w*h
    coverage=min(1.0, card_area/image_area if image_area else 0)
    brightness=float(np.mean(gray))
    contrast=float(np.std(gray))
    # Prototype score: intentionally conservative, not a PSA-certified grade.
    centering=max(1,min(10,round(5+coverage*5)))
    corners=max(1,min(10,round(4+contrast/35)))
    edges_score=max(1,min(10,round(5+coverage*4)))
    surface=max(1,min(10,round(6+brightness/64)))
    overall=round((centering+corners+edges_score+surface)/4,1)
    return {
        "grade": overall,
        "subgrades":{
            "Centering":centering,
            "Corners":corners,
            "Edges":edges_score,
            "Surface":surface
        },
        "note":"Prototype computer-vision beoordeling. Geen officiële PSA-beoordeling.",
        "image_size":[w,h]
    }

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.post("/api/grade")
async def grade(file: UploadFile=File(...)):
    return JSONResponse(grade_image(await file.read()))

@app.get("/api/vault")
def vault():
    return JSONResponse(json.loads(VAULT.read_text(encoding="utf-8")))

@app.post("/api/vault")
async def save(card: dict):
    cards=json.loads(VAULT.read_text(encoding="utf-8"))
    card["id"]=str(uuid.uuid4())
    cards.append(card)
    VAULT.write_text(json.dumps(cards,ensure_ascii=False,indent=2),encoding="utf-8")
    return card

HTML = r"""<!doctype html>
<html lang="nl"><head>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#090b12">
<title>PokémonGrader</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#090b12;color:#f5f7fb;font-family:system-ui,-apple-system,sans-serif}
main{max-width:650px;margin:auto;padding:20px}.logo{font-size:30px;font-weight:900;margin:8px 0}
.sub{color:#9da5b4;margin-bottom:22px}.card{background:#121621;border:1px solid #252b39;border-radius:20px;padding:18px;margin:14px 0}
button{width:100%;border:0;border-radius:16px;padding:16px;background:#fff;color:#090b12;font-size:17px;font-weight:800}
input[type=file]{display:none}.camera{display:block;text-align:center;cursor:pointer;padding:20px;border:2px dashed #444d61;border-radius:18px;margin-bottom:12px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.metric{background:#0c0f17;border-radius:14px;padding:14px}.num{font-size:28px;font-weight:900}
.grade{font-size:64px;font-weight:950;text-align:center}.muted{color:#9da5b4}.success{margin-top:12px;color:#7ee787}
</style></head><body><main>
<div class="logo">⚡ PokémonGrader</div>
<div class="sub">Mobiele kaartanalyse • grading prototype</div>
<div class="card">
<label class="camera"><input id="file" type="file" accept="image/*" capture="environment">📷 Maak foto van Pokémon-kaart</label>
<button onclick="grade()">Kaart beoordelen</button>
<div id="status" class="muted" style="margin-top:12px"></div>
</div>
<div id="result"></div>
<div class="card"><b>Vault</b><div class="muted">Bewaar je grades lokaal op de server.</div><button style="margin-top:12px" onclick="loadVault()">Bekijk Vault</button><div id="vault"></div></div>
</main>
<script>
async function grade(){
 const f=document.getElementById('file').files[0];
 if(!f){status.textContent='Kies eerst een foto.';return}
 status.textContent='Kaart wordt geanalyseerd…';
 const fd=new FormData();fd.append('file',f);
 const r=await fetch('/api/grade',{method:'POST',body:fd});const x=await r.json();
 if(x.error){status.textContent=x.error;return}
 status.textContent='Analyse klaar.';
 result.innerHTML=`<div class="card"><div class="muted" style="text-align:center">Totaalscore</div><div class="grade">${x.grade}</div><div class="grid">
 ${Object.entries(x.subgrades).map(([k,v])=>`<div class="metric"><div class="muted">${k}</div><div class="num">${v}/10</div></div>`).join('')}</div>
 <button style="margin-top:12px" onclick='saveCard(${JSON.stringify(x)})'>Opslaan in Vault</button>
 <div class="muted" style="margin-top:12px;font-size:13px">${x.note}</div></div>`;
}
async function saveCard(x){await fetch('/api/vault',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(x)});alert('Opgeslagen in Vault');}
async function loadVault(){const r=await fetch('/api/vault');const x=await r.json();vault.innerHTML=x.length?x.map(c=>`<div style="padding:10px 0;border-bottom:1px solid #252b39">Grade <b>${c.grade}</b> — ${new Date().toLocaleDateString()}</div>`).join(''):'<p class="muted">Vault is leeg.</p>'}
</script></body></html>"""
