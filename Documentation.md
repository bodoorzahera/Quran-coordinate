# نظام إحداثيات كلمات القرآن الكريم — التوثيق الشامل

## نظرة عامة

النظام مكون من **3 أجزاء** تعمل معاً:

```
┌─────────────────────────────────────────────────────────┐
│                    النظام الكامل                         │
│                                                         │
│  ┌──────────────┐    ┌──────────┐    ┌───────────────┐  │
│  │  السكربت     │───▶│  JSON    │◀───│  السيرفر      │  │
│  │ generate_    │    │ output/  │    │  server.py    │  │
│  │ coords.py   │    │ page-*.  │    │  (FastAPI)    │  │
│  └──────┬───────┘    │ json     │    └───────┬───────┘  │
│         │            └──────────┘            │          │
│         ▼                                    ▼          │
│  ┌──────────────┐                   ┌───────────────┐   │
│  │  المدخلات    │                   │  المتصفح      │   │
│  │ • صور PNG    │                   │  HTML/Canvas   │   │
│  │ • خطوط QCF  │                   │  JavaScript    │   │
│  │ • قاعدة بيانات│                  └───────────────┘   │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

---

## هيكل الملفات

```
project/
├── generate_coords.py     # السكربت الرئيسي (يولّد JSON)
├── server.py              # سيرفر العرض والتعديل (FastAPI)
├── quran_glyphs.db        # قاعدة بيانات SQLite (تُبنى مرة واحدة)
├── quran.com-images/      # مستودع GitHub (يُنسخ مرة واحدة)
│   ├── res/fonts/         # خطوط QCF_P001.TTF - QCF_P604.TTF
│   └── sql/               # ملف SQL الأصلي
├── images/                # صور صفحات المصحف
│   ├── page-001.png
│   ├── page-002.png
│   └── ...
└── output/                # المخرجات (JSON + debug images)
    ├── page-001.json
    ├── page-003.json
    ├── debug-page-003.png
    └── ...
