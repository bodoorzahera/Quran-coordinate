#!/usr/bin/env python3
"""Quran Word Coordinate Viewer & Editor v6"""
import json,os,argparse,glob,shutil,sqlite3

_PKG_DATA = os.path.join(os.path.dirname(__file__), "data")

def _lazy_imports():
    from fastapi import FastAPI,HTTPException,Request
    from fastapi.responses import HTMLResponse,FileResponse
    import uvicorn
    return FastAPI,HTTPException,Request,HTMLResponse,FileResponse,uvicorn

app = None
CFG={"img":"./images","js":_PKG_DATA,"mu":"./mushaf","wf":"./word_freq.db","ver":"./app_version.json"}

def _ensure_app():
    global app
    if app is not None:
        return app
    FastAPI,HTTPException,Request,HTMLResponse,FileResponse,uvicorn = _lazy_imports()
    app = FastAPI()

    def get_wf_conn():
        p=CFG["wf"]
        if not os.path.exists(p):return None
        return sqlite3.connect(p)

    def pages_list():
        pp=set()
        for f in glob.glob(os.path.join(CFG["js"],"page-*.json")):
            try:pp.add(int(os.path.basename(f).split("-")[1].split(".")[0]))
            except:pass
        return sorted(pp)

    def find_img(n):
        for e in["png","jpg","jpeg","webp"]:
            p=os.path.join(CFG["img"],f"page-{n:03d}.{e}")
            if os.path.exists(p):return p

    def load_mu(n):
        p=os.path.join(CFG["mu"],f"page-{n:03d}.json")
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
    async def ap():return{"pages":pages_list()}

    @app.get("/api/page/{n}")
    async def gp(n:int):
        p=os.path.join(CFG["js"],f"page-{n:03d}.json")
        if not os.path.exists(p):raise HTTPException(404)
        with open(p,"r",encoding="utf-8")as f:d=json.load(f)
        d["mushaf"]=load_mu(n);return d

    @app.get("/api/image/{n}")
    async def gi(n:int):
        img=find_img(n)
        if not img:raise HTTPException(404)
        return FileResponse(img)

    @app.post("/api/page/{n}/save")
    async def sv(n:int,req:Request):
        body=await req.json();p=os.path.join(CFG["js"],f"page-{n:03d}.json")
        if not os.path.exists(p):raise HTTPException(404)
        bak=p+".bak"
        if not os.path.exists(bak):shutil.copy2(p,bak)
        with open(p,"r",encoding="utf-8")as f:d=json.load(f)
        d["coords"]=body.get("coords",{})
        with open(p,"w",encoding="utf-8")as f:json.dump(d,f,ensure_ascii=False,indent=2)
        return{"ok":True}

    @app.get("/api/word-freq/page/{n}")
    async def wf_page(n:int):
        conn=get_wf_conn()
        if not conn:return{"freqs":{}}
        c=conn.cursor()
        c.execute("""
            SELECT wo.location, wv.vocalized, wb.bare, wb.count as bare_count, wv.count as voc_count, wb.bare_id
            FROM word_occurrence wo
            JOIN word_vocalized wv ON wv.voc_id=wo.voc_id
            JOIN word_bare wb ON wb.bare_id=wv.bare_id
            WHERE wo.page=?
        """,(n,))
        freqs={}
        for loc,voc,bare,bc,vc,bid in c.fetchall():
            freqs[loc]={"bare":bare,"bare_count":bc,"bare_id":bid}
        conn.close()
        return{"freqs":freqs}

    @app.get("/api/word-freq/variants/{bare_id}")
    async def wf_variants(bare_id:int):
        conn=get_wf_conn()
        if not conn:return{"variants":[]}
        c=conn.cursor()
        c.execute("SELECT bare FROM word_bare WHERE bare_id=?",(bare_id,))
        row=c.fetchone()
        bare=row[0] if row else ""
        c.execute("""
            SELECT voc_id, vocalized, count FROM word_vocalized
            WHERE bare_id=? ORDER BY count DESC
        """,(bare_id,))
        variants=[{"voc_id":r[0],"vocalized":r[1],"count":r[2]} for r in c.fetchall()]
        conn.close()
        return{"bare":bare,"bare_id":bare_id,"variants":variants}

    @app.get("/api/word-freq/occurrences/{voc_id}")
    async def wf_occurrences(voc_id:int):
        conn=get_wf_conn()
        if not conn:return{"occurrences":[]}
        c=conn.cursor()
        c.execute("SELECT vocalized FROM word_vocalized WHERE voc_id=?",(voc_id,))
        row=c.fetchone()
        vocalized=row[0] if row else ""
        c.execute("""
            SELECT wo.page, wo.sura, wo.ayah, wo.word_pos, wo.location,
                   COALESCE(sn.name,'') as sura_name
            FROM word_occurrence wo
            LEFT JOIN sura_names sn ON sn.sura=wo.sura
            WHERE wo.voc_id=?
            ORDER BY wo.sura, wo.ayah, wo.word_pos
        """,(voc_id,))
        occs=[{"page":r[0],"sura":r[1],"ayah":r[2],"word_pos":r[3],"location":r[4],"sura_name":r[5]} for r in c.fetchall()]
        conn.close()
        return{"vocalized":vocalized,"voc_id":voc_id,"occurrences":occs}

    _mutashabihat_cache = {}

    import re as _re
    _ARABIC_NUMS = _re.compile(r'[\u0660-\u0669\u06F0-\u06F9\s]+$')

    def _clean_word(w):
        return _ARABIC_NUMS.sub('', w).strip()

    def _load_all_ayahs():
        """Load all mushaf pages and return list of ayah dicts sorted by location."""
        mu_dir = CFG["mu"]
        # Map (sura, ayah) -> {words: [...], page: int}
        ayah_map = {}
        for page_num in range(1, 605):
            p = os.path.join(mu_dir, f"page-{page_num:03d}.json")
            if not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for line in data.get("lines", []):
                if line.get("type") != "text":
                    continue
                for word in line.get("words", []):
                    loc = word.get("location", "")
                    raw = word.get("word", "")
                    if not loc:
                        continue
                    parts = loc.split(":")
                    if len(parts) < 3:
                        continue
                    try:
                        sura = int(parts[0])
                        ayah = int(parts[1])
                        wpos = int(parts[2])
                    except ValueError:
                        continue
                    key = (sura, ayah)
                    if key not in ayah_map:
                        ayah_map[key] = {"sura": sura, "ayah": ayah, "page": page_num, "words": []}
                    ayah_map[key]["words"].append((wpos, _clean_word(raw)))
        # Sort words within each ayah and build final list
        ayahs = []
        for key in sorted(ayah_map.keys()):
            entry = ayah_map[key]
            entry["words"].sort(key=lambda x: x[0])
            entry["clean_words"] = [w for _, w in entry["words"]]
            ayahs.append(entry)
        return ayahs

    def _get_sura_names():
        conn = get_wf_conn()
        if not conn:
            return {}
        try:
            c = conn.cursor()
            c.execute("SELECT sura, name FROM sura_names")
            names = {row[0]: row[1] for row in c.fetchall()}
            conn.close()
            return names
        except Exception:
            conn.close()
            return {}

    @app.get("/api/version")
    async def version():
        p=CFG["ver"]
        if not os.path.exists(p):
            return{"version":"1.0.0","release_date":"","download_url":"","changelog":[]}
        with open(p,"r",encoding="utf-8")as f:return json.load(f)

    @app.get("/api/mutashabihat/{n}")
    async def mutashabihat(n: int):
        if n < 1 or n > 20:
            from fastapi import HTTPException as _HE
            raise _HE(400, detail="n must be between 1 and 20")
        if n in _mutashabihat_cache:
            return _mutashabihat_cache[n]

        ayahs = _load_all_ayahs()
        sura_names = _get_sura_names()

        # Build index: prefix tuple -> list of ayah indices
        from collections import defaultdict as _dd
        groups_map = _dd(list)
        for idx, ayah in enumerate(ayahs):
            words = ayah["clean_words"]
            if len(words) < n:
                continue
            key = tuple(words[:n])
            groups_map[key].append(idx)

        # Filter groups with 2+ ayahs
        result_groups = []
        for key, indices in groups_map.items():
            if len(indices) < 2:
                continue
            group_ayahs = []
            for idx in indices:
                ayah = ayahs[idx]
                sura = ayah["sura"]
                ayah_num = ayah["ayah"]
                text = " ".join(ayah["clean_words"])
                # Previous ayah context: last 5 words of previous ayah
                prev_text = ""
                if idx > 0:
                    prev = ayahs[idx - 1]
                    if prev["sura"] == sura:
                        prev_text = " ".join(prev["clean_words"][-5:])
                # Next ayah context: first 5 words of next ayah
                next_text = ""
                if idx < len(ayahs) - 1:
                    nxt = ayahs[idx + 1]
                    if nxt["sura"] == sura:
                        next_text = " ".join(nxt["clean_words"][:5])
                group_ayahs.append({
                    "sura": sura,
                    "ayah": ayah_num,
                    "text": text,
                    "prev_text": prev_text,
                    "next_text": next_text,
                    "page": ayah["page"],
                    "sura_name": sura_names.get(sura, ""),
                })
            result_groups.append({
                "prefix": " ".join(key),
                "count": len(indices),
                "ayahs": group_ayahs,
            })

        # Sort by count descending then by prefix
        result_groups.sort(key=lambda g: (-g["count"], g["prefix"]))

        result = {"n": n, "total_groups": len(result_groups), "groups": result_groups}
        _mutashabihat_cache[n] = result
        return result

    return app

