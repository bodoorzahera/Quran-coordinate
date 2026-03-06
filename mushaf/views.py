from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.core.paginator import Paginator
import json
import os
import re
from .models import *
from .forms import *

def index(request):
    """الصفحة الرئيسية"""
    return redirect('page_view', page_num=1)

def page_view(request, page_num):
    """عرض صفحة معينة من المصحف"""
    page = get_object_or_404(MushafPage, page_number=page_num)
    lines = page.lines.prefetch_related('words', 'words__farsh_variants', 
                                       'words__character_colors',
                                       'words__osol_origins', 'words__osol_cases')
    
    # جلب الأصول
    all_origins = OsolOrigin.objects.prefetch_related('cases').all()
    
    context = {
        'page': page,
        'lines': lines,
        'all_origins': all_origins,
        'is_odd': page.is_odd,
        'prev_page': page_num - 1 if page_num > 1 else None,
        'next_page': page_num + 1 if page_num < 604 else None,
    }
    return render(request, 'mushaf/page_view.html', context)

def load_json_data(request):
    """تحميل بيانات JSON من الملفات"""
    if request.method == 'POST':
        try:
            # تحميل osol.json
            osol_path = os.path.join('data', 'osol.json')
            if os.path.exists(osol_path):
                with open(osol_path, 'r', encoding='utf-8') as f:
                    osol_data = json.load(f)
                    
                # حفظ الأصول
                for origin_data in osol_data.get('qiraat_origins', []):
                    origin, created = OsolOrigin.objects.update_or_create(
                        origin_id=origin_data['id'],
                        defaults={
                            'name': origin_data['name'],
                            'arabic_name': origin_data['arabicName'],
                            'description': origin_data['description'],
                            'readers': origin_data.get('readers', [])
                        }
                    )
                    
                    # حفظ الحالات
                    for case_data in origin_data.get('cases', []):
                        OsolCase.objects.update_or_create(
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
            
            # تحميل صفحات المصحف
            mushaf_dir = 'mushaf'
            loaded_count = 0
            
            for i in range(1, 605):
                page_file = f'page{i:03d}.json'
                page_path = os.path.join(mushaf_dir, page_file)
                
                if os.path.exists(page_path):
                    with open(page_path, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                    
                    # إنشاء أو تحديث الصفحة
                    page, created = MushafPage.objects.update_or_create(
                        page_number=i,
                        defaults={
                            'image_path': f'images/page{i:03d}.png',
                            'json_data': page_data,
                            'lines_count': len(page_data.get('lines', []))
                        }
                    )
                    
                    # حفظ السطور والكلمات
                    for line_data in page_data.get('lines', []):
                        line, _ = PageLine.objects.update_or_create(
                            page=page,
                            line_number=line_data['line'],
                            defaults={
                                'line_type': line_data['type'],
                                'text': line_data.get('text', ''),
                                'verse_range': line_data.get('verseRange', '')
                            }
                        )
                        
                        # حفظ الكلمات
                        for idx, word_data in enumerate(line_data.get('words', [])):
                            word, _ = Word.objects.update_or_create(
                                line=line,
                                location=word_data['location'],
                                defaults={
                                    'word_text': word_data['word'],
                                    'qpc_v2': word_data.get('qpcV2', ''),
                                    'qpc_v1': word_data.get('qpcV1', ''),
                                    'order': idx
                                }
                            )
                            
                            # ربط الأصول إذا وجدت
                            if 'osol' in word_data:
                                for osol_id in word_data['osol']:
                                    try:
                                        origin = OsolOrigin.objects.get(origin_id=osol_id)
                                        word.osol_origins.add(origin)
                                    except OsolOrigin.DoesNotExist:
                                        pass
                    
                    loaded_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'تم تحميل {loaded_count} صفحة بنجاح',
                'origins_count': OsolOrigin.objects.count(),
                'cases_count': OsolCase.objects.count()
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'mushaf/load_data.html')

@csrf_exempt
def word_add(request):
    """إضافة كلمة جديدة"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            line = get_object_or_404(PageLine, id=data['line_id'])
            
            word = Word.objects.create(
                line=line,
                location=data['location'],
                word_text=data['word_text'],
                location_type=data.get('location_type', 'page'),
                x_position=data.get('x', 0),
                y_position=data.get('y', 0),
                width=data.get('width', 100),
                height=data.get('height', 30),
                font_size=data.get('font_size', 24),
                color=data.get('color', '#000000'),
                opacity=data.get('opacity', 1.0),
                order=data.get('order', 0)
            )
            
            # إضافة الأصول
            if 'osol_origins' in data:
                origins = OsolOrigin.objects.filter(origin_id__in=data['osol_origins'])
                word.osol_origins.set(origins)
            
            return JsonResponse({
                'success': True,
                'word_id': word.id,
                'message': 'تمت إضافة الكلمة بنجاح'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def word_update(request, word_id):
    """تعديل كلمة موجودة"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # البحث عن الكلمة باستخدام location كـ string
            word = Word.objects.filter(location=word_id).first()
            
            if not word:
                # محاولة البحث بـ ID رقمي
                try:
                    word = Word.objects.get(id=int(word_id))
                except (ValueError, Word.DoesNotExist):
                    return JsonResponse({
                        'success': False, 
                        'error': f'الكلمة غير موجودة: {word_id}'
                    })
            
            # تحديث الحقول
            for field in ['word_text', 'x_position', 'y_position', 'width', 'height',
                         'font_size', 'color', 'opacity', 'location_type']:
                if field in data:
                    setattr(word, field, data[field])
            
            word.save()
            
            # تحديث الأصول
            if 'osol_origins' in data:
                origins = OsolOrigin.objects.filter(origin_id__in=data['osol_origins'])
                word.osol_origins.set(origins)
            
            if 'osol_cases' in data:
                cases = OsolCase.objects.filter(case_id__in=data['osol_cases'])
                word.osol_cases.set(cases)
            
            # تحديث ألوان الحروف
            if 'character_colors' in data:
                CharacterColor.objects.filter(word=word).delete()
                for idx, color in data['character_colors'].items():
                    CharacterColor.objects.create(
                        word=word,
                        character_index=int(idx),
                        color=color
                    )
            
            return JsonResponse({'success': True, 'message': 'تم تحديث الكلمة بنجاح'})
        except json.JSONDecodeError as e:
            return JsonResponse({'success': False, 'error': f'JSON غير صحيح: {str(e)}'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def word_delete(request, word_id):
    """حذف كلمة"""
    if request.method == 'POST':
        try:
            # البحث عن الكلمة باستخدام location
            word = Word.objects.filter(location=word_id).first()
            
            if not word:
                # محاولة البحث بـ ID رقمي
                try:
                    word = Word.objects.get(id=int(word_id))
                except (ValueError, Word.DoesNotExist):
                    return JsonResponse({
                        'success': False, 
                        'error': f'الكلمة غير موجودة: {word_id}'
                    })
            
            word.delete()
            return JsonResponse({'success': True, 'message': 'تم حذف الكلمة بنجاح'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

from django.core.cache import cache

def search_words(request):
    """البحث المتقدم في الكلمات - محسّن للأداء مع cache"""
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'no_tashkeel')
    pattern = request.GET.get('pattern', '').strip()
    osol_origin = request.GET.get('osol_origin', '').strip()
    osol_case = request.GET.get('osol_case', '').strip()
    
    # البداية من مجموعة فارغة
    words = Word.objects.none()
    total_results = 0
    
    # البحث النصي - محسّن مع cache
    if query:
        if search_type == 'no_tashkeel':
            # محاولة استخدام الفهرس من cache
            words_index = cache.get('words_no_tashkeel_index')
            
            if words_index:
                # استخدام الفهرس السريع
                query_clean = remove_tashkeel(query)
                matching_ids = []
                
                # البحث في الفهرس
                for word_text, ids in words_index.items():
                    if query_clean in word_text:
                        matching_ids.extend(ids)
                
                words = Word.objects.filter(id__in=matching_ids)
            else:
                # fallback للطريقة العادية
                words = Word.objects.filter(word_text__icontains=query)
        else:
            # البحث بالتشكيل
            words = Word.objects.filter(word_text__icontains=query)
    
    # البحث بالنمط - محسّن بحد أقصى
    elif pattern:
        try:
            # تنظيف النمط - إزالة / و /g
            clean_pattern = pattern.strip()
            
            # إزالة العلامات الشائعة
            if clean_pattern.startswith('/'):
                clean_pattern = clean_pattern[1:]
            if clean_pattern.endswith('/g'):
                clean_pattern = clean_pattern[:-2]
            elif clean_pattern.endswith('/'):
                clean_pattern = clean_pattern[:-1]
            
            # إزالة backslashes الزائدة من JavaScript
            # مثل: ه\\s+[أ-ي] يصبح ه\s+[أ-ي]
            clean_pattern = clean_pattern.replace('\\\\', '\\')
            
            print(f"Pattern after cleaning: {clean_pattern}")
            
            # محاولة استخدام cache
            cache_key = f'pattern_search_{clean_pattern}'
            cached_results = cache.get(cache_key)
            
            if cached_results:
                words = Word.objects.filter(id__in=cached_results)
            else:
                # حد أقصى للكلمات المفحوصة
                MAX_WORDS_TO_CHECK = 10000
                
                matching_words = []
                sample_words = Word.objects.all()[:MAX_WORDS_TO_CHECK]
                
                # تجربة compile مرة واحدة
                try:
                    compiled_pattern = re.compile(clean_pattern, re.UNICODE)
                except re.error as e:
                    print(f"Regex compile error: {e}")
                    words = Word.objects.none()
                    return render(request, 'mushaf/search.html', {
                        'words': Word.objects.none(),
                        'query': query,
                        'search_type': search_type,
                        'pattern': pattern,
                        'osol_origin': osol_origin,
                        'osol_case': osol_case,
                        'all_origins': OsolOrigin.objects.all(),
                        'all_cases': OsolCase.objects.all(),
                        'total_results': 0,
                        'is_limited': False,
                        'error': f'نمط غير صحيح: {e}'
                    })
                
                for word in sample_words:
                    try:
                        if compiled_pattern.search(word.word_text):
                            matching_words.append(word.id)
                            if len(matching_words) >= 500:
                                break
                    except Exception as e:
                        print(f"Search error: {e}")
                        break
                
                print(f"Found {len(matching_words)} matches")
                
                # حفظ في cache لمدة 5 دقائق
                cache.set(cache_key, matching_words, timeout=300)
                words = Word.objects.filter(id__in=matching_words)
            
        except Exception as e:
            print(f"Pattern search error: {e}")
            words = Word.objects.none()
    
    # البحث في الأصول
    elif osol_origin:
        try:
            origin_id = int(osol_origin)
            words = Word.objects.filter(osol_origins__origin_id=origin_id)
        except ValueError:
            pass
    
    elif osol_case:
        words = Word.objects.filter(osol_cases__case_id=osol_case)
    
    # إزالة التكرار
    words = words.distinct()
    
    # عد النتائج
    total_results = words.count()
    
    # حد أقصى للنتائج المعروضة
    is_limited = False
    if total_results > 1000:
        words = words[:1000]
        is_limited = True
    
    # ترتيب النتائج - استخدام select_related لتحسين الأداء
    words = words.select_related('line__page').prefetch_related(
        'osol_origins', 'osol_cases'
    ).order_by('line__page__page_number', 'line__line_number', 'order')
    
    # التقسيم إلى صفحات
    paginator = Paginator(words, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'words': page_obj,
        'query': query,
        'search_type': search_type,
        'pattern': pattern,
        'osol_origin': osol_origin,
        'osol_case': osol_case,
        'all_origins': OsolOrigin.objects.all(),
        'all_cases': OsolCase.objects.all(),
        'total_results': min(total_results, 1000) if is_limited else total_results,
        'is_limited': is_limited
    }
    
    return render(request, 'mushaf/search.html', context)

@csrf_exempt
def apply_to_multiple(request):
    """تعميم خصائص على كلمات متعددة"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            source_word_location = data.get('source_word_location') or data.get('source_word_id')
            target_word_locations = data.get('target_word_locations') or data.get('target_word_ids', [])
            properties = data.get('properties', [])
            
            # البحث عن الكلمة المصدر
            source_word = Word.objects.filter(location=source_word_location).first()
            if not source_word:
                try:
                    source_word = Word.objects.get(id=int(source_word_location))
                except (ValueError, Word.DoesNotExist):
                    return JsonResponse({
                        'success': False, 
                        'error': f'الكلمة المصدر غير موجودة: {source_word_location}'
                    })
            
            # البحث عن الكلمات المستهدفة
            target_words = []
            for loc in target_word_locations:
                word = Word.objects.filter(location=loc).first()
                if not word:
                    try:
                        word = Word.objects.get(id=int(loc))
                    except (ValueError, Word.DoesNotExist):
                        continue
                if word and word.id != source_word.id:
                    target_words.append(word)
            
            if not target_words:
                return JsonResponse({
                    'success': False,
                    'error': 'لم يتم العثور على كلمات مستهدفة صالحة'
                })
            
            updated_count = 0
            for word in target_words:
                for prop in properties:
                    if hasattr(source_word, prop):
                        setattr(word, prop, getattr(source_word, prop))
                word.save()
                updated_count += 1
            
            return JsonResponse({
                'success': True,
                'message': f'تم تطبيق الخصائص على {updated_count} كلمة'
            })
        except json.JSONDecodeError as e:
            return JsonResponse({'success': False, 'error': f'JSON غير صحيح: {str(e)}'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def export_page(request, page_num):
    """تصدير الصفحة كصورة"""
    page = get_object_or_404(MushafPage, page_number=page_num)
    # يتم التنفيذ عبر JavaScript في الواجهة الأمامية
    return JsonResponse({
        'success': True,
        'page_number': page_num,
        'image_path': page.image_path
    })

def osol_details(request, origin_id):
    """عرض تفاصيل أصل معين"""
    origin = get_object_or_404(OsolOrigin, origin_id=origin_id)
    cases = origin.cases.all()
    related_words = Word.objects.filter(osol_origins=origin).select_related(
        'line__page'
    )[:100]
    
    context = {
        'origin': origin,
        'cases': cases,
        'related_words': related_words,
        'related_count': Word.objects.filter(osol_origins=origin).count()
    }
    
    return render(request, 'mushaf/osol_details.html', context)

def remove_tashkeel(text):
    """إزالة التشكيل والهمزات من النص للبحث"""
    if not text:
        return ''
    
    # التشكيل
    tashkeel = ['ً', 'ٌ', 'ٍ', 'َ', 'ُ', 'ِ', 'ّ', 'ْ', 'ـ', 'ٰ', 'ٓ', 'ٔ', 'ٕ', 'ٖ', 'ٗ', '٘', 'ٙ', 'ٚ', 'ٛ', '٠', '٪']
    for t in tashkeel:
        text = text.replace(t, '')
    
    # توحيد الألف
    text = text.replace('أ', 'ا')
    text = text.replace('إ', 'ا')
    text = text.replace('آ', 'ا')
    text = text.replace('ٱ', 'ا')
    
    # توحيد الهاء
    text = text.replace('ة', 'ه')
    
    # توحيد الياء
    text = text.replace('ى', 'ي')
    text = text.replace('ئ', 'ي')
    
    # توحيد الواو
    text = text.replace('ؤ', 'و')
    
    return text

@csrf_exempt
def save_page_data(request, page_num):
    """حفظ بيانات الصفحة في JSON"""
    if request.method == 'POST':
        try:
            page = get_object_or_404(MushafPage, page_number=page_num)
            lines = page.lines.prefetch_related('words__osol_origins', 'words__osol_cases')
            
            # بناء البيانات
            page_data = {
                'page': page_num,
                'lines': []
            }
            
            for line in lines:
                line_data = {
                    'line': line.line_number,
                    'type': line.line_type,
                    'text': line.text,
                    'verseRange': line.verse_range,
                    'words': [],
                    'osol': [o.origin_id for o in line.osol_origins.all()]
                }
                
                for word in line.words.all():
                    word_data = {
                        'location': word.location,
                        'word': word.word_text,
                        'qpcV2': word.qpc_v2,
                        'qpcV1': word.qpc_v1,
                        'position': {
                            'x': word.x_position,
                            'y': word.y_position,
                            'width': word.width,
                            'height': word.height
                        },
                        'style': {
                            'fontSize': word.font_size,
                            'color': word.color,
                            'opacity': word.opacity
                        },
                        'osol': [o.origin_id for o in word.osol_origins.all()]
                    }
                    line_data['words'].append(word_data)
                
                page_data['lines'].append(line_data)
            
            # حفظ في الملف
            output_path = f'mushaf/page{page_num:03d}.json'
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)
            
            return JsonResponse({'success': True, 'message': 'تم حفظ البيانات بنجاح'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