```

---

## الجزء 1: السكربت (`generate_coords.py`)

### الغرض

يأخذ صورة صفحة + بيانات خطوط QPC ← يُنتج ملف JSON بإحداثيات كل كلمة.

### البلوكات الرئيسية

---

### البلوك 1: بناء قاعدة البيانات

```python
def build_sqlite_db(quran_images_dir, db_path='quran_glyphs.db'):
```

**ماذا يفعل:** يقرأ ملف `02-database.sql` من مستودع quran.com-images ويحوله لـ SQLite.

**متى يُشغَّل:** مرة واحدة فقط (أو عند `--build-db`).

**الجداول الثلاثة:**

| الجدول | الغرض | مثال |
|--------|-------|------|
| `glyph` | كل glyph مع كود الخط | glyph_id=1, code=0xFB51, type=1 (كلمة) |
| `glyph_page_line` | موقع كل glyph في صفحة وسطر | page=3, line=1, position=1, type='ayah' |
| `glyph_ayah` | ربط الـ glyph بالآية | sura=2, ayah=6, position=1 |

**أنواع الأسطر (`line_type`):**
- `ayah` — سطر آيات (نعالجه وننتج إحداثيات)
- `sura` — عنوان سورة (نتخطاه)
- `bismillah` — بسملة (نتخطاه)

**أنواع الـ glyph (`glyph_type_id`):**
- `1` = كلمة قرآنية (نحفظها في JSON)
- `2` = علامة نهاية آية ⑥
- `3` = علامة خاصة (صلى، قلى...)
- `6` = جزء من عنوان سورة
- `17` = جزء من بسملة

---

### البلوك 2: كاش الخطوط

```python
def get_font_advances(font_path):
```

**ماذا يفعل:** يفتح خط QCF_P{NNN}.TTF ويستخرج advance width لكل حرف.

**لماذا advance width؟** هو العرض المخصص لكل glyph في الخط — يعطينا **نسب** عرض كل كلمة للأخرى.

**مثال:** لو كلمة "الله" advance=1664 وكلمة "على" advance=1714:
- نسبة "الله" = 1664/(1664+1714) = 49%
- نسبة "على" = 1714/(1664+1714) = 51%
- لو السطر عرضه 200px ← "الله"≈98px و "على"≈102px

**ملاحظة مهمة:** النسب من الخط ليست مطابقة 100% للصورة لأن الصور قد تكون من إصدار مختلف. لذلك نستخدمها كـ "تقدير أولي" ثم نصحح بالخطوة التالية.

---

### البلوك 3: كشف الأسطر تلقائياً

```python
def detect_line_bands(gray, min_ink=5, min_height=15):
```

**ماذا يفعل:** يمسح الصورة عمودياً ويجد كل شريط أفقي فيه حبر (= سطر نص).

**الخوارزمية:**
1. لكل صف y في الصورة، يعد عدد البكسلات الداكنة (< 180)
2. لو الصف فيه حبر (> 5 بكسلات) ← بداية شريط
3. لو الصف فاضي ← نهاية شريط
4. لو ارتفاع الشريط > 15px ← سطر حقيقي (مش ضوضاء)

**المخرج:** قائمة `[(y_start, y_end), ...]` لكل سطر في الصفحة.

**لماذا هذا أفضل من مواقع ثابتة:**
- صفحة 1 و 2: 8 أسطر فقط (خط كبير)
- صفحات عادية: 15 سطر
- صفحات بها عنوان سورة: 15 سطر لكن بعضها header/basmala

---

### البلوك 4: تحليل الصورة

```python
def find_ink_extent(gray, y1, y2):     # حدود الحبر في سطر
def find_all_gaps(gray, y1, y2, x1, x2):  # الفراغات بين الكلمات
```

**`find_ink_extent`:** يجد أقصى يسار وأقصى يمين وأعلى وأسفل للحبر في سطر معين.

**`find_all_gaps`:** يجد كل الفراغات (أعمدة بدون حبر ≥ 2 بكسل) في سطر. كل فراغ له:
- `center`: منتصف الفراغ (بالبكسل)
- `width`: عرض الفراغ (بالبكسل)

---

### البلوك 5: الخوارزمية الرئيسية (قلب النظام)

```python
def compute_line_cuts(glyphs, font_adv, gray, y1, y2, ink_l, ink_r):
```

**يحدد حدود كل كلمة في سطر واحد.**

**الخطوات الأربع:**

```
الخطوة 1: حساب المواقع المتوقعة من الخط
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
كل glyph له advance width ← نحسب نسبته من المجموع
← نحول النسبة لموقع بكسل على السطر (proportional cut)

مثال لسطر عرضه 840px مع 3 كلمات بنسب 30%/40%/30%:
  حد 1 عند x = 879 - 252 = 627
  حد 2 عند x = 879 - 588 = 291

الخطوة 2: كشف كل الفراغات من الصورة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
نمسح السطر أفقياً ونجد كل عمود بدون حبر
فراغ = سلسلة أعمدة متتالية بدون حبر ≥ 2px

الخطوة 3: الربط الذكي (Smart Snap)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
لكل حد متوقع من الخطوة 1:
  • نبحث عن كل فراغ حقيقي ضمن ±30px (SNAP_RANGE)
  • نحسب نقاط لكل فراغ مرشح:
      score = gap_width × 2.0 − distance × 0.5
      (نفضل: فراغ أعرض + أقرب للهدف)
  • نتأكد إن الكلمة الناتجة ≥ 30% من العرض المتوقع
  • نختار الفراغ بأعلى نقاط (أو نستخدم الموقع المتوقع كفول باك)

الخطوة 4: التصحيح النهائي
━━━━━━━━━━━━━━━━━━━━━━━━━
  • نتأكد إن الحدود تتناقص (من اليمين لليسار - RTL)
  • نصلح أي كلمة أضيق من الحد الأدنى
```

**مثال بصري:**

```
السطر في الصورة:
  |  إِنَّ  ·  ٱلَّذِينَ  ·  كَفَرُوا۟  ·  سَوَآءٌ  |
               ↑ 10px gap    ↑ 7px gap    ↑ 5px gap

الخط يتوقع:    |--35px--|---140px---|---110px---|---95px--|
الفراغ الحقيقي:          ↑ x=703       ↑ x=595    ↑ x=499

