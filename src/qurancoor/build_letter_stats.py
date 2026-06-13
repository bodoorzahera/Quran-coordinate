#!/usr/bin/env python3
"""
Quran Letter Statistics Builder
================================
Counts every Arabic letter per surah and saves to JSON.

USAGE:
  python3 build_letter_stats.py --mushaf-dir ./mushaf --output letter_stats.json
"""

import json, os, sys, glob, re, unicodedata, argparse

# 28 standard Arabic letters + hamza
ARABIC_LETTERS = list("ءابتثجحخدذرزسشصضطظعغفقكلمنهوي")

# Normalize variants to base letters
LETTER_MAP = {
    'آ': 'ا', 'أ': 'ا', 'إ': 'ا', 'ٱ': 'ا',  # alef variants → alef
    'ؤ': 'ء',  # waw+hamza → hamza
    'ئ': 'ء',  # yeh+hamza → hamza
    'ة': 'ة',  # teh marbuta kept separate
    'ى': 'ي',  # alef maqsura → yeh
}

# Add teh marbuta to our letter list
ALL_LETTERS = list("ءابةتثجحخدذرزسشصضطظعغفقكلمنهوي")

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

# Strip trailing ayah numbers
_TRAILING_NUMS = re.compile(r'[\s\d\u0660-\u0669\u06F0-\u06F9]+$')


def clean_word(w):
    """Remove trailing digits and diacritics, return only base letters."""
    w = _TRAILING_NUMS.sub('', w)
    return w


def count_letters(word):
    """Count Arabic letters in a word, normalizing variants."""
    counts = {}
    for ch in word:
        # Skip diacritics (combining marks), tatweel, small waw/yeh, annotation marks
        cat = unicodedata.category(ch)
        if cat.startswith('M'):
            continue
        if ch == '\u0640':  # tatweel
            continue
        if ch in ('\u06E5', '\u06E6'):  # small waw/yeh (not counted as letters)
            continue
        if '\u06D6' <= ch <= '\u06ED':  # Quranic annotation marks
            continue

        # Normalize
        ch = LETTER_MAP.get(ch, ch)

        if ch in ALL_LETTERS:
            counts[ch] = counts.get(ch, 0) + 1
    return counts


def build_stats(mushaf_dir):
    """Scan all mushaf pages and count letters per surah."""
    # sura_num -> {letter: count}
    sura_counts = {}

    files = sorted(glob.glob(os.path.join(mushaf_dir, "page-*.json")))
    if not files:
        print(f"ERROR: No page-*.json files in {mushaf_dir}")
        return None

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for line in data.get("lines", []):
            if line.get("type") != "text":
                continue
            for w in line.get("words", []):
                loc = w.get("location", "")
                raw = w.get("word", "")
                if not loc:
                    continue
                parts = loc.split(":")
                if len(parts) < 3:
                    continue
                sura = int(parts[0])
                word = clean_word(raw)
                letter_counts = count_letters(word)

                if sura not in sura_counts:
                    sura_counts[sura] = {}
                for letter, cnt in letter_counts.items():
                    sura_counts[sura][letter] = sura_counts[sura].get(letter, 0) + cnt

    # Build result
    result = {
        "letters": ALL_LETTERS,
        "suras": []
    }

    # Total across all suras
    total_counts = {}

    for sura_num in range(1, 115):
        counts = sura_counts.get(sura_num, {})
        sura_total = sum(counts.values())
        letter_list = {l: counts.get(l, 0) for l in ALL_LETTERS}

        for l, c in letter_list.items():
            total_counts[l] = total_counts.get(l, 0) + c

        result["suras"].append({
            "number": sura_num,
            "name": SURA_NAMES[sura_num] if sura_num < len(SURA_NAMES) else "",
            "total_letters": sura_total,
            "counts": letter_list,
        })

    result["total"] = {l: total_counts.get(l, 0) for l in ALL_LETTERS}
    result["grand_total"] = sum(total_counts.values())

    return result


def main():
    parser = argparse.ArgumentParser(description="Build Quran letter statistics")
    parser.add_argument("--mushaf-dir", default="./mushaf")
    parser.add_argument("--output", default="letter_stats.json")
    args = parser.parse_args()

    print("Building letter statistics...")
    stats = build_stats(args.mushaf_dir)
    if not stats:
        sys.exit(1)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"Saved to {args.output}")
    print(f"  {stats['grand_total']:,} total letters across 114 suras")
    print(f"\n  Top 10 letters:")
    sorted_total = sorted(stats['total'].items(), key=lambda x: -x[1])
    for letter, count in sorted_total[:10]:
        print(f"    {letter}  ×{count:,}")


if __name__ == "__main__":
    main()
