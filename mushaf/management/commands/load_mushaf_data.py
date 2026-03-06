"""
Django management command لتحميل بيانات المصحف والأصول من ملفات JSON
الاستخدام: python manage.py load_mushaf_data
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from mushaf.models import *
import json
import os
from pathlib import Path

class Command(BaseCommand):
    help = 'تحميل بيانات المصحف والأصول القرائية من ملفات JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--osol-only',
            action='store_true',
            help='تحميل الأصول فقط بدون صفحات المصحف',
        )
        parser.add_argument(
            '--pages-only',
            action='store_true',
            help='تحميل صفحات المصحف فقط بدون الأصول',
        )
        parser.add_argument(
            '--start-page',
            type=int,
            default=1,
            help='رقم الصفحة الأولى للتحميل (افتراضي: 1)',
        )
        parser.add_argument(
            '--end-page',
            type=int,
            default=604,
            help='رقم الصفحة الأخيرة للتحميل (افتراضي: 604)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('بدء تحميل البيانات...'))
        
        # تحميل الأصول
        if not options['pages_only']:
            self.load_osol_data()
        
        # تحميل صفحات المصحف
        if not options['osol_only']:
            start_page = options['start_page']
            end_page = options['end_page']
            self.load_mushaf_pages(start_page, end_page)
        
        self.stdout.write(self.style.SUCCESS('✓ اكتمل تحميل البيانات بنجاح!'))

    def load_osol_data(self):
        """تحميل بيانات الأصول من osol.json"""
        self.stdout.write('جاري تحميل الأصول القرائية...')
        
        osol_path = Path(settings.DATA_DIR) / 'osol.json'
        
        if not osol_path.exists():
            self.stdout.write(
                self.style.WARNING(f'⚠ ملف الأصول غير موجود: {osol_path}')
            )
            return
        
        try:
            with open(osol_path, 'r', encoding='utf-8') as f:
                osol_data = json.load(f)
            
            origins_count = 0
            cases_count = 0
            
            for origin_data in osol_data.get('qiraat_origins', []):
                origin, created = OsolOrigin.objects.update_or_create(
                    origin_id=origin_data['id'],
                    defaults={
                        'name': origin_data.get('name', ''),
                        'arabic_name': origin_data.get('arabicName', ''),
                        'description': origin_data.get('description', ''),
                        'readers': origin_data.get('readers', [])
                    }
                )
                
                if created:
                    origins_count += 1
                    self.stdout.write(f'  ✓ تم إنشاء أصل جديد: {origin.arabic_name}')
                
                # تحميل الحالات
                for case_data in origin_data.get('cases', []):
                    case, created = OsolCase.objects.update_or_create(
                        case_id=case_data['caseId'],
                        defaults={
                            'origin': origin,
                            'name': case_data.get('name', ''),
                            'condition': case_data.get('condition', ''),
                            'solution': case_data.get('solution', ''),
                            'description': case_data.get('description', ''),
                            'readers': case_data.get('readers', []),
                            'example_data': case_data.get('example', {}),
                            'patterns': case_data.get('patterns', []),
                            'exceptions': case_data.get('exceptions', [])
                        }
                    )
                    
                    if created:
                        cases_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ تم تحميل {origins_count} أصل و {cases_count} حالة'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ خطأ في تحميل الأصول: {str(e)}')
            )

    def load_mushaf_pages(self, start_page, end_page):
        """تحميل صفحات المصحف من ملفات JSON"""
        self.stdout.write(
            f'جاري تحميل صفحات المصحف من {start_page} إلى {end_page}...'
        )
        
        mushaf_dir = Path(settings.MUSHAF_DIR)
        
        if not mushaf_dir.exists():
            self.stdout.write(
                self.style.WARNING(f'⚠ مجلد المصحف غير موجود: {mushaf_dir}')
            )
            return
        
        loaded_count = 0
        error_count = 0
        
        for page_num in range(start_page, end_page + 1):
            try:
                page_file = f'Page{page_num:03d}.json'
                page_path = mushaf_dir / page_file
                
                if not page_path.exists():
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ الصفحة {page_num} غير موجودة')
                    )
                    error_count += 1
                    continue
                
                with open(page_path, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                
                # إنشاء أو تحديث الصفحة
                page, created = MushafPage.objects.update_or_create(
                    page_number=page_num,
                    defaults={
                        'image_path': f'images/page{page_num:03d}.png',
                        'json_data': page_data,
                        'lines_count': len(page_data.get('lines', []))
                    }
                )
                
                # حذف البيانات القديمة للصفحة
                if not created:
                    page.lines.all().delete()
                
                # تحميل السطور والكلمات
                words_count = 0
                for line_data in page_data.get('lines', []):
                    line = PageLine.objects.create(
                        page=page,
                        line_number=line_data['line'],
                        line_type=line_data.get('type', 'text'),
                        text=line_data.get('text', ''),
                        verse_range=line_data.get('verseRange', '')
                    )
                    
                    # ربط أصول السطر
                    if 'osol' in line_data:
                        for osol_id in line_data['osol']:
                            try:
                                origin = OsolOrigin.objects.get(origin_id=osol_id)
                                line.osol_origins.add(origin)
                            except OsolOrigin.DoesNotExist:
                                pass
                    
                    # تحميل الكلمات
                    for idx, word_data in enumerate(line_data.get('words', [])):
                        word = Word.objects.create(
                            line=line,
                            location=word_data.get('location', ''),
                            word_text=word_data.get('word', ''),
                            qpc_v2=word_data.get('qpcV2', ''),
                            qpc_v1=word_data.get('qpcV1', ''),
                            order=idx
                        )
                        
                        # تطبيق الموقع والتنسيق إذا وجد
                        if 'position' in word_data:
                            pos = word_data['position']
                            word.x_position = pos.get('x', 0)
                            word.y_position = pos.get('y', 0)
                            word.width = pos.get('width', 100)
                            word.height = pos.get('height', 30)
                        
                        if 'style' in word_data:
                            style = word_data['style']
                            word.font_size = style.get('fontSize', 24)
                            word.color = style.get('color', '#000000')
                            word.opacity = style.get('opacity', 1.0)
                        
                        word.save()
                        
                        # ربط الأصول
                        if 'osol' in word_data:
                            for osol_id in word_data['osol']:
                                try:
                                    origin = OsolOrigin.objects.get(origin_id=osol_id)
                                    word.osol_origins.add(origin)
                                except OsolOrigin.DoesNotExist:
                                    pass
                        
                        # تحميل الفرش إذا وجد
                        if 'الفرش' in word_data:
                            farsh_data = word_data['الفرش']
                            Farsh.objects.create(
                                word=word,
                                readers=farsh_data.get('readers', []),
                                alerts=farsh_data.get('alerts', []),
                                highlight_coords=farsh_data.get('coords', {})
                            )
                        
                        words_count += 1
                
                loaded_count += 1
                
                if page_num % 10 == 0:
                    self.stdout.write(f'  ✓ تم تحميل {loaded_count} صفحة...')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ خطأ في تحميل الصفحة {page_num}: {str(e)}')
                )
                error_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ تم تحميل {loaded_count} صفحة بنجاح'
            )
        )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠ فشل تحميل {error_count} صفحة')
            )