HTML=r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Quran Word Coordinates Viewer</title>
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0f172a;--sf:#1e293b;--sf2:#334155;--brd:rgba(255,255,255,.08);
  --ac:#e94560;--bl:#3b82f6;--gn:#22c55e;--gd:#eab308;
  --tx:#f1f5f9;--tx2:#94a3b8;--vpbg:#080c15;
}
[data-theme="light"]{
  --bg:#f0f2f5;--sf:#ffffff;--sf2:#e5e7eb;--brd:rgba(0,0,0,.1);
  --ac:#dc2626;--bl:#2563eb;--gn:#16a34a;--gd:#ca8a04;
  --tx:#1e293b;--tx2:#64748b;--vpbg:#d1d5db;
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'Tajawal',sans-serif;background:var(--vpbg);color:var(--tx)}
#toolbar{
  position:fixed;top:0;left:0;right:0;z-index:100;
  display:flex;align-items:center;gap:6px;padding:8px 12px;
  background:var(--sf);border-bottom:2px solid var(--brd);
  flex-wrap:wrap;font-size:15px;
}
#toolbar .g{display:flex;align-items:center;gap:4px}
.btn{
  background:var(--sf2);color:var(--tx);border:1px solid var(--brd);
  border-radius:8px;padding:7px 14px;font:inherit;font-size:15px;
  cursor:pointer;white-space:nowrap;touch-action:manipulation;transition:all .1s;
}
.btn:active{transform:scale(.94);opacity:.8}
.btn.on{background:var(--ac);color:#fff;border-color:var(--ac)}
.btn.grn{background:var(--gn);color:#fff;border-color:var(--gn)}
.btn.red{background:#dc2626;color:#fff}
.btn.lock{font-size:20px;padding:5px 12px}
.btn.lock.locked{background:#f59e0b;color:#000}
.btn.lock.unlocked{background:var(--gn);color:#fff}
#toolbar input[type=number]{
  width:60px;background:var(--sf2);color:var(--tx);border:1px solid var(--brd);
  border-radius:8px;padding:7px 6px;font-size:15px;text-align:center;font-family:inherit;
}
#toolbar .sep{width:1px;height:28px;background:var(--brd);margin:0 2px}
#toolbar .lbl{font-size:13px;color:var(--tx2)}
.st{font-size:12px;color:var(--tx2)}.st .mis{color:var(--ac);font-weight:700}
#vp{position:fixed;left:0;right:0;bottom:0;overflow:hidden;background:var(--vpbg);touch-action:none}
.cw{position:absolute;transform-origin:0 0}
.pf{background:#000;border-radius:6px;box-shadow:0 8px 40px rgba(0,0,0,.5);display:inline-block;position:relative}
.pf img{display:block;pointer-events:none;user-select:none;-webkit-user-drag:none}
.pf .ov{position:absolute;top:0;left:0;width:100%;height:100%}
.wb{position:absolute;border:2px solid;border-radius:2px;display:flex;align-items:center;justify-content:center;overflow:visible;cursor:pointer}
.wb:hover{filter:brightness(1.25)}.wb.sel{border-width:3px;z-index:10;filter:brightness(1.4)}
.wb.nomatch{border-style:dashed!important;opacity:.55}
.wb .wl{font-family:'Amiri',serif;color:#fff;white-space:nowrap;pointer-events:none;line-height:1;direction:rtl;padding:1px 4px;border-radius:2px;background:rgba(0,0,0,.55);overflow:hidden;text-overflow:ellipsis;max-width:100%}
.wb .wl.err{background:rgba(220,38,38,.6);color:#fca5a5;font-family:monospace;font-size:9px!important;direction:ltr}
.wb .hd{position:absolute;width:20px;height:20px;background:var(--ac);border:2px solid #fff;border-radius:50%;display:none;z-index:20;touch-action:none}
.wb.sel .hd{display:block}
.hd.tl{top:-10px;left:-10px;cursor:nw-resize}.hd.tr{top:-10px;right:-10px;cursor:ne-resize}
.hd.bl{bottom:-10px;left:-10px;cursor:sw-resize}.hd.br{bottom:-10px;right:-10px;cursor:se-resize}
#infoP{
  position:fixed;bottom:0;left:0;right:0;z-index:200;
  background:var(--sf);border-top:2px solid var(--ac);
  padding:8px 10px;display:none;flex-direction:column;gap:6px;
  box-shadow:0 -4px 20px rgba(0,0,0,.4);font-size:15px;
}
#infoP.vis{display:flex}
#infoP .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:center}
#infoP .wd{font:24px/1 'Amiri',serif;color:var(--gd);direction:rtl;text-align:center}
#infoP .fd{display:flex;align-items:center;gap:1px}
#infoP .fd label{font-size:13px;color:var(--tx2);width:20px;text-align:center;font-weight:700}
#infoP input{background:var(--sf2);color:var(--tx);border:1px solid var(--brd);padding:5px 4px;font-size:14px;width:50px;text-align:center;font-family:inherit;border-radius:0}
#infoP .li{width:100px;font:15px 'Amiri',serif;direction:ltr;text-align:center;border-radius:6px}
.ibtn{border:none;border-radius:6px;padding:6px 14px;font:15px 'Tajawal',sans-serif;cursor:pointer;color:#fff}
.ar{
  background:var(--sf2);color:var(--tx);border:1px solid var(--brd);
  min-width:34px;height:34px;display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:16px;font-weight:700;touch-action:manipulation;user-select:none;
}
.ar:active{background:var(--ac);color:#fff}
.ar.ll{border-radius:6px 0 0 6px}.ar.rr{border-radius:0 6px 6px 0}
.toast{position:fixed;top:60px;left:50%;transform:translateX(-50%) translateY(-20px);padding:8px 20px;border-radius:8px;font-size:14px;opacity:0;transition:all .3s;z-index:999;pointer-events:none;font-weight:600}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.wf-badge{
  position:absolute;bottom:-20px;left:50%;transform:translateX(-50%);
  background:rgba(37,99,235,0.9);color:#fff;font-size:13px;font-weight:700;
  padding:2px 8px;border-radius:10px;cursor:pointer;
  font-family:'Tajawal',sans-serif;white-space:nowrap;pointer-events:auto;
  z-index:5;line-height:1.4;min-width:24px;text-align:center;
  box-shadow:0 2px 6px rgba(0,0,0,.3);
}
.wf-badge:hover{background:rgba(37,99,235,1);transform:translateX(-50%) scale(1.2)}
#wfPopup{
  position:fixed;z-index:300;background:var(--sf);border:2px solid var(--ac);
  border-radius:12px;padding:0;min-width:280px;max-width:90vw;max-height:70vh;
  box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;overflow:hidden;font-family:'Tajawal',sans-serif;
}
#wfPopup.vis{display:flex;flex-direction:column}
#wfPopup .wfh{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--ac);color:#fff;font-size:16px;}
#wfPopup .wfh .wfw{font-family:'Amiri',serif;font-size:22px;direction:rtl}
#wfPopup .wfh .wfc{font-size:13px;opacity:.85}
#wfPopup .wfh button{background:none;border:none;color:#fff;font-size:20px;cursor:pointer;padding:2px 6px}
#wfPopup .wfb{overflow-y:auto;max-height:55vh;padding:8px}
.var-row{display:flex;align-items:center;justify-content:space-between;padding:8px 10px;margin:3px 0;border-radius:8px;background:var(--sf2);cursor:pointer;transition:background .1s;gap:8px;}
.var-row:hover{background:var(--ac);color:#fff}
.var-row .vw{font-family:'Amiri',serif;font-size:20px;direction:rtl;flex:1}
.var-row .vc{background:var(--bl);color:#fff;padding:2px 10px;border-radius:12px;font-size:13px;font-weight:700;min-width:32px;text-align:center}
#occPopup{
  position:fixed;z-index:310;background:var(--sf);border:2px solid var(--gd);
  border-radius:12px;padding:0;min-width:300px;max-width:92vw;max-height:75vh;
  box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;overflow:hidden;
}
#occPopup.vis{display:flex;flex-direction:column}
#occPopup .occh{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--gd);color:#000;font-size:15px;}
#occPopup .occh .occw{font-family:'Amiri',serif;font-size:20px;direction:rtl}
#occPopup .occb{overflow-y:auto;max-height:60vh;padding:6px}
.occ-row{display:flex;align-items:center;gap:8px;padding:7px 10px;margin:2px 0;border-radius:6px;background:var(--sf2);cursor:pointer;transition:background .1s;font-size:14px;}
.occ-row:hover{background:var(--bl);color:#fff}
.occ-row .occ-sura{font-weight:700;min-width:80px}
.occ-row .occ-ref{color:var(--tx2);font-size:12px;direction:ltr}
</style>
</head>
<body>
<div id="toolbar">
 <div class="g">
  <button class="btn" onclick="prevPage()">&#9664;</button>
  <input type="number" id="pgIn" min="1" max="604" value="1" onchange="loadPage(+this.value)">
  <button class="btn" onclick="nextPage()">&#9654;</button>
  <span class="lbl" id="pgCnt"></span>
 </div><div class="sep"></div>
 <div class="g">
  <button class="btn" onclick="doZoom(1.3)">+</button>
  <button class="btn" onclick="doZoom(.77)">-</button>
  <button class="btn" onclick="zoomFit()">Fit</button>
  <span class="lbl" id="zLbl">100%</span>
 </div><div class="sep"></div>
 <div class="g">
  <button class="btn on" id="bxBtn" onclick="togBoxes()">Boxes</button>
  <button class="btn on" id="lblBtn" onclick="togLabels()">Labels</button>
 </div><div class="sep"></div>
 <div class="g">
  <button class="btn lock locked" id="lockBtn" onclick="togLock()">&#128274;</button>
  <button class="btn" id="addBtn" onclick="togAdd()" style="display:none">+ Add</button>
  <button class="btn red" id="delBtn" onclick="delSel()" style="display:none">Del</button>
 </div><div class="sep"></div>
 <div class="g">
  <button class="btn grn" onclick="saveAll()">Save</button>
  <span class="st" id="stats"></span>
 </div><div class="sep"></div>
 <div class="g">
  <button class="btn" onclick="uiZoom(-1)">A-</button>
  <button class="btn" onclick="uiZoom(1)">A+</button>
  <button class="btn" id="themeBtn" onclick="togTheme()">&#9728;&#65039;</button>
 </div><div class="sep"></div>
 <div class="g">
  <span class="lbl">Badge</span>
  <button class="btn" onclick="badgeZoom(-1)" style="padding:3px 8px">-</button>
  <button class="btn" onclick="badgeZoom(1)" style="padding:3px 8px">+</button>
 </div><div class="sep"></div>
 <a href="/download/" target="_blank" class="btn" style="background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:700;border:none;box-shadow:0 0 10px rgba(22,163,74,.4)">
  <span style="font-size:18px">&#11015;</span> تطبيق Android
 </a>
</div>
<div id="vp">
 <div class="cw" id="cw">
  <div class="pf"><img id="pgImg" src=""><div class="ov" id="ov"></div></div>
 </div>
</div>
<div id="infoP">
 <div class="row">
  <div class="wd" id="wordDisp"></div>
  <div class="fd"><label style="width:auto">Loc</label><input class="li" id="locIn" dir="ltr"></div>
  <button class="ibtn" onclick="applyLoc()" style="background:var(--bl)">Apply</button>
  <button class="ibtn" onclick="desel()" style="background:var(--sf2);color:var(--tx)">X</button>
 </div>
 <div class="row" id="editRow">
  <div class="fd"><label>X</label>
   <div class="ar ll" data-f="cX" data-d="-10">&raquo;</div><div class="ar" data-f="cX" data-d="-1">&rsaquo;</div>
   <input type="number" id="cX">
   <div class="ar" data-f="cX" data-d="1">&lsaquo;</div><div class="ar rr" data-f="cX" data-d="10">&laquo;</div>
  </div>
  <div class="fd"><label>Y</label>
   <div class="ar ll" data-f="cY" data-d="-10">&raquo;</div><div class="ar" data-f="cY" data-d="-1">&rsaquo;</div>
   <input type="number" id="cY">
   <div class="ar" data-f="cY" data-d="1">&lsaquo;</div><div class="ar rr" data-f="cY" data-d="10">&laquo;</div>
  </div>
  <div class="fd"><label>W</label>
   <div class="ar ll" data-f="cW" data-d="-10">&raquo;</div><div class="ar" data-f="cW" data-d="-1">&rsaquo;</div>
   <input type="number" id="cW">
   <div class="ar" data-f="cW" data-d="1">&lsaquo;</div><div class="ar rr" data-f="cW" data-d="10">&laquo;</div>
  </div>
  <div class="fd"><label>H</label>
   <div class="ar ll" data-f="cH" data-d="-10">&raquo;</div><div class="ar" data-f="cH" data-d="-1">&rsaquo;</div>
   <input type="number" id="cH">
   <div class="ar" data-f="cH" data-d="1">&lsaquo;</div><div class="ar rr" data-f="cH" data-d="10">&laquo;</div>
  </div>
 </div>
</div>
<div class="toast" id="toast"></div>
<div id="wfPopup">
 <div class="wfh"><div><span class="wfw" id="wfWord"></span> <span class="wfc" id="wfCount"></span></div><button onclick="closeWf()">X</button></div>
 <div class="wfb" id="wfBody"></div>
</div>
<div id="occPopup">
 <div class="occh"><div><span class="occw" id="occWord"></span> <span id="occCount" style="font-size:13px"></span></div><button onclick="closeOcc()" style="background:none;border:none;color:#000;font-size:20px;cursor:pointer">X</button></div>
 <div class="occb" id="occBody"></div>
</div>
<script>
const $=id=>document.getElementById(id);
let curPage=1,pages=[],coords={},mushaf={};
let showBoxes=true,showLabels=true,addMode=false,selLoc=null,dirty=false;
let editLocked=true,natW=900,natH=1437;
let wordFreqs={};
const MARGIN=80;
let vx=0,vy=0,vs=1,interaction=null;
const BADGE_SIZES=[8,10,13,16,20,24,30];
let badgeIdx=2;
const UI_S=[0.75,0.85,1,1.15,1.3,1.5,1.7];
let uiIdx=2;
let darkMode=true;
const COLS=[
  {b:'#e94560',bg:'rgba(233,69,96,0.22)'},{b:'#3b82f6',bg:'rgba(59,130,246,0.22)'},
  {b:'#eab308',bg:'rgba(234,179,8,0.22)'},{b:'#22c55e',bg:'rgba(34,197,94,0.22)'},
  {b:'#a855f7',bg:'rgba(168,85,247,0.22)'},{b:'#f97316',bg:'rgba(249,115,22,0.22)'},
  {b:'#06b6d4',bg:'rgba(6,182,212,0.22)'},{b:'#ec4899',bg:'rgba(236,72,153,0.22)'},
];
async function init(){
  const r=await fetch('/api/pages');const d=await r.json();
  pages=d.pages;$('pgCnt').textContent=`/ ${pages.length}`;
  const su=localStorage.getItem('uiIdx');if(su!=null)uiIdx=+su;
  const sb=localStorage.getItem('badgeIdx');if(sb!=null)badgeIdx=+sb;
  const st=localStorage.getItem('theme');if(st==='light'){darkMode=false;document.documentElement.dataset.theme='light';$('themeBtn').innerHTML='&#127769;';}
  applyUi();
  if(pages.length){curPage=pages[0];$('pgIn').value=curPage;await loadPage(curPage);}
}
function togTheme(){
  darkMode=!darkMode;
  if(darkMode){document.documentElement.removeAttribute('data-theme');$('themeBtn').innerHTML='&#9728;&#65039;';localStorage.setItem('theme','dark');}
  else{document.documentElement.dataset.theme='light';$('themeBtn').innerHTML='&#127769;';localStorage.setItem('theme','light');}
}
function uiZoom(d){uiIdx=Math.max(0,Math.min(UI_S.length-1,uiIdx+d));applyUi();localStorage.setItem('uiIdx',uiIdx);}
function badgeZoom(d){badgeIdx=Math.max(0,Math.min(BADGE_SIZES.length-1,badgeIdx+d));localStorage.setItem('badgeIdx',badgeIdx);render();}
function applyUi(){
  const s=UI_S[uiIdx];
  $('toolbar').style.fontSize=(15*s)+'px';$('toolbar').style.padding=(8*s)+'px '+(12*s)+'px';
  document.querySelectorAll('#toolbar .btn').forEach(b=>{b.style.padding=(7*s)+'px '+(14*s)+'px';b.style.fontSize=(15*s)+'px';b.style.borderRadius=(8*s)+'px';});
  document.querySelectorAll('#toolbar input').forEach(b=>{b.style.padding=(7*s)+'px';b.style.fontSize=(15*s)+'px';});
  $('infoP').style.fontSize=(15*s)+'px';$('infoP').style.padding=(8*s)+'px '+(10*s)+'px';
  document.querySelectorAll('#infoP .ar').forEach(b=>{b.style.minWidth=(34*s)+'px';b.style.height=(34*s)+'px';b.style.fontSize=(16*s)+'px';});
  document.querySelectorAll('#infoP input').forEach(b=>{b.style.fontSize=(14*s)+'px';b.style.padding=(5*s)+'px';});
  document.querySelectorAll('#infoP .ibtn').forEach(b=>{b.style.fontSize=(15*s)+'px';b.style.padding=(6*s)+'px '+(14*s)+'px';});
  requestAnimationFrame(()=>{$('vp').style.top=$('toolbar').offsetHeight+'px';});
}
async function loadPage(n){
  n=Math.max(1,Math.min(604,n));curPage=n;$('pgIn').value=n;
  const img=$('pgImg');img.src=`/api/image/${n}`;
  await new Promise(r=>{img.onload=r;img.onerror=()=>r();});
  natW=img.naturalWidth||900;natH=img.naturalHeight||1437;
  img.style.width=natW+'px';img.style.height=natH+'px';
  try{const r=await fetch(`/api/page/${n}`);const d=await r.json();coords=d.coords||{};mushaf=d.mushaf||{};}catch{coords={};mushaf={};}
  try{const r=await fetch(`/api/word-freq/page/${n}`);const d=await r.json();wordFreqs=d.freqs||{};}catch{wordFreqs={};}
  dirty=false;selLoc=null;$('infoP').classList.remove('vis');zoomFit();render();updateStats();
}
function prevPage(){const i=pages.indexOf(curPage);if(i>0)loadPage(pages[i-1]);}
function nextPage(){const i=pages.indexOf(curPage);if(i<pages.length-1)loadPage(pages[i+1]);}
function applyView(){$('cw').style.transform=`translate(${vx}px,${vy}px) scale(${vs})`;$('zLbl').textContent=Math.round(vs*100)+'%';}
function doZoom(f,cx,cy){const v=$('vp');if(cx===undefined){cx=v.clientWidth/2;cy=v.clientHeight/2;}const o=vs;vs=Math.max(0.1,Math.min(6,vs*f));const r=vs/o;vx=cx-(cx-vx)*r;vy=cy-(cy-vy)*r;applyView();render();}
function zoomFit(){const v=$('vp'),tw=natW+MARGIN*2,th=natH+MARGIN*2;vs=Math.min(v.clientWidth/tw,v.clientHeight/th);vx=(v.clientWidth-tw*vs)/2+MARGIN*vs;vy=(v.clientHeight-th*vs)/2+MARGIN*vs;applyView();render();}
function togLock(){
  editLocked=!editLocked;const b=$('lockBtn');
  if(editLocked){b.innerHTML='&#128274;';b.className='btn lock locked';$('addBtn').style.display='none';$('delBtn').style.display='none';$('editRow').style.display='none';}
  else{b.innerHTML='&#128275;';b.className='btn lock unlocked';$('addBtn').style.display='';$('delBtn').style.display='';if(selLoc)$('editRow').style.display='';}
  render();
}
function updateStats(){
  const cK=Object.keys(coords),mK=Object.keys(mushaf);
  const noM=cK.filter(l=>!mushaf[l]),miss=mK.filter(l=>!coords[l]);
  let h=`${cK.length}/${mK.length}`;
  if(noM.length)h+=` <span class="mis">${noM.length}!</span>`;
  if(miss.length)h+=` <span class="mis">-${miss.length}</span>`;
  $('stats').innerHTML=h;
}
function render(){
  const ov=$('ov');ov.innerHTML='';if(!showBoxes)return;
  Object.keys(coords).forEach((loc,i)=>{
    const c=coords[loc],box=c.h||c;if(!box||box.w===undefined)return;
    const col=COLS[i%COLS.length],hasMu=!!mushaf[loc],isSel=loc===selLoc;
    const div=document.createElement('div');
    div.className='wb'+(isSel?' sel':'')+(hasMu?'':' nomatch');
    div.dataset.loc=loc;
    div.style.cssText=`left:${box.x/natW*100}%;top:${box.y/natH*100}%;width:${box.w/natW*100}%;height:${box.h/natH*100}%;border-color:${col.b};background:${hasMu?col.bg:'rgba(255,0,0,0.15)'}`;
    if(showLabels){
      const lbl=document.createElement('span');
      lbl.className=hasMu?'wl':'wl err';lbl.textContent=hasMu?mushaf[loc].word:loc;
      const bH=box.h*vs,bW=box.w*vs;let fs=Math.max(6,Math.min(26,bH*0.45));
      if(hasMu)fs=Math.min(fs,Math.max(6,bW/(mushaf[loc].word.length*0.5)));
      lbl.style.fontSize=fs+'px';div.appendChild(lbl);
    }
    if(!editLocked&&isSel)['tl','tr','bl','br'].forEach(h=>{const hd=document.createElement('div');hd.className=`hd ${h}`;hd.dataset.handle=h;div.appendChild(hd);});
    if(showLabels&&wordFreqs[loc]){
      const wf=wordFreqs[loc];
      const badge=document.createElement('div');badge.className='wf-badge';
      badge.textContent=wf.bare_count;badge.title=wf.bare+' x '+wf.bare_count;
      const bfs=BADGE_SIZES[badgeIdx];
      badge.style.fontSize=bfs+'px';badge.style.padding=Math.max(1,bfs*0.15)+'px '+Math.max(4,bfs*0.6)+'px';
      badge.style.bottom=(-bfs*1.5)+'px';
      badge.addEventListener('pointerdown',ev=>{ev.stopPropagation();ev.preventDefault();openWf(wf.bare_id,ev.clientX,ev.clientY);});
      div.appendChild(badge);
    }
    ov.appendChild(div);
  });
}
function togBoxes(){showBoxes=!showBoxes;$('bxBtn').classList.toggle('on',showBoxes);render();}
function togLabels(){showLabels=!showLabels;$('lblBtn').classList.toggle('on',showLabels);render();}
function togAdd(){if(editLocked)return;addMode=!addMode;$('addBtn').classList.toggle('on',addMode);$('addBtn').textContent=addMode?'Cancel':'+ Add';$('ov').style.cursor=addMode?'crosshair':'';}
function addBox(px,py){
  const w=60,h=50,x=Math.max(0,px-w/2),y=Math.max(0,py-h/2);
  const miss=Object.keys(mushaf).filter(l=>!coords[l]);
  let nl=miss.length?miss[0]:'new:0:1';let nn=1;while(coords[nl]){nn++;nl=`new:0:${nn}`;}
  coords[nl]={h:{x:Math.round(x),y:Math.round(y),w,h}};
  dirty=true;selLoc=nl;render();showInfo(nl);togAdd();updateStats();toast('New box added');
}
function delSel(){if(editLocked||!selLoc){toast('Select a box first',1);return;}if(!confirm(`Delete ${selLoc}?`))return;delete coords[selLoc];dirty=true;selLoc=null;$('infoP').classList.remove('vis');render();updateStats();toast('Deleted');}
function selectBox(l){selLoc=l;render();showInfo(l);}
function desel(){selLoc=null;$('infoP').classList.remove('vis');render();}
function showInfo(l){
  const c=coords[l],box=c.h||c;
  $('locIn').value=l;$('cX').value=box.x;$('cY').value=box.y;$('cW').value=box.w;$('cH').value=box.h;
  const wd=$('wordDisp');
  if(mushaf[l]){wd.textContent=mushaf[l].word;wd.style.color='var(--gd)';}else{wd.textContent='No word';wd.style.color='#f87171';}
  $('editRow').style.display=editLocked?'none':'';$('infoP').classList.add('vis');
}
function applyLoc(){
  if(!selLoc||editLocked)return;const nl=$('locIn').value.trim();
  if(nl!==selLoc){if(coords[nl]){toast('Exists!',1);return;}coords[nl]=coords[selLoc];delete coords[selLoc];selLoc=nl;}
  const c=coords[selLoc],b=c.h||c;
  b.x=+$('cX').value;b.y=+$('cY').value;b.w=Math.max(5,+$('cW').value);b.h=Math.max(5,+$('cH').value);
  dirty=true;render();updateStats();showInfo(selLoc);toast('Applied');
}
async function saveAll(){
  try{const r=await fetch(`/api/page/${curPage}/save`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({coords})});
  if(r.ok){dirty=false;toast('Saved');updateStats();}else toast('Error!',1);}
  catch(e){toast('Error: '+e.message,1);}
}
let sTimer=null;
document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.ar[data-f]').forEach(el=>{
    el.addEventListener('pointerdown',e=>{
      e.preventDefault();const f=el.dataset.f,d=+el.dataset.d;
      stepOnce(f,d);let delay=220;
      const rep=()=>{stepOnce(f,d);delay=Math.max(35,delay*0.7);sTimer=setTimeout(rep,delay);};
      sTimer=setTimeout(rep,delay);
    });
    el.addEventListener('pointerup',sStop);el.addEventListener('pointerleave',sStop);
  });
});
function sStop(){if(sTimer){clearTimeout(sTimer);sTimer=null;}}
function stepOnce(f,d){
  if(!selLoc||editLocked)return;
  $(f).value=Math.max(0,+$(f).value+d);
  const b=(coords[selLoc].h||coords[selLoc]);
  b.x=+$('cX').value;b.y=+$('cY').value;b.w=Math.max(5,+$('cW').value);b.h=Math.max(5,+$('cH').value);
  dirty=true;render();
}
function s2n(sx,sy){const r=$('vp').getBoundingClientRect();return{px:(sx-r.left-vx)/vs,py:(sy-r.top-vy)/vs};}
function hitBox(px,py){
  if(selLoc&&coords[selLoc]){const b=(coords[selLoc].h||coords[selLoc]);if(px>=b.x&&px<=b.x+b.w&&py>=b.y&&py<=b.y+b.h)return selLoc;}
  const ll=Object.keys(coords);for(let i=ll.length-1;i>=0;i--){const l=ll[i],b=(coords[l].h||coords[l]);if(b.w===undefined)continue;if(px>=b.x&&px<=b.x+b.w&&py>=b.y&&py<=b.y+b.h)return l;}return null;
}
function hitHd(px,py){
  if(!selLoc||!coords[selLoc]||editLocked)return null;
  const b=(coords[selLoc].h||coords[selLoc]),thr=20/vs;
  for(const[k,pt]of Object.entries({tl:{x:b.x,y:b.y},tr:{x:b.x+b.w,y:b.y},bl:{x:b.x,y:b.y+b.h},br:{x:b.x+b.w,y:b.y+b.h}}))
    if(Math.abs(px-pt.x)<thr&&Math.abs(py-pt.y)<thr)return k;
  return null;
}
function getT(e){return e.touches?Array.from(e.touches).map(t=>({x:t.clientX,y:t.clientY})):[{x:e.clientX,y:e.clientY}];}
function dist2(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
function mid2(a,b){return{x:(a.x+b.x)/2,y:(a.y+b.y)/2};}
const vp=$('vp');
vp.addEventListener('touchstart',onDown,{passive:false});
vp.addEventListener('touchmove',onMove,{passive:false});
vp.addEventListener('touchend',onUp,{passive:false});
vp.addEventListener('touchcancel',onUp);
vp.addEventListener('mousedown',onDown);
window.addEventListener('mousemove',onMove);
window.addEventListener('mouseup',onUp);
vp.addEventListener('wheel',e=>{e.preventDefault();const r=vp.getBoundingClientRect();doZoom(e.deltaY<0?1.2:0.83,e.clientX-r.left,e.clientY-r.top);},{passive:false});
function onDown(e){
  e.preventDefault();const tt=getT(e);
  if(tt.length>=2){interaction={type:'pinch',d0:dist2(tt[0],tt[1]),m0:mid2(tt[0],tt[1]),vs0:vs,vx0:vx,vy0:vy};return;}
  const t=tt[0],nat=s2n(t.x,t.y);
  if(!editLocked&&addMode){addBox(nat.px,nat.py);return;}
  if(!editLocked){const hh=hitHd(nat.px,nat.py);if(hh&&selLoc){interaction={type:'resize',handle:hh,loc:selLoc,spx:nat.px,spy:nat.py,orig:{...(coords[selLoc].h||coords[selLoc])}};return;}}
  const hit=hitBox(nat.px,nat.py);
  if(hit){selLoc=hit;showInfo(hit);if(!editLocked){interaction={type:'drag',loc:hit,spx:nat.px,spy:nat.py,orig:{...(coords[hit].h||coords[hit])}};}render();return;}
  desel();interaction={type:'pan',sx:t.x,sy:t.y,vx0:vx,vy0:vy};
}
function onMove(e){
  if(!interaction)return;e.preventDefault();const tt=getT(e);
  if(interaction.type==='pinch'&&tt.length>=2){
    const d=dist2(tt[0],tt[1]),m=mid2(tt[0],tt[1]),r=vp.getBoundingClientRect();
    const cx=m.x-r.left,cy=m.y-r.top,cx0=interaction.m0.x-r.left,cy0=interaction.m0.y-r.top;
    const ns=Math.max(0.1,Math.min(6,interaction.vs0*(d/interaction.d0))),ratio=ns/interaction.vs0;
    vs=ns;vx=cx-(cx0-interaction.vx0)*ratio;vy=cy-(cy0-interaction.vy0)*ratio;applyView();render();return;
  }
  if(interaction.type==='pan'){const t=tt[0];vx=interaction.vx0+(t.x-interaction.sx);vy=interaction.vy0+(t.y-interaction.sy);applyView();return;}
  if(interaction.type==='drag'){
    const nat=s2n(tt[0].x,tt[0].y),dx=nat.px-interaction.spx,dy=nat.py-interaction.spy,o=interaction.orig,b=(coords[interaction.loc].h||coords[interaction.loc]);
    b.x=Math.round(Math.max(0,Math.min(natW-o.w,o.x+dx)));b.y=Math.round(Math.max(0,Math.min(natH-o.h,o.y+dy)));
    dirty=true;
    const el=document.querySelector(`.wb[data-loc="${CSS.escape(interaction.loc)}"]`);
    if(el){el.style.left=(b.x/natW*100)+'%';el.style.top=(b.y/natH*100)+'%';}
    showInfo(interaction.loc);return;
  }
  if(interaction.type==='resize'){
    const nat=s2n(tt[0].x,tt[0].y),dx=nat.px-interaction.spx,dy=nat.py-interaction.spy,o=interaction.orig,b=(coords[interaction.loc].h||coords[interaction.loc]);
    let nx=o.x,ny=o.y,nw=o.w,nh=o.h;const hh=interaction.handle;
    if(hh.includes('l')){nx=o.x+dx;nw=o.w-dx;}if(hh.includes('r'))nw=o.w+dx;
    if(hh.includes('t')){ny=o.y+dy;nh=o.h-dy;}if(hh.includes('b'))nh=o.h+dy;
    if(nw<10){nw=10;if(hh.includes('l'))nx=o.x+o.w-10;}if(nh<10){nh=10;if(hh.includes('t'))ny=o.y+o.h-10;}
    b.x=Math.round(nx);b.y=Math.round(ny);b.w=Math.round(nw);b.h=Math.round(nh);
    dirty=true;
    const el=document.querySelector(`.wb[data-loc="${CSS.escape(interaction.loc)}"]`);
    if(el){el.style.left=(b.x/natW*100)+'%';el.style.top=(b.y/natH*100)+'%';el.style.width=(b.w/natW*100)+'%';el.style.height=(b.h/natH*100)+'%';}
    showInfo(interaction.loc);return;
  }
}
function onUp(e){
  const hadDrag=interaction&&(interaction.type==='drag'||interaction.type==='resize');
  const rem=e.touches?e.touches.length:0;
  if(rem===0)interaction=null;
  else if(rem===1&&interaction&&interaction.type==='pinch'){const t=e.touches[0];interaction={type:'pan',sx:t.clientX,sy:t.clientY,vx0:vx,vy0:vy};}
  if(hadDrag)render();
}
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;
  switch(e.key){
    case'ArrowLeft':nextPage();break;case'ArrowRight':prevPage();break;
    case'Escape':addMode?togAdd():desel();break;case'Delete':case'Backspace':if(!editLocked)delSel();break;
    case'b':togBoxes();break;case'l':togLabels();break;
    case'+':case'=':doZoom(1.25);break;case'-':doZoom(0.8);break;
    case'e':togLock();break;
    case's':if(e.ctrlKey||e.metaKey){e.preventDefault();saveAll();}break;
  }
});
function toast(m,err){const t=$('toast');t.textContent=m;t.style.background=err?'#dc2626':'#22c55e';t.style.color=err?'#fff':'#000';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200);}
async function openWf(bareId,cx,cy){
  const popup=$('wfPopup');
  try{
    const r=await fetch(`/api/word-freq/variants/${bareId}`);const d=await r.json();
    $('wfWord').textContent=d.bare;
    const total=d.variants.reduce((s,v)=>s+v.count,0);
    $('wfCount').textContent='x '+total;
    const body=$('wfBody');body.innerHTML='';
    d.variants.forEach(v=>{
      const row=document.createElement('div');row.className='var-row';
      row.innerHTML=`<span class="vw">${v.vocalized}</span><span class="vc">${v.count}</span>`;
      row.addEventListener('click',()=>openOcc(v.voc_id,v.vocalized));
      body.appendChild(row);
    });
    const vw=window.innerWidth,vh=window.innerHeight;
    let px=Math.min(cx,vw-300),py=Math.min(cy,vh-300);
    if(px<10)px=10;if(py<50)py=50;
    popup.style.left=px+'px';popup.style.top=py+'px';popup.className='vis';
  }catch(e){toast('Load error',1);}
}
function closeWf(){$('wfPopup').className='';}
async function openOcc(vocId,vocalized){
  closeWf();const popup=$('occPopup');
  try{
    const r=await fetch(`/api/word-freq/occurrences/${vocId}`);const d=await r.json();
    $('occWord').textContent=d.vocalized||vocalized;
    $('occCount').textContent='('+d.occurrences.length+' occurrences)';
    const body=$('occBody');body.innerHTML='';
    d.occurrences.forEach(o=>{
      const row=document.createElement('div');row.className='occ-row';
      row.innerHTML=`<span class="occ-sura">${o.sura_name||'Sura '+o.sura}</span><span>Ayah ${o.ayah}</span><span class="occ-ref">p${o.page} [${o.location}]</span>`;
      row.addEventListener('click',()=>{
        closeOcc();
        if(pages.includes(o.page)){
          loadPage(o.page).then(()=>{
            if(coords[o.location]){
              selectBox(o.location);
              const b=(coords[o.location].h||coords[o.location]);const v=$('vp');
              vx=v.clientWidth/2-b.x*vs-b.w*vs/2;vy=v.clientHeight/2-b.y*vs-b.h*vs/2;
              applyView();render();
            }
          });
        }else{toast('Page '+o.page+' not available',1);}
      });
      body.appendChild(row);
    });
    const vw=window.innerWidth,vh=window.innerHeight;
    popup.style.left=Math.max(10,Math.min(vw-320,vw/2-150))+'px';
    popup.style.top=Math.max(50,vh/2-200)+'px';popup.className='vis';
  }catch(e){toast('Load error',1);}
}
function closeOcc(){$('occPopup').className='';}
document.addEventListener('pointerdown',e=>{
  if($('wfPopup').classList.contains('vis')&&!$('wfPopup').contains(e.target))closeWf();
  if($('occPopup').classList.contains('vis')&&!$('occPopup').contains(e.target))closeOcc();
});
$('editRow').style.display='none';
init();
</script>
</body>
</html>
"""

def main():
    parser=argparse.ArgumentParser(description="Quran Word Coordinates Viewer")
    parser.add_argument("--images-dir",default="./images",help="Directory with page images")
    parser.add_argument("--json-dir",default=None,help="Directory with coord JSONs (default: bundled package data)")
    parser.add_argument("--mushaf-dir",default="./mushaf",help="Directory with mushaf JSONs")
    parser.add_argument("--host",default="0.0.0.0")
    parser.add_argument("--port",type=int,default=8003)
    parser.add_argument("--word-freq-db",default="./word_freq.db")
    a=parser.parse_args()
    CFG["img"]=a.images_dir
    CFG["js"]=a.json_dir if a.json_dir else _PKG_DATA
    CFG["mu"]=a.mushaf_dir
    CFG["wf"]=a.word_freq_db
    the_app = _ensure_app()
    import uvicorn
    print(f"Quran Coords Viewer -> http://localhost:{a.port}")
    print(f"  Images: {CFG['img']}")
    print(f"  Coords: {CFG['js']}")
    print(f"  Mushaf: {CFG['mu']}")
    uvicorn.run(the_app,host=a.host,port=a.port,log_level="info")

if __name__=="__main__":main()