النتيجة: snap كل حد للفراغ الأقرب
  إِنَّ = [844-879]  ← 35px  ✓
  ٱلَّذِينَ = [703-844]  ← 141px  ✓
  كَفَرُوا۟ = [595-703]  ← 108px  ✓
  سَوَآءٌ = [499-595]  ← 96px  ✓
```

---

### البلوك 6: معالجة صفحة كاملة

```python
def process_page(page_num, base_dir, fonts_dir, db_path, output_dir, debug=False):
```

**التدفق:**
1. تحميل الصورة + الخط + بيانات DB
2. كشف الأسطر من الصورة (`detect_line_bands`) ← مثلاً 15 band
3. ربط كل band بسطر من DB ← band[0] = line 1, band[2] = line 3 (sura)...
4. لكل سطر `line_type == 'ayah'`: تشغيل `compute_line_cuts`
5. تخطي أسطر `sura` و `bismillah`
6. حفظ النتيجة كـ JSON
7. (اختياري) رسم debug image بإطارات ملونة

---

### تشغيل السكربت

```bash
# أول مرة: بناء قاعدة البيانات
python3 generate_coords.py --build-db -q quran.com-images

# صفحة واحدة مع debug
python3 generate_coords.py -b . -q quran.com-images -o output --page 3 --debug

# كل الصفحات
python3 generate_coords.py -b . -q quran.com-images -o output

# نطاق محدد
python3 generate_coords.py -b . -q quran.com-images -o output --start 1 --end 20 --debug
```

### صيغة ملف JSON الناتج

```json
{
  "page": 3,
  "coords": {
    "2:6:1": {
      "h": {"x": 844, "y": 23, "w": 35, "h": 68},
      "p": {"x": 844, "y": 18, "w": 35, "h": 23},
      "o": {"x": 0, "y": 23, "w": 39, "h": 68}
    }
  }
}
```

**مفتاح الموقع:** `"سورة:آية:كلمة"` ← `"2:6:1"` = سورة البقرة، آية 6، كلمة 1

**الطبقات الثلاث:**

| الطبقة | الغرض | الاستخدام |
|--------|-------|-----------|
| `h` (highlight) | إطار التظليل الكامل حول الكلمة | تظليل عند الضغط |
| `p` (pronunciation) | منطقة صغيرة فوق الكلمة | عرض نطق أو تفسير |
| `o` (ornament) | منطقة ثابتة يسار السطر | زخرفة أو رقم آية |

---

## الجزء 2: السيرفر (`server.py`)

### الغرض

يعرض الصور مع الإطارات في المتصفح ويسمح بالتنقل والتعديل.

---

### البلوك 1: FastAPI Backend

```python
app = FastAPI(title="Quran Coords Viewer")
```

**الـ API Endpoints:**

| Method | Path | الغرض | يُرجع |
|--------|------|-------|-------|
| `GET` | `/` | الصفحة الرئيسية | HTML |
| `GET` | `/api/pages` | قائمة الصفحات المتاحة | `{"pages": [3, 4, ...]}` |
| `GET` | `/api/page/{n}` | بيانات JSON لصفحة | `{"page": 3, "coords": {...}}` |
| `GET` | `/api/image/{n}` | صورة الصفحة | PNG file |
| `POST` | `/api/page/{n}/update` | تحديث إحداثيات كلمة | `{"ok": true}` |

**كيف تضيف endpoint جديد:**

```python
# أضف هذا في server.py قبل متغير VIEWER_HTML

@app.get("/api/my-feature/{page_num}")
async def my_feature(page_num: int):
    # اعمل اللي تحتاجه
    return {"result": "data"}
