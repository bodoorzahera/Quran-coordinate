
# mushaf/tests.py
"""
اختبارات تطبيق المصحف الإلكتروني
"""
from django.test import TestCase, Client
from django.urls import reverse
from .models import *
import json

class OsolOriginTestCase(TestCase):
    """اختبارات نموذج الأصول"""
    
    def setUp(self):
        self.origin = OsolOrigin.objects.create(
            origin_id=1,
            name='Test Origin',
            arabic_name='أصل تجريبي',
            description='وصف الأصل التجريبي',
            readers=['قارئ1', 'قارئ2']
        )
    
    def test_origin_creation(self):
        """اختبار إنشاء أصل"""
        self.assertEqual(self.origin.origin_id, 1)
        self.assertEqual(self.origin.arabic_name, 'أصل تجريبي')
        self.assertEqual(len(self.origin.readers), 2)
    
    def test_origin_str(self):
        """اختبار عرض الأصل"""
        self.assertEqual(str(self.origin), '1 - أصل تجريبي')

class OsolCaseTestCase(TestCase):
    """اختبارات نموذج حالات الأصول"""
    
    def setUp(self):
        self.origin = OsolOrigin.objects.create(
            origin_id=1,
            name='Test Origin',
            arabic_name='أصل تجريبي',
            description='وصف',
            readers=['قارئ1']
        )
        
        self.case = OsolCase.objects.create(
            origin=self.origin,
            case_id='1.1',
            name='حالة تجريبية',
            condition='شرط الحالة',
            solution='حل الحالة',
            readers=['قارئ1']
        )
    
    def test_case_creation(self):
        """اختبار إنشاء حالة"""
        self.assertEqual(self.case.case_id, '1.1')
        self.assertEqual(self.case.name, 'حالة تجريبية')
        self.assertEqual(self.case.origin, self.origin)
    
    def test_case_str(self):
        """اختبار عرض الحالة"""
        self.assertEqual(str(self.case), '1.1 - حالة تجريبية')

class MushafPageTestCase(TestCase):
    """اختبارات نموذج الصفحة"""
    
    def setUp(self):
        self.page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={'page': 1, 'lines': []},
            lines_count=15
        )
    
    def test_page_creation(self):
        """اختبار إنشاء صفحة"""
        self.assertEqual(self.page.page_number, 1)
        self.assertEqual(self.page.lines_count, 15)
    
    def test_page_is_odd(self):
        """اختبار تحديد الصفحة الفردية"""
        self.assertTrue(self.page.is_odd)
        
        page2 = MushafPage.objects.create(
            page_number=2,
            image_path='images/page002.png',
            json_data={},
            lines_count=15
        )
        self.assertFalse(page2.is_odd)

class PageLineTestCase(TestCase):
    """اختبارات نموذج السطر"""
    
    def setUp(self):
        self.page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={},
            lines_count=15
        )
        
        self.line = PageLine.objects.create(
            page=self.page,
            line_number=1,
            line_type='text',
            text='بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
            verse_range='1:1'
        )
    
    def test_line_creation(self):
        """اختبار إنشاء سطر"""
        self.assertEqual(self.line.line_number, 1)
        self.assertEqual(self.line.line_type, 'text')
        self.assertEqual(self.line.page, self.page)
    
    def test_line_str(self):
        """اختبار عرض السطر"""
        self.assertEqual(str(self.line), 'صفحة 1 - سطر 1')

class WordTestCase(TestCase):
    """اختبارات نموذج الكلمة"""
    
    def setUp(self):
        self.page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={},
            lines_count=15
        )
        
        self.line = PageLine.objects.create(
            page=self.page,
            line_number=1,
            line_type='text',
            text='بسم الله',
            verse_range='1:1'
        )
        
        self.word = Word.objects.create(
            line=self.line,
            location='1:1:1',
            word_text='بِسْمِ',
            location_type='page',
            x_position=10.0,
            y_position=20.0,
            font_size=24,
            color='#000000',
            order=0
        )
    
    def test_word_creation(self):
        """اختبار إنشاء كلمة"""
        self.assertEqual(self.word.word_text, 'بِسْمِ')
        self.assertEqual(self.word.location, '1:1:1')
        self.assertEqual(self.word.font_size, 24)
    
    def test_word_position(self):
        """اختبار موقع الكلمة"""
        self.assertEqual(self.word.x_position, 10.0)
        self.assertEqual(self.word.y_position, 20.0)
    
    def test_word_str(self):
        """اختبار عرض الكلمة"""
        self.assertEqual(str(self.word), 'بِسْمِ (1:1:1)')

class ViewsTestCase(TestCase):
    """اختبارات العروض"""
    
    def setUp(self):
        self.client = Client()
        
        # إنشاء صفحة تجريبية
        self.page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={'page': 1, 'lines': []},
            lines_count=15
        )
    
    def test_index_redirects(self):
        """اختبار توجيه الصفحة الرئيسية"""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('page_view', args=[1]))
    
    def test_page_view(self):
        """اختبار عرض الصفحة"""
        response = self.client.get(reverse('page_view', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'صفحة 1')
    
    def test_search_view(self):
        """اختبار صفحة البحث"""
        response = self.client.get(reverse('search_words'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'البحث المتقدم')
    
    def test_word_add(self):
        """اختبار إضافة كلمة"""
        line = PageLine.objects.create(
            page=self.page,
            line_number=1,
            line_type='text',
            text='test',
            verse_range='1:1'
        )
        
        data = {
            'line_id': line.id,
            'location': '1:1:1',
            'word_text': 'تجربة',
            'location_type': 'page',
            'x': 0,
            'y': 0,
            'font_size': 24,
            'color': '#000000'
        }
        
        response = self.client.post(
            reverse('word_add'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])

class SearchTestCase(TestCase):
    """اختبارات البحث"""
    
    def setUp(self):
        # إنشاء بيانات تجريبية
        page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={},
            lines_count=1
        )
        
        line = PageLine.objects.create(
            page=page,
            line_number=1,
            line_type='text',
            text='بسم الله الرحمن الرحيم',
            verse_range='1:1'
        )
        
        Word.objects.create(
            line=line,
            location='1:1:1',
            word_text='بِسْمِ',
            order=0
        )
        
        Word.objects.create(
            line=line,
            location='1:1:2',
            word_text='اللَّهِ',
            order=1
        )
    
    def test_search_by_text(self):
        """اختبار البحث بالنص"""
        response = self.client.get(reverse('search_words'), {'q': 'بسم'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'بِسْمِ')
    
    def test_search_no_results(self):
        """اختبار البحث بدون نتائج"""
        response = self.client.get(reverse('search_words'), {'q': 'كلمة_غير_موجودة'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'لم يتم العثور على نتائج')
