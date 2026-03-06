#!/usr/bin/env python3
"""
Quran Word Frequency Database Builder
======================================

Scans all mushaf/page-NNN.json files and builds a SQLite database with:
  1. Every word occurrence (location, page, sura, ayah, word_pos, with/without tashkeel)
  2. Frequency of each unique word WITHOUT tashkeel (bare form)
  3. Frequency of each unique word WITH tashkeel (vocalized form)
  4. Grouping: bare → [vocalized variants with counts]

USAGE:
  python3 build_word_freq.py --mushaf-dir ./mushaf --db word_freq.db

  # Or specify sura names file for display
  python3 build_word_freq.py --mushaf-dir ./mushaf --db word_freq.db
"""

import json, os, sys, re, sqlite3, argparse, glob, unicodedata


def strip_trailing_digits(word):
    """Remove trailing digits (Western, Arabic-Indic, Extended Arabic-Indic) from word."""
    return re.sub(r'[\d\u0660-\u0669\u06F0-\u06F9]+$', '', word)


def strip_tashkeel(word):
    """Remove all Arabic diacritics/tashkeel, normalize letters."""
    # First strip trailing digits (ayah numbers attached to words)
    word = strip_trailing_digits(word)
    result = ''
    for ch in word:
        cat = unicodedata.category(ch)
        # Skip combining marks (diacritics, vowels, shadda, sukun, etc.)
        if cat.startswith('M'):
            continue
        # Skip tatweel (kashida)
        if ch == '\u0640':
            continue
        # Skip Quranic annotation marks (U+06D6–U+06ED)
        if '\u06D6' <= ch <= '\u06ED':
            continue
        # Skip superscript alef and similar
        if ch in '\u0670\u0671':
            # U+0670 = superscript alef (keep as alef)
            result += 'ا'
            continue
        result += ch

    # Normalize alef variants → bare alef
    result = re.sub('[إأآٱ]', 'ا', result)
    # Normalize teh marbuta → heh
    result = result.replace('ة', 'ه')
    # Normalize alef maqsura → ya
    result = result.replace('ى', 'ي')
    return result


# Sura names (114 suras)
SURA_NAMES = [
    "", "الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف",
    "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "إبراهيم", "الحجر",
    "النحل", "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون",
    "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم",
    "لقمان", "السجدة", "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص",
    "الزمر", "غافر", "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية",
    "الأحقاف", "محمد", "الفتح", "الحجرات", "ق", "الذاريات", "الطور",
    "النجم", "القمر", "الرحمن", "الواقعة", "الحديد", "المجادلة", "الحشر",
    "الممتحنة", "الصف", "الجمعة", "المنافقون", "التغابن", "الطلاق", "التحريم",
    "الملك", "القلم", "الحاقة", "المعارج", "نوح", "الجن", "المزمل",
    "المدثر", "القيامة", "الإنسان", "المرسلات", "النبأ", "النازعات", "عبس",
    "التكوير", "الانفطار", "المطففين", "الانشقاق", "البروج", "الطارق", "الأعلى",
    "الغاشية", "الفجر", "البلد", "الشمس", "الليل", "الضحى", "الشرح",
    "التين", "العلق", "القدر", "البينة", "الزلزلة", "العاديات", "القارعة",
    "التكاثر", "العصر", "الهمزة", "الفيل", "قريش", "الماعون", "الكوثر",
    "الكافرون", "النصر", "المسد", "الإخلاص", "الفلق", "الناس",
]


