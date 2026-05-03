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
        csv_path = os.path.join(settings.BASE_DIR, 'static', "CP_handel_ICT'22.csv")
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
        
        # 1. Fetch Ratings (Batch with individual fallback)
        def fetch_ratings_batch(h_list):
            valid_h = [h for h in h_list if h and h not in ['—', '0', '', 'blank']]
            if not valid_h: return
            
            try:
                url = f"https://codeforces.com/api/user.info?handles={';'.join(valid_h)}"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data['status'] == 'OK':
                        for user_info in data['result']:
                            ratings[user_info['handle'].lower()] = user_info.get('maxRating', 0)
                        return True
                return False
            except:
                return False

        # Try batching first, then individuals if batch fails
        batch_size = 50
        for i in range(0, len(handles), batch_size):
            batch = handles[i:i+batch_size]
            if not fetch_ratings_batch(batch):
                # Fallback to individual info for this batch
                for h in batch:
                    if h and h not in ['—', '0', '', 'blank']:
                        fetch_ratings_batch([h])

        # 2. Fetch Solves (Using Threads to avoid 30s timeout)
        def fetch_user_solves(handle):
            if not handle or handle in ['—', '0', '', 'blank']:
                return None, None
            
            h_lower = handle.lower()
            try:
                print(f" > Fetching solves for: {handle}...")
                url = f"https://codeforces.com/api/user.status?handle={handle}"
                resp = requests.get(url, timeout=7)
                if resp.status_code != 200:
                    print(f" [!] Failed: {handle} (Status {resp.status_code})")
                    return handle, f"Error {resp.status_code}"
                
                data = resp.json()
                if data['status'] != 'OK':
                    print(f" [!] CF Error: {handle} ({data.get('comment', 'Unknown')})")
                    return handle, data.get('comment', 'CF Error')
                
                unique_problems = set()
                for sub in data.get('result', []):
                    if sub['verdict'] == 'OK':
                        if start_ts <= sub['creationTimeSeconds'] <= end_ts:
                            p = sub['problem']
                            unique_problems.add(f"{p.get('contestId')}-{p.get('index')}")
                
                print(f" [+] Success: {handle} ({len(unique_problems)} unique solves)")
                return h_lower, len(unique_problems)
            except Exception as e:
                print(f" [!] Connection Error: {handle}")
                return handle, "Timeout/Connection"

        print(f"--- Starting parallel solve check for {len(handles)} students ---")
        # Use ThreadPoolExecutor to fetch status in parallel
        max_workers = 5 
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_handle = {executor.submit(fetch_user_solves, h): h for h in handles}
            
            view_start_time = time.time()
            count = 0
            
            for future in concurrent.futures.as_completed(future_to_handle):
                count += 1
                if time.time() - view_start_time > 26:
                    print(f"\n!!! REACHED TIMEOUT LIMIT (Processed {count}/{len(handles)}) !!!")
                    break
                    
                handle_or_h_lower, result = future.result()
                if handle_or_h_lower:
                    if isinstance(result, int):
                        results[handle_or_h_lower] = result
                    else:
                        errors[handle_or_h_lower] = result

        print(f"--- Check Complete: {len(results)} fetched, {len(errors)} errors ---\n")
        return JsonResponse({
            'results': results,
            'ratings': ratings,
            'errors': errors
        })
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
