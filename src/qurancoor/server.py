#!/usr/bin/env python3
"""Quran Word Coordinate Viewer & Editor v6"""
import json,os,argparse,glob,shutil,sqlite3

_PKG_DATA = os.path.join(os.path.dirname(__file__), "data")

def _lazy_imports():
    from fastapi import FastAPI,HTTPException,Request
    from fastapi.responses import HTMLResponse,FileResponse,Response
    import uvicorn
    return FastAPI,HTTPException,Request,HTMLResponse,FileResponse,uvicorn

app = None
CFG={"img":"./images","js":_PKG_DATA,"mu":"./mushaf","wf":"./word_freq.db","ver":"./app_version.json","ann":"./announcements.json","ls":"./letter_stats.json","aa":"./asma_allah.json"}

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

    @app.get("/manifest.json")
    async def manifest():
        m={
            "name":"إحداثيات كلمات القرآن",
            "short_name":"إحداثيات القرآن",
            "description":"عارض إحداثيات كلمات القرآن الكريم",
            "start_url":"/",
            "display":"standalone",
            "orientation":"portrait",
            "background_color":"#0f172a",
            "theme_color":"#e94560",
            "dir":"rtl",
            "lang":"ar",
            "icons":[
                {"src":"/api/image/1","sizes":"any","type":"image/png","purpose":"any"},
            ],
            "categories":["education","books"],
        }
        return Response(content=json.dumps(m,ensure_ascii=False),media_type="application/manifest+json")

    @app.get("/sw.js")
    async def service_worker():
        sw="""const CACHE='qurancoor-v2';
const PRECACHE=['/'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(PRECACHE)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  const r=e.request;
  if(r.method!=='GET')return;
  if(r.url.includes('/api/')){
    e.respondWith(fetch(r).then(res=>{
      if(res.ok&&r.url.includes('/api/image/')){const c=res.clone();caches.open(CACHE).then(ca=>ca.put(r,c));}
      return res;
    }).catch(()=>caches.match(r)));
    return;
  }
  e.respondWith(fetch(r).catch(()=>caches.match(r)));
});"""
        return Response(content=sw,media_type="application/javascript",headers={"Service-Worker-Allowed":"/"})

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

    @app.get("/api/letter-stats")
    async def letter_stats():
        p=CFG["ls"]
        if not os.path.exists(p):return{"error":"letter_stats.json not found"}
        with open(p,"r",encoding="utf-8") as f:return json.load(f)

    @app.get("/letter-stats",response_class=HTMLResponse)
    async def letter_stats_page():return LETTER_STATS_HTML

    @app.get("/quiz",response_class=HTMLResponse)
    async def quiz_page():return QUIZ_HTML

    @app.get("/asma-allah",response_class=HTMLResponse)
    async def asma_page():return ASMA_HTML

    @app.get("/api/asma-allah")
    async def asma_data():
        p=CFG["aa"]
        if not os.path.exists(p):return{"error":"asma_allah.json not found"}
        with open(p,"r",encoding="utf-8") as f:return json.load(f)

    @app.get("/api/suras")
    async def suras_list():
        sn=_get_sura_names()
        return{"suras":[{"number":k,"name":v} for k,v in sorted(sn.items())]}

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

    @app.get("/api/announcements")
    async def announcements():
        import datetime as _dt
        p=CFG["ann"]
        if not os.path.exists(p):
            return{"announcements":[]}
        with open(p,"r",encoding="utf-8")as f:
            data=json.load(f)
        today=_dt.date.today().isoformat()
        active=[a for a in data.get("announcements",[])
                if not a.get("expires") or a["expires"]>=today]
        return{"announcements":active}

    _ayah_db_cache = {}  # {(sura, ayah): {page, words}}
    _sura_ayah_cache = {}  # {sura: count}

    def _ensure_ayah_db():
        if _ayah_db_cache:
            return
        for a in _load_all_ayahs():
            key = (a['sura'], a['ayah'])
            _ayah_db_cache[key] = {'page': a['page'], 'words': a['clean_words']}
            _sura_ayah_cache[a['sura']] = _sura_ayah_cache.get(a['sura'], 0) + 1

    @app.get("/api/suras")
    async def get_suras():
        _ensure_ayah_db()
        sura_names = _get_sura_names()
        return {"suras": [
            {"sura": s, "name": sura_names.get(s, ""), "ayah_count": cnt}
            for s, cnt in sorted(_sura_ayah_cache.items())
        ]}

    @app.get("/api/quiz/random")
    async def quiz_random(sura: int = 0):
        import random as _random
        _ensure_ayah_db()
        sura_names = _get_sura_names()
        keys = [k for k in _ayah_db_cache if sura == 0 or k[0] == sura]
        if not keys:
            raise HTTPException(404, detail="not found")
        chosen = _random.choice(keys)
        data = _ayah_db_cache[chosen]
        return {
            "sura": chosen[0], "ayah": chosen[1],
            "page": data["page"],
            "sura_name": sura_names.get(chosen[0], ""),
            "words": data["words"]
        }

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
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="إحداثيات القرآن">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/api/image/1">
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
#ann-bar{
  position:fixed;top:0;left:0;right:0;z-index:110;
  display:none;flex-direction:column;gap:0;
}
.ann-item{
  display:flex;align-items:center;gap:10px;padding:8px 14px;
  font-size:14px;font-weight:600;cursor:default;
}
.ann-item.info{background:#1e40af;color:#e0f2fe;}
.ann-item.success{background:#14532d;color:#dcfce7;}
.ann-item.warning{background:#78350f;color:#fef3c7;}
.ann-item.danger{background:#7f1d1d;color:#fee2e2;}
.ann-item .ann-icon{font-size:16px;flex-shrink:0}
.ann-item .ann-body{flex:1;line-height:1.4}
.ann-item .ann-title{font-weight:700;margin-left:6px}
.ann-item .ann-close{background:none;border:none;color:inherit;font-size:18px;cursor:pointer;opacity:.7;padding:0 4px;line-height:1;flex-shrink:0}
.ann-item .ann-close:hover{opacity:1}
#drawer-overlay{
  position:fixed;inset:0;z-index:99;background:rgba(0,0,0,.5);
  display:none;opacity:0;transition:opacity .3s;
}
#drawer-overlay.vis{display:block;opacity:1}
#toolbar{
  position:fixed;top:0;right:0;bottom:0;z-index:100;width:280px;
  display:flex;flex-direction:column;gap:10px;padding:16px 14px;
  background:var(--sf);border-left:2px solid var(--brd);
  overflow-y:auto;font-size:17px;
  transform:translateX(100%);transition:transform .3s ease;
}
#toolbar.open{transform:translateX(0)}
#toolbar .g{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
#toolbar .sep{width:100%;height:1px;background:var(--brd);margin:2px 0}
#tb-toggle{
  position:fixed;top:10px;right:10px;z-index:101;
  width:44px;height:44px;border-radius:50%;border:none;
  background:var(--ac);color:#fff;font-size:22px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  box-shadow:0 2px 12px rgba(0,0,0,.4);
  touch-action:manipulation;
}
#page-indicator{
  position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:50;
  background:rgba(0,0,0,.65);color:#fff;padding:6px 18px;border-radius:20px;
  font-size:16px;font-weight:700;pointer-events:none;
  font-family:'Tajawal',sans-serif;backdrop-filter:blur(6px);
}
.btn{
  background:var(--sf2);color:var(--tx);border:1px solid var(--brd);
  border-radius:8px;padding:10px 16px;font:inherit;font-size:17px;
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
  width:65px;background:var(--sf2);color:var(--tx);border:1px solid var(--brd);
  border-radius:8px;padding:10px 6px;font-size:17px;text-align:center;font-family:inherit;
}
#toolbar .lbl{font-size:15px;color:var(--tx2)}
#toolbar>.btn,#toolbar>a.btn{width:100%;text-align:center;justify-content:center}
.st{font-size:14px;color:var(--tx2)}.st .mis{color:var(--ac);font-weight:700}
#vp{position:fixed;inset:0;overflow:hidden;background:var(--vpbg);touch-action:none}
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
  position:absolute;bottom:-22px;left:50%;transform:translateX(-50%);
  background:rgba(37,99,235,0.9);color:#fff;font-size:15px;font-weight:700;
  padding:3px 10px;border-radius:12px;cursor:pointer;
  font-family:'Tajawal',sans-serif;white-space:nowrap;pointer-events:auto;
  z-index:5;line-height:1.4;min-width:28px;text-align:center;
  box-shadow:0 2px 6px rgba(0,0,0,.3);
}
.wf-badge:hover{background:rgba(37,99,235,1);transform:translateX(-50%) scale(1.2)}
.wb.ayah-hl{border-color:#06b6d4!important;background:rgba(6,182,212,.3)!important;z-index:7;border-width:3px}
.wb.word-selected{border-color:#f0c040!important;background:rgba(240,192,64,.35)!important;z-index:8}
.wb.word-selected .wl{background:rgba(240,192,64,.7);color:#000}
#selBar{
  position:fixed;bottom:0;left:0;right:0;z-index:250;
  background:var(--sf);border-top:2px solid #f0c040;
  padding:10px 14px;display:none;flex-direction:column;gap:8px;
  box-shadow:0 -4px 20px rgba(0,0,0,.5);
}
#selBar.vis{display:flex}
#selBar .sel-text{font:22px/1.6 'Amiri',serif;color:var(--tx);direction:rtl;text-align:center;
  max-height:120px;overflow-y:auto;padding:6px;background:var(--sf2);border-radius:8px;
  user-select:text;-webkit-user-select:text}
#selBar .sel-actions{display:flex;gap:8px;justify-content:center;align-items:center}
#selBar .sel-count{font-size:13px;color:var(--tx2)}
.btn.sel-active{background:#f0c040!important;color:#000!important;border-color:#f0c040!important}
#wfPopup{
  position:fixed;z-index:300;background:var(--sf);border:2px solid var(--ac);
  border-radius:14px;padding:0;min-width:340px;max-width:94vw;max-height:75vh;
  box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;overflow:hidden;font-family:'Tajawal',sans-serif;
}
#wfPopup.vis{display:flex;flex-direction:column}
#wfPopup .wfh{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;background:var(--ac);color:#fff;font-size:20px;}
#wfPopup .wfh .wfw{font-family:'Amiri',serif;font-size:30px;direction:rtl}
#wfPopup .wfh .wfc{font-size:16px;opacity:.85}
#wfPopup .wfh button{background:none;border:none;color:#fff;font-size:24px;cursor:pointer;padding:4px 8px}
#wfPopup .wfb{overflow-y:auto;max-height:60vh;padding:10px}
.var-row{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;margin:4px 0;border-radius:10px;background:var(--sf2);cursor:pointer;transition:background .1s;gap:10px;}
.var-row:hover{background:var(--ac);color:#fff}
.var-row .vw{font-family:'Amiri',serif;font-size:26px;direction:rtl;flex:1}
.var-row .vc{background:var(--bl);color:#fff;padding:4px 14px;border-radius:14px;font-size:16px;font-weight:700;min-width:40px;text-align:center}
#occPopup{
  position:fixed;z-index:310;background:var(--sf);border:2px solid var(--gd);
  border-radius:14px;padding:0;min-width:340px;max-width:94vw;max-height:80vh;
  box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;overflow:hidden;
}
#occPopup.vis{display:flex;flex-direction:column}
#occPopup .occh{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;background:var(--gd);color:#000;font-size:18px;}
#occPopup .occh .occw{font-family:'Amiri',serif;font-size:28px;direction:rtl}
#occPopup .occb{overflow-y:auto;max-height:65vh;padding:8px}
.occ-row{display:flex;align-items:center;gap:10px;padding:10px 14px;margin:3px 0;border-radius:8px;background:var(--sf2);cursor:pointer;transition:background .1s;font-size:17px;}
.occ-row:hover{background:var(--bl);color:#fff}
.occ-row .occ-sura{font-weight:700;min-width:90px;font-size:17px}
.occ-row .occ-ref{color:var(--tx2);font-size:14px;direction:ltr}
#install-banner{
  display:none;position:fixed;bottom:0;left:0;right:0;z-index:150;
  background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
  border-top:3px solid var(--ac);
  padding:18px 16px;
  box-shadow:0 -4px 24px rgba(0,0,0,.5);
  animation:slideUp .4s ease-out;
}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
#install-banner .ib-content{
  display:flex;align-items:center;gap:14px;max-width:600px;margin:0 auto;
}
#install-banner .ib-icon{font-size:40px;flex-shrink:0}
#install-banner .ib-text{flex:1}
#install-banner .ib-title{font-size:17px;font-weight:700;color:#f1f5f9;margin-bottom:4px}
#install-banner .ib-desc{font-size:13px;color:#94a3b8;line-height:1.4}
#install-banner .ib-actions{display:flex;gap:8px;flex-shrink:0}
#install-banner .ib-install{
  background:linear-gradient(135deg,#e94560,#dc2626);color:#fff;
  border:none;border-radius:10px;padding:10px 20px;font:inherit;font-size:15px;
  font-weight:700;cursor:pointer;white-space:nowrap;
}
#install-banner .ib-close{
  background:none;border:1px solid rgba(255,255,255,.15);border-radius:10px;
  color:#94a3b8;padding:10px 14px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap;
}
</style>
</head>
<body>
<div id="install-banner">
 <div class="ib-content">
  <div class="ib-icon">&#128218;</div>
  <div class="ib-text">
   <div class="ib-title">تثبيت تطبيق إحداثيات القرآن</div>
   <div class="ib-desc">ثبّت التطبيق على جهازك للوصول السريع والاستخدام بدون إنترنت</div>
  </div>
  <div class="ib-actions">
   <button class="ib-install" onclick="promptInstall()">تثبيت</button>
   <button class="ib-close" onclick="dismissInstallBanner()">لاحقاً</button>
  </div>
 </div>
