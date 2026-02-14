#!/usr/bin/env python3
"""
Quran Word Coordinate Viewer & Editor
======================================
FastAPI app to view page images overlaid with word bounding boxes.

USAGE:
  python3 server.py --images-dir ./images --json-dir ./output --port 8000
  Then open http://localhost:8000
"""

import json, os, argparse, glob
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

app = FastAPI(title="Quran Coords Viewer")

IMAGES_DIR = "./images"
JSON_DIR = "./output"


def get_available_pages():
    pages = []
    for f in sorted(glob.glob(os.path.join(JSON_DIR, "page-*.json"))):
        num = int(Path(f).stem.split("-")[1])
        pages.append(num)
    return pages


def find_image(page_num):
    for ext in ["png", "jpg", "jpeg", "webp"]:
        p = os.path.join(IMAGES_DIR, f"page-{page_num:03d}.{ext}")
        if os.path.exists(p):
            return p
    return None


@app.get("/", response_class=HTMLResponse)
async def index():
    return VIEWER_HTML


@app.get("/api/pages")
async def list_pages():
    return {"pages": get_available_pages()}


@app.get("/api/page/{page_num}")
async def get_page_data(page_num: int):
    json_path = os.path.join(JSON_DIR, f"page-{page_num:03d}.json")
    if not os.path.exists(json_path):
        raise HTTPException(404, f"No JSON for page {page_num}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/api/image/{page_num}")
async def get_image(page_num: int):
    img = find_image(page_num)
    if not img:
        raise HTTPException(404, f"No image for page {page_num}")
    return FileResponse(img)


@app.post("/api/page/{page_num}/update")
async def update_coords(page_num: int, body: dict):
    json_path = os.path.join(JSON_DIR, f"page-{page_num:03d}.json")
    if not os.path.exists(json_path):
        raise HTTPException(404)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    loc = body.get("location")
    layer = body.get("layer", "h")
    updates = body.get("updates", {})
    if loc and loc in data.get("coords", {}):
        for k, v in updates.items():
            if k in ("x", "y", "w", "h"):
                data["coords"][loc][layer][k] = int(v)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"ok": True}
    raise HTTPException(400, "Invalid location")


VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quran Word Coordinates Viewer</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  :root{--bg:#0f1117;--surface:#1a1d27;--surface2:#242837;--border:#2e3345;--text:#e4e6f0;--text2:#8b90a5;--accent:#6c9fff;--accent2:#4a7ae0;--gold:#d4a853}
  body{font-family:'IBM Plex Sans Arabic',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;direction:ltr;overflow:hidden}
  header{background:var(--surface);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  header h1{font-family:'Amiri',serif;font-size:18px;color:var(--gold);white-space:nowrap}
  .nav-controls{display:flex;align-items:center;gap:6px}
  .btn{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:5px 12px;border-radius:5px;cursor:pointer;font-size:13px;transition:background .1s}
  .btn:hover{background:var(--border)}
  .btn.active{background:var(--accent2);border-color:var(--accent)}
  .page-input{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:5px 8px;border-radius:5px;width:60px;text-align:center;font-size:13px}
  .page-input:focus{outline:none;border-color:var(--accent)}
  .lbl{color:var(--text2);font-size:12px}
  .zoom-lbl{font-size:11px;color:var(--text2);min-width:36px;text-align:center}
  .stats{margin-left:auto;font-size:12px;color:var(--text2)}
  .stats b{color:var(--accent);font-weight:500}
  .main{display:flex;height:calc(100vh - 49px)}
  .canvas-area{flex:1;overflow:auto;display:flex;justify-content:center;align-items:flex-start;padding:12px}
  #mainCanvas{cursor:crosshair}
  .side-panel{width:300px;min-width:260px;background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:12px}
  .panel-section{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px}
  .panel-title{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--text2);margin-bottom:8px}
  .sel-loc{text-align:center;font-size:13px;color:var(--accent);font-family:monospace;margin-bottom:6px}
  .coord-row{display:flex;gap:6px;align-items:center;margin-top:4px}
  .coord-label{color:var(--text2);font-size:12px;width:14px;font-weight:600}
  .coord-input{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:3px 6px;border-radius:4px;font-size:12px;width:68px;font-family:monospace}
  .coord-input:focus{outline:none;border-color:var(--accent)}
  .save-btn{background:var(--accent2);color:white;border:none;padding:7px;border-radius:5px;cursor:pointer;font-size:12px;width:100%;margin-top:8px}
  .save-btn:hover{background:var(--accent)}
  .no-sel{color:var(--text2);text-align:center;padding:14px 0;font-size:13px}
  .word-list{max-height:55vh;overflow-y:auto}
  .word-item{display:flex;align-items:center;gap:6px;padding:3px 6px;border-radius:4px;cursor:pointer;font-size:12px}
  .word-item:hover{background:var(--border)}
  .word-item.active{background:rgba(212,168,83,.15)}
  .wi-loc{font-family:monospace;font-size:10px;color:var(--text2);white-space:nowrap}
  .wi-txt{font-family:'Amiri',serif;font-size:15px;direction:rtl;flex:1;text-align:right}
</style>
</head>
<body>
<header>
  <h1>📖 Quran Coords</h1>
  <div class="nav-controls">
    <button class="btn" onclick="prevPage()">◀</button>
    <input type="number" class="page-input" id="pageInput" min="1" max="604" value="3"
           onchange="goToPage(this.value)" onkeydown="if(event.key==='Enter')goToPage(this.value)">
    <button class="btn" onclick="nextPage()">▶</button>
    <span class="lbl">/ <span id="totalPages">604</span></span>
  </div>
  <div class="nav-controls">
    <button class="btn" onclick="zoomOut()">−</button>
    <span class="zoom-lbl" id="zoomLabel">100%</span>
    <button class="btn" onclick="zoomIn()">+</button>
    <button class="btn" onclick="zoomFit()">Fit</button>
  </div>
  <button class="btn active" id="btnBorders" onclick="toggleBorders()">Borders</button>
  <div class="stats">Words: <b id="wordCount">0</b></div>
</header>
<div class="main">
  <div class="canvas-area" id="canvasArea">
    <canvas id="mainCanvas"></canvas>
  </div>
  <div class="side-panel">
    <div class="panel-section">
      <div class="panel-title">Selected Word</div>
      <div id="selContent"><div class="no-sel">اضغط على كلمة في الصورة</div></div>
    </div>
    <div class="panel-section">
      <div class="panel-title">Words on Page</div>
      <div class="word-list" id="wordList"></div>
    </div>
  </div>
</div>
<script>
let curPage=3, pageData=null, selWord=null, showB=true, zoom=1, img=null, nw=900, nh=1437;
const C=['#FF4444','#44BB44','#4488FF','#FFAA22','#BB44FF','#22CCCC','#DD4488','#99AA22'];

function hexRgba(h,a){return`rgba(${parseInt(h.slice(1,3),16)},${parseInt(h.slice(3,5),16)},${parseInt(h.slice(5,7),16)},${a})`}

function draw(){
  const cv=document.getElementById('mainCanvas');
  if(!img||!img.complete)return;
  const dw=Math.round(nw*zoom), dh=Math.round(nh*zoom);
  cv.width=dw; cv.height=dh;
  const ctx=cv.getContext('2d');
  ctx.imageSmoothingEnabled=true;
  ctx.drawImage(img,0,0,dw,dh);
  if(!pageData||!pageData.coords)return;
  const s=zoom;
  Object.entries(pageData.coords).forEach(([loc,layers],i)=>{
    const h=layers.h, x=h.x*s, y=h.y*s, w=h.w*s, ht=h.h*s, c=C[i%C.length];
    if(showB){
      ctx.fillStyle=hexRgba(c,0.08); ctx.fillRect(x,y,w,ht);
      ctx.strokeStyle=hexRgba(c,0.55); ctx.lineWidth=Math.max(1,zoom*1.5);
      ctx.strokeRect(x,y,w,ht);
    }
    if(loc===selWord){
      ctx.fillStyle='rgba(212,168,83,0.25)'; ctx.fillRect(x,y,w,ht);
      ctx.strokeStyle='#d4a853'; ctx.lineWidth=Math.max(2,zoom*2.5);
      ctx.strokeRect(x,y,w,ht);
    }
  });
  document.getElementById('zoomLabel').textContent=Math.round(zoom*100)+'%';
}

document.getElementById('mainCanvas').addEventListener('click',function(e){
  if(!pageData||!pageData.coords)return;
  const r=this.getBoundingClientRect();
  const cx=(e.clientX-r.left)/zoom, cy=(e.clientY-r.top)/zoom;
  let found=null, best=1e9;
  for(const[loc,layers]of Object.entries(pageData.coords)){
    const h=layers.h;
    if(cx>=h.x&&cx<=h.x+h.w&&cy>=h.y&&cy<=h.y+h.h){
      const a=h.w*h.h; if(a<best){best=a;found=loc;}
    }
  }
  if(found)selectWord(found);
  else{selWord=null;draw();renderList();updateSel();}
});

async function fetchPages(){
  try{const r=await fetch('/api/pages'),d=await r.json();
  if(d.pages&&d.pages.length){
    document.getElementById('totalPages').textContent=d.pages[d.pages.length-1];
    curPage=d.pages[0];document.getElementById('pageInput').value=curPage;loadPage(curPage);
  }}catch(e){console.error(e)}
}

async function loadPage(n){
  curPage=n; document.getElementById('pageInput').value=n; selWord=null;
  img=new Image();
  img.onload=()=>{nw=img.naturalWidth;nh=img.naturalHeight;zoomFit();draw();};
  img.src='/api/image/'+n;
  try{const r=await fetch('/api/page/'+n);
    if(!r.ok){pageData=null;return;}
    pageData=await r.json();
    document.getElementById('wordCount').textContent=Object.keys(pageData.coords||{}).length;
    renderList();updateSel();draw();
  }catch(e){pageData=null;}
}

function selectWord(loc){selWord=loc;draw();renderList();updateSel();}

function renderList(){
  const el=document.getElementById('wordList'); el.innerHTML='';
  if(!pageData||!pageData.coords)return;
  const lines={};
  Object.entries(pageData.coords).forEach(([loc,l])=>{
    const k=Math.round(l.h.y/40); if(!lines[k])lines[k]=[]; lines[k].push([loc,l]);
  });
  Object.keys(lines).sort((a,b)=>a-b).forEach(k=>{
    lines[k].sort((a,b)=>b[1].h.x-a[1].h.x).forEach(([loc])=>{
      const d=document.createElement('div');
      d.className='word-item'+(selWord===loc?' active':'');
      d.innerHTML=`<span class="wi-loc">${loc}</span>`;
      d.onclick=()=>selectWord(loc);
      el.appendChild(d);
    });
  });
}

function updateSel(){
  const el=document.getElementById('selContent');
  if(!selWord||!pageData||!pageData.coords[selWord]){
    el.innerHTML='<div class="no-sel">اضغط على كلمة في الصورة</div>';return;
  }
  const h=pageData.coords[selWord].h;
  el.innerHTML=`<div class="sel-loc">${selWord}</div>
    <div class="coord-row"><span class="coord-label">x</span><input class="coord-input" type="number" value="${h.x}" data-prop="x"><span class="coord-label">y</span><input class="coord-input" type="number" value="${h.y}" data-prop="y"></div>
    <div class="coord-row"><span class="coord-label">w</span><input class="coord-input" type="number" value="${h.w}" data-prop="w"><span class="coord-label">h</span><input class="coord-input" type="number" value="${h.h}" data-prop="h"></div>
    <button class="save-btn" onclick="saveCoords()">💾 حفظ</button>`;
}

async function saveCoords(){
  if(!selWord)return;
  const u={}; document.querySelectorAll('#selContent .coord-input').forEach(i=>{u[i.dataset.prop]=parseInt(i.value)});
  try{const r=await fetch('/api/page/'+curPage+'/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:selWord,layer:'h',updates:u})});
    if(r.ok){await loadPage(curPage);selectWord(selWord);}
  }catch(e){console.error(e)}
}

function prevPage(){if(curPage>1)loadPage(curPage-1)}
function nextPage(){if(curPage<604)loadPage(curPage+1)}
function goToPage(n){n=parseInt(n);if(n>=1&&n<=604)loadPage(n)}
function zoomIn(){zoom=Math.min(zoom+.15,4);draw()}
function zoomOut(){zoom=Math.max(zoom-.15,.2);draw()}
function zoomFit(){const a=document.getElementById('canvasArea');zoom=Math.min((a.clientHeight-24)/nh,(a.clientWidth-24)/nw);zoom=Math.max(.2,Math.min(zoom,2));draw()}
function toggleBorders(){showB=!showB;document.getElementById('btnBorders').classList.toggle('active',showB);draw()}

document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT')return;
  if(e.key==='ArrowLeft')nextPage();if(e.key==='ArrowRight')prevPage();
  if(e.key==='b')toggleBorders();if(e.key==='+'||e.key==='=')zoomIn();if(e.key==='-')zoomOut();
  if(e.key==='0')zoomFit();if(e.key==='Escape'){selWord=null;draw();renderList();updateSel();}
});

fetchPages();
</script>
</body>
</html>
"""


def main():
    global IMAGES_DIR, JSON_DIR
    parser = argparse.ArgumentParser(description="Quran Coords Viewer")
    parser.add_argument("--images-dir", "-i", default="./images")
    parser.add_argument("--json-dir", "-j", default="./output")
    parser.add_argument("--port", "-p", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    IMAGES_DIR = os.path.abspath(args.images_dir)
    JSON_DIR = os.path.abspath(args.json_dir)
    print(f"📖 Quran Coords Viewer")
    print(f"   Images: {IMAGES_DIR}")
    print(f"   JSON:   {JSON_DIR}")
    print(f"   URL:    http://localhost:{args.port}")
    pages = get_available_pages()
    print(f"   Found {len(pages)} pages")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
