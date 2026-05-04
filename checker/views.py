import csv
import io
import requests
import time
import os
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StudentList, Student
from datetime import datetime, timedelta

def index(request):
    return render(request, 'checker/index.html')

def ensure_permanent_list():
    name = "ICT'22 - MBSTU"
    if not StudentList.objects.filter(name=name).exists():
        csv_path = os.path.join(settings.BASE_DIR, 'static', "CP_handle_ICT'22.csv")
        if os.path.exists(csv_path):
            student_list = StudentList.objects.create(name=name)
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                students_to_create = []
                for row in reader:
                    handle = row.get('CF Handle', row.get('handle', '')).strip()
                    # Include all rows as requested
                    students_to_create.append(Student(
                        student_list=student_list,
                        student_id=row.get('ID', '').strip(),
                        name=row.get('Name', 'Unknown').strip(),
                        handle=handle if handle else '—'
                    ))
                Student.objects.bulk_create(students_to_create)

@csrf_exempt
def upload_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        list_name = request.POST.get('name', csv_file.name)
        
        decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
        reader = csv.DictReader(decoded_file)
        
        # Normalize field names
        fieldnames = [f.lower().strip() for f in reader.fieldnames]
        
        # Mapping with prioritization
        id_col = next((f for f in reader.fieldnames if f.lower().strip() in ['id', 'student_id', 'studentid', 'roll']), None)
        name_col = next((f for f in reader.fieldnames if f.lower().strip() == 'name' or 'name' in f.lower()), None)
        handle_col = next((f for f in reader.fieldnames if any(k in f.lower().strip() for k in ['cf_handle', 'handle', 'cf', 'codeforces'])), None)
        
        if not handle_col:
            return JsonResponse({'error': f'No handle column found in CSV. Found: {", ".join(reader.fieldnames)}'}, status=400)
            
        student_list = StudentList.objects.create(name=list_name)
        
        students_to_create = []
        for row in reader:
            handle = row.get(handle_col, '').strip()
            # Include all rows as requested
            students_to_create.append(Student(
                student_list=student_list,
                student_id=row.get(id_col, '').strip() if id_col else '',
                name=row.get(name_col, 'Unknown').strip() if name_col else 'Unknown',
                handle=handle if handle else '—'
            ))
        
        Student.objects.bulk_create(students_to_create)
        
        return JsonResponse({
            'message': f'Successfully uploaded {len(students_to_create)} students',
            'list_id': student_list.id,
            'list_name': student_list.name
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_student_lists(request):
    ensure_permanent_list()
    lists = StudentList.objects.all().order_by('-created_at')
    data = [{'id': l.id, 'name': l.name, 'created_at': l.created_at} for l in lists]
    return JsonResponse({'lists': data})

@csrf_exempt
def clear_lists(request):
    if request.method == 'POST':
        # Explicitly delete all to trigger cascades if needed, though CASCADE is set
        Student.objects.all().delete()
        StudentList.objects.all().delete()
        return JsonResponse({'message': 'All saved lists cleared successfully'})
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_students(request, list_id):
    try:
        student_list = StudentList.objects.get(id=list_id)
        students = student_list.students.all()
        data = [{
            'id': s.student_id,
            'name': s.name,
            'handle': s.handle
        } for s in students]
        return JsonResponse({'name': student_list.name, 'students': data})
    except StudentList.DoesNotExist:
        return JsonResponse({'error': 'List not found'}, status=404)

import concurrent.futures

@csrf_exempt
def check_solves(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    import json
    try:
        data = json.loads(request.body)
        handles = data.get('handles', [])
        days = int(data.get('days', 1))
        
        now = datetime.now()
        start_ts = int((now - timedelta(days=days)).timestamp())
        end_ts = int(now.timestamp())
        
        results = {}
        ratings = {}
        errors = {}
        
        # 1. Fetch Ratings (Batch-only for large lists to save time)
        def fetch_ratings_batch(h_list):
            valid_h = [h for h in h_list if h and h not in ['—', '0', '', 'blank']]
            if not valid_h: return
            
            try:
                # Use a shorter timeout for ratings to move on quickly if CF is slow
                url = f"https://codeforces.com/api/user.info?handles={';'.join(valid_h)}"
                res = requests.get(url, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    if data['status'] == 'OK':
                        for user_info in data['result']:
                            ratings[user_info['handle'].lower()] = user_info.get('maxRating', 0)
                        return True
                return False
            except:
                return False

        # Try batching. If it fails, only do individual fallback if list is small (< 10)
        # otherwise we'll definitely hit the 30s timeout.
        batch_size = 50
        for i in range(0, len(handles), batch_size):
            batch = handles[i:i+batch_size]
            if not fetch_ratings_batch(batch):
                if len(batch) < 10:
                    for h in batch:
                        if h and h not in ['—', '0', '', 'blank']:
                            fetch_ratings_batch([h])
                else:
                    print(f" [!] Rating batch {i//batch_size + 1} failed. Skipping fallback to save time.")

        # 2. Fetch Solves (Using Threads with rate limiting)
        def fetch_user_solves(handle):
            if not handle or handle in ['—', '0', '', 'blank']:
                return None, None
            
            h_lower = handle.lower()
            import random
            time.sleep(random.uniform(0.1, 0.5))

            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    url = f"https://codeforces.com/api/user.status?handle={handle}"
                    resp = requests.get(url, timeout=5)
                    
                    if resp.status_code == 429:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    
                    if resp.status_code != 200:
                        return handle, f"Error {resp.status_code}"
                    
                    data = resp.json()
                    if data['status'] != 'OK':
                        return handle, data.get('comment', 'CF Error')
                    
                    unique_problems = set()
                    for sub in data.get('result', []):
                        if sub['verdict'] == 'OK':
                            if start_ts <= sub['creationTimeSeconds'] <= end_ts:
                                p = sub['problem']
                                unique_problems.add(f"{p.get('contestId')}-{p.get('index')}")
                    
                    return h_lower, len(unique_problems)
                except Exception as e:
                    if attempt == max_retries:
                        return handle, "Timeout"
                    time.sleep(1)
            return handle, "Rate Limited"

        total_handles = len(handles)
        print(f"--- Parallel check started: {total_handles} handles ---")
        max_workers = 3 
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_handle = {executor.submit(fetch_user_solves, h): h for h in handles}
            
            view_start_time = time.time()
            completed_count = 0
            
            for future in concurrent.futures.as_completed(future_to_handle):
                completed_count += 1
                current_handle = future_to_handle[future]
                
                if time.time() - view_start_time > 80:
                    print(f"!!! SAFEGUARD: Returning partial results ({completed_count}/{total_handles}) !!!")
                    break
                    
                try:
                    handle_or_h_lower, result = future.result()
                    if handle_or_h_lower:
                        if isinstance(result, int):
                            results[handle_or_h_lower] = result
                            print(f" [{completed_count}/{total_handles}] Success: {current_handle} ({result} solves)")
                        else:
                            errors[handle_or_h_lower] = result
                            print(f" [{completed_count}/{total_handles}] FAILED: {current_handle} ({result})")
                except Exception as e:
                    print(f" [{completed_count}/{total_handles}] CRITICAL ERROR: {current_handle} ({str(e)})")
                    pass

        print(f"--- Check Complete: {len(results)} fetched, {len(errors)} errors ---\n")
        return JsonResponse({
            'results': results,
            'ratings': ratings,
            'errors': errors
        })
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