def build_db(mushaf_dir, db_path):
    """Scan all mushaf pages and build the frequency database."""

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables
    c.executescript("""
        DROP TABLE IF EXISTS word_occurrence;
        DROP TABLE IF EXISTS word_vocalized;
        DROP TABLE IF EXISTS word_bare;
        DROP TABLE IF EXISTS sura_names;

        CREATE TABLE sura_names (
            sura INTEGER PRIMARY KEY,
            name TEXT
        );

        CREATE TABLE word_bare (
            bare_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bare TEXT UNIQUE NOT NULL,
            count INTEGER DEFAULT 0
        );

        CREATE TABLE word_vocalized (
            voc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bare_id INTEGER NOT NULL,
            vocalized TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            FOREIGN KEY (bare_id) REFERENCES word_bare(bare_id),
            UNIQUE(bare_id, vocalized)
        );

        CREATE TABLE word_occurrence (
            occ_id INTEGER PRIMARY KEY AUTOINCREMENT,
            voc_id INTEGER NOT NULL,
            page INTEGER NOT NULL,
            sura INTEGER NOT NULL,
            ayah INTEGER NOT NULL,
            word_pos INTEGER NOT NULL,
            location TEXT NOT NULL,
            FOREIGN KEY (voc_id) REFERENCES word_vocalized(voc_id)
        );
    """)

    # Insert sura names
    for i, name in enumerate(SURA_NAMES):
        if i > 0:
            c.execute("INSERT INTO sura_names VALUES (?,?)", (i, name))

    # Scan all pages
    files = sorted(glob.glob(os.path.join(mushaf_dir, "page-*.json")))
    if not files:
        print(f"ERROR: No page-*.json files in {mushaf_dir}")
        conn.close()
        return False

    total_words = 0
    bare_cache = {}   # bare → bare_id
    voc_cache = {}    # (bare_id, vocalized) → voc_id

    for fi, fpath in enumerate(files):
        page_num = int(os.path.basename(fpath).split("-")[1].split(".")[0])
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for line in data.get("lines", []):
            for w in line.get("words", []):
                location = w.get("location", "")
                vocalized = strip_trailing_digits(w.get("word", "").strip())
                if not location or not vocalized:
                    continue

                parts = location.split(":")
                if len(parts) != 3:
                    continue
                sura, ayah, wpos = int(parts[0]), int(parts[1]), int(parts[2])

                bare = strip_tashkeel(vocalized)
                if not bare:
                    continue

                # Get or create bare entry
                if bare not in bare_cache:
                    c.execute("INSERT OR IGNORE INTO word_bare (bare) VALUES (?)", (bare,))
                    c.execute("SELECT bare_id FROM word_bare WHERE bare=?", (bare,))
                    bare_cache[bare] = c.fetchone()[0]
                bare_id = bare_cache[bare]

                # Get or create vocalized entry
                vkey = (bare_id, vocalized)
                if vkey not in voc_cache:
                    c.execute("INSERT OR IGNORE INTO word_vocalized (bare_id, vocalized) VALUES (?,?)",
                              (bare_id, vocalized))
                    c.execute("SELECT voc_id FROM word_vocalized WHERE bare_id=? AND vocalized=?",
                              (bare_id, vocalized))
                    voc_cache[vkey] = c.fetchone()[0]
                voc_id = voc_cache[vkey]

                # Insert occurrence
                c.execute("INSERT INTO word_occurrence (voc_id, page, sura, ayah, word_pos, location) VALUES (?,?,?,?,?,?)",
                          (voc_id, page_num, sura, ayah, wpos, location))
                total_words += 1

        if (fi + 1) % 50 == 0 or fi == len(files) - 1:
            print(f"  [{fi+1}/{len(files)}] page {page_num}... ({total_words} words)")

    # Update counts
    print("  Updating counts...")
    c.execute("UPDATE word_vocalized SET count = (SELECT COUNT(*) FROM word_occurrence WHERE word_occurrence.voc_id = word_vocalized.voc_id)")
    c.execute("UPDATE word_bare SET count = (SELECT SUM(wv.count) FROM word_vocalized wv WHERE wv.bare_id = word_bare.bare_id)")

    # Create indexes
    c.execute("CREATE INDEX idx_occ_voc ON word_occurrence(voc_id)")
    c.execute("CREATE INDEX idx_occ_page ON word_occurrence(page)")
    c.execute("CREATE INDEX idx_occ_loc ON word_occurrence(location)")
    c.execute("CREATE INDEX idx_voc_bare ON word_vocalized(bare_id)")
    c.execute("CREATE INDEX idx_bare_text ON word_bare(bare)")

    conn.commit()

    # Stats
    c.execute("SELECT COUNT(*) FROM word_bare")
    n_bare = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM word_vocalized")
    n_voc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM word_occurrence")
    n_occ = c.fetchone()[0]
    c.execute("SELECT bare, count FROM word_bare ORDER BY count DESC LIMIT 10")
    top = c.fetchall()

    conn.close()

    print(f"\n✓ Database: {db_path}")
    print(f"  {n_occ:,} total word occurrences")
    print(f"  {n_bare:,} unique words (without tashkeel)")
    print(f"  {n_voc:,} unique words (with tashkeel)")
    print(f"\n  Top 10 most frequent words:")
    for bare, count in top:
        print(f"    {bare:>15s}  ×{count}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Build Quran word frequency database")
    parser.add_argument("--mushaf-dir", default="./mushaf", help="Directory with page-NNN.json files")
    parser.add_argument("--db", default="word_freq.db", help="Output SQLite database path")
    args = parser.parse_args()

    print(f"📖 Building word frequency database...")
    print(f"   Source: {args.mushaf_dir}")
    if not build_db(args.mushaf_dir, args.db):
        sys.exit(1)


if __name__ == "__main__":
    main()
