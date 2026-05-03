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

@csrf_exempt
def check_solves(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    import json
    try:
        data = json.loads(request.body)
        handles = data.get('handles', [])
        days = int(data.get('days', 1))
        
        # Calculate time range
        now = datetime.now()
        start_time = now - timedelta(days=days)
        start_ts = int(start_time.timestamp())
        end_ts = int(now.timestamp())
        
        results = {}
        ratings = {}
        errors = {}
        
        print(f"--- API CHECK START: {len(handles)} handles, {days} days ---")
        
        # Helper to fetch user info in batches
        def fetch_ratings(h_list):
            try:
                # Filter out empty or invalid handles
                valid_h = [h for h in h_list if h and h not in ['—', '0', '', 'blank']]
                if not valid_h: return
                
                info_url = f"https://codeforces.com/api/user.info?handles={';'.join(valid_h)}"
                info_res = requests.get(info_url, timeout=10)
                if info_res.status_code == 200:
                    info_data = info_res.json()
                    if info_data['status'] == 'OK':
                        for user_info in info_data['result']:
                            ratings[user_info['handle'].lower()] = user_info.get('maxRating', 0)
            except Exception as e:
                print(f"Batch info error: {str(e)}")

        # Try batching info first
        if handles:
            batch_size = 50
            for i in range(0, len(handles), batch_size):
                fetch_ratings(handles[i:i+batch_size])

        # Track start time to avoid Render 30s timeout
        view_start_time = time.time()
        
        for handle in handles:
            # Check if we are approaching the 30s timeout (e.g., stop at 25s)
            if time.time() - view_start_time > 25:
                print("Approaching timeout, stopping processing and returning partial results.")
                break

            if not handle or handle in ['—', '0', '', 'blank']:
                continue
            
            h_lower = handle.lower()
            try:
                url = f"https://codeforces.com/api/user.status?handle={handle}"
                response = requests.get(url, timeout=5)
                
                if response.status_code != 200:
                    errors[handle] = f"CF Error {response.status_code}"
                    continue
                
                data = response.json()
                if data['status'] != 'OK':
                    errors[handle] = data.get('comment', 'Unknown CF error')
                    continue
                
                unique_problems = set()
                all_submissions = data.get('result', [])
                
                for sub in all_submissions:
                    if sub['verdict'] == 'OK':
                        c_time = sub['creationTimeSeconds']
                        if start_ts <= c_time <= end_ts:
                            problem = sub['problem']
                            p_id = f"{problem.get('contestId')}-{problem.get('index')}"
                            unique_problems.add(p_id)
                
                results[h_lower] = len(unique_problems)
                time.sleep(0.2) # Reduced sleep
            except Exception as e:
                print(f"Error for {handle}: {str(e)}")
                errors[handle] = "Connection Error"
        
        print(f"--- API CHECK COMPLETE: {len(results)} success, {len(errors)} errors ---")
        return JsonResponse({
            'results': results,
            'ratings': ratings,
            'errors': errors
        })
    except Exception as e:
        print(f"CRITICAL VIEW ERROR: {str(e)}")
        return JsonResponse({'error': 'Server processed error: ' + str(e)}, status=500)