```

---

### البلوك 2: Frontend (HTML + CSS + JavaScript)

الـ frontend كله في متغير `VIEWER_HTML` داخل server.py (ملف واحد).

**تخطيط الواجهة:**

```
┌──────────────────────────────────────────────────────┐
│ Header                                                │
│ [◀][003][▶] / 604    [−][100%][+][Fit]  [Borders]    │
├─────────────────────────────────────┬────────────────┤
│                                     │ Side Panel     │
│          Canvas Area                │                │
│                                     │ ┌────────────┐ │
│    ┌──────────────────────┐         │ │ Selected   │ │
│    │                      │         │ │ Word       │ │
│    │   صورة المصحف +      │         │ │ 2:6:1      │ │
│    │   إطارات ملونة       │         │ │ x=844 y=23 │ │
│    │   (كلها على Canvas)  │         │ │ [💾 حفظ]   │ │
│    │                      │         │ └────────────┘ │
│    │                      │         │ ┌────────────┐ │
│    └──────────────────────┘         │ │ Words List │ │
│                                     │ │ 2:6:1      │ │
│                                     │ │ 2:6:2      │ │
│                                     │ │ ...        │ │
│                                     │ └────────────┘ │
└─────────────────────────────────────┴────────────────┘
```

**لماذا Canvas وليس CSS overlay:**

```
❌ طريقة CSS القديمة (كانت تسبب مشاكل النسب):
   <img> في حجم + <div> فوقه بحجم مختلف = إزاحة

✅ طريقة Canvas الحالية (pixel-perfect):
   كل شيء يُرسم على نفس الـ canvas بنفس الـ scale
   
   ctx.drawImage(img, 0, 0, w*zoom, h*zoom);     // الصورة
   ctx.strokeRect(x*zoom, y*zoom, ...);           // الإطار
   // كلاهما مضروب في نفس zoom = متطابقين دائماً
```

**الدوال الرئيسية في JavaScript:**

| الدالة | الغرض |
|--------|-------|
| `fetchPages()` | يجلب قائمة الصفحات عند فتح الموقع |
| `loadPage(n)` | يحمّل صورة + JSON لصفحة معينة |
| `draw()` | يرسم الصورة + كل الإطارات على Canvas |
| `selectWord(loc)` | يحدد كلمة ويعرض تفاصيلها |
| `saveCoords()` | يرسل التعديلات للسيرفر عبر POST |
| `zoomFit/In/Out()` | تحكم بالتكبير والتصغير |
| `toggleBorders()` | إظهار/إخفاء الإطارات |

**كشف الضغط على كلمة:**

```javascript
canvas.addEventListener('click', function(e) {
  // 1. تحويل موقع الضغط لإحداثيات الصورة الأصلية
  const cx = (e.clientX - rect.left) / zoom;
  const cy = (e.clientY - rect.top) / zoom;

  // 2. البحث عن أصغر كلمة تحتوي هذا الموقع
  for (const [loc, layers] of Object.entries(pageData.coords)) {
    const h = layers.h;
    if (cx >= h.x && cx <= h.x + h.w && cy >= h.y && cy <= h.y + h.h) {
      selectWord(loc);  // وجدناها!
    }
  }
});
```

### تشغيل السيرفر

```bash
python3 server.py --images-dir ./images --json-dir ./output --port 8000
# ثم افتح http://localhost:8000
```

### اختصارات لوحة المفاتيح

| المفتاح | الوظيفة |
|---------|---------|
| ← → | تنقل بين الصفحات |
| B | إظهار/إخفاء الإطارات |
| + / − | تكبير/تصغير |
| 0 | ملاءمة الشاشة |
| Esc | إلغاء التحديد |

---

## الجزء 3: قاعدة البيانات (`quran_glyphs.db`)

### العلاقات

```
glyph (الكلمة/الرمز)
  ├── glyph_page_line (أين في الصفحة؟)
  │     • page_number = 3
  │     • line_number = 1
  │     • line_type = 'ayah'
  │     • position = 1 (ترتيبه في السطر)
  │
  └── glyph_ayah (أي آية؟)
        • sura_number = 2
        • ayah_number = 6
        • position = 1 (ترتيب الكلمة في الآية)
```

### استعلامات مفيدة

```sql
-- كل الأسطر في صفحة مع أنواعها
SELECT DISTINCT line_number, line_type
FROM glyph_page_line WHERE page_number = 592
ORDER BY line_number;

-- كلمات سطر معين
SELECT g.glyph_code, g.glyph_type_id,
       ga.sura_number, ga.ayah_number, ga.position
FROM glyph_page_line gpl
JOIN glyph g ON g.glyph_id = gpl.glyph_id
LEFT JOIN glyph_ayah ga ON ga.glyph_id = gpl.glyph_id
WHERE gpl.page_number = 3 AND gpl.line_number = 1
ORDER BY gpl.position;

