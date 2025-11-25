document.addEventListener("DOMContentLoaded", async () => {
    const serviceList = document.querySelector(".service-list");
    const pagination = document.getElementById("pagination");
    const searchInput = document.querySelector(".search-container input");
    const searchBtn = document.querySelector(".search-container button");
    const resultCount = document.getElementById("result-count");
    const favoriteCount = document.getElementById("favorite-count");
    const viewBtns = document.querySelectorAll(".view-btn");
    
    serviceList.innerHTML = "<p>데이터를 불러오는 중입니다...</p>";

    const itemsPerPage = 5;
    let currentPage = 1;
    let services = [];
    let searchKeyword = "";
    let currentView = "all"; // "all" 또는 "favorites"
    const favorites = new Set(JSON.parse(localStorage.getItem("favorites") || "[]"));

    const filters = {
        "life-cycle": ["임신","출산","영유아","아동","청소년","청년","중장년", "노인"],
        "household": ["장애인","여성","한부모","맞벌이","저소득층","보훈대상","다문화","북한이탈주민"],
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
    const clearFiltersBtn = document.getElementById('clear-filters');

    // --- 즐겨찾기 저장 함수 ---
    function saveFavorites() {
        localStorage.setItem("favorites", JSON.stringify(Array.from(favorites)));
        favoriteCount.textContent = favorites.size;
    }

    function updateLists() {
        selectedList.textContent = `선택된 목록: ${Array.from(selectedCategories).join(', ') || '없음'}`;
        excludedList.textContent = `제외된 목록: ${Array.from(excludedCategories).join(', ') || '없음'}`;
    }

    // --- 필터 초기화 버튼 기능 ---
    clearFiltersBtn.addEventListener("click", () => {
        selectedCategories.clear();
        excludedCategories.clear();
        
        // 모든 필터 버튼 상태 초기화
        document.querySelectorAll(".filter-btn").forEach(btn => {
            btn.dataset.clickCount = 0;
            btn.classList.remove("selected", "excluded");
        });

        updateLists();
        currentPage = 1;
        applyFilters();
    });

    // --- 뷰 토글 버튼 이벤트 ---
    viewBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            viewBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentView = btn.dataset.view;
            currentPage = 1;
            applyFilters();
        });
    });

    // 초기 즐겨찾기 개수 표시
    favoriteCount.textContent = favorites.size;

    // --- 데이터 불러오기 ---
    try {
        const res = await fetch("https://port-0-socialwelfare-mgjckxvm97f5b4e4.sel3.cloudtype.app/services");
        const data = await res.json();
        // 정규화: 서비스 배열을 받아 각 항목의 필드를 안전하게 초기화하고
        // 카테고리를 배열로 보장합니다. 백엔드에서 문자열로 반환할 수도 있으므로
        // 쉼표로 분리해 배열로 변환합니다.
        services = (data.data || []).map(s => {
            const catsRaw = s.카테고리 || [];
            // 강력한 분리 로직: 한 항목에 '아동, 청소년, 교육'처럼 묶여있거나
            // '아동/청소년' 등 여러 구분자가 섞여 있어도 각각 분리합니다.
            const splitRegex = /[,/|;、·\/\\]+|\s{2,}|\s?[-–—]\s?|\s+/; // 여러 구분자 지원
            let cats = [];
            if (Array.isArray(catsRaw)) {
                catsRaw.forEach(elem => {
                    if (!elem) return;
                    const parts = elem.toString().split(splitRegex).map(c => c.trim()).filter(Boolean);
                    parts.forEach(p => cats.push(p));
                });
            } else if (typeof catsRaw === 'string') {
                cats = catsRaw.split(splitRegex).map(c => c.trim()).filter(Boolean);
            } else {
                cats = [];
            }
            // 순서 보존된 중복 제거
            const seen = new Set();
            cats = cats.filter(c => {
                const key = c.toString();
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });

            return {
                ...s,
                정책명: s.정책명 || "",
                지원대상: s.지원대상 || "",
                참고사항: s.참고사항 || "",
                상세내용: s.상세내용 || "",
                링크: s.링크 || s.정책링크 || "",
                카테고리: cats
            };
        });

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
            const cats = Array.isArray(service.카테고리) ? service.카테고리 : [];
            item.dataset.category = cats.join(",");
            const isFavorited = favorites.has(service.정책명);
            item.innerHTML = `
                <div class="service-item-header">
                    <div class="service-header-top">
                        <span class="title">${service.정책명 || "제목 없음"}</span>
                        <button class="favorite-btn ${isFavorited ? 'active' : ''}">⭐</button>
                    </div>
                    <div class="category-container">
                        ${cats.map(c => `<span class="service-category-label">${c}</span>`).join('')}
                    </div>
                </div>
                <div class="service-item-details">
                    <p><strong>참고사항:</strong> ${service.참고사항 || "정보 없음"}</p>
                    <p><strong>지원대상:</strong> ${service.지원대상 || "정보 없음"}</p>
                    <p><strong>상세내용:</strong> ${service.상세내용 || "정보 없음"}</p>
                    <p><strong>복지신청:</strong> <a href="${service.링크}" target="_blank">지원 신청하기</a></p>
                </div>
            `;
            
            // 즐겨찾기 버튼 이벤트
            const favoriteBtn = item.querySelector(".favorite-btn");
            favoriteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                const policyName = service.정책명;
                if (favorites.has(policyName)) {
                    favorites.delete(policyName);
                    favoriteBtn.classList.remove("active");
                } else {
                    favorites.add(policyName);
                    favoriteBtn.classList.add("active");
                }
                saveFavorites();
            });
            
            item.addEventListener("click", () => item.classList.toggle("active"));
            serviceList.appendChild(item);
        });

        renderPagination(list.length);
    }

    // --- 필터 + 검색 적용 ---
    function applyFilters() {
        const keyword = searchKeyword.trim().toLowerCase();
        let filtered = services.filter(service => {
            const cats = Array.isArray(service.카테고리) ? service.카테고리.map(c => (c||"").toString().trim()) : [];
            const catsLower = cats.map(c => c.toLowerCase());
            const text = `${service.정책명 || ''} ${service.지원대상 || ''} ${service.상세내용 || ''} ${service.참고사항 || ''}`.toLowerCase();

            // 제외 카테고리에 하나라도 포함되어 있으면 제외
            for (const ex of excludedCategories) {
                if (catsLower.includes(ex.toLowerCase())) return false;
            }

            // 선택된 카테고리가 있으면 하나라도 포함되어야 함
            if (selectedCategories.size > 0) {
                let any = false;
                for (const sel of selectedCategories) {
                    if (catsLower.includes(sel.toLowerCase())) { any = true; break; }
                }
                if (!any) return false;
            }

            // 키워드 검색
            if (keyword && !text.includes(keyword)) return false;

            return true;
        });
        
        // 뷰에 따라 필터링
        if (currentView === "favorites") {
            filtered = filtered.filter(s => favorites.has(s.정책명));
        }
        
        // 결과 카운트 업데이트
        resultCount.textContent = `검색 결과: ${filtered.length}개`;
        
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
