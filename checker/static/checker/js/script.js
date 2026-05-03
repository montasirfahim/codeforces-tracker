document.addEventListener('DOMContentLoaded', () => {
    console.log("CF Checker JS Loaded - Version 1.2 (Debug Enabled)");

    // ── Elements ──────────────────────────────────────────────
    const daysInput    = document.getElementById('daysInput');
    const uploadBtn    = document.getElementById('uploadBtn');
    const csvInput     = document.getElementById('csvFileInput');
    const listSelect   = document.getElementById('listSelect');
    const loadSavedBtn = document.getElementById('loadSavedBtn');
    const checkBtn     = document.getElementById('checkSolvesBtn');
    const clearListsBtn = document.getElementById('clearListsBtn');
    const listContainer = document.getElementById('studentsList');
    const log          = document.getElementById('errorLog');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText    = document.getElementById('loadingText');

    if (!checkBtn) {
        console.error("FATAL ERROR: 'checkSolvesBtn' not found in DOM!");
    } else {
        console.log("SUCCESS: 'checkSolvesBtn' found.");
    }

    let students = [];
    let solves   = {};
    let ratings  = {};
    let errors   = {};

    // ── Load Saved Lists ──────────────────────────────────────
    async function refreshLists() {
        console.log("Refreshing saved lists...");
        try {
            const res = await fetch('/api/lists/');
            const data = await res.json();
            listSelect.innerHTML = '<option value="">Select Saved List...</option>';
            data.lists.forEach(l => {
                const opt = document.createElement('option');
                opt.value = l.id;
                opt.textContent = `${l.name} (${new Date(l.created_at).toLocaleDateString()})`;
                listSelect.appendChild(opt);
            });
            console.log(`Loaded ${data.lists.length} lists.`);
        } catch (e) {
            console.error('Failed to load lists', e);
        }
    }

    refreshLists();

    // ── Render Table ──────────────────────────────────────────
    function render() {
        console.log("Rendering table with", students.length, "students.");
        if (students.length === 0) {
            listContainer.innerHTML = '<p class="text-center py-10 text-slate-400">No students loaded. Upload a CSV or select a list to begin.</p>';
            return;
        }

        let html = `
            <div class="overflow-x-auto rounded-xl shadow border border-slate-200">
                <table class="min-w-full divide-y divide-slate-200 text-sm">
                    <thead class="bg-slate-50 text-xs font-bold uppercase tracking-wider text-slate-500">
                        <tr>
                            <th class="px-5 py-3 text-left">#</th>
                            <th class="px-5 py-3 text-left">Name</th>
                            <th class="px-5 py-3 text-left">ID</th>
                            <th class="px-5 py-3 text-left">CF Handle</th>
                            <th class="px-5 py-3 text-center">Max Rating</th>
                            <th class="px-5 py-3 text-center">Solves</th>
                            <th class="px-5 py-3 text-center">Status</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 bg-white">
        `;

        students.forEach((s, idx) => {
            const displayHandle = s.handle;
            const h             = displayHandle.toLowerCase();
            const count         = solves[h];
            const rating        = ratings[h];
            const err           = errors[displayHandle] || errors[h];

            let rowClass = 'bg-white';
            let badge    = '<span class="text-slate-300 text-lg">—</span>';
            let ratingBox = '<span class="text-slate-300">—</span>';
            let status   = '<span class="text-slate-400 text-xs italic">Not Checked</span>';

            if (err) {
                rowClass = 'bg-red-50';
                badge    = '<span class="text-xl">⚠️</span>';
                status   = `<span class="text-red-600 text-xs font-bold">${err}</span>`;

            } else {
                if (rating !== undefined) {
                    let rColor = 'text-slate-400';
                    if (rating >= 2400) rColor = 'text-red-600 font-bold';
                    else if (rating >= 2100) rColor = 'text-orange-500 font-bold';
                    else if (rating >= 1900) rColor = 'text-violet-600 font-bold';
                    else if (rating >= 1600) rColor = 'text-blue-600 font-bold';
                    else if (rating >= 1400) rColor = 'text-cyan-600 font-bold';
                    else if (rating >= 1200) rColor = 'text-emerald-600 font-bold';
                    else if (rating > 0) rColor = 'text-gray-500 font-bold';
                    
                    ratingBox = `<span class="${rColor}">${rating || 0}</span>`;
                }

                if (count !== undefined) {
                    const target = (parseInt(daysInput.value) || 1) * 3;
                    if (count < target) {
                        rowClass = 'bg-red-50';
                        badge    = `<span class="inline-flex items-center justify-center w-9 h-9 rounded-full bg-red-600 text-white font-bold text-base">${count}</span>`;
                        status   = `<span class="inline-block px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-bold">❌ Below Target (${target})</span>`;
                    } else {
                        rowClass = 'bg-emerald-50';
                        badge    = `<span class="inline-flex items-center justify-center w-9 h-9 rounded-full bg-emerald-500 text-white font-bold text-base">${count}</span>`;
                        status   = '<span class="inline-block px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 text-xs font-bold">✅ Target Met</span>';
                    }
                }
            }

            html += `
                <tr class="${rowClass} transition-colors">
                    <td class="px-5 py-3 text-slate-400 font-medium">${idx + 1}</td>
                    <td class="px-5 py-3 text-slate-800">${s.name || 'Unknown'}</td>
                    <td class="px-5 py-3 font-bold text-slate-700">${s.id || '—'}</td>
                    <td class="px-5 py-3 font-mono">
                        <a href="https://codeforces.com/profile/${encodeURIComponent(displayHandle)}"
                           target="_blank"
                           class="text-indigo-600 hover:underline">${displayHandle}</a>
                    </td>
                    <td class="px-5 py-3 text-center font-bold">${ratingBox}</td>
                    <td class="px-5 py-3 text-center">${badge}</td>
                    <td class="px-5 py-3 text-center">${status}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        listContainer.innerHTML = html;
    }

    // ── Upload CSV ────────────────────────────────────────────
    uploadBtn.addEventListener('click', () => csvInput.click());

    csvInput.addEventListener('change', async e => {
        const file = e.target.files[0];
        if (!file) return;
        
        console.log("Uploading CSV:", file.name);
        const formData = new FormData();
        formData.append('csv_file', file);
        
        loadingText.textContent = 'Uploading CSV and processing students...';
        loadingOverlay.classList.remove('hidden');
        try {
            const res = await fetch('/api/upload/', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            
            alert(data.message);
            await refreshLists();
            listSelect.value = data.list_id;
            loadSavedBtn.click();
        } catch (err) {
            console.error("Upload Error:", err);
            alert('Upload failed: ' + err.message);
        } finally {
            loadingOverlay.classList.add('hidden');
            csvInput.value = '';
        }
    });

    // ── Load List ─────────────────────────────────────────────
    loadSavedBtn.addEventListener('click', async () => {
        const listId = listSelect.value;
        if (!listId) { alert('Select a list first!'); return; }

        console.log("Loading student list ID:", listId);
        loadingText.textContent = 'Loading student list...';
        loadingOverlay.classList.remove('hidden');
        try {
            const res = await fetch(`/api/students/${listId}/`);
            const data = await res.json();
            students = data.students;
            solves = {};
            ratings = {};
            errors = {};
            console.log(`Loaded ${students.length} students.`);
            render();
        } catch (err) {
            console.error("Load Error:", err);
            alert('Failed to load students');
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });

    // ── Check Solves ──────────────────────────────────────────
    checkBtn.addEventListener('click', async () => {
        console.log("--- Check Solves Clicked ---");
        
        if (students.length === 0) { 
            console.warn("Aborting: No students in list.");
            alert('Load students first!'); 
            return; 
        }

        const days = daysInput.value;
        console.log(`Parameters: ${students.length} students, ${days} days.`);

        if (!days || days < 1) { 
            console.warn("Aborting: Invalid days.");
            alert('Enter valid days!'); 
            return; 
        }

        checkBtn.disabled = true;
        checkBtn.textContent = 'Checking...';
        loadingText.textContent = 'Fetching student data from Codeforces...';
        loadingOverlay.classList.remove('hidden');
        
        const handles = students.map(s => s.handle);
        console.log("Handles to verify:", handles);
        
        try {
            console.log("Calling API: /api/check/ ...");
            const res = await fetch('/api/check/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ handles, days })
            });
            
            console.log("API Response Status:", res.status);
            const data = await res.json();
            console.log("API Data:", data);
            
            // Normalize keys to lowercase for robust matching
            solves = {};
            if (data.results) {
                Object.entries(data.results).forEach(([k, v]) => {
                    solves[k.toLowerCase()] = v;
                });
            }

            ratings = {};
            if (data.ratings) {
                Object.entries(data.ratings).forEach(([k, v]) => {
                    ratings[k.toLowerCase()] = v;
                });
            }

            errors = data.errors || {};
            
            // Update error log
            log.innerHTML = '';
            Object.entries(errors).forEach(([h, msg]) => {
                const entry = document.createElement('div');
                entry.className = 'border-l-2 border-red-400 pl-2 mb-2 text-xs text-red-600';
                entry.innerHTML = `<strong>${h}:</strong> ${msg}`;
                log.prepend(entry);
            });
            
            if (Object.keys(errors).length === 0) {
                log.innerHTML = '<p class="text-slate-400 italic text-center py-4">No errors reported.</p>';
            }
            
            console.log("Check complete, re-rendering...");
            render();
        } catch (err) {
            console.error("Check Error:", err);
            alert('Check failed: ' + err.message);
        } finally {
            checkBtn.disabled = false;
            checkBtn.textContent = 'Check Solves';
            loadingOverlay.classList.add('hidden');
        }
    });

    // ── Clear Log ─────────────────────────────────────────────
    document.getElementById('clearLogBtn').addEventListener('click', () => {
        log.innerHTML = '<p class="text-slate-400 italic text-center py-4">No errors reported.</p>';
    });

    // ── Clear Saved Lists ─────────────────────────────────────
    clearListsBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to clear all saved student lists? This will also reset the permanent list (it will be reloaded on next refresh).')) return;

        console.log("Clearing all saved lists...");
        loadingText.textContent = 'Clearing all saved lists...';
        loadingOverlay.classList.remove('hidden');
        try {
            const res = await fetch('/api/clear/', { method: 'POST' });
            const data = await res.json();
            alert(data.message);
            students = [];
            solves = {};
            ratings = {};
            errors = {};
            render();
            await refreshLists();
        } catch (err) {
            console.error("Clear Error:", err);
            alert('Failed to clear lists');
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });
});