-- صفحات فيها عنوان سورة
SELECT DISTINCT page_number
FROM glyph_page_line WHERE line_type = 'sura'
ORDER BY page_number;

-- عدد الكلمات في كل صفحة
SELECT gpl.page_number, COUNT(*)
FROM glyph_page_line gpl
JOIN glyph g ON g.glyph_id = gpl.glyph_id
WHERE g.glyph_type_id = 1 AND gpl.line_type = 'ayah'
GROUP BY gpl.page_number;
```

---

## دليل إضافة ميزات جديدة

### المبدأ العام

```
1. حدد: هل التغيير في البيانات أم العرض أم الاثنين؟
2. لو بيانات ← عدّل generate_coords.py ← أعد توليد JSON
3. لو عرض ← عدّل VIEWER_HTML في server.py
4. لو API ← أضف endpoint في server.py ثم استدعيه من JavaScript
```

---

### مثال 1: إضافة عرض نص الكلمة العربي

**الهدف:** لما المستخدم يضغط على كلمة، يشوف النص العربي مش بس الإحداثيات.

**الخطوة 1 — السكربت:** أضف النص في JSON

```python
# في process_page()، عند حفظ الإحداثيات:
coords[loc] = {
    'h': {'x': xl, 'y': ink_top, 'w': w, 'h': h_h},
    'p': {...},
    'o': {...},
    'text': word_text,   # ← أضف هذا السطر
}
```

**الخطوة 2 — الواجهة:** اعرض النص

```javascript
// في updateSel()، أضف قبل sel-loc:
el.innerHTML = `
  <div style="font-family:Amiri; font-size:28px;
       color:#d4a853; text-align:center; direction:rtl">
    ${pageData.coords[selWord].text || selWord}
  </div>
  <div class="sel-loc">${selWord}</div>
  ...
`;
```

**الخطوة 3:** أعد توليد JSON وافتح المتصفح.

---

### مثال 2: إضافة تصدير CSV

**الخطوة 1 — Backend:** أضف endpoint

```python
from fastapi.responses import Response

@app.get("/api/page/{page_num}/csv")
async def export_csv(page_num: int):
    json_path = os.path.join(JSON_DIR, f"page-{page_num:03d}.json")
    with open(json_path) as f:
        data = json.load(f)
    lines = ["location,x,y,w,h"]
    for loc, layers in data['coords'].items():
        h = layers['h']
        lines.append(f"{loc},{h['x']},{h['y']},{h['w']},{h['h']}")
    return Response(
        content="\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=page-{page_num:03d}.csv"}
    )
