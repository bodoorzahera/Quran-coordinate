#!/usr/bin/env python3
"""Quran Word Coordinate Viewer & Editor v4"""
import json,os,argparse,glob,shutil
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import HTMLResponse,FileResponse
import uvicorn

app=FastAPI()
IMAGES_DIR="./images";JSON_DIR="./output";MUSHAF_DIR="./mushaf"

def get_pages():
    pp=set()
    for f in glob.glob(os.path.join(JSON_DIR,"page-*.json")):
        try:pp.add(int(os.path.basename(f).replace("page-","").replace(".json","")))
        except:pass
    return sorted(pp)

def find_img(n):
    for e in["png","jpg","jpeg","webp"]:
        p=os.path.join(IMAGES_DIR,f"page-{n:03d}.{e}")
        if os.path.exists(p):return p

def load_mushaf(n):
    p=os.path.join(MUSHAF_DIR,f"page-{n:03d}.json")
    if not os.path.exists(p):return{}
    with open(p,"r",encoding="utf-8")as f:d=json.load(f)
    m={}
    for l in d.get("lines",[]):
        for w in l.get("words",[]):
            loc=w.get("location","")
            if loc:m[loc]={"word":w.get("word",""),"line":l.get("line",0)}
    return m

@app.get("/",response_class=HTMLResponse)
async def index():return HTML
@app.get("/api/pages")
async def api_pages():return{"pages":get_pages()}
@app.get("/api/page/{n}")
async def api_page(n:int):
    p=os.path.join(JSON_DIR,f"page-{n:03d}.json")
    if not os.path.exists(p):raise HTTPException(404)
    with open(p,"r",encoding="utf-8")as f:d=json.load(f)
    d["mushaf"]=load_mushaf(n);return d
@app.get("/api/image/{n}")
async def api_img(n:int):
    img=find_img(n)
    if not img:raise HTTPException(404)
    return FileResponse(img)
@app.post("/api/page/{n}/save")
async def api_save(n:int,request:Request):
    body=await request.json();p=os.path.join(JSON_DIR,f"page-{n:03d}.json")
    if not os.path.exists(p):raise HTTPException(404)
    bak=p+".bak"
    if not os.path.exists(bak):shutil.copy2(p,bak)
    with open(p,"r",encoding="utf-8")as f:d=json.load(f)
    d["coords"]=body.get("coords",{})
    with open(p,"w",encoding="utf-8")as f:json.dump(d,f,ensure_ascii=False,indent=2)
    return{"ok":True}

