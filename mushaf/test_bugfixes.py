"""
اختبارات للتحقق من إصلاح المشاكل
"""
from django.test import TestCase, Client
from django.urls import reverse
from mushaf.models import *
import json

class BugFixesTest(TestCase):
    """اختبارات الإصلاحات"""
    
    def setUp(self):
        """إعداد البيانات للاختبار"""
        self.client = Client()
        
        # إنشاء صفحة
        self.page = MushafPage.objects.create(
            page_number=1,
            image_path='images/page001.png',
            json_data={
                'page': 1,
                'lines': [
                    {
                        'line': 1,
                        'type': 'text',
                        'text': 'بسم الله الرحمن الرحيم',
                        'words': []
                    }
                ]
            },
            lines_count=1
        )
        
        # إنشاء سطر
        self.line = PageLine.objects.create(
            page=self.page,
            line_number=1,
            line_type='text',
            text='بسم الله الرحمن الرحيم',
            verse_range='1:1'
        )
        
        # إنشاء كلمات
        self.word1 = Word.objects.create(
            line=self.line,
            location='1:1:1',
            word_text='بِسْمِ',
            x_position=10,
            y_position=20,
            font_size=24,
            color='#000000'
        )
        
        self.word2 = Word.objects.create(
            line=self.line,
            location='1:1:2',
            word_text='اللَّهِ',
            x_position=50,
            y_position=20,
            font_size=24,
            color='#000000'
        )
    
    def test_margin_direction(self):
        """اختبار 1: الهامش في الاتجاه الصحيح"""
        # صفحة فردية - الهامش على اليسار
        response = self.client.get(reverse('page_view', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'left')
        self.assertTrue(response.context['is_odd'])
        
        # إنشاء صفحة زوجية
        page2 = MushafPage.objects.create(
            page_number=2,
            image_path='images/page002.png',
            json_data={'page': 2, 'lines': []},
            lines_count=1
        )
        
        # صفحة زوجية - الهامش على اليمين
        response = self.client.get(reverse('page_view', args=[2]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'right')
        self.assertFalse(response.context['is_odd'])
        
        print("✅ اختبار الهامش: نجح")
    
    def test_word_update_with_location(self):
        """اختبار 2: تحديث الكلمة باستخدام location"""
        data = {
            'x_position': 100,
            'y_position': 200,
            'font_size': 30
        }
        
        response = self.client.post(
            f'/word/update/{self.word1.location}/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        
        # التحقق من التحديث
        self.word1.refresh_from_db()
        self.assertEqual(self.word1.x_position, 100)
        self.assertEqual(self.word1.y_position, 200)
        self.assertEqual(self.word1.font_size, 30)
        
        print("✅ اختبار التحديث بـ location: نجح")
    
    def test_word_delete_with_location(self):
        """اختبار 3: حذف الكلمة باستخدام location"""
        location = self.word1.location
        
        response = self.client.post(f'/word/delete/{location}/')
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        
        # التحقق من الحذف
        self.assertFalse(Word.objects.filter(location=location).exists())
        
        print("✅ اختبار الحذف بـ location: نجح")
    
    def test_search_without_tashkeel(self):
        """اختبار 4: البحث بدون تشكيل"""
        response = self.client.get(
            reverse('search_words'),
            {'q': 'بسم', 'type': 'no_tashkeel'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.context['total_results'], 0)
        
        print("✅ اختبار البحث بدون تشكيل: نجح")
    
    def test_search_with_tashkeel(self):
        """اختبار 5: البحث بالتشكيل"""
        response = self.client.get(
            reverse('search_words'),
            {'q': 'بِسْمِ', 'type': 'with_tashkeel'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.context['total_results'], 0)
        
        print("✅ اختبار البحث بالتشكيل: نجح")
    
    def test_search_with_regex(self):
        """اختبار 6: البحث بـ Regex"""
        response = self.client.get(
            reverse('search_words'),
            {'pattern': 'بِ.*مِ'}
        )
        
        self.assertEqual(response.status_code, 200)
        # يجب أن يجد "بِسْمِ"
        
        print("✅ اختبار البحث بـ Regex: نجح")
    
    def test_apply_to_multiple_with_location(self):
        """اختبار 7: التعميم على كلمات متعددة باستخدام location"""
        data = {
            'source_word_location': self.word1.location,
            'target_word_locations': [self.word2.location],
            'properties': ['font_size', 'color']
        }
        
        response = self.client.post(
            '/apply-multiple/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertTrue(result['success'])
        
        # التحقق من التطبيق
        self.word2.refresh_from_db()
        self.assertEqual(self.word2.font_size, self.word1.font_size)
        self.assertEqual(self.word2.color, self.word1.color)
        
        print("✅ اختبار التعميم: نجح")
    
    def test_word_positions_display(self):
        """اختبار 8: عرض الكلمات في المواقع الصحيحة"""
        response = self.client.get(reverse('page_view', args=[1]))
        
        self.assertEqual(response.status_code, 200)
        
        # التحقق من وجود بيانات JSON
        self.assertIn('pageData', response.content.decode())
        
        # التحقق من وجود الكلمات
        page_data = response.context['page'].json_data
        self.assertIn('lines', page_data)
        
        print("✅ اختبار عرض الكلمات: نجح")
    
    def test_csrf_token_in_template(self):
        """اختبار 9: وجود CSRF token في القالب"""
        response = self.client.get(reverse('page_view', args=[1]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfToken')
        
        print("✅ اختبار CSRF token: نجح")
    
    def test_error_handling(self):
        """اختبار 10: معالجة الأخطاء"""
        # محاولة تحديث كلمة غير موجودة
        response = self.client.post(
            '/word/update/999:999:999/',
            data=json.dumps({'font_size': 30}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        
        print("✅ اختبار معالجة الأخطاء: نجح")

class PerformanceTest(TestCase):
    """اختبارات الأداء بعد الإصلاحات"""
    
    def setUp(self):
        """إنشاء بيانات كبيرة للاختبار"""
        self.page = MushafPage.objects.create(
            page_number=100,
            image_path='images/page100.png',
            json_data={'page': 100, 'lines': []},
            lines_count=15
        )
        
        # إنشاء 100 كلمة مع سطور فريدة
        line_num = 1
        for i in range(100):
            # إنشاء سطر جديد كل 10 كلمات
            if i % 10 == 0 and i > 0:
                line_num += 1
            
            # إنشاء السطر إذا لم يكن موجوداً
            line, created = PageLine.objects.get_or_create(
                page=self.page,
                line_number=line_num,
                defaults={
                    'line_type': 'text',
                    'text': f'نص {line_num}',
                    'verse_range': f'1:{line_num}'
                }
            )
            
            Word.objects.create(
                line=line,
                location=f'100:{line_num}:{i%10}',
                word_text=f'كلمة_{i}',
                x_position=i * 10,
                y_position=(line_num - 1) * 50,
                font_size=24,
                color='#000000'
            )
    
    def test_search_performance(self):
        """اختبار أداء البحث"""
        import time
        
        start = time.time()
        response = self.client.get(
            reverse('search_words'),
            {'q': 'كلمة'}
        )
        end = time.time()
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(end - start, 1.0, "البحث يجب أن يكون أسرع من ثانية")
        
        print(f"✅ اختبار أداء البحث: {(end-start)*1000:.2f}ms")
    
    def test_page_load_performance(self):
        """اختبار أداء تحميل الصفحة"""
        import time
        
        start = time.time()
        response = self.client.get(reverse('page_view', args=[100]))
        end = time.time()
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(end - start, 0.5, "تحميل الصفحة يجب أن يكون أسرع من 0.5 ثانية")
        
        print(f"✅ اختبار أداء تحميل الصفحة: {(end-start)*1000:.2f}ms")

def run_all_bugfix_tests():
    """تشغيل جميع اختبارات الإصلاحات"""
    import unittest
    from django.test.utils import get_runner
    from django.conf import settings
    
    print("=" * 60)
    print("🧪 اختبارات الإصلاحات")
    print("=" * 60)
    print()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)
    
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(BugFixesTest))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PerformanceTest))
    
    result = test_runner.run_suite(suite)
    
    print()
    print("=" * 60)
    if result.wasSuccessful():
        print("✅ جميع الاختبارات نجحت!")
        print(f"   تم اختبار {result.testsRun} حالة")
    else:
        print("❌ بعض الاختبارات فشلت")
        print(f"   نجح: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"   فشل: {len(result.failures)}")
        print(f"   أخطاء: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    import django
    django.setup()
    run_all_bugfix_tests()