</div>
<div id="ann-bar"></div>
<button id="tb-toggle" onclick="toggleDrawer()">&#9776;</button>
<div id="drawer-overlay" onclick="closeDrawer()"></div>
<div id="page-indicator"><span id="pgInd">1 / 604</span></div>
<div id="toolbar">
 <div class="g" style="justify-content:space-between;width:100%">
  <span style="font-weight:700;font-size:16px">&#9776; القائمة</span>
  <button class="btn" onclick="closeDrawer()" style="padding:4px 12px;font-size:20px">&#10005;</button>
 </div><div class="sep"></div>
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
  <button class="btn" id="bxBtn" onclick="togBoxes()">Boxes</button>
  <button class="btn" id="lblBtn" onclick="togLabels()">Labels</button>
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
 <button class="btn" id="selBtn" onclick="togSelect()">&#9998; تحديد</button>
 <button class="btn" id="installBtn" onclick="promptInstall()" style="display:none;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;font-weight:700;border:none;box-shadow:0 0 10px rgba(37,99,235,.4);align-items:center;gap:6px">
  <span style="font-size:18px">&#128229;</span> تثبيت التطبيق
 </button>
 <a href="/download/" target="_blank" class="btn" style="background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:700;border:none;box-shadow:0 0 10px rgba(22,163,74,.4)">
  <span style="font-size:18px">&#11015;</span> تطبيق Android
 </a>
 <a href="/asma-allah" target="_blank" class="btn" style="background:linear-gradient(135deg,#0891b2,#0e7490);color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:700;border:none;box-shadow:0 0 10px rgba(8,145,178,.4)">
  <span style="font-size:16px">&#10026;</span> الأسماء الحسنى
 </a>
 <a href="/quiz" target="_blank" class="btn" style="background:linear-gradient(135deg,#d97706,#b45309);color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:700;border:none;box-shadow:0 0 10px rgba(217,119,6,.4)">
  <span style="font-size:16px">&#127919;</span> اختبار الحفظ
 </a>
 <a href="/letter-stats" target="_blank" class="btn" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;text-decoration:none;display:flex;align-items:center;gap:6px;font-weight:700;border:none;box-shadow:0 0 10px rgba(124,58,237,.4)">
  <span style="font-size:16px">&#1571;&#1576;&#1578;</span> إحصائيات الحروف
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
<div id="selBar">
 <div class="sel-text" id="selText"></div>
 <div class="sel-actions">
  <span class="sel-count" id="selCount"></span>
  <button class="ibtn" onclick="copySelection()" style="background:#f0c040;color:#000;font-weight:700">&#128203; نسخ</button>
  <button class="ibtn" onclick="clearSelection()" style="background:var(--sf2);color:var(--tx)">مسح التحديد</button>
  <button class="ibtn" onclick="togSelect()" style="background:#dc2626;color:#fff">&#10005; إغلاق</button>
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
let showBoxes=false,showLabels=false,addMode=false,selLoc=null,dirty=false;
let editLocked=true,natW=900,natH=1437;
let wordFreqs={};
let selectMode=false,selectedLocs=new Set();
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
  if(pages.length){
    const params=new URLSearchParams(window.location.search);
    const urlP=params.get('page');
    curPage=urlP&&+urlP>=1&&+urlP<=604?+urlP:pages[0];
    $('pgIn').value=curPage;await loadPage(curPage);
    // Highlight ayah if hl param exists (e.g. hl=2:163)
    const hl=params.get('hl');
    if(hl)highlightAyah(hl);
  }
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
  requestAnimationFrame(()=>updateVpTop());
}
function updateVpTop(){
  // vp is now full screen, no top offset needed
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
  $('pgInd').textContent=`${n} / ${pages.length}`;
  const url=new URL(window.location);url.searchParams.set('page',n);history.replaceState(null,'',url);
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
  const ov=$('ov');ov.innerHTML='';if(!showBoxes&&!selectMode&&!hlAyah)return;
  const selOnly=selectMode&&!showBoxes;
  const hlOnly=hlAyah&&!showBoxes; // highlight mode without boxes
  Object.keys(coords).forEach((loc,i)=>{
    const c=coords[loc],box=c.h||c;if(!box||box.w===undefined)return;
    const col=COLS[i%COLS.length],hasMu=!!mushaf[loc],isSel=loc===selLoc;
    const div=document.createElement('div');
    const isWordSel=selectedLocs.has(loc);
    const locParts=loc.split(':');
    const isHl=hlAyah&&locParts.length>=2&&(locParts[0]+':'+locParts[1])===hlAyah;
    div.className='wb'+(isSel?' sel':'')+(hasMu?'':' nomatch')+(isWordSel?' word-selected':'')+(isHl?' ayah-hl':'');
    div.dataset.loc=loc;
    const pos=`left:${box.x/natW*100}%;top:${box.y/natH*100}%;width:${box.w/natW*100}%;height:${box.h/natH*100}%`;
    if(hlOnly){
      // Only show highlighted ayah boxes
      if(isHl) div.style.cssText=pos+`;border-color:#06b6d4;background:rgba(6,182,212,.3)`;
      else { div.style.cssText=pos+`;border-color:transparent;background:transparent;pointer-events:none`; }
    } else if(selOnly&&!isWordSel){
      div.style.cssText=pos+`;border-color:transparent;background:transparent`;
    } else if(selOnly&&isWordSel){
      div.style.cssText=pos+`;border-color:#f0c040;background:rgba(240,192,64,.35)`;
    } else {
      div.style.cssText=pos+`;border-color:${col.b};background:${hasMu?col.bg:'rgba(255,0,0,0.15)'}`;
    }
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
      badge.addEventListener('pointerdown',ev=>{ev.stopPropagation();ev.preventDefault();if(!selectMode)openWf(wf.bare_id,ev.clientX,ev.clientY);});
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
vp.addEventListener('wheel',e=>{e.preventDefault();},{passive:false}); // page fixed, no wheel zoom
function onDown(e){
  e.preventDefault();const tt=getT(e);
  if(tt.length>=2)return; // page is fixed, no pinch zoom
  const t=tt[0],nat=s2n(t.x,t.y);
  if(selectMode){
    selectWordAt(nat.px,nat.py);
    interaction={type:'select'};return;
  }
  if(!editLocked&&addMode){addBox(nat.px,nat.py);return;}
  if(!editLocked){const hh=hitHd(nat.px,nat.py);if(hh&&selLoc){interaction={type:'resize',handle:hh,loc:selLoc,spx:nat.px,spy:nat.py,orig:{...(coords[selLoc].h||coords[selLoc])}};return;}}
  const hit=hitBox(nat.px,nat.py);
  if(hit){selLoc=hit;showInfo(hit);if(!editLocked){interaction={type:'drag',loc:hit,spx:nat.px,spy:nat.py,orig:{...(coords[hit].h||coords[hit])}};}render();return;}
  desel();interaction={type:'swipe',sx:t.x,sy:t.y,t0:Date.now()};
}
function onMove(e){
  if(!interaction)return;e.preventDefault();const tt=getT(e);
  if(interaction.type==='pinch'&&tt.length>=2){
    const d=dist2(tt[0],tt[1]),m=mid2(tt[0],tt[1]),r=vp.getBoundingClientRect();
    const cx=m.x-r.left,cy=m.y-r.top,cx0=interaction.m0.x-r.left,cy0=interaction.m0.y-r.top;
    const ns=Math.max(0.1,Math.min(6,interaction.vs0*(d/interaction.d0))),ratio=ns/interaction.vs0;
    vs=ns;vx=cx-(cx0-interaction.vx0)*ratio;vy=cy-(cy0-interaction.vy0)*ratio;applyView();render();return;
  }
  if(interaction.type==='select')return;
  if(interaction.type==='swipe')return;
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
  if(interaction&&interaction.type==='swipe'){
    const tt=e.changedTouches?[{x:e.changedTouches[0].clientX,y:e.changedTouches[0].clientY}]:[{x:e.clientX,y:e.clientY}];
    const dx=tt[0].x-interaction.sx,dt=Date.now()-interaction.t0;
    interaction=null;
    if(dt<500&&Math.abs(dx)>50){if(dx>0)prevPage();else nextPage();}
    return;
  }
  const rem=e.touches?e.touches.length:0;
  if(rem===0)interaction=null;
  else if(rem===1&&interaction&&interaction.type==='pinch'){const t=e.touches[0];interaction={type:'swipe',sx:t.clientX,sy:t.clientY,t0:Date.now()};}
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
// ── Announcements ─────────────────────────────────────────────────────────────
(async()=>{
  const ICONS={info:'ℹ️',success:'✅',warning:'⚠️',danger:'🚨'};
  try{
    const r=await fetch('/api/announcements');
    const d=await r.json();
    const dismissed=JSON.parse(localStorage.getItem('ann_dismissed')||'[]');
    const bar=$('ann-bar');
    let shown=0;
    for(const ann of(d.announcements||[])){
      if(dismissed.includes(ann.id))continue;
      const type=ann.type||'info';
      const div=document.createElement('div');
      div.className=`ann-item ${type}`;
      div.innerHTML=`<span class="ann-icon">${ICONS[type]||'📢'}</span>`
        +(ann.title?`<span class="ann-title">${ann.title}</span>`:'')
        +`<span class="ann-body">${ann.body||''}</span>`
        +`<button class="ann-close" title="إغلاق">✕</button>`;
      div.querySelector('.ann-close').onclick=()=>{
        dismissed.push(ann.id);
        localStorage.setItem('ann_dismissed',JSON.stringify(dismissed));
        div.remove();
        if(!bar.children.length)bar.style.display='none';
        updateVpTop();
      };
      bar.appendChild(div);shown++;
    }
    if(shown>0){bar.style.display='flex';requestAnimationFrame(()=>updateVpTop());}
  }catch(e){}
})();
// ─── Ayah Highlight ──────────────────────────────────────────────────────
let hlAyah=null; // e.g. "2:163"
function highlightAyah(ayahKey){
  hlAyah=ayahKey;
  render();
}
// ─── Sura Names ──────────────────────────────────────────────────────────
const SURA_NAMES=['','\u0627\u0644\u0641\u0627\u062A\u062D\u0629','\u0627\u0644\u0628\u0642\u0631\u0629','\u0622\u0644 \u0639\u0645\u0631\u0627\u0646','\u0627\u0644\u0646\u0633\u0627\u0621','\u0627\u0644\u0645\u0627\u0626\u062F\u0629','\u0627\u0644\u0623\u0646\u0639\u0627\u0645','\u0627\u0644\u0623\u0639\u0631\u0627\u0641','\u0627\u0644\u0623\u0646\u0641\u0627\u0644','\u0627\u0644\u062A\u0648\u0628\u0629','\u064A\u0648\u0646\u0633','\u0647\u0648\u062F','\u064A\u0648\u0633\u0641','\u0627\u0644\u0631\u0639\u062F','\u0625\u0628\u0631\u0627\u0647\u064A\u0645','\u0627\u0644\u062D\u062C\u0631','\u0627\u0644\u0646\u062D\u0644','\u0627\u0644\u0625\u0633\u0631\u0627\u0621','\u0627\u0644\u0643\u0647\u0641','\u0645\u0631\u064A\u0645','\u0637\u0647','\u0627\u0644\u0623\u0646\u0628\u064A\u0627\u0621','\u0627\u0644\u062D\u062C','\u0627\u0644\u0645\u0624\u0645\u0646\u0648\u0646','\u0627\u0644\u0646\u0648\u0631','\u0627\u0644\u0641\u0631\u0642\u0627\u0646','\u0627\u0644\u0634\u0639\u0631\u0627\u0621','\u0627\u0644\u0646\u0645\u0644','\u0627\u0644\u0642\u0635\u0635','\u0627\u0644\u0639\u0646\u0643\u0628\u0648\u062A','\u0627\u0644\u0631\u0648\u0645','\u0644\u0642\u0645\u0627\u0646','\u0627\u0644\u0633\u062C\u062F\u0629','\u0627\u0644\u0623\u062D\u0632\u0627\u0628','\u0633\u0628\u0623','\u0641\u0627\u0637\u0631','\u064A\u0633','\u0627\u0644\u0635\u0627\u0641\u0627\u062A','\u0635','\u0627\u0644\u0632\u0645\u0631','\u063A\u0627\u0641\u0631','\u0641\u0635\u0644\u062A','\u0627\u0644\u0634\u0648\u0631\u0649','\u0627\u0644\u0632\u062E\u0631\u0641','\u0627\u0644\u062F\u062E\u0627\u0646','\u0627\u0644\u062C\u0627\u062B\u064A\u0629','\u0627\u0644\u0623\u062D\u0642\u0627\u0641','\u0645\u062D\u0645\u062F','\u0627\u0644\u0641\u062A\u062D','\u0627\u0644\u062D\u062C\u0631\u0627\u062A','\u0642','\u0627\u0644\u0630\u0627\u0631\u064A\u0627\u062A','\u0627\u0644\u0637\u0648\u0631','\u0627\u0644\u0646\u062C\u0645','\u0627\u0644\u0642\u0645\u0631','\u0627\u0644\u0631\u062D\u0645\u0646','\u0627\u0644\u0648\u0627\u0642\u0639\u0629','\u0627\u0644\u062D\u062F\u064A\u062F','\u0627\u0644\u0645\u062C\u0627\u062F\u0644\u0629','\u0627\u0644\u062D\u0634\u0631','\u0627\u0644\u0645\u0645\u062A\u062D\u0646\u0629','\u0627\u0644\u0635\u0641','\u0627\u0644\u062C\u0645\u0639\u0629','\u0627\u0644\u0645\u0646\u0627\u0641\u0642\u0648\u0646','\u0627\u0644\u062A\u063A\u0627\u0628\u0646','\u0627\u0644\u0637\u0644\u0627\u0642','\u0627\u0644\u062A\u062D\u0631\u064A\u0645','\u0627\u0644\u0645\u0644\u0643','\u0627\u0644\u0642\u0644\u0645','\u0627\u0644\u062D\u0627\u0642\u0629','\u0627\u0644\u0645\u0639\u0627\u0631\u062C','\u0646\u0648\u062D','\u0627\u0644\u062C\u0646','\u0627\u0644\u0645\u0632\u0645\u0644','\u0627\u0644\u0645\u062F\u062B\u0631','\u0627\u0644\u0642\u064A\u0627\u0645\u0629','\u0627\u0644\u0625\u0646\u0633\u0627\u0646','\u0627\u0644\u0645\u0631\u0633\u0644\u0627\u062A','\u0627\u0644\u0646\u0628\u0623','\u0627\u0644\u0646\u0627\u0632\u0639\u0627\u062A','\u0639\u0628\u0633','\u0627\u0644\u062A\u0643\u0648\u064A\u0631','\u0627\u0644\u0627\u0646\u0641\u0637\u0627\u0631','\u0627\u0644\u0645\u0637\u0641\u0641\u064A\u0646','\u0627\u0644\u0627\u0646\u0634\u0642\u0627\u0642','\u0627\u0644\u0628\u0631\u0648\u062C','\u0627\u0644\u0637\u0627\u0631\u0642','\u0627\u0644\u0623\u0639\u0644\u0649','\u0627\u0644\u063A\u0627\u0634\u064A\u0629','\u0627\u0644\u0641\u062C\u0631','\u0627\u0644\u0628\u0644\u062F','\u0627\u0644\u0634\u0645\u0633','\u0627\u0644\u0644\u064A\u0644','\u0627\u0644\u0636\u062D\u0649','\u0627\u0644\u0634\u0631\u062D','\u0627\u0644\u062A\u064A\u0646','\u0627\u0644\u0639\u0644\u0642','\u0627\u0644\u0642\u062F\u0631','\u0627\u0644\u0628\u064A\u0646\u0629','\u0627\u0644\u0632\u0644\u0632\u0644\u0629','\u0627\u0644\u0639\u0627\u062F\u064A\u0627\u062A','\u0627\u0644\u0642\u0627\u0631\u0639\u0629','\u0627\u0644\u062A\u0643\u0627\u062B\u0631','\u0627\u0644\u0639\u0635\u0631','\u0627\u0644\u0647\u0645\u0632\u0629','\u0627\u0644\u0641\u064A\u0644','\u0642\u0631\u064A\u0634','\u0627\u0644\u0645\u0627\u0639\u0648\u0646','\u0627\u0644\u0643\u0648\u062B\u0631','\u0627\u0644\u0643\u0627\u0641\u0631\u0648\u0646','\u0627\u0644\u0646\u0635\u0631','\u0627\u0644\u0645\u0633\u062F','\u0627\u0644\u0625\u062E\u0644\u0627\u0635','\u0627\u0644\u0641\u0644\u0642','\u0627\u0644\u0646\u0627\u0633'];
// ─── Word Selection & Copy ───────────────────────────────────────────────
let selAnchor=null; // first selected word location (anchor for range)
function togSelect(){
  selectMode=!selectMode;
  $('selBtn').classList.toggle('sel-active',selectMode);
  $('selBtn').innerHTML=selectMode?'&#9998; \u0625\u0644\u063A\u0627\u0621 \u0627\u0644\u062A\u062D\u062F\u064A\u062F':'&#9998; \u062A\u062D\u062F\u064A\u062F';
  if(!selectMode){clearSelection();$('selBar').classList.remove('vis');}
  else{$('selBar').classList.add('vis');updateSelBar();}
  $('ov').style.cursor=selectMode?'text':'';
}
function clearSelection(){selectedLocs.clear();selAnchor=null;render();updateSelBar();}
function getWordText(loc){
  if(!mushaf[loc])return'';
  return mushaf[loc].word.replace(/[\s\d\u0660-\u0669\u06F0-\u06F9]+$/,'');
}
function locCompare(a,b){
  const pa=a.split(':').map(Number),pb=b.split(':').map(Number);
  return pa[0]-pb[0]||pa[1]-pb[1]||pa[2]-pb[2];
}
function getAllLocsSorted(){
  return Object.keys(mushaf).sort(locCompare);
}
function getSelectionText(forCopy){
  const sorted=[...selectedLocs].sort(locCompare);
  if(!sorted.length)return'';
  let text='',lastAyah='';
  const suras=new Set();
  sorted.forEach(loc=>{
    const parts=loc.split(':');
    const ayahKey=parts[0]+':'+parts[1];
    suras.add(+parts[0]);
    if(lastAyah&&lastAyah!==ayahKey)text+=' \uFD3F'+lastAyah.split(':')[1]+'\uFD3E ';
    else if(text)text+=' ';
    text+=getWordText(loc);
    lastAyah=ayahKey;
  });
  if(lastAyah)text+=' \uFD3F'+lastAyah.split(':')[1]+'\uFD3E';
  if(forCopy){
    // Add sura name(s) and page number
    const suraList=[...suras].map(s=>SURA_NAMES[s]||(''+s));
    const firstAyah=sorted[0].split(':')[1];
    const lastA=sorted[sorted.length-1].split(':')[1];
    const ayahRange=firstAyah===lastA?firstAyah:firstAyah+'-'+lastA;
    let header='\u0633\u0648\u0631\u0629 '+suraList.join(' / ');
    header+=' - \u0627\u0644\u0622\u064A\u0629 '+ayahRange;
    header+=' - \u0635\u0641\u062D\u0629 '+curPage;
    text=text+'\n['+header+']';
  }
  return text;
}
function updateSelBar(){
  const text=getSelectionText();
  $('selText').textContent=text||'\u0627\u0636\u063A\u0637 \u0623\u0648\u0644 \u0643\u0644\u0645\u0629 \u062B\u0645 \u0622\u062E\u0631 \u0643\u0644\u0645\u0629';
  $('selCount').textContent=selectedLocs.size?selectedLocs.size+' \u0643\u0644\u0645\u0629':'';
}
function copySelection(){
  const text=getSelectionText(true);
  if(!text){toast('\u0644\u0627 \u064A\u0648\u062C\u062F \u0646\u0635 \u0645\u062D\u062F\u062F',1);return;}
  navigator.clipboard.writeText(text).then(()=>{
    toast('\u062A\u0645 \u0627\u0644\u0646\u0633\u062E \u2713');
  }).catch(()=>{
    const ta=document.createElement('textarea');
    ta.value=text;ta.style.cssText='position:fixed;opacity:0';
    document.body.appendChild(ta);ta.select();
    document.execCommand('copy');document.body.removeChild(ta);
    toast('\u062A\u0645 \u0627\u0644\u0646\u0633\u062E \u2713');
  });
}
function hitWord(px,py){
  const ll=Object.keys(coords);
  for(let i=ll.length-1;i>=0;i--){
    const l=ll[i],c=coords[l],b=c.h||c;
    if(b.w===undefined)continue;
    if(px>=b.x&&px<=b.x+b.w&&py>=b.y&&py<=b.y+b.h)return l;
  }
  return null;
}
function selectWordAt(px,py){
  const hit=hitWord(px,py);
  if(!hit)return false;
  if(!selAnchor){
    // First tap: set anchor
    selectedLocs.clear();
    selectedLocs.add(hit);
    selAnchor=hit;
  } else {
    // Second tap: select range from anchor to this word
    const allLocs=getAllLocsSorted();
    const i1=allLocs.indexOf(selAnchor), i2=allLocs.indexOf(hit);
    if(i1>=0&&i2>=0){
      const lo=Math.min(i1,i2), hi=Math.max(i1,i2);
      selectedLocs.clear();
      for(let i=lo;i<=hi;i++)selectedLocs.add(allLocs[i]);
    }
    selAnchor=null;
  }
  render();updateSelBar();return true;
}
// Side drawer
let _drawerOpen=false;
function openDrawer(){_drawerOpen=true;$('toolbar').classList.add('open');$('drawer-overlay').classList.add('vis');}
function closeDrawer(){_drawerOpen=false;$('toolbar').classList.remove('open');$('drawer-overlay').classList.remove('vis');}
function toggleDrawer(){_drawerOpen?closeDrawer():openDrawer();}
// PWA: service worker registration & install prompt
let _deferredInstall=null;
window.addEventListener('beforeinstallprompt',e=>{
  e.preventDefault();_deferredInstall=e;
  showInstallBtn(true);
  // show banner every visit (no localStorage check)
  document.getElementById('install-banner').style.display='block';
});
window.addEventListener('appinstalled',()=>{_deferredInstall=null;showInstallBtn(false);document.getElementById('install-banner').style.display='none'});
function showInstallBtn(v){const b=$('installBtn');if(b)b.style.display=v?'inline-flex':'none';}
function dismissInstallBanner(){document.getElementById('install-banner').style.display='none';}
function promptInstall(){if(_deferredInstall){_deferredInstall.prompt();_deferredInstall.userChoice.then(r=>{_deferredInstall=null;showInstallBtn(false);document.getElementById('install-banner').style.display='none'})}}
if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{});}
// iOS Safari: no beforeinstallprompt, show manual guidance
if(!window.matchMedia('(display-mode:standalone)').matches && !navigator.standalone){
  const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent);
  if(isIOS && !_deferredInstall){
    const bn=document.getElementById('install-banner');
    bn.querySelector('.ib-desc').textContent='اضغط على زر المشاركة ⬆ ثم اختر "إضافة إلى الشاشة الرئيسية"';
    bn.querySelector('.ib-install').style.display='none';
    bn.style.display='block';
  }
}
init();
</script>
</body>
</html>
"""

ASMA_HTML=r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>أسماء الله الحسنى</title>
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Tajawal',sans-serif;background:#0a0f1a;color:#e2e8f0;min-height:100vh}
.header{background:linear-gradient(135deg,#0c1829,#1a1a2e);padding:32px 20px;text-align:center;border-bottom:2px solid #1e3a5f;position:relative;overflow:hidden}
.header::before{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 50% 0%,rgba(6,182,212,.12),transparent 70%);pointer-events:none}
.header h1{font:36px/1.2 'Amiri',serif;font-weight:700;color:#67e8f9;margin-bottom:6px;position:relative}
.header p{font-size:15px;color:#94a3b8;position:relative}
.header a{color:#60a5fa;text-decoration:none;font-size:14px;position:relative}
.container{max-width:900px;margin:0 auto;padding:20px}
.search-box{margin-bottom:24px;position:sticky;top:0;z-index:10;padding:12px 0;background:#0a0f1a}
.search-box input{width:100%;background:#1e293b;color:#e2e8f0;border:2px solid #334155;border-radius:14px;padding:14px 20px;font:17px 'Tajawal',sans-serif;outline:none;transition:border .2s}
.search-box input:focus{border-color:#06b6d4}
.search-box input::placeholder{color:#64748b}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:16px}
.card{background:linear-gradient(145deg,#111827,#1e293b);border:1px solid #1e3a5f;border-radius:18px;padding:0;overflow:hidden;transition:all .3s;cursor:pointer}
.card:hover{border-color:#06b6d4;transform:translateY(-3px);box-shadow:0 12px 40px rgba(6,182,212,.15)}
.card-top{padding:20px 20px 14px;text-align:center;border-bottom:1px solid rgba(255,255,255,.05)}
.card-num{display:inline-block;background:rgba(6,182,212,.15);color:#67e8f9;font-size:13px;font-weight:700;padding:2px 10px;border-radius:20px;margin-bottom:10px}
.card-name{font:36px 'Amiri',serif;font-weight:700;color:#f0fdfa;line-height:1.3;margin-bottom:4px}
.card-eng{font-size:14px;color:#67e8f9;font-weight:600;letter-spacing:.5px;direction:ltr}
.card-body{padding:14px 20px 18px}
.card-meaning{font-size:15px;color:#cbd5e1;line-height:1.8}
.card-verses{margin-top:12px;padding-top:10px;border-top:1px solid rgba(255,255,255,.06)}
.card-verses-title{font-size:13px;color:#06b6d4;font-weight:700;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.card-verses-title::before{content:'📖';font-size:14px}
.verse-tag{display:inline-block;background:rgba(6,182,212,.1);color:#67e8f9;font-size:13px;padding:3px 10px;border-radius:8px;margin:2px 4px 2px 0;font-weight:600}
a.verse-link{text-decoration:none;cursor:pointer;transition:all .2s}
a.verse-link:hover{background:rgba(6,182,212,.3);transform:scale(1.05)}
.verse-item{margin-bottom:10px}
.verse-text{font:20px/1.9 'Amiri',serif;color:#cbd5e1;direction:rtl;margin-top:6px;padding:8px 12px;background:rgba(0,0,0,.25);border-radius:8px;border-right:3px solid #0e7490}
.hl-name{color:#fbbf24;font-weight:700;background:rgba(251,191,36,.12);padding:0 4px;border-radius:4px}
.count-badge{text-align:center;padding:16px;font-size:18px;color:#94a3b8;margin-bottom:20px}
.count-badge span{color:#67e8f9;font-weight:800;font-size:22px}
/* Expanded card */
.card.expanded .card-body{display:block}
.card .card-body{display:none}
.card.expanded{grid-column:1/-1;max-width:600px;margin:0 auto}
@media(max-width:600px){.grid{grid-template-columns:1fr}.card.expanded{max-width:100%}}
</style>
</head>
<body>
<div class="header">
 <h1>أسماء الله الحسنى</h1>
 <p>٩٩ اسماً من أسماء الله عز وجل مع معانيها ومواضع ورودها في القرآن</p>
 <a href="/">← العودة للمصحف</a>
</div>
<div class="container">
 <div class="search-box"><input type="text" id="search" placeholder="ابحث في الأسماء الحسنى..." oninput="filterNames()"></div>
 <div class="count-badge">عدد الأسماء: <span>٩٩</span></div>
 <div class="grid" id="grid"></div>
</div>
<script>
let data=null,expanded=null;
async function init(){
 try{
  const r=await fetch('/api/asma-allah');data=await r.json();
  if(data.error){document.getElementById('grid').textContent=data.error;return;}
  renderAll(data.names);
 }catch(e){document.getElementById('grid').textContent='خطأ في تحميل البيانات';}
}
function toAr(n){return n.toString().replace(/\d/g,d=>'٠١٢٣٤٥٦٧٨٩'[d]);}
function stripTashkeel(s){return s.replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g,'').replace(/[\u0622\u0623\u0625\u0671]/g,'\u0627');}
function highlightName(ayahText,name){
 // Try to find the name (without tashkeel) inside the ayah words
 const words=ayahText.split(/\s+/);
 const nameStripped=stripTashkeel(name);
 let html='';
 words.forEach((w,i)=>{
  if(i>0)html+=' ';
  const wStripped=stripTashkeel(w);
  if(wStripped.includes(nameStripped)||nameStripped.includes(wStripped)){
   html+='<span class="hl-name">'+w+'</span>';
  } else {
   html+=w;
  }
 });
 return html;
}
function renderAll(names){
 const grid=document.getElementById('grid');
 grid.innerHTML='';
 names.forEach(n=>{
  const card=document.createElement('div');
  card.className='card';
  card.dataset.num=n.number;
  let versesHtml='';
  if(n.verses&&n.verses.length){
   versesHtml='<div class="card-verses"><div class="card-verses-title">مواضع الورود ('+toAr(n.verses.length)+' مواضع)</div>';
   n.verses.forEach(v=>{
    // Highlight the name inside the ayah text
    let ayahDisp='';
    if(v.ayah_text){
     const nameClean=n.name.replace(/[\u064B-\u065F]/g,'');
     ayahDisp=highlightName(v.ayah_text,nameClean);
    }
    const link=v.page?'/?page='+v.page+'&hl='+v.sura_number+':'+v.ayah:'#';
    versesHtml+='<div class="verse-item">';
    versesHtml+='<a href="'+link+'" class="verse-tag verse-link" '+(v.page?'target="_blank"':'')+'>'+v.sura+' - الآية '+toAr(v.ayah)+' ← صفحة '+toAr(v.page)+'</a>';
    if(ayahDisp)versesHtml+='<div class="verse-text">'+ayahDisp+'</div>';
    versesHtml+='</div>';
   });
   versesHtml+='</div>';
  }
  card.innerHTML=`
   <div class="card-top">
    <div class="card-num">${toAr(n.number)}</div>
    <div class="card-name">${n.name}</div>
    <div class="card-eng">${n.english}</div>
   </div>
   <div class="card-body">
    <div class="card-meaning">${n.meaning}</div>
    ${versesHtml}
   </div>`;
  card.addEventListener('click',()=>toggleCard(card));
  grid.appendChild(card);
 });
}
function toggleCard(card){
 const wasExpanded=card.classList.contains('expanded');
 document.querySelectorAll('.card.expanded').forEach(c=>c.classList.remove('expanded'));
 if(!wasExpanded){
  card.classList.add('expanded');
  setTimeout(()=>card.scrollIntoView({behavior:'smooth',block:'center'}),100);
 }
}
function filterNames(){
 const q=document.getElementById('search').value.trim().toLowerCase();
 if(!q){renderAll(data.names);return;}
 const filtered=data.names.filter(n=>
  n.name.includes(q)||n.english.toLowerCase().includes(q)||n.meaning.includes(q)
 );
 renderAll(filtered);
}
init();
</script>
</body>
</html>"""

QUIZ_HTML="""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>اختبار الحفظ — مصحف الكلمات</title>
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Tajawal',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.header{background:linear-gradient(135deg,#78350f,#0f172a);padding:24px;text-align:center;border-bottom:2px solid #d97706}
.header h1{font-size:28px;font-weight:800;color:#fbbf24;margin-bottom:6px}
.header p{font-size:15px;color:#94a3b8}
.header a{color:#60a5fa;text-decoration:none;font-size:14px}
.container{max-width:700px;margin:0 auto;padding:20px}
.setup{background:#1e293b;border-radius:14px;padding:24px;margin-bottom:20px;border:1px solid #334155}
.setup h2{font-size:20px;color:#fbbf24;margin-bottom:16px;font-weight:700}
.form-row{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap;align-items:center}
.form-row label{font-size:15px;color:#94a3b8;min-width:60px}
.form-row select{flex:1;min-width:180px;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:10px;padding:12px 14px;font:16px 'Tajawal',sans-serif}
.diff-btns{display:flex;gap:10px;flex-wrap:wrap}
.diff-btn{flex:1;min-width:100px;padding:14px 10px;border:2px solid #334155;border-radius:12px;background:#0f172a;color:#94a3b8;font:16px 'Tajawal',sans-serif;font-weight:700;cursor:pointer;text-align:center;transition:all .2s}
.diff-btn:hover{border-color:#fbbf24}
.diff-btn.active{border-color:#fbbf24;background:#78350f;color:#fbbf24}
.start-btn{width:100%;padding:16px;border:none;border-radius:12px;background:linear-gradient(135deg,#d97706,#b45309);color:#fff;font:18px 'Tajawal',sans-serif;font-weight:800;cursor:pointer;margin-top:8px;transition:transform .1s}
.start-btn:active{transform:scale(.97)}
.start-btn:disabled{opacity:.5;cursor:not-allowed}
.score-bar{display:flex;justify-content:center;gap:20px;margin-bottom:20px;font-size:17px;font-weight:700}
.score-bar .correct{color:#22c55e}.score-bar .wrong{color:#ef4444}.score-bar .total{color:#fbbf24}
.question{background:#1e293b;border-radius:14px;padding:24px;margin-bottom:16px;border:1px solid #334155}
.q-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.q-sura{font-size:17px;font-weight:700;color:#fbbf24}
.q-ref{font-size:14px;color:#64748b;direction:ltr}
.ayah-display{font:28px/2 'Amiri',serif;color:#e2e8f0;direction:rtl;text-align:center;margin-bottom:20px;line-height:2.2}
.word-visible{color:#e2e8f0}
.word-blank{display:inline-block;min-width:60px;border-bottom:3px solid #fbbf24;margin:0 4px;vertical-align:baseline}
.word-blank input{width:100%;background:transparent;border:none;outline:none;color:#fbbf24;font:24px 'Amiri',serif;text-align:center;padding:2px 0;direction:rtl}
.word-correct{color:#22c55e;font-weight:700}
.word-wrong{color:#ef4444;text-decoration:line-through}
.word-answer{color:#22c55e;font-size:22px;display:block;text-align:center}
.actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.act-btn{padding:14px 28px;border:none;border-radius:10px;font:16px 'Tajawal',sans-serif;font-weight:700;cursor:pointer;transition:all .1s}
.act-btn:active{transform:scale(.95)}
.act-btn.submit{background:#2563eb;color:#fff}
.act-btn.next{background:#16a34a;color:#fff}
.act-btn.show{background:#64748b;color:#fff}
.result-msg{text-align:center;font-size:20px;font-weight:700;margin:16px 0;padding:12px;border-radius:10px}
.result-msg.perfect{background:rgba(34,197,94,.15);color:#22c55e;border:1px solid #22c55e}
.result-msg.partial{background:rgba(234,179,8,.15);color:#eab308;border:1px solid #eab308}
.result-msg.fail{background:rgba(239,68,68,.15);color:#ef4444;border:1px solid #ef4444}
</style>
</head>
<body>
<div class="header">
 <h1>اختبار الحفظ الذاتي</h1>
 <p>اختبر حفظك للقرآن الكريم بثلاث مستويات صعوبة</p>
 <a href="/">← العودة للمصحف</a>
</div>
<div class="container">
 <div class="setup" id="setup">
  <h2>إعدادات الاختبار</h2>
  <div class="form-row">
   <label>السورة</label>
   <select id="suraSelect"><option value="0">القرآن كامل (عشوائي)</option></select>
  </div>
  <div class="form-row">
   <label>المستوى</label>
   <div class="diff-btns">
    <button class="diff-btn active" data-diff="easy" onclick="setDiff('easy',this)">سهل<br><small>25% مخفي</small></button>
    <button class="diff-btn" data-diff="medium" onclick="setDiff('medium',this)">متوسط<br><small>50% مخفي</small></button>
    <button class="diff-btn" data-diff="hard" onclick="setDiff('hard',this)">صعب<br><small>100% مخفي</small></button>
   </div>
  </div>
  <button class="start-btn" onclick="startQuiz()">ابدأ الاختبار</button>
 </div>
 <div id="quizArea" style="display:none">
  <div class="score-bar">
   <span class="correct">✓ <span id="scCorrect">0</span></span>
   <span class="wrong">✗ <span id="scWrong">0</span></span>
   <span class="total">المجموع: <span id="scTotal">0</span></span>
  </div>
  <div class="question" id="questionBox"></div>
  <div class="actions" id="actionBtns"></div>
 </div>
</div>
<script>
const $=id=>document.getElementById(id);
let diff='easy',sura=0,score={correct:0,wrong:0},curWords=[],curHidden=[],submitted=false;
const DIFF_RATIO={easy:.25,medium:.5,hard:1};

async function init(){
 try{
  const r=await fetch('/api/suras');const d=await r.json();
  d.suras.forEach(s=>{
   const o=document.createElement('option');o.value=s.number;
   o.textContent=s.number+'. '+s.name;$('suraSelect').appendChild(o);
  });
 }catch{}
}

function setDiff(d,btn){
 diff=d;
 document.querySelectorAll('.diff-btn').forEach(b=>b.classList.remove('active'));
 btn.classList.add('active');
}

function normalize(w){
 return w.replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u0640\u06E5\u06E6]/g,'')
         .replace(/[\u0622\u0623\u0625\u0671]/g,'\u0627')
         .replace(/\u0629/g,'\u0647').replace(/\u0649/g,'\u064A')
         .replace(/[\s\d\u0660-\u0669\u06F0-\u06F9]+$/,'').trim();
}

async function startQuiz(){
 sura=+$('suraSelect').value;
 $('setup').style.display='none';
 $('quizArea').style.display='block';
 await loadQuestion();
}

async function loadQuestion(){
 submitted=false;
 $('questionBox').innerHTML='<div style="text-align:center;color:#94a3b8;padding:20px">جاري التحميل...</div>';
 $('actionBtns').innerHTML='';
 try{
  const r=await fetch('/api/quiz/random?sura='+sura);
  const d=await r.json();
  curWords=d.words.map(w=>w.replace(/[\s\d\u0660-\u0669\u06F0-\u06F9]+$/,''));

  // Decide which words to hide
  const ratio=DIFF_RATIO[diff];
  const n=Math.max(1,Math.round(curWords.length*ratio));
  const indices=[...Array(curWords.length).keys()];
  // Shuffle and pick n
  for(let i=indices.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[indices[i],indices[j]]=[indices[j],indices[i]];}
  curHidden=new Set(indices.slice(0,n));

  // Render
  let header=`<div class="q-header"><span class="q-sura">${d.sura_name}</span><span class="q-ref">${d.sura}:${d.ayah} | صفحة ${d.page}</span></div>`;
  let ayah='<div class="ayah-display">';
  curWords.forEach((w,i)=>{
   if(curHidden.has(i)){
    ayah+=`<span class="word-blank"><input type="text" id="inp${i}" autocomplete="off" autocorrect="off" spellcheck="false"></span>`;
   } else {
    ayah+=`<span class="word-visible">${w}</span> `;
   }
  });
  ayah+='</div>';
  $('questionBox').innerHTML=header+ayah;
  $('actionBtns').innerHTML=`
   <button class="act-btn submit" onclick="submitAnswer()">تحقق</button>
   <button class="act-btn show" onclick="showAnswer()">أظهر الإجابة</button>
   <button class="act-btn next" onclick="loadQuestion()">سؤال جديد</button>
  `;
  // Focus first input
  const first=$('inp'+[...curHidden][0]);
  if(first)setTimeout(()=>first.focus(),100);

  // Enter key submits
  document.querySelectorAll('.word-blank input').forEach(inp=>{
   inp.addEventListener('keydown',e=>{
    if(e.key==='Enter'){e.preventDefault();submitAnswer();}
   });
  });
 }catch(e){
  $('questionBox').innerHTML='<div style="text-align:center;color:#ef4444;padding:20px">خطأ في تحميل السؤال</div>';
 }
}

function submitAnswer(){
 if(submitted)return;submitted=true;
 let correctCount=0,totalBlanks=curHidden.size;
 curHidden.forEach(i=>{
  const inp=$('inp'+i);
  if(!inp)return;
  const userVal=normalize(inp.value);
  const expected=normalize(curWords[i]);
  const isCorrect=userVal===expected;
  if(isCorrect)correctCount++;
  const parent=inp.parentElement;
  inp.remove();
  if(isCorrect){
   parent.innerHTML=`<span class="word-correct">${curWords[i]}</span>`;
  } else {
   let html=inp.value?`<span class="word-wrong">${inp.value}</span>`:'';
   html+=`<span class="word-answer">${curWords[i]}</span>`;
   parent.innerHTML=html;
  }
 });
 // Update score
 if(correctCount===totalBlanks)score.correct++;
 else score.wrong++;
 $('scCorrect').textContent=score.correct;
 $('scWrong').textContent=score.wrong;
 $('scTotal').textContent=score.correct+score.wrong;
 // Result message
 let msg='',cls='';
 if(correctCount===totalBlanks){msg='\u2705 ممتاز! كل الإجابات صحيحة';cls='perfect';}
 else if(correctCount>0){msg=`${correctCount} من ${totalBlanks} صحيح`;cls='partial';}
 else{msg='\u274C لم تصب أي إجابة';cls='fail';}
 const div=document.createElement('div');
 div.className='result-msg '+cls;div.textContent=msg;
 $('questionBox').appendChild(div);
}

function showAnswer(){
 if(submitted)return;submitted=true;
 curHidden.forEach(i=>{
  const inp=$('inp'+i);if(!inp)return;
  const parent=inp.parentElement;
  inp.remove();
  parent.innerHTML=`<span class="word-answer">${curWords[i]}</span>`;
 });
 score.wrong++;
 $('scWrong').textContent=score.wrong;
 $('scTotal').textContent=score.correct+score.wrong;
}

init();
</script>
</body>
</html>"""

LETTER_STATS_HTML="""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>إحصائيات حروف القرآن الكريم</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Tajawal',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.header{background:linear-gradient(135deg,#1e3a5f,#0f172a);padding:24px;text-align:center;border-bottom:2px solid #334155}
.header h1{font-size:28px;font-weight:800;color:#f0c040;margin-bottom:6px}
.header p{font-size:15px;color:#94a3b8}
.header a{color:#60a5fa;text-decoration:none;font-size:14px}
.container{max-width:1400px;margin:0 auto;padding:20px}
.controls{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.controls select,.controls input{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:8px 14px;font-family:inherit;font-size:14px}
.controls select{min-width:200px}
.controls button{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:8px 18px;font-family:inherit;font-size:14px;cursor:pointer;font-weight:600}
.controls button:hover{background:#1d4ed8}
.controls button.active{background:#16a34a}
.tabs{display:flex;gap:6px;margin-bottom:20px}
.tabs button{background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:8px 8px 0 0;padding:10px 20px;font-family:inherit;font-size:15px;cursor:pointer;font-weight:600;border-bottom:none}
.tabs button.active{background:#1e3a5f;color:#f0c040;border-color:#f0c040}
.tab-content{display:none}
.tab-content.active{display:block}
/* Overview cards */
.overview{display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:8px;margin-bottom:24px}
.lcard{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px 8px;text-align:center;transition:all .2s}
.lcard:hover{border-color:#f0c040;transform:translateY(-2px)}
.lcard .letter{font-size:32px;font-weight:800;color:#f0c040;line-height:1.2}
.lcard .count{font-size:13px;color:#94a3b8;margin-top:4px}
.lcard .pct{font-size:11px;color:#64748b}
/* Bar chart */
.chart-container{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:20px;border:1px solid #334155}
.chart-title{font-size:18px;font-weight:700;color:#f0c040;margin-bottom:16px}
.bar-row{display:flex;align-items:center;margin-bottom:6px;gap:8px}
.bar-label{width:30px;text-align:center;font-size:22px;font-weight:700;color:#e2e8f0;flex-shrink:0}
.bar-track{flex:1;height:28px;background:#0f172a;border-radius:6px;overflow:hidden;position:relative}
.bar-fill{height:100%;border-radius:6px;transition:width .5s ease;display:flex;align-items:center;padding:0 8px;min-width:fit-content}
.bar-fill span{font-size:12px;color:#fff;font-weight:600;white-space:nowrap}
/* Table */
.stats-table{width:100%;border-collapse:collapse;font-size:13px}
.stats-table th{background:#1e3a5f;color:#f0c040;padding:10px 6px;position:sticky;top:0;z-index:2;font-weight:700}
.stats-table td{padding:8px 6px;border-bottom:1px solid #1e293b;text-align:center}
.stats-table tr:hover{background:#1e293b}
.stats-table td:first-child{font-weight:700;color:#f0c040;text-align:right;white-space:nowrap}
.stats-table td:nth-child(2){color:#94a3b8;text-align:right}
.table-wrap{overflow-x:auto;background:#0f172a;border-radius:12px;border:1px solid #334155;max-height:70vh;overflow-y:auto}
.stats-table th.letter-col{font-size:20px;min-width:40px;writing-mode:initial}
.highlight{background:#f0c04020 !important;color:#f0c040 !important;font-weight:700}
/* Sura detail */
.sura-detail{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:768px){.sura-detail{grid-template-columns:1fr}}
.grand-total{background:linear-gradient(135deg,#1e3a5f,#162d50);border:2px solid #f0c040;border-radius:14px;padding:20px;text-align:center;margin-bottom:24px}
.grand-total .num{font-size:42px;font-weight:800;color:#f0c040}
.grand-total .label{font-size:16px;color:#94a3b8;margin-top:4px}
.color-1{background:linear-gradient(90deg,#2563eb,#3b82f6)}
.color-2{background:linear-gradient(90deg,#16a34a,#22c55e)}
.color-3{background:linear-gradient(90deg,#d97706,#f59e0b)}
.color-4{background:linear-gradient(90deg,#dc2626,#ef4444)}
.color-5{background:linear-gradient(90deg,#7c3aed,#8b5cf6)}
.color-6{background:linear-gradient(90deg,#0891b2,#06b6d4)}
.back-link{display:inline-block;margin-bottom:16px;color:#60a5fa;text-decoration:none;font-size:14px}
</style>
</head>
<body>
<div class="header">
 <h1>إحصائيات حروف القرآن الكريم</h1>
 <p>عدد تكرار كل حرف عربي في كل سورة</p>
 <a href="/">← العودة للمصحف</a>
</div>
<div class="container">
 <div id="loading" style="text-align:center;padding:40px;font-size:18px;color:#94a3b8">جاري التحميل...</div>
 <div id="app" style="display:none">
  <div class="grand-total">
   <div class="num" id="grandTotal"></div>
   <div class="label">إجمالي عدد الحروف في القرآن الكريم</div>
  </div>
  <div class="tabs">
   <button class="active" onclick="showTab('overview')">نظرة عامة</button>
   <button onclick="showTab('table')">جدول تفصيلي</button>
   <button onclick="showTab('sura')">بحث بالسورة</button>
  </div>
  <div id="tab-overview" class="tab-content active">
   <div class="chart-title">ترتيب الحروف من الأكثر تكراراً</div>
   <div class="overview" id="overviewCards"></div>
   <div class="chart-container">
    <div class="chart-title">الرسم البياني</div>
    <div id="barChart"></div>
   </div>
  </div>
  <div id="tab-table" class="tab-content">
   <div class="controls">
    <button id="sortBtn" onclick="toggleSort()">ترتيب حسب رقم السورة</button>
   </div>
   <div class="table-wrap" id="tableWrap"></div>
  </div>
  <div id="tab-sura" class="tab-content">
   <div class="controls">
    <select id="suraSelect" onchange="showSuraDetail()">
     <option value="">اختر سورة...</option>
    </select>
   </div>
   <div id="suraDetail"></div>
  </div>
 </div>
</div>
<script>
let data=null,sortByCount=false;
const COLORS=['color-1','color-2','color-3','color-4','color-5','color-6'];

async function init(){
 try{
  const r=await fetch('/api/letter-stats');
  data=await r.json();
  if(data.error){document.getElementById('loading').textContent=data.error;return;}
  document.getElementById('loading').style.display='none';
  document.getElementById('app').style.display='block';
  document.getElementById('grandTotal').textContent=data.grand_total.toLocaleString('ar-EG');
  renderOverview();
  renderTable();
  fillSuraSelect();
 }catch(e){document.getElementById('loading').textContent='خطأ في تحميل البيانات';}
}

function showTab(name){
 document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
 document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
 document.getElementById('tab-'+name).classList.add('active');
 event.target.classList.add('active');
}

function renderOverview(){
 const sorted=[...data.letters].sort((a,b)=>data.total[b]-data.total[a]);
 const max=data.total[sorted[0]];
 // Cards
 let cards='';
 sorted.forEach(l=>{
  const c=data.total[l];
  const pct=(c/data.grand_total*100).toFixed(1);
  cards+=`<div class="lcard"><div class="letter">${l}</div><div class="count">${c.toLocaleString('ar-EG')}</div><div class="pct">${pct}%</div></div>`;
 });
 document.getElementById('overviewCards').innerHTML=cards;
 // Bar chart
 let bars='';
 sorted.forEach((l,i)=>{
  const c=data.total[l];
  const w=(c/max*100).toFixed(1);
  const cl=COLORS[i%COLORS.length];
  bars+=`<div class="bar-row"><div class="bar-label">${l}</div><div class="bar-track"><div class="bar-fill ${cl}" style="width:${w}%"><span>${c.toLocaleString('ar-EG')}</span></div></div></div>`;
 });
 document.getElementById('barChart').innerHTML=bars;
}

function renderTable(){
 const letters=data.letters;
 let suras=[...data.suras];
 if(sortByCount)suras.sort((a,b)=>b.total_letters-a.total_letters);
 let html='<table class="stats-table"><thead><tr><th>#</th><th>السورة</th><th>المجموع</th>';
 letters.forEach(l=>{html+=`<th class="letter-col">${l}</th>`;});
 html+='</tr></thead><tbody>';
 suras.forEach(s=>{
  const maxInSura=Math.max(...letters.map(l=>s.counts[l]||0));
  html+=`<tr><td>${s.number}</td><td>${s.name}</td><td style="color:#f0c040;font-weight:700">${s.total_letters.toLocaleString('ar-EG')}</td>`;
  letters.forEach(l=>{
   const v=s.counts[l]||0;
   const cls=v===maxInSura&&v>0?' highlight':'';
   html+=`<td class="${cls}">${v||'·'}</td>`;
  });
  html+='</tr>';
 });
 // Total row
 html+='<tr style="background:#1e3a5f;font-weight:700"><td></td><td>المجموع</td><td style="color:#f0c040">'+data.grand_total.toLocaleString('ar-EG')+'</td>';
 letters.forEach(l=>{html+=`<td style="color:#f0c040">${data.total[l].toLocaleString('ar-EG')}</td>`;});
 html+='</tr></tbody></table>';
 document.getElementById('tableWrap').innerHTML=html;
}

function toggleSort(){
 sortByCount=!sortByCount;
 document.getElementById('sortBtn').textContent=sortByCount?'ترتيب حسب عدد الحروف':'ترتيب حسب رقم السورة';
 renderTable();
}

function fillSuraSelect(){
 const sel=document.getElementById('suraSelect');
 data.suras.forEach(s=>{
  const opt=document.createElement('option');
  opt.value=s.number;
  opt.textContent=`${s.number}. ${s.name}`;
  sel.appendChild(opt);
 });
}

function showSuraDetail(){
 const num=parseInt(document.getElementById('suraSelect').value);
 if(!num){document.getElementById('suraDetail').innerHTML='';return;}
 const s=data.suras.find(x=>x.number===num);
 if(!s)return;
 const sorted=[...data.letters].filter(l=>s.counts[l]>0).sort((a,b)=>s.counts[b]-s.counts[a]);
 const max=s.counts[sorted[0]]||1;
 let html=`<div class="sura-detail"><div>
  <div class="chart-container"><div class="chart-title">سورة ${s.name} — ${s.total_letters.toLocaleString('ar-EG')} حرف</div>`;
 sorted.forEach((l,i)=>{
  const c=s.counts[l];
  const w=(c/max*100).toFixed(1);
  const pct=(c/s.total_letters*100).toFixed(1);
  const cl=COLORS[i%COLORS.length];
  html+=`<div class="bar-row"><div class="bar-label">${l}</div><div class="bar-track"><div class="bar-fill ${cl}" style="width:${w}%"><span>${c} (${pct}%)</span></div></div></div>`;
 });
 html+='</div></div><div><div class="overview">';
 sorted.forEach(l=>{
  const c=s.counts[l];
  const pct=(c/s.total_letters*100).toFixed(1);
  html+=`<div class="lcard"><div class="letter">${l}</div><div class="count">${c.toLocaleString('ar-EG')}</div><div class="pct">${pct}%</div></div>`;
 });
 html+='</div></div></div>';
 document.getElementById('suraDetail').innerHTML=html;
}

init();
</script>
</body>
</html>"""

def main():
    parser=argparse.ArgumentParser(description="Quran Word Coordinates Viewer")
    parser.add_argument("--images-dir",default="./images",help="Directory with page images")
    parser.add_argument("--json-dir",default=None,help="Directory with coord JSONs (default: bundled package data)")
    parser.add_argument("--mushaf-dir",default="./mushaf",help="Directory with mushaf JSONs")
    parser.add_argument("--host",default="0.0.0.0")
    parser.add_argument("--port",type=int,default=8003)
    parser.add_argument("--word-freq-db",default="./word_freq.db")
    parser.add_argument("--letter-stats",default="./letter_stats.json",help="Letter statistics JSON file")
    a=parser.parse_args()
    CFG["img"]=a.images_dir
    CFG["js"]=a.json_dir if a.json_dir else _PKG_DATA
    CFG["mu"]=a.mushaf_dir
    CFG["wf"]=a.word_freq_db
    CFG["ls"]=a.letter_stats
    the_app = _ensure_app()
    import uvicorn
    print(f"Quran Coords Viewer -> http://localhost:{a.port}")
    print(f"  Images: {CFG['img']}")
    print(f"  Coords: {CFG['js']}")
    print(f"  Mushaf: {CFG['mu']}")
    uvicorn.run(the_app,host=a.host,port=a.port,log_level="info")

if __name__=="__main__":main()