```

**الخطوة 2 — Frontend:** أضف زر في الـ header

```html
<button class="btn" onclick="window.open('/api/page/'+curPage+'/csv')">📥 CSV</button>
```

---

### مثال 3: تلوين حسب السورة

**Frontend فقط — لا تحتاج تغيير backend أو سكربت:**

```javascript
// في draw()، بدّل طريقة اختيار اللون:
entries.forEach(([loc, layers], i) => {
  const sura = parseInt(loc.split(':')[0]);
  // لون مختلف لكل سورة
  const hue = (sura * 137) % 360;  // توزيع ألوان متباين
  ctx.strokeStyle = `hsla(${hue}, 70%, 55%, 0.6)`;
  ctx.fillStyle = `hsla(${hue}, 70%, 55%, 0.08)`;
  // ... باقي الرسم
});
```

---

### مثال 4: إضافة بحث عن كلمة/آية

**الخطوة 1 — Backend:**

```python
@app.get("/api/search/{query}")
async def search_word(query: str):
    """يبحث في كل ملفات JSON عن موقع كلمة/آية"""
    results = []
    for f in glob.glob(os.path.join(JSON_DIR, "page-*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for loc in data.get('coords', {}):
            if query in loc:  # بحث بسيط في "2:6:1" format
                results.append({"page": data['page'], "location": loc})
    return {"results": results}
```

**الخطوة 2 — Frontend:**

```javascript
// أضف input في الـ header
// <input id="searchInput" placeholder="2:255" onkeydown="if(event.key==='Enter')doSearch()">

async function doSearch() {
  const q = document.getElementById('searchInput').value;
  const r = await fetch('/api/search/' + encodeURIComponent(q));
  const d = await r.json();
  if (d.results.length > 0) {
    const first = d.results[0];
    await loadPage(first.page);
    selectWord(first.location);
  }
}
```

---

## تعديل معاملات السكربت

```python
# في generate_coords.py:

SNAP_RANGE = 30       # نطاق البحث عن فراغ (±بكسل)
                      # ↑ زيادة = مرونة أكثر (قد يمسك فراغ خاطئ)
                      # ↓ تقليل = أدق (قد يفوت الفراغ الصحيح)

MIN_WORD_RATIO = 0.30 # الحد الأدنى لعرض الكلمة كنسبة من المتوقع
                      # ↑ زيادة = يرفض snaps أكثر
                      # ↓ تقليل = يقبل كلمات أضيق

INK_THRESH = 180      # عتبة الحبر (0=أسود، 255=أبيض)
                      # ↑ زيادة = حساسية أعلى (رمادي فاتح = حبر)
                      # ↓ تقليل = حساسية أقل
```

---

## خطوات التطوير المعتادة

### عند تعديل السكربت:

```bash
# 1. عدّل generate_coords.py
# 2. اختبر على صفحة واحدة
python3 generate_coords.py -b . -q quran.com-images -o output --page 3 --debug
# 3. افتح debug-page-003.png وتأكد بصرياً
# 4. اختبر صفحة بها عنوان سورة
python3 generate_coords.py ... --page 592 --debug
# 5. اختبر صفحة 1 و 2 (layout خاص)
python3 generate_coords.py ... --page 1 --debug
# 6. لو كله تمام، شغّل على كل الصفحات
python3 generate_coords.py -b . -q quran.com-images -o output
```

### عند تعديل الواجهة:

```bash
# 1. عدّل VIEWER_HTML في server.py
# 2. أعد تشغيل السيرفر (Ctrl+C ثم python3 server.py ...)
# 3. افتح المتصفح وامسح الكاش (Ctrl+Shift+R)
```

### عند إضافة API endpoint:

```bash
# 1. أضف @app.get/post في server.py (قبل VIEWER_HTML)
# 2. أضف استدعاء fetch() في JavaScript داخل VIEWER_HTML
# 3. أعد تشغيل السيرفر
```

---

## خريطة التدفق الكاملة

```
صورة page-003.png                    quran_glyphs.db
       │                                    │
       ▼                                    ▼
detect_line_bands()              query line_type + glyphs
  يكتشف 15 شريط                   يجلب نوع كل سطر
       │                                    │
       ▼                                    ▼
   bands[0..14]  ◄──── ربط ────►  all_lines{1..15}
       │                                    │
       │         لكل سطر ayah:              │
       ▼              │                     ▼
find_ink_extent()     │            font advance widths
  حدود الحبر          │            نسب عرض الكلمات
       │              │                     │
       ▼              ▼                     ▼
find_all_gaps() ───► compute_line_cuts() ◄── proportional positions
  كل الفراغات         │
                      │ لكل حد: snap to nearest gap
                      ▼
              cuts = [879, 849, 706, ...]
                      │
                      ▼
              coords["2:6:1"] = {x, y, w, h}
                      │
                      ▼
              page-003.json
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
  server.py يقرأه          debug image يُرسم
  ويعرضه في المتصفح        للمراجعة البصرية
```

---

## استكشاف الأخطاء

| المشكلة | السبب المحتمل | الحل |
|---------|--------------|------|
| "skip" عند تشغيل صفحة | صورة أو خط غير موجود | تأكد من `images/page-NNN.png` و `QCF_PNNN.TTF` |
| كلمات مدمجة | الفراغ بين الكلمتين < 2px | قلل الحد الأدنى في `find_all_gaps` |
| إطارات منزاحة لأسفل | `detect_line_bands` أخطأ | قلل `min_ink` أو `min_height` |
| حدود خاطئة لصفحات بها headers | السطر لم يُتخطى | تأكد أن `line_type != 'ayah'` يُتخطى |
| الإطارات مش فوق الكلمات في المتصفح | مشكلة zoom/scale | تأكد إنك تستخدم Canvas (وليس CSS overlay) |
| خطأ "No JSON for page" | السكربت لم يُشغَّل لهذه الصفحة | شغّل السكربت أولاً |
| `ERROR: sql not found` | مستودع quran.com-images مش موجود | `git clone` المستودع |

---

## ملاحظات مهمة

1. **الصفحتان 1 و 2** لهما layout مختلف (8 أسطر بخط كبير). السكربت يتعامل معهم تلقائياً عبر `detect_line_bands`.

2. **الخطوط QCF** مختلفة لكل صفحة (QCF_P001.TTF ≠ QCF_P002.TTF). لا تستخدم خط صفحة لمعالجة صفحة أخرى.

3. **مشكلة الحروف المنفصلة:** حروف مثل ا، د، ر، و تخلق فراغات داخل الكلمة (intra-word gaps) شبيهة بالفراغات بين الكلمات (inter-word gaps). الفرق بينهم أحياناً 1-2 بكسل فقط! لذلك لا يمكن الاعتماد على حجم الفراغ وحده — نستخدم الخط كتقدير أولي والفراغ كدليل.

4. **ترتيب RTL:** النص العربي من اليمين لليسار. في الكود: `ink_r` = بداية السطر (يمين)، `ink_l` = نهاية السطر (يسار). الـ cuts تتناقص من اليمين لليسار.

5. **علامات الآيات** (⑥ ⑦...) والعلامات الخاصة (صلى، قلى...) تأخذ مكان في السطر وتُحسب في النسب لكن لا تُحفظ كإحداثيات كلمات في الـ JSON (`glyph_type_id != 1`).

---

## ملحق: خريطة الدوال

### generate_coords.py

```
main()
 ├── build_sqlite_db()           # بناء DB (مرة واحدة)
 └── process_page()              # لكل صفحة:
      ├── get_font_advances()    #   قراءة خط QCF
      ├── detect_line_bands()    #   كشف أسطر من الصورة
      └── [لكل سطر ayah]:
           ├── find_ink_extent() #   حدود الحبر
           ├── find_all_gaps()   #   الفراغات
           └── compute_line_cuts() # الخوارزمية الرئيسية
```

### server.py

```
main()
 └── uvicorn.run(app)
      ├── GET  /                   ← يرجع VIEWER_HTML
      ├── GET  /api/pages          ← يمسح output/ ويرجع أرقام الصفحات
      ├── GET  /api/page/{n}       ← يقرأ page-NNN.json ويرجعه
      ├── GET  /api/image/{n}      ← يرجع images/page-NNN.png
      └── POST /api/page/{n}/update ← يعدّل إحداثية في JSON ويحفظ

Frontend JavaScript:
 ├── fetchPages()      ← GET /api/pages عند فتح الموقع
 ├── loadPage(n)       ← GET /api/image + /api/page
 ├── draw()            ← يرسم صورة + إطارات على Canvas
 ├── selectWord(loc)   ← يحدد كلمة ويحدّث Side Panel
 ├── saveCoords()      ← POST /api/page/{n}/update
 └── zoomFit/In/Out()  ← يغيّر zoom ويعيد draw()
```

---

## المكتبات المطلوبة

```bash
# للسكربت
pip install numpy Pillow fonttools

# للسيرفر
pip install fastapi uvicorn

# قاعدة البيانات (مدمجة في Python)
# sqlite3 — لا تحتاج تثبيت

# مستودع الخطوط (مرة واحدة)
git clone https://github.com/quran/quran.com-images.git
```

---

## فصل الـ Frontend لملف مستقل (اختياري)

لتسهيل التعديل على الواجهة بدون إعادة تشغيل السيرفر:

**الخطوة 1:** أنشئ `static/index.html` وانقل محتوى `VIEWER_HTML` إليه.

**الخطوة 2:** عدّل server.py:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html") as f:
        return f.read()
```

**النتيجة:** تقدر تعدّل HTML/CSS/JS وتعمل refresh في المتصفح بدون إعادة تشغيل السيرفر.
