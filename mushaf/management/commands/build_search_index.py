"""
Management command لبناء فهرس للبحث السريع
الاستخدام: python manage.py build_search_index
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from mushaf.models import Word
import re

def remove_tashkeel(text):
    """إزالة التشكيل من النص"""
    tashkeel = ['ً', 'ٌ', 'ٍ', 'َ', 'ُ', 'ِ', 'ّ', 'ْ', 'ـ']
    for t in tashkeel:
        text = text.replace(t, '')
    return text

class Command(BaseCommand):
    help = 'بناء فهرس للبحث السريع'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='مسح الفهرس الموجود قبل البناء',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('بدء بناء فهرس البحث...'))
        
        if options['clear']:
            cache.clear()
            self.stdout.write(self.style.WARNING('تم مسح الفهرس القديم'))
        
        # بناء فهرس للكلمات بدون تشكيل
        self.stdout.write('بناء فهرس الكلمات بدون تشكيل...')
        
        words_index = {}
        total_words = Word.objects.count()
        processed = 0
        
        for word in Word.objects.select_related('line__page').iterator(chunk_size=1000):
            # الكلمة بدون تشكيل
            clean_text = remove_tashkeel(word.word_text)
            
            if clean_text not in words_index:
                words_index[clean_text] = []
            
            words_index[clean_text].append(word.id)
            
            processed += 1
            if processed % 5000 == 0:
                self.stdout.write(f'  معالجة {processed}/{total_words} كلمة...')
        
        # حفظ الفهرس في cache
        self.stdout.write('حفظ الفهرس في cache...')
        cache.set('words_no_tashkeel_index', words_index, timeout=None)
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ تم بناء فهرس لـ {len(words_index)} كلمة فريدة من أصل {total_words} كلمة'
        ))
        
        # إحصائيات
        self.stdout.write('\nإحصائيات:')
        self.stdout.write(f'  - إجمالي الكلمات: {total_words}')
        self.stdout.write(f'  - كلمات فريدة (بدون تشكيل): {len(words_index)}')
        
        # أمثلة
        self.stdout.write('\nأمثلة من الفهرس:')
        for word_text, ids in list(words_index.items())[:5]:
            self.stdout.write(f'  - "{word_text}": {len(ids)} مرة')
        
        self.stdout.write(self.style.SUCCESS('\n✅ اكتمل بناء الفهرس!'))
