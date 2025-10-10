document.addEventListener("DOMContentLoaded", async () => {
    const serviceList = document.querySelector(".service-list");
    const pagination = document.getElementById("pagination");
    const searchInput = document.querySelector(".search-container input");
    const searchBtn = document.querySelector(".search-container button");
    serviceList.innerHTML = "<p>데이터를 불러오는 중입니다...</p>";

    const itemsPerPage = 5;
    let currentPage = 1;
    let services = [];
    let searchKeyword = "";

    const filters = {
        "life-cycle": ["임신·출산","영유아","아동","청소년","청년","중장년·노인"],
        "household": ["장애인","여성","한부모","맞벌이","저소득층","보훈대상","다문화·북한이탈주민"],
        "interest": ["안전","위기","법률","신체건강","정신건강","문화·여가","생활지원","주거","보육","교육","돌봄","금융","에너지","농어민","디지털","환경·교통","입양·위탁보호","기타"]
    };

    const selectedCategories = new Set();
    const excludedCategories = new Set();

    // --- 필터 버튼 생성 ---
    for (const [id, arr] of Object.entries(filters)) {
        const container = document.getElementById(id);
        arr.forEach(cat => {
            const btn = document.createElement("button");
            btn.className = "filter-btn";
            btn.textContent = cat;
            btn.dataset.value = cat;
            btn.dataset.clickCount = 0;
            container.appendChild(btn);

            btn.addEventListener("click", () => {
                let count = (parseInt(btn.dataset.clickCount) + 1) % 3;
                btn.dataset.clickCount = count;
                selectedCategories.delete(cat);
                excludedCategories.delete(cat);
                btn.classList.remove("selected", "excluded");

                if (count === 1) { selectedCategories.add(cat); btn.classList.add("selected"); }
                else if (count === 2) { excludedCategories.add(cat); btn.classList.add("excluded"); }

                updateLists();
                currentPage = 1;
                applyFilters();
            });
        });
    }

    const selectedList = document.getElementById('selected-list');
    const excludedList = document.getElementById('excluded-list');

    function updateLists() {
        selectedList.textContent = `선택된 목록: ${Array.from(selectedCategories).join(', ') || '없음'}`;
        excludedList.textContent = `제외된 목록: ${Array.from(excludedCategories).join(', ') || '없음'}`;
    }

    // --- 데이터 불러오기 ---
    try {
        const res = await fetch("https://port-0-socialwelfare-mgjckxvm97f5b4e4.sel3.cloudtype.app/services");
        const data = await res.json();
        services = data.data;
        renderServices(services);
    } catch (e) {
        console.error(e);
        serviceList.innerHTML = "<p>데이터를 불러오지 못했습니다.</p>";
    }

    // --- 서비스 렌더링 ---
    function renderServices(list) {
        serviceList.innerHTML = "";
        const start = (currentPage - 1) * itemsPerPage;
        const pagedList = list.slice(start, start + itemsPerPage);

        if (pagedList.length === 0) {
            serviceList.innerHTML = "<p>표시할 서비스가 없습니다.</p>";
            pagination.innerHTML = "";
            return;
        }

        pagedList.forEach(service => {
            const item = document.createElement("div");
            item.className = "service-item";
            item.dataset.category = service.카테고리.join(",");
            item.innerHTML = `
                <div class="service-item-header">
                    <span>${service.정책명 || "제목 없음"}</span>
                    ${service.카테고리.map(c => `<span class="service-category-label">${c}</span>`).join('')}
                </div>
                <div class="service-item-details">
                    <p><strong>참고사항:</strong> ${service.참고사항 || "정보 없음"}</p>
                    <p><strong>지원대상:</strong> ${service.지원대상 || "정보 없음"}</p>
                    <p><strong>상세내용:</strong> ${service.상세내용 || "정보 없음"}</p>
                    <p><strong>복지신청:</strong> <a href="${service.링크}" target="_blank">지원 신청하기</a></p>
                </div>
            `;
            item.addEventListener("click", () => item.classList.toggle("active"));
            serviceList.appendChild(item);
        });

        renderPagination(list.length);
    }

    // --- 필터 + 검색 적용 ---
    function applyFilters() {
        const keyword = searchKeyword.trim();
        const filtered = services.filter(service => {
            const cats = service.카테고리.map(c => c.trim());
            const text = `${service.정책명} ${service.지원대상} ${service.상세내용} ${service.참고사항}`.toLowerCase();

            if (cats.some(c => excludedCategories.has(c))) return false;
            if (selectedCategories.size > 0 && !cats.some(c => selectedCategories.has(c))) return false;
            if (keyword && !text.includes(keyword.toLowerCase())) return false;

            return true;
        });
        renderServices(filtered);
    }

    // --- 페이지네이션 ---
    function renderPagination(totalItems) {
        pagination.innerHTML = "";
        const totalPages = Math.ceil(totalItems / itemsPerPage);
        if (totalPages <= 1) return;

        const groupSize = 10;
        const currentGroupStart = Math.floor((currentPage - 1) / groupSize) * groupSize + 1;
        const currentGroupEnd = Math.min(currentGroupStart + groupSize - 1, totalPages);

        function createBtn(label, page, disabled = false) {
            const btn = document.createElement("button");
            btn.textContent = label;
            btn.className = "page-btn";
            if (disabled) btn.classList.add("disabled");
            if (!disabled) {
                btn.onclick = () => {
                    currentPage = page;
                    applyFilters();
                };
            }
            return btn;
        }

        pagination.appendChild(createBtn("<<", 1, currentPage === 1));
        pagination.appendChild(createBtn("<", currentGroupStart - 1, currentGroupStart === 1));

        for (let i = currentGroupStart; i <= currentGroupEnd; i++) {
            const btn = createBtn(i, i);
            if (i === currentPage) btn.classList.add("active");
            pagination.appendChild(btn);
        }

        pagination.appendChild(createBtn(">", currentGroupEnd + 1, currentGroupEnd >= totalPages));
        pagination.appendChild(createBtn(">>", totalPages, currentPage === totalPages));
    }

    // --- 검색 기능 ---
    searchBtn.addEventListener("click", () => {
        searchKeyword = searchInput.value;
        currentPage = 1;
        applyFilters();
    });

    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            searchKeyword = searchInput.value;
            currentPage = 1;
            applyFilters();
        }
    });
});
