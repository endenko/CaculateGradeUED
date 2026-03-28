let transcriptData = JSON.parse(localStorage.getItem('kanna_transcript_v2')) || [];
const gradeMap = { 'A+': 4.0, 'A': 4.0, 'B+': 3.5, 'B': 3.0, 'C+': 2.5, 'C': 2.0, 'D+': 1.5, 'D': 1.0, 'F': 0.0 };

function saveData() {
    localStorage.setItem('kanna_transcript_v2', JSON.stringify(transcriptData));
    renderTable();
    calculateStats();
}

let debounceTimer;
function searchSubject() {
    const query = document.getElementById('inputName').value;
    if (query.length < 2) { document.getElementById('suggestions').style.display = 'none'; return; }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        fetch(`/api/search_subject?q=${encodeURIComponent(query)}`)
            .then(res => res.json())
            .then(data => {
                const box = document.getElementById('suggestions');
                box.innerHTML = '';
                if (data.length > 0) {
                    box.style.display = 'block';
                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'suggestion-item small';
                        div.innerHTML = `<b>${item.ten_mon}</b> <span class="text-muted float-end">(${item.tin_chi} tín)</span>`;
                        div.onclick = () => {
                            document.getElementById('inputName').value = item.ten_mon;
                            document.getElementById('inputCredits').value = item.tin_chi;
                            box.style.display = 'none';
                        };
                        box.appendChild(div);
                    });
                } else {
                    box.style.display = 'none';
                }
            });
    }, 300);
}

// Tắt gợi ý khi click ra ngoài
document.addEventListener('click', function (event) {
    const box = document.getElementById('suggestions');
    const input = document.getElementById('inputName');
    if (event.target !== box && event.target !== input) {
        box.style.display = 'none';
    }
});

function convertGrade() {
    let inputEl = document.getElementById('inputGrade10');
    let val = parseFloat(inputEl.value);

    if (val > 10) { val = 10; inputEl.value = 10; }
    else if (val < 0) { val = 0; inputEl.value = 0; }

    let char = '';
    if (!isNaN(val)) {
        if (val >= 9.0) char = 'A+';
        else if (val >= 8.5) char = 'A';
        else if (val >= 8.0) char = 'B+';
        else if (val >= 7.0) char = 'B';
        else if (val >= 6.5) char = 'C+';
        else if (val >= 5.5) char = 'C';
        else if (val >= 5.0) char = 'D+';
        else if (val >= 4.0) char = 'D';
        else char = 'F';
    }
    document.getElementById('inputGrade4').value = char;
}

function addManualSubject() {
    const name = document.getElementById('inputName').value;
    const credits = parseInt(document.getElementById('inputCredits').value);
    const grade = document.getElementById('inputGrade4').value;

    if (name && credits && grade) {
        transcriptData.push({ ten_mon: name, tin_chi: credits, diem_he_4: grade, sim_grade: null });
        saveData();
        document.getElementById('inputName').value = '';
        document.getElementById('inputGrade10').value = '';
        document.getElementById('inputGrade4').value = '';
    } else {
        alert("Vui lòng nhập đủ thông tin bạn nhé!");
    }
}

