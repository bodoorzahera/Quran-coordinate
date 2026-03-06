from pathlib import Path

# مجلد الصور
images_dir = Path("images/page00")  # عدّل لو عندك مجلد مختلف

# عدد الصفحات اللي عايز تتحقق منها
total_pages = 604

existing_pages = []
missing_pages = []

for i in range(1, total_pages + 1):
    filename = f"page{i:03d}.png"
    file_path = images_dir / filename
    if file_path.exists():
        existing_pages.append(i)
    else:
        missing_pages.append(i)

print("✅ الصفحات الموجودة:", existing_pages)
print("⚠️ الصفحات المفقودة:", missing_pages)
print(f"إجمالي موجود: {len(existing_pages)}, إجمالي مفقود: {len(missing_pages)}")