HTML=r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>محرر إحداثيات كلمات القرآن</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Tajawal:wght@400;500;700&display=swap');
:root{--bg:#0f172a;--sf:#1e293b;--sf2:#334155;--ac:#e94560;--bl:#3b82f6;--gn:#22c55e;--gd:#eab308;--tx:#f1f5f9;--tx2:#94a3b8}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'Tajawal',sans-serif;background:var(--bg);color:var(--tx);display:flex;flex-direction:column}

.tb{display:flex;align-items:center;gap:5px;padding:6px 10px;background:var(--sf);border-bottom:1px solid rgba(255,255,255,.06);flex-shrink:0;flex-wrap:wrap;z-index:100}
.tb .g{display:flex;align-items:center;gap:3px}
.tb button{background:var(--sf2);color:var(--tx);border:1px solid rgba(255,255,255,.08);border-radius:6px;padding:5px 10px;font:13px/1 'Tajawal',sans-serif;cursor:pointer;white-space:nowrap;touch-action:manipulation;transition:all .1s}
.tb button:active{transform:scale(.95)}
.tb button.on{background:var(--ac);border-color:var(--ac)}
.tb button.grn{background:var(--gn);border-color:var(--gn);color:#000}
.tb button.red{background:#dc2626}
.tb button.lock-btn{font-size:16px;padding:4px 10px}
.tb button.lock-btn.locked{background:#f59e0b;border-color:#f59e0b;color:#000}
.tb button.lock-btn.unlocked{background:#22c55e;border-color:#22c55e;color:#000}
.tb input[type=number]{width:56px;background:var(--sf2);color:var(--tx);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px;font-size:13px;text-align:center;font-family:inherit}
.tb .sep{width:1px;height:22px;background:rgba(255,255,255,.08);margin:0 2px}
.tb .lbl{font-size:11px;color:var(--tx2)}

/* Main viewport */
.vp{flex:1;overflow:hidden;position:relative;background:#0a0f1a}

/* Canvas sits inside viewport, transformed */
.cw{position:absolute;transform-origin:0 0}
.cw .page-frame{background:#000;border-radius:6px;box-shadow:0 8px 40px rgba(0,0,0,.6);padding:0;display:inline-block;position:relative}
.cw .page-frame img{display:block;pointer-events:none;user-select:none;-webkit-user-drag:none}
.cw .ov{position:absolute;top:0;left:0;width:100%;height:100%}

/* Word boxes */
.wb{position:absolute;border:2px solid;border-radius:2px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.wb.interactive{cursor:pointer;touch-action:none}
.wb.interactive:hover{filter:brightness(1.3)}
.wb.sel{border-width:3px;z-index:10;filter:brightness(1.4)}
.wb.nomatch{border-style:dashed!important;opacity:.6}
.wb .wl{font-family:'Amiri',serif;color:#fff;white-space:nowrap;pointer-events:none;line-height:1;direction:rtl;padding:1px 4px;border-radius:2px;background:rgba(0,0,0,.55)}
.wb .wl.err{background:rgba(220,38,38,.6);color:#fca5a5;font-family:monospace;font-size:8px!important;direction:ltr}

.wb .hd{position:absolute;width:18px;height:18px;background:var(--ac);border:2px solid #fff;border-radius:50%;display:none;z-index:20;touch-action:none}
.wb.sel .hd{display:block}
.hd.tl{top:-9px;left:-9px;cursor:nw-resize}.hd.tr{top:-9px;right:-9px;cursor:ne-resize}
.hd.bl{bottom:-9px;left:-9px;cursor:sw-resize}.hd.br{bottom:-9px;right:-9px;cursor:se-resize}

/* Info panel */
.ip{position:fixed;bottom:0;left:0;right:0;background:var(--sf);border-top:2px solid var(--ac);padding:6px 8px;display:none;flex-direction:column;gap:6px;z-index:200;box-shadow:0 -4px 20px rgba(0,0,0,.5)}
.ip.vis{display:flex}
.ip .row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:center}
.ip .wd{font:22px/1 'Amiri',serif;color:var(--gd);direction:rtl;text-align:center}
.ip .fd{display:flex;align-items:center;gap:2px}
.ip .fd label{font-size:11px;color:var(--tx2);min-width:14px;text-align:center}
.ip input{background:var(--sf2);color:var(--tx);border:1px solid rgba(255,255,255,.12);border-radius:4px;padding:3px 4px;font-size:12px;width:48px;text-align:center;font-family:inherit}
.ip .li{width:95px;font:14px 'Amiri',serif;direction:ltr;text-align:center}
.ip button{border:none;border-radius:5px;padding:4px 10px;font:12px 'Tajawal',sans-serif;cursor:pointer;color:#fff}
/* Stepper arrows */
.ip .arrows{display:flex;gap:1px}
.ip .arr{background:var(--sf2);color:var(--tx);border:1px solid rgba(255,255,255,.1);width:26px;height:26px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:11px;touch-action:manipulation;user-select:none;transition:background .1s}
.ip .arr:active{background:var(--ac)}
.ip .arr:first-child{border-radius:4px 0 0 4px}
.ip .arr:last-child{border-radius:0 4px 4px 0}
.ip .arr.single{border-radius:0}

.toast{position:fixed;top:55px;left:50%;transform:translateX(-50%) translateY(-20px);padding:7px 18px;border-radius:8px;font-size:13px;opacity:0;transition:all .3s;z-index:999;pointer-events:none;font-weight:500}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.st{font-size:11px;color:var(--tx2);padding:0 4px}.st .mis{color:var(--ac);font-weight:600}

@media(max-width:600px){.tb{padding:4px 6px;gap:2px}.tb button{padding:4px 7px;font-size:11px}.ip{padding:6px 8px;gap:6px}}
</style>
</head>
<body>
<div class="tb">
  <div class="g">
    <button onclick="prevPage()">◀</button>
    <input type="number" id="pgIn" min="1" max="604" value="3" onchange="loadPage(+this.value)">
    <button onclick="nextPage()">▶</button>
    <span class="lbl" id="pgCnt"></span>
  </div><div class="sep"></div>
  <div class="g">
    <button onclick="doZoom(1.3)">+</button>
    <button onclick="doZoom(0.77)">−</button>
    <button onclick="zoomFit()">ملائمة</button>
    <span class="lbl" id="zLbl">100%</span>
  </div><div class="sep"></div>
  <div class="g">
    <button id="bxBtn" onclick="togBoxes()" class="on">إطارات</button>
    <button id="lblBtn" onclick="togLabels()" class="on">كلمات</button>
  </div><div class="sep"></div>
  <div class="g">
    <button id="lockBtn" class="lock-btn locked" onclick="togLock()">🔒</button>
    <button id="addBtn" onclick="togAdd()" style="display:none">+ إضافة</button>
    <button id="delBtn" class="red" onclick="delSel()" style="display:none">🗑</button>
  </div><div class="sep"></div>
  <div class="g">
    <button class="grn" onclick="saveAll()">💾</button>
    <span class="st" id="stats"></span>
  </div>
</div>

<div class="vp" id="vp">
  <div class="cw" id="cw">
    <div class="page-frame" id="pf">
      <img id="pgImg" src="" alt="">
      <div class="ov" id="ov"></div>
    </div>
  </div>
</div>

<div class="ip" id="infoP">
  <div class="row">
    <div class="wd" id="wordDisp"></div>
    <div class="fd"><label>الموقع:</label><input class="li" id="locIn" placeholder="s:a:w" dir="ltr"></div>
    <button onclick="applyEdits()" style="background:var(--bl)">تطبيق</button>
    <button onclick="desel()" style="background:transparent;border:1px solid rgba(255,255,255,.15)">✕</button>
  </div>
  <div class="row">
    <div class="fd">
      <label>X</label>
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cX',-10)" onpointerup="stepStop()" onpointerleave="stepStop()">«</div>
        <div class="arr single" onpointerdown="stepStart('cX',-1)" onpointerup="stepStop()" onpointerleave="stepStop()">‹</div>
      </div>
      <input type="number" id="cX">
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cX',1)" onpointerup="stepStop()" onpointerleave="stepStop()">›</div>
        <div class="arr single" onpointerdown="stepStart('cX',10)" onpointerup="stepStop()" onpointerleave="stepStop()">»</div>
      </div>
    </div>
    <div class="fd">
      <label>Y</label>
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cY',-10)" onpointerup="stepStop()" onpointerleave="stepStop()">«</div>
        <div class="arr single" onpointerdown="stepStart('cY',-1)" onpointerup="stepStop()" onpointerleave="stepStop()">‹</div>
      </div>
      <input type="number" id="cY">
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cY',1)" onpointerup="stepStop()" onpointerleave="stepStop()">›</div>
        <div class="arr single" onpointerdown="stepStart('cY',10)" onpointerup="stepStop()" onpointerleave="stepStop()">»</div>
      </div>
    </div>
    <div class="fd">
      <label>W</label>
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cW',-10)" onpointerup="stepStop()" onpointerleave="stepStop()">«</div>
        <div class="arr single" onpointerdown="stepStart('cW',-1)" onpointerup="stepStop()" onpointerleave="stepStop()">‹</div>
      </div>
      <input type="number" id="cW">
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cW',1)" onpointerup="stepStop()" onpointerleave="stepStop()">›</div>
        <div class="arr single" onpointerdown="stepStart('cW',10)" onpointerup="stepStop()" onpointerleave="stepStop()">»</div>
      </div>
    </div>
    <div class="fd">
      <label>H</label>
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cH',-10)" onpointerup="stepStop()" onpointerleave="stepStop()">«</div>
        <div class="arr single" onpointerdown="stepStart('cH',-1)" onpointerup="stepStop()" onpointerleave="stepStop()">‹</div>
      </div>
      <input type="number" id="cH">
      <div class="arrows">
        <div class="arr" onpointerdown="stepStart('cH',1)" onpointerup="stepStop()" onpointerleave="stepStop()">›</div>
        <div class="arr single" onpointerdown="stepStart('cH',10)" onpointerup="stepStop()" onpointerleave="stepStop()">»</div>
      </div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
// ─── State ───
let curPage=3,pages=[],coords={},mushaf={};
let showBoxes=true,showLabels=true,addMode=false,selLoc=null,dirty=false;
let editLocked=true; // START LOCKED
let natW=900,natH=1437;
const MARGIN=80; // px margin around image in native coords

// View transform
let vx=0,vy=0,vs=1;
let interaction=null; // {type:'pan'|'pinch'|'boxmove'|'boxresize', ...}

const COLS=[
  {b:'#e94560',bg:'rgba(233,69,96,0.22)'},{b:'#3b82f6',bg:'rgba(59,130,246,0.22)'},
  {b:'#eab308',bg:'rgba(234,179,8,0.22)'},{b:'#22c55e',bg:'rgba(34,197,94,0.22)'},
  {b:'#a855f7',bg:'rgba(168,85,247,0.22)'},{b:'#f97316',bg:'rgba(249,115,22,0.22)'},
  {b:'#06b6d4',bg:'rgba(6,182,212,0.22)'},{b:'#ec4899',bg:'rgba(236,72,153,0.22)'},
];

// ─── Init ───
async function init(){
  const r=await fetch('/api/pages');const d=await r.json();
  pages=d.pages;$('pgCnt').textContent=`/ ${pages.length}`;
  if(pages.length){curPage=pages[0];$('pgIn').value=curPage;await loadPage(curPage);}
}
function $(id){return document.getElementById(id);}

// ─── Page ───
async function loadPage(n){
  n=Math.max(1,Math.min(604,n));curPage=n;$('pgIn').value=n;
  const img=$('pgImg');img.src=`/api/image/${n}`;
  await new Promise(r=>{img.onload=r;img.onerror=()=>r();});
  natW=img.naturalWidth||900;natH=img.naturalHeight||1437;
  // Set image size explicitly
  img.style.width=natW+'px';img.style.height=natH+'px';
  try{const r=await fetch(`/api/page/${n}`);const d=await r.json();coords=d.coords||{};mushaf=d.mushaf||{};}
  catch{coords={};mushaf={};}
  dirty=false;selLoc=null;$('infoP').classList.remove('vis');
  zoomFit();render();updateStats();
}
function prevPage(){const i=pages.indexOf(curPage);if(i>0)loadPage(pages[i-1]);}
function nextPage(){const i=pages.indexOf(curPage);if(i<pages.length-1)loadPage(pages[i+1]);}

// ─── View ───
function applyView(){
  $('cw').style.transform=`translate(${vx}px,${vy}px) scale(${vs})`;
  $('zLbl').textContent=Math.round(vs*100)+'%';
}
function doZoom(factor,cx,cy){
  const vp=$('vp');
  if(cx===undefined){cx=vp.clientWidth/2;cy=vp.clientHeight/2;}
  const old=vs;
  vs=Math.max(0.1,Math.min(6,vs*factor));
  const r=vs/old;
  vx=cx-(cx-vx)*r;
  vy=cy-(cy-vy)*r;
  applyView();render();
}
function zoomFit(){
  const vp=$('vp');
  // Include margins
  const totalW=natW+MARGIN*2;
  const totalH=natH+MARGIN*2;
  vs=Math.min(vp.clientWidth/totalW,vp.clientHeight/totalH);
  vx=(vp.clientWidth-totalW*vs)/2+MARGIN*vs;
  vy=(vp.clientHeight-totalH*vs)/2+MARGIN*vs;
  applyView();render();
}

// ─── Lock/Unlock ───
function togLock(){
  editLocked=!editLocked;
  const btn=$('lockBtn');
  if(editLocked){
    btn.textContent='🔒';btn.className='lock-btn locked';
    $('addBtn').style.display='none';$('delBtn').style.display='none';
    desel();
  }else{
    btn.textContent='🔓';btn.className='lock-btn unlocked';
    $('addBtn').style.display='';$('delBtn').style.display='';
  }
  render();
}

// ─── Stats ───
function updateStats(){
  const cK=Object.keys(coords),mK=Object.keys(mushaf);
  const noM=cK.filter(l=>!mushaf[l]),miss=mK.filter(l=>!coords[l]);
  let h=`إطارات: ${cK.length} | كلمات: ${mK.length}`;
  if(noM.length)h+=` | <span class="mis">بلا كلمة: ${noM.length}</span>`;
  if(miss.length)h+=` | <span class="mis">بلا إطار: ${miss.length}</span>`;
  $('stats').innerHTML=h;
}

// ─── Render ───
function render(){
  const ov=$('ov');ov.innerHTML='';if(!showBoxes)return;
  const locs=Object.keys(coords);
  locs.forEach((loc,i)=>{
    const c=coords[loc];const box=c.h||c;
    if(!box||box.w===undefined)return;
    const col=COLS[i%COLS.length];
    const hasMu=!!mushaf[loc];const isSel=loc===selLoc;

    const div=document.createElement('div');
    div.className='wb'+(isSel?' sel':'')+(hasMu?'':' nomatch')+(!editLocked?' interactive':'');
    div.dataset.loc=loc;
    div.style.left=(box.x/natW*100)+'%';
    div.style.top=(box.y/natH*100)+'%';
    div.style.width=(box.w/natW*100)+'%';
    div.style.height=(box.h/natH*100)+'%';
    div.style.borderColor=col.b;
    div.style.backgroundColor=hasMu?col.bg:'rgba(255,0,0,0.15)';

    if(showLabels){
      const lbl=document.createElement('span');
      if(hasMu){lbl.className='wl';lbl.textContent=mushaf[loc].word;}
      else{lbl.className='wl err';lbl.textContent=loc;}
      const bHpx=box.h*vs,bWpx=box.w*vs;
      let fs=Math.max(6,Math.min(26,bHpx*0.45));
      if(hasMu){const cc=mushaf[loc].word.length;fs=Math.min(fs,Math.max(6,bWpx/(cc*0.5)));}
      lbl.style.fontSize=fs+'px';
      div.appendChild(lbl);
    }

    if(!editLocked){
      ['tl','tr','bl','br'].forEach(h=>{const hd=document.createElement('div');hd.className=`hd ${h}`;hd.dataset.handle=h;div.appendChild(hd);});
    }
    ov.appendChild(div);
  });
}

function togBoxes(){showBoxes=!showBoxes;$('bxBtn').classList.toggle('on',showBoxes);render();}
function togLabels(){showLabels=!showLabels;$('lblBtn').classList.toggle('on',showLabels);render();}

// ─── Add/Delete ───
function togAdd(){
  if(editLocked)return;
  addMode=!addMode;$('addBtn').classList.toggle('on',addMode);
  $('addBtn').textContent=addMode?'❌ إلغاء':'+ إضافة';
  $('ov').style.cursor=addMode?'crosshair':'';
}
function addBox(px,py){
  const w=60,h=50,x=Math.max(0,px-w/2),y=Math.max(0,py-h/2);
  const miss=Object.keys(mushaf).filter(l=>!coords[l]);
  let nl=miss.length?miss[0]:'new:0:1';let nn=1;while(coords[nl]){nn++;nl=`new:0:${nn}`;}
  coords[nl]={h:{x:Math.round(x),y:Math.round(y),w,h}};
  dirty=true;selLoc=nl;render();showInfo(nl);togAdd();updateStats();toast('إطار جديد');
}
function delSel(){
  if(editLocked||!selLoc){toast('حدد إطاراً',1);return;}
  if(!confirm(`حذف ${selLoc}؟`))return;
  delete coords[selLoc];dirty=true;selLoc=null;$('infoP').classList.remove('vis');
  render();updateStats();toast('تم الحذف');
}

// ─── Selection ───
function selectBox(l){if(editLocked)return;selLoc=l;render();showInfo(l);}
function desel(){selLoc=null;$('infoP').classList.remove('vis');render();}
function showInfo(l){
  const p=$('infoP');const c=coords[l];const box=c.h||c;
  $('locIn').value=l;$('cX').value=box.x;$('cY').value=box.y;$('cW').value=box.w;$('cH').value=box.h;
  const wd=$('wordDisp');
  if(mushaf[l]){wd.textContent=mushaf[l].word;wd.style.color='var(--gd)';}
  else{wd.textContent='⚠ لا كلمة';wd.style.color='#f87171';}
  p.classList.add('vis');
}
function applyEdits(){
  if(!selLoc||editLocked)return;
  const nl=$('locIn').value.trim();
  const nx=+$('cX').value,ny=+$('cY').value,nw=+$('cW').value,nh=+$('cH').value;
  if(nl!==selLoc){if(coords[nl]){toast('موجود!',1);return;}coords[nl]=coords[selLoc];delete coords[selLoc];selLoc=nl;}
  const c=coords[selLoc];if(c.h)c.h={x:nx,y:ny,w:nw,h:nh};else coords[selLoc]={h:{x:nx,y:ny,w:nw,h:nh}};
  dirty=true;render();updateStats();showInfo(selLoc);toast('تم');
}
async function saveAll(){
  $('stats').textContent='حفظ...';
  try{const r=await fetch(`/api/page/${curPage}/save`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({coords})});
  if(r.ok){dirty=false;toast('✓ تم الحفظ');updateStats();}else toast('خطأ!',1);}
  catch(e){toast('خطأ: '+e.message,1);}
}

// ─── Coordinate helpers ───
function s2n(cx,cy){
  // screen coords → native image coords
  return{px:(cx-vpRect().left-vx)/vs, py:(cy-vpRect().top-vy)/vs};
}
function vpRect(){return $('vp').getBoundingClientRect();}

function hitBox(px,py){
  if(selLoc&&coords[selLoc]){const b=coords[selLoc].h||coords[selLoc];if(px>=b.x&&px<=b.x+b.w&&py>=b.y&&py<=b.y+b.h)return selLoc;}
  const ll=Object.keys(coords);for(let i=ll.length-1;i>=0;i--){const l=ll[i];const c=coords[l];const b=c.h||c;if(b.w===undefined)continue;if(px>=b.x&&px<=b.x+b.w&&py>=b.y&&py<=b.y+b.h)return l;}
  return null;
}
function hitHandle(px,py){
  if(!selLoc||!coords[selLoc])return null;const b=coords[selLoc].h||coords[selLoc];const thr=18/vs;
  const cc={tl:{x:b.x,y:b.y},tr:{x:b.x+b.w,y:b.y},bl:{x:b.x,y:b.y+b.h},br:{x:b.x+b.w,y:b.y+b.h}};
  for(const[k,pt]of Object.entries(cc)){if(Math.abs(px-pt.x)<thr&&Math.abs(py-pt.y)<thr)return k;}return null;
}

// ─── Pointer handling ───
const vp=$('vp');

function getT(e){
  if(!e.touches)return[{x:e.clientX,y:e.clientY,id:0}];
  return Array.from(e.touches).map(t=>({x:t.clientX,y:t.clientY,id:t.identifier}));
}
function dist2(a,b){return Math.sqrt((a.x-b.x)**2+(a.y-b.y)**2);}
function mid2(a,b){return{x:(a.x+b.x)/2,y:(a.y+b.y)/2};}

vp.addEventListener('touchstart',onDown,{passive:false});
vp.addEventListener('touchmove',onMove,{passive:false});
vp.addEventListener('touchend',onUp,{passive:false});
vp.addEventListener('touchcancel',onUp);
vp.addEventListener('mousedown',onDown);
window.addEventListener('mousemove',onMove);
window.addEventListener('mouseup',onUp);
vp.addEventListener('wheel',e=>{
  e.preventDefault();
  const r=vpRect();
  doZoom(e.deltaY<0?1.2:0.83, e.clientX-r.left, e.clientY-r.top);
},{passive:false});

function onDown(e){
  const tt=getT(e);

  // 2+ fingers → always pinch (regardless of lock)
  if(tt.length>=2){
    e.preventDefault();
    interaction={type:'pinch',d0:dist2(tt[0],tt[1]),m0:mid2(tt[0],tt[1]),vs0:vs,vx0:vx,vy0:vy};
    return;
  }

  const t=tt[0];
  const nat=s2n(t.x,t.y);

  // UNLOCKED mode: check boxes first
  if(!editLocked){
    if(addMode){e.preventDefault();addBox(nat.px,nat.py);return;}
    const hh=hitHandle(nat.px,nat.py);
    if(hh&&selLoc){
      e.preventDefault();const b=coords[selLoc].h||coords[selLoc];
      interaction={type:'boxresize',handle:hh,loc:selLoc,spx:nat.px,spy:nat.py,orig:{...b}};return;
    }
    const hit=hitBox(nat.px,nat.py);
    if(hit){
      e.preventDefault();selectBox(hit);const b=coords[hit].h||coords[hit];
      interaction={type:'boxmove',loc:hit,spx:nat.px,spy:nat.py,orig:{...b}};return;
    }
    desel();
  }

  // Pan (always works - locked or unlocked on empty area)
  e.preventDefault();
  interaction={type:'pan',sx:t.x,sy:t.y,vx0:vx,vy0:vy};
}

function onMove(e){
  if(!interaction)return;
  const tt=getT(e);

  if(interaction.type==='pinch'&&tt.length>=2){
    e.preventDefault();
    const d=dist2(tt[0],tt[1]);
    const m=mid2(tt[0],tt[1]);
    const r=vpRect();
    const cx=m.x-r.left, cy=m.y-r.top;
    const cx0=interaction.m0.x-r.left, cy0=interaction.m0.y-r.top;
    const newS=Math.max(0.1,Math.min(6,interaction.vs0*(d/interaction.d0)));
    const ratio=newS/interaction.vs0;
    vs=newS;
    vx=cx-(cx0-interaction.vx0)*ratio;
    vy=cy-(cy0-interaction.vy0)*ratio;
    applyView();render();return;
  }

  if(interaction.type==='pan'){
    e.preventDefault();const t=tt[0];
    vx=interaction.vx0+(t.x-interaction.sx);
    vy=interaction.vy0+(t.y-interaction.sy);
    applyView();return;
  }

  if(interaction.type==='boxmove'||interaction.type==='boxresize'){
    e.preventDefault();const t=tt[0];const nat=s2n(t.x,t.y);
    const dx=nat.px-interaction.spx,dy=nat.py-interaction.spy;
    const o=interaction.orig;const c=coords[interaction.loc];const b=c.h||c;
    if(interaction.type==='boxmove'){
      b.x=Math.round(Math.max(0,Math.min(natW-o.w,o.x+dx)));
      b.y=Math.round(Math.max(0,Math.min(natH-o.h,o.y+dy)));
    }else{
      const hh=interaction.handle;let nx=o.x,ny=o.y,nw=o.w,nh=o.h;
      if(hh.includes('l')){nx=o.x+dx;nw=o.w-dx;}if(hh.includes('r'))nw=o.w+dx;
      if(hh.includes('t')){ny=o.y+dy;nh=o.h-dy;}if(hh.includes('b'))nh=o.h+dy;
      if(nw<10){nw=10;if(hh.includes('l'))nx=o.x+o.w-10;}
      if(nh<10){nh=10;if(hh.includes('t'))ny=o.y+o.h-10;}
      b.x=Math.round(nx);b.y=Math.round(ny);b.w=Math.round(nw);b.h=Math.round(nh);
    }
    dirty=true;render();if(selLoc===interaction.loc)showInfo(interaction.loc);
  }
}

function onUp(e){
  if(!e.touches||e.touches.length===0)interaction=null;
  else if(e.touches.length===1&&interaction&&interaction.type==='pinch'){
    const t=e.touches[0];
    interaction={type:'pan',sx:t.clientX,sy:t.clientY,vx0:vx,vy0:vy};
  }
}

// ─── Keyboard ───
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;
  switch(e.key){
    case'ArrowLeft':nextPage();break;case'ArrowRight':prevPage();break;
    case'Escape':addMode?togAdd():desel();break;
    case'Delete':case'Backspace':if(!editLocked)delSel();break;
    case'b':case'B':togBoxes();break;case'l':case'L':togLabels();break;
    case'+':case'=':doZoom(1.25);break;case'-':doZoom(0.8);break;
    case'e':case'E':togLock();break;
    case's':if(e.ctrlKey||e.metaKey){e.preventDefault();saveAll();}break;
  }
});

// ─── Stepper arrows (hold to repeat) ───
let stepTimer=null,stepDelay=300;
function stepStart(field,delta){
  stepOnce(field,delta);
  stepDelay=300;
  stepTimer=setTimeout(function repeat(){
    stepOnce(field,delta);
    stepDelay=Math.max(50,stepDelay*0.8);
    stepTimer=setTimeout(repeat,stepDelay);
  },stepDelay);
}
function stepStop(){if(stepTimer){clearTimeout(stepTimer);stepTimer=null;}}
function stepOnce(field,delta){
  if(!selLoc||editLocked)return;
  const inp=$(field);
  inp.value=Math.max(0,+inp.value+delta);
  liveUpdate();
}
function liveUpdate(){
  if(!selLoc)return;
  const c=coords[selLoc];const b=c.h||c;
  b.x=+$('cX').value;b.y=+$('cY').value;b.w=Math.max(5,+$('cW').value);b.h=Math.max(5,+$('cH').value);
  dirty=true;render();
}

function toast(m,err){const t=$('toast');t.textContent=m;t.style.background=err?'#dc2626':'#22c55e';t.style.color=err?'#fff':'#000';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200);}

init();
</script>
</body>
</html>
"""

def main():
    global IMAGES_DIR,JSON_DIR,MUSHAF_DIR
    parser=argparse.ArgumentParser()
    parser.add_argument("--images-dir",default="./images")
    parser.add_argument("--json-dir",default="./output")
    parser.add_argument("--mushaf-dir",default="./mushaf")
    parser.add_argument("--host",default="0.0.0.0")
    parser.add_argument("--port",type=int,default=8006)
    a=parser.parse_args()
    IMAGES_DIR=a.images_dir;JSON_DIR=a.json_dir;MUSHAF_DIR=a.mushaf_dir
    print(f"📖 Quran Coords v4 → http://localhost:{a.port}")
    uvicorn.run(app,host=a.host,port=a.port,log_level="info")

if __name__=="__main__":main()
