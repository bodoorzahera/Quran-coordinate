from django.core.management.base import BaseCommand
from django.db import transaction
from mushaf.models import *
import json
import os

class Command(BaseCommand):
    help = 'تحميل البيانات التجريبية للمصحف'

    def handle(self, *args, **options):
        self.stdout.write('بدء تحميل البيانات التجريبية...')
        
        try:
            with transaction.atomic():
                # تحميل الأصول
                self.load_osol_data()
                
                # إنشاء صفحة تجريبية
                self.create_sample_page()
                
            self.stdout.write(
                self.style.SUCCESS('تم تحميل البيانات التجريبية بنجاح!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'خطأ في تحميل البيانات: {e}')
            )

    def load_osol_data(self):
        """تحميل بيانات الأصول"""
        osol_path = 'data/osol.json'
        
        if not os.path.exists(osol_path):
            self.stdout.write(
                self.style.WARNING(f'ملف الأصول غير موجود: {osol_path}')
            )
            return
            
        with open(osol_path, 'r', encoding='utf-8') as f:
            osol_data = json.load(f)
            
        for origin_data in osol_data.get('qiraat_origins', []):
            origin, created = OsolOrigin.objects.update_or_create(
                origin_id=origin_data['id'],
                defaults={
                    'name': origin_data['name'],
                    'arabic_name': origin_data['arabicName'],
                    'description': origin_data['description'],
                    'readers': origin_data['readers']
                }
            )
            
            if created:
                self.stdout.write(f'تم إنشاء أصل جديد: {origin.arabic_name}')
            
            for case_data in origin_data.get('cases', []):
                case, created = OsolCase.objects.update_or_create(
                    case_id=case_data['caseId'],
                    defaults={
                        'origin': origin,
                        'name': case_data['name'],
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
                    self.stdout.write(f'تم إنشاء حالة جديدة: {case.name}')

    def create_sample_page(self):
        """إنشاء صفحة تجريبية"""
        # إنشاء الصفحة الأولى
        page, created = MushafPage.objects.update_or_create(
            page_number=1,
            defaults={
                'image_path': 'images/page001.png',
                'json_data': {},
                'lines_count': 7
            }
        )
        
        if created:
            self.stdout.write('تم إنشاء الصفحة الأولى')
        
        # حذف السطور القديمة
        page.lines.all().delete()
        
        # إنشاء سطور تجريبية
        lines_data = [
            {
                'line_number': 1,
                'line_type': 'surah-header',
                'text': 'سُورَةُ ٱلْفَاتِحَةِ',
                'verse_range': '',
                'words': []
            },
            {
                'line_number': 2,
                'line_type': 'text',
                'text': 'بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ ١',
                'verse_range': '1:1-1:1',
                'words': [
                    {'location': '1:1:1', 'word': 'بِسْمِ', 'x': 100, 'y': 80},
                    {'location': '1:1:2', 'word': 'ٱللَّهِ', 'x': 200, 'y': 80},
                    {'location': '1:1:3', 'word': 'ٱلرَّحْمَـٰنِ', 'x': 300, 'y': 80},
                    {'location': '1:1:4', 'word': 'ٱلرَّحِيمِ', 'x': 450, 'y': 80},
                ]
            },
            {
                'line_number': 3,
                'line_type': 'text',
                'text': 'ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ ٢',
                'verse_range': '1:2-1:2',
                'words': [
                    {'location': '1:2:1', 'word': 'ٱلْحَمْدُ', 'x': 100, 'y': 120},
                    {'location': '1:2:2', 'word': 'لِلَّهِ', 'x': 200, 'y': 120},
                    {'location': '1:2:3', 'word': 'رَبِّ', 'x': 280, 'y': 120},
                    {'location': '1:2:4', 'word': 'ٱلْعَـٰلَمِينَ', 'x': 350, 'y': 120},
                ]
            }
        ]
        
        for line_data in lines_data:
            line = PageLine.objects.create(
                page=page,
                line_number=line_data['line_number'],
                line_type=line_data['line_type'],
                text=line_data['text'],
                verse_range=line_data['verse_range']
            )
            
            for word_order, word_data in enumerate(line_data['words']):
                Word.objects.create(
                    line=line,
                    location=word_data['location'],
                    word_text=word_data['word'],
                    x_position=word_data['x'],
                    y_position=word_data['y'],
                    width=80,
                    height=30,
                    font_size=24,
                    color='#000000',
                    order=word_order
                )
        
        self.stdout.write('تم إنشاء البيانات التجريبية للصفحة الأولى')