function uploadOCR() {
    const fileInput = document.getElementById('ocrFile');
    if (fileInput.files.length === 0) return alert("Vui lòng chọn ảnh trước bạn nhé!");

    const mode = document.querySelector('input[name="ocrMode"]:checked').value;
    const formData = new FormData();
    formData.append('file_anh', fileInput.files[0]);
    formData.append('mode', mode);

    document.getElementById('ocrLoading').style.display = 'inline-block';

    fetch('/api/process_ocr', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(resp => {
            document.getElementById('ocrLoading').style.display = 'none';
            if (resp.success) {
                let count = 0;
                resp.data.forEach(newSub => {
                    if (!transcriptData.some(s => s.ten_mon === newSub.ten_mon)) {
                        transcriptData.push({ ...newSub, sim_grade: null });
                        count++;
                    }
                });
                saveData();
                alert(`Đã thêm thành công ${count} môn! (Chế độ: ${mode === 'computer' ? 'Máy tính' : 'Viết tay'})`);
            } else {
                alert("Lỗi OCR: " + resp.error);
            }
        })
        .catch(err => {
            document.getElementById('ocrLoading').style.display = 'none';
            alert("Lỗi kết nối server!");
        });
}

function renderTable() {
    const tbody = document.getElementById('transcriptTable');
    tbody.innerHTML = '';

    transcriptData.forEach((item, index) => {
        let badgeClass = 'bg-F';
        let d = item.diem_he_4 || '';
        if (d.includes('A+')) badgeClass = 'bg-A-plus';
        else if (d.includes('A')) badgeClass = 'bg-A';
        else if (d.includes('B')) badgeClass = 'bg-B';
        else if (d.includes('C')) badgeClass = 'bg-C';
        else if (d.includes('D')) badgeClass = 'bg-D';

        let rowClass = "";
        let selectVal = "";
        if (item.sim_grade) {
            selectVal = item.sim_grade;
            rowClass = "table-warning";
        }

        let displayName = item.ten_mon;
        if (item.percentage) {
            displayName = `${item.ten_mon} <span class="text-success badge bg-light text-dark border ms-1" style="font-size: 0.7rem;">${item.percentage} giống</span>`;
        }

        const tr = document.createElement('tr');
        tr.className = rowClass;
        tr.innerHTML = `
            <td>${displayName}</td>
            <td class="text-center fw-bold">${item.tin_chi}</td>
            <td class="text-center"><span class="badge-grade ${badgeClass}">${item.diem_he_4}</span></td>
            <td class="text-center">
                <select class="form-select form-select-sm" onchange="updateSim(${index}, this.value)">
                    <option value="" ${selectVal == "" ? "selected" : ""}>-- Giữ --</option>
                    <option value="A+" ${selectVal == "A+" ? "selected" : ""}>A+</option>
                    <option value="A" ${selectVal == "A" ? "selected" : ""}>A</option>
                    <option value="B+" ${selectVal == "B+" ? "selected" : ""}>B+</option>
                    <option value="B" ${selectVal == "B" ? "selected" : ""}>B</option>
                    <option value="C+" ${selectVal == "C+" ? "selected" : ""}>C+</option>
                    <option value="C" ${selectVal == "C" ? "selected" : ""}>C</option>
                    <option value="D+" ${selectVal == "D+" ? "selected" : ""}>D+</option>
                    <option value="D" ${selectVal == "D" ? "selected" : ""}>D</option>
                </select>
            </td>
            <td class="text-center"><i class="fas fa-times text-danger" style="cursor:pointer" onclick="removeSubject(${index})"></i></td>
        `;
        tbody.appendChild(tr);
    });

    generateSuggestions();
}

function removeSubject(index) {
    if (confirm("Xóa môn này nhé?")) {
        transcriptData.splice(index, 1);
        saveData();
    }
}

function clearAllData() {
    transcriptData = [];
    saveData();
}

function updateSim(index, val) {
    transcriptData[index].sim_grade = val === "" ? null : val;
    saveData();
}

function resetSimulation() {
    transcriptData.forEach(m => m.sim_grade = null);
    saveData();
}

function calculateStats() {
    let totalTin = 0;
    let totalRealScore = 0;
    let totalSimScore = 0;

    transcriptData.forEach(m => {
        let realScore = gradeMap[m.diem_he_4] || 0;
        let simScore = m.sim_grade ? gradeMap[m.sim_grade] : realScore;

        totalTin += m.tin_chi;
        totalRealScore += realScore * m.tin_chi;
        totalSimScore += simScore * m.tin_chi;
    });

    const curGPA = totalTin > 0 ? (totalRealScore / totalTin).toFixed(2) : "0.00";
    const simGPA = totalTin > 0 ? (totalSimScore / totalTin).toFixed(2) : "0.00";
    const diff = (simGPA - curGPA).toFixed(2);

    document.getElementById('displayGPA').innerText = curGPA;
    document.getElementById('simulatedGPA').innerText = simGPA;
    const diffEl = document.getElementById('diffGPA');
    diffEl.innerText = (diff > 0 ? "+" : "") + diff;

    if (diff > 0) diffEl.parentElement.className = 'card score-box bg-success text-white';
    else if (diff < 0) diffEl.parentElement.className = 'card score-box bg-danger text-white';
    else diffEl.parentElement.className = 'card score-box diff';

    const target = parseInt(document.getElementById('targetCredits').value);
    const percent = Math.min(100, Math.round((totalTin / target) * 100));
    const bar = document.getElementById('gradProgressBar');
    bar.style.width = percent + "%";
    bar.innerText = percent + "%";
    document.getElementById('progressText').innerText = `${totalTin} / ${target} TC`;

    const rem = Math.max(0, target - totalTin);
    document.getElementById('remainingCredits').value = rem;
}

function generateSuggestions() {
    const list = document.getElementById('suggestionList');
    list.innerHTML = "";
    let candidates = transcriptData.filter(m => (gradeMap[m.diem_he_4] || 0) < 3.0);

    candidates.sort((a, b) => {
        let impactA = (4.0 - (gradeMap[a.diem_he_4] || 0)) * a.tin_chi;
        let impactB = (4.0 - (gradeMap[b.diem_he_4] || 0)) * b.tin_chi;
        return impactB - impactA;
    });

    if (candidates.length === 0 && transcriptData.length > 0) {
        list.innerHTML = "<div class='text-center text-success mt-2'>🎉 Tuyệt vời! Bảng điểm đẹp, không cần học lại!</div>";
    } else {
        candidates.slice(0, 5).forEach(m => {
            let current = gradeMap[m.diem_he_4];
            let gain = ((4.0 - current) * m.tin_chi) / Math.max(1, transcriptData.reduce((s, x) => s + x.tin_chi, 0));

            list.innerHTML += `
        <div class="suggestion-alert p-2 rounded small mb-2" onclick="fillSim('${m.ten_mon}')">
            <div class="fw-bold">${m.ten_mon} (${m.tin_chi} TC)</div>
            <div class="d-flex justify-content-between text-muted">
                <span>Điểm: <b class="text-danger">${m.diem_he_4}</b></span>
                <span class="text-success fw-bold">GPA +${gain.toFixed(2)} 🚀</span>
            </div>
        </div>`;
        });
    }
}

function fillSim(name) {
    let idx = transcriptData.findIndex(m => m.ten_mon === name);
    if (idx !== -1) {
        updateSim(idx, "A+");
        document.querySelectorAll('#transcriptTable tr')[idx].scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

function calculateGraduationPath() {
    const targetGPA = parseFloat(document.getElementById('goalGPA').value);
    const remCredits = parseInt(document.getElementById('remainingCredits').value);
    const curGPA = parseFloat(document.getElementById('simulatedGPA').innerText);

    let totalTin = transcriptData.reduce((s, m) => s + m.tin_chi, 0);
    let currentTotalScore = curGPA * totalTin;

    if (remCredits <= 0) {
        document.getElementById('gradResult').style.display = 'block';
        document.getElementById('gradResult').className = "bg-warning text-dark";
        document.getElementById('gradResult').innerHTML = "Đã đủ tín chỉ rồi! Kết quả hiện tại là chốt hạ.";
        return;
    }

    const totalTargetCredits = totalTin + remCredits;
    const requiredTotalScore = targetGPA * totalTargetCredits;
    const neededScoreFromRemaining = requiredTotalScore - currentTotalScore;
    const neededGPA = neededScoreFromRemaining / remCredits;

    const resDiv = document.getElementById('gradResult');
    resDiv.style.display = 'block';

    if (neededGPA > 4.0) {
        resDiv.className = "bg-danger text-white";
        resDiv.innerHTML = `❌ <b>Khó quá!</b><br>Cần đạt trung bình <b>${neededGPA.toFixed(2)}</b> (Hơn cả 4.0).`;
    } else if (neededGPA < 0) {
        resDiv.className = "bg-success text-white";
        resDiv.innerHTML = `🎉 <b>Dư sức!</b><br>Đã tích lũy đủ điểm để đạt mục tiêu.`;
    } else {
        resDiv.className = "bg-info text-white";
        resDiv.innerHTML = `🎯 <b>Mục tiêu:</b><br>Cần đạt GPA trung bình <b>${neededGPA.toFixed(2)}</b> cho ${remCredits} tín chỉ cuối.`;
    }
}

function calcDRL() {
    const target = parseInt(document.getElementById('drlTarget').value);
    const sem1 = parseFloat(document.getElementById('drlSem1').value);
    const resBox = document.getElementById('drlResult');

    resBox.style.display = 'block';

    if (isNaN(sem1)) {
        resBox.innerHTML = `🎯 Để đạt <b>${target}</b> cả năm, mỗi kỳ bạn cần phấn đấu đạt trung bình <b>${target}</b> điểm nhé!`;
    } else {
        const needed = (target * 2) - sem1;

        if (needed > 100) {
            resBox.className = "alert alert-danger border text-center small p-1";
            resBox.innerHTML = `😱 <b>Nguy hiểm!</b> Cần <b>${needed}</b> điểm. (Max 100).`;
        } else if (needed <= 50) {
            resBox.className = "alert alert-success border text-center small p-1";
            resBox.innerHTML = `😎 <b>Dễ ợt!</b> Chỉ cần <b>${Math.max(0, needed)}</b> điểm.`;
        } else {
            resBox.className = "alert alert-info border text-center small p-1";
            resBox.innerHTML = `🔥 <b>Chiến lược:</b> Kỳ 2 cần đạt <b>${needed}</b> điểm ĐRL.`;
        }
    }
}

renderTable();
calculateStats();