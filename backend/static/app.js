// ==============================================================================
// REVIEW DASHBOARD CLIENT LOGIC (VANILLA JS APP)
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // App State
    let runs = [];
    let currentSelectedRunDate = null;
    let currentFilter = "unreviewed"; // "unreviewed" or "all"
    let searchQuery = "";
    let isGenerating = false;
    let pollingInterval = null;

    // DOM Elements
    const runsList = document.getElementById("runs-list");
    const emptyState = document.getElementById("empty-state");
    const detailPane = document.getElementById("detail-pane");
    const searchInput = document.getElementById("search-input");
    const seriesFilter = document.getElementById("series-filter");
    
    // Generator Widget DOM Elements
    const btnToggleGenerator = document.getElementById("btn-toggle-generator");
    const generatorBody = document.getElementById("generator-body");
    const generateDate = document.getElementById("generate-date");
    const generateForce = document.getElementById("generate-force");
    const generateTopic = document.getElementById("generate-topic");
    const generateSeries = document.getElementById("generate-series");
    const generateEpisode = document.getElementById("generate-episode");
    const btnStartGeneration = document.getElementById("btn-start-generation");
    const consoleContainer = document.getElementById("console-container");
    const consoleOutput = document.getElementById("console-output");
    const consolePulse = document.getElementById("console-pulse");
    
    // Tab Elements
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    // Detail Pane Elements
    const detailDate = document.getElementById("detail-date");
    const detailTitle = document.getElementById("detail-title");
    const detailStatus = document.getElementById("detail-status");
    const videoPlayer = document.getElementById("video-player");
    const videoError = document.getElementById("video-error");
    const thumbnailImg = document.getElementById("thumbnail-img");
    const thumbnailError = document.getElementById("thumbnail-error");
    const factCheckSummaryText = document.getElementById("fact-check-summary-text");
    const factCheckList = document.getElementById("fact-check-list");
    const badgeWarningCount = document.getElementById("badge-warning-count");
    
    // SEO tab elements
    const seoTitlePart1 = document.getElementById("seo-title-part1");
    const seoDescPart1 = document.getElementById("seo-description-part1");
    const seoTagsPart1 = document.getElementById("seo-tags-part1");
    const seoTitlePart2 = document.getElementById("seo-title-part2");
    const seoDescPart2 = document.getElementById("seo-description-part2");
    const seoTagsPart2 = document.getElementById("seo-tags-part2");
    
    // Script tab elements
    const scriptContentBox = document.getElementById("script-content");

    // Action buttons
    const btnApprove = document.getElementById("btn-approve");
    const btnReject = document.getElementById("btn-reject");
    const btnDelete = document.getElementById("btn-delete");
    
    // Toggle filter buttons
    const btnFilterUnreviewed = document.getElementById("btn-unreviewed");
    const btnFilterAll = document.getElementById("btn-all");

    // --------------------------------------------------------------------------
    // API CALLS
    // --------------------------------------------------------------------------

    // Populate unique series dropdown filter
    function populateSeriesFilter() {
        if (!seriesFilter) return;
        const selectedVal = seriesFilter.value;
        const uniqueSeries = new Set();
        runs.forEach(run => {
            if (run.series) {
                uniqueSeries.add(run.series);
            }
        });
        
        seriesFilter.innerHTML = '<option value="">All Series</option>';
        Array.from(uniqueSeries).sort().forEach(s => {
            const opt = document.createElement("option");
            opt.value = s;
            opt.textContent = s;
            seriesFilter.appendChild(opt);
        });
        
        if (uniqueSeries.has(selectedVal)) {
            seriesFilter.value = selectedVal;
        } else {
            seriesFilter.value = "";
        }
    }

    // Fetch all runs
    async function fetchRuns() {
        try {
            const response = await fetch("/api/runs");
            if (!response.ok) throw new Error("Failed to fetch runs.");
            runs = response.ok ? await response.json() : [];
            populateSeriesFilter();
            renderRunsList();
        } catch (error) {
            console.error("Error fetching runs:", error);
            runsList.innerHTML = `<div class="empty-state"><p style="color: var(--color-flagged)">Error loading runs. Please check server logs.</p></div>`;
        }
    }

    // Fetch details of a single run
    async function fetchRunDetail(dateStr) {
        try {
            // Reset player source to prevent loading old videos
            videoPlayer.pause();
            videoPlayer.removeAttribute("src");
            videoPlayer.load();

            const response = await fetch(`/api/runs/${dateStr}`);
            if (!response.ok) throw new Error("Failed to fetch run details.");
            const detail = await response.json();
            renderRunDetail(detail);
        } catch (error) {
            console.error(`Error fetching detail for run ${dateStr}:`, error);
        }
    }

    // Update approval status
    async function updateRunStatus(dateStr, status) {
        try {
            const response = await fetch(`/api/runs/${dateStr}/status`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ status })
            });

            if (!response.ok) throw new Error("Failed to update status.");
            
            // Update local state
            const run = runs.find(r => r.date === dateStr);
            if (run) {
                run.approval_status = status;
            }

            // Update UI status badge immediately
            updateStatusBadge(status);

            // Re-render sidebar runs list to show new status dots
            renderRunsList();

            // If we are showing only unreviewed runs, auto-advance or show empty state
            if (currentFilter === "unreviewed") {
                // Find next unreviewed run
                const filtered = getFilteredRuns();
                if (filtered.length > 0) {
                    // Find index of current or choose first
                    const nextRun = filtered[0];
                    selectRun(nextRun.date);
                } else {
                    currentSelectedRunDate = null;
                    detailPane.classList.add("hidden");
                    emptyState.classList.remove("hidden");
                }
            }
        } catch (error) {
            console.error(`Error updating status for run ${dateStr}:`, error);
            alert("Error saving approval status.");
        }
    }

    // Trigger video generation pipeline
    async function startGeneration() {
        if (isGenerating) return;

        const dateStr = generateDate.value;
        const force = generateForce.checked;
        const topic = generateTopic.value ? generateTopic.value.trim() : null;
        const series = generateSeries.value ? generateSeries.value.trim() : null;
        const episodeVal = generateEpisode.value ? generateEpisode.value.trim() : null;
        const episode = episodeVal ? parseInt(episodeVal, 10) : null;

        if (!dateStr) {
            alert("Please select a date first.");
            return;
        }

        isGenerating = true;
        btnStartGeneration.disabled = true;
        btnStartGeneration.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Starting...`;
        consoleContainer.classList.remove("hidden");
        consoleOutput.textContent = "Connecting to pipeline orchestrator...\n";
        consolePulse.classList.add("active");

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ date_str: dateStr, force, topic, series, episode })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Failed to start generation.");
            }

            consoleOutput.textContent += `Pipeline triggered successfully for date ${dateStr}.\nStreaming execution logs...\n\n`;
            
            // Start polling logs and status
            startPollingStatusAndLogs(dateStr);

        } catch (error) {
            console.error("Error starting generation:", error);
            consoleOutput.textContent += `[ERROR] Failed to start pipeline: ${error.message}\n`;
            resetGeneratorButton("Generation Failed", "error");
        }
    }

    // Polling status and logs
    function startPollingStatusAndLogs(dateStr) {
        btnStartGeneration.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Generating...`;
        
        if (pollingInterval) clearInterval(pollingInterval);
        
        pollingInterval = setInterval(async () => {
            try {
                // 1. Fetch status
                const statusRes = await fetch("/api/generate/status");
                const status = await statusRes.json();

                // 2. Fetch logs
                const logsRes = await fetch("/api/generate/logs");
                const logsData = await logsRes.json();
                
                // Render logs in terminal
                if (logsData.logs) {
                    consoleOutput.textContent = logsData.logs;
                    // Auto scroll to bottom
                    consoleOutput.scrollTop = consoleOutput.scrollHeight;
                }

                // Check if completed
                if (!status.active && status.exit_code !== null) {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    
                    if (status.exit_code === 0) {
                        consoleOutput.textContent += "\n[SUCCESS] Pipeline execution finished successfully.";
                        resetGeneratorButton("Success!", "success");
                        // Refresh runs list
                        await fetchRuns();
                        // Automatically select the new run
                        selectRun(dateStr);
                    } else {
                        consoleOutput.textContent += `\n[ERROR] Pipeline failed with exit code: ${status.exit_code}`;
                        resetGeneratorButton("Failed!", "error");
                    }
                }
            } catch (error) {
                console.error("Error polling pipeline status:", error);
            }
        }, 1500);
    }

    function resetGeneratorButton(text, state) {
        isGenerating = false;
        consolePulse.classList.remove("active");
        btnStartGeneration.innerHTML = text;
        
        if (state === "success") {
            btnStartGeneration.style.backgroundColor = "var(--color-verified)";
        } else if (state === "error") {
            btnStartGeneration.style.backgroundColor = "var(--color-flagged)";
        }

        setTimeout(() => {
            btnStartGeneration.disabled = false;
            btnStartGeneration.innerHTML = `<i class="fa-solid fa-play"></i> Start Generation`;
            btnStartGeneration.style.backgroundColor = ""; // reset
        }, 4000);
    }

    // Check if generation is already running on page load
    async function checkActiveGeneration() {
        try {
            const response = await fetch("/api/generate/status");
            const status = await response.json();
            if (status.active && status.date) {
                isGenerating = true;
                btnStartGeneration.disabled = true;
                consoleContainer.classList.remove("hidden");
                consolePulse.classList.add("active");
                // Open widget body if collapsed
                generatorBody.classList.remove("hidden");
                btnToggleGenerator.classList.add("open");
                startPollingStatusAndLogs(status.date);
            }
        } catch (error) {
            console.error("Error checking active generation status:", error);
        }
    }

    // --------------------------------------------------------------------------
    // UI RENDERING
    // --------------------------------------------------------------------------

    // Helper to get filtered list based on current selection
    function getFilteredRuns() {
        const seriesFilterVal = seriesFilter ? seriesFilter.value : "";
        return runs.filter(run => {
            // Apply filter
            if (currentFilter === "unreviewed" && run.approval_status !== "unreviewed") {
                return false;
            }
            // Apply series filter
            if (seriesFilterVal && run.series !== seriesFilterVal) {
                return false;
            }
            // Apply search
            if (searchQuery) {
                const searchLower = searchQuery.toLowerCase();
                const titleMatch = run.title && run.title.toLowerCase().includes(searchLower);
                const dateMatch = run.date && run.date.includes(searchLower);
                return titleMatch || dateMatch;
            }
            return true;
        });
    }

    // Render Runs Card List in Sidebar
    function renderRunsList() {
        const filtered = getFilteredRuns();
        runsList.innerHTML = "";

        if (filtered.length === 0) {
            runsList.innerHTML = `<div class="empty-state" style="padding: 20px 0;"><p>No runs found matching filters.</p></div>`;
            return;
        }

        filtered.forEach(run => {
            const card = document.createElement("div");
            card.className = `run-card ${run.date === currentSelectedRunDate ? "active" : ""}`;
            card.setAttribute("data-date", run.date);
            
            // Warnings check
            const warningBadge = run.warnings_count > 0 
                ? `<span class="warn-badge"><i class="fa-solid fa-triangle-exclamation"></i> ${run.warnings_count}</span>` 
                : "";

            // Series badge check
            const seriesBadge = run.series 
                ? `<span class="series-badge" title="${run.series}${run.episode !== null ? ' Ep. ' + run.episode : ''}"><i class="fa-solid fa-layer-group"></i> ${run.series}${run.episode !== null ? ' Ep. ' + run.episode : ''}</span>`
                : "";

            card.innerHTML = `
                <div class="run-card-header">
                    <span class="run-card-date">${run.date}</span>
                    ${seriesBadge}
                    <div class="status-dot-container">
                        <span class="status-dot ${run.approval_status}"></span>
                        <span style="font-size: 11px; text-transform: capitalize; color: var(--text-secondary)">${run.approval_status}</span>
                    </div>
                </div>
                <div class="run-card-title">${run.title}</div>
                <div class="run-card-footer">
                    <div class="run-card-icons">
                        <span class="${run.has_video ? "active" : ""}" title="Video MP4 Available"><i class="fa-solid fa-play"></i></span>
                        <span class="${run.has_thumbnail ? "active" : ""}" title="Thumbnail Available"><i class="fa-regular fa-image"></i></span>
                        <span class="${run.has_script ? "active" : ""}" title="Script Available"><i class="fa-solid fa-file-lines"></i></span>
                    </div>
                    ${warningBadge}
                </div>
            `;

            card.addEventListener("click", () => selectRun(run.date));
            runsList.appendChild(card);
        });
    }

    // Change status badge style on the fly
    function updateStatusBadge(status) {
        detailStatus.textContent = status;
        detailStatus.className = `status-badge ${status}`;
    }

    // Render Detail View Panel
    function renderRunDetail(detail) {
        detailDate.textContent = detail.date;
        detailTitle.textContent = detail.title;
        updateStatusBadge(detail.approval_status);

        const detailSeriesBadge = document.getElementById("detail-series-badge");
        if (detailSeriesBadge) {
            if (detail.series) {
                detailSeriesBadge.textContent = `${detail.series}${detail.episode !== null ? ' Ep. ' + detail.episode : ''}`;
                detailSeriesBadge.classList.remove("hidden");
            } else {
                detailSeriesBadge.classList.add("hidden");
            }
        }

        // Render Video Player
        if (detail.video_url) {
            videoPlayer.src = `${detail.video_url}?t=${Date.now()}`;
            videoPlayer.classList.remove("hidden");
            videoError.classList.add("hidden");
        } else {
            videoPlayer.removeAttribute("src");
            videoPlayer.classList.add("hidden");
            videoError.classList.remove("hidden");
        }

        // Render Thumbnail Image
        if (detail.thumbnail_url) {
            thumbnailImg.src = `${detail.thumbnail_url}?t=${Date.now()}`;
            thumbnailImg.classList.remove("hidden");
            thumbnailError.classList.add("hidden");
        } else {
            thumbnailImg.src = "";
            thumbnailImg.classList.add("hidden");
            thumbnailError.classList.remove("hidden");
        }

        // Render Fact Check Report
        factCheckList.innerHTML = "";
        let verifiedCount = 0;
        let flaggedCount = 0;
        let unverifiedCount = 0;

        if (detail.fact_check && detail.fact_check.length > 0) {
            detail.fact_check.forEach(item => {
                const status = item.status.toLowerCase();
                if (status === "verified") verifiedCount++;
                else if (status === "flagged") flaggedCount++;
                else unverifiedCount++;

                const element = document.createElement("div");
                element.className = `fact-check-item ${status}`;
                element.innerHTML = `
                    <div class="fact-header">
                        <span class="fact-claim">${item.claim}</span>
                        <span class="fact-badge ${status}">${item.status}</span>
                    </div>
                    <div class="fact-explanation">${item.explanation}</div>
                `;
                factCheckList.appendChild(element);
            });

            // Update flags badge counter on tab header
            const totalWarnings = flaggedCount + unverifiedCount;
            badgeWarningCount.textContent = totalWarnings;
            if (totalWarnings > 0) {
                badgeWarningCount.classList.remove("hidden");
            } else {
                badgeWarningCount.classList.add("hidden");
            }

            factCheckSummaryText.innerHTML = `
                Report finished. Analyzed <strong>${detail.fact_check.length}</strong> major claims. 
                <span style="color: var(--color-flagged)">${flaggedCount} flagged</span>, 
                <span style="color: var(--color-unverified)">${unverifiedCount} unverified</span>, and 
                <span style="color: var(--color-verified)">${verifiedCount} verified</span>.
            `;
        } else {
            badgeWarningCount.classList.add("hidden");
            factCheckList.innerHTML = `<div class="empty-state" style="padding: 10px 0;"><p>No fact-check results found. Make sure the fact checker step (Step 04) ran.</p></div>`;
            factCheckSummaryText.innerHTML = "No fact-check report has been generated for this run.";
        }

        // Render SEO Metadata
        function renderTagsHelper(container, tagsList) {
            container.innerHTML = "";
            if (tagsList && tagsList.length > 0) {
                tagsList.forEach(tag => {
                    const chip = document.createElement("span");
                    chip.className = "tag-chip";
                    chip.textContent = tag;
                    container.appendChild(chip);
                });
            } else {
                container.innerHTML = `<span style="color: var(--text-muted); font-size: 13px;">No tags.</span>`;
            }
        }

        if (detail.seo) {
            if (detail.seo.part1) {
                seoTitlePart1.textContent = detail.seo.part1.title || "No Title.";
                seoDescPart1.textContent = detail.seo.part1.description || "No Description.";
                renderTagsHelper(seoTagsPart1, detail.seo.part1.tags);
                
                seoTitlePart2.textContent = detail.seo.part2.title || "No Title.";
                seoDescPart2.textContent = detail.seo.part2.description || "No Description.";
                renderTagsHelper(seoTagsPart2, detail.seo.part2.tags);
            } else {
                // Fallback for older non-split runs
                seoTitlePart1.textContent = detail.seo.title || "No Title.";
                seoDescPart1.textContent = detail.seo.description || "No Description.";
                renderTagsHelper(seoTagsPart1, detail.seo.tags);
                
                seoTitlePart2.textContent = "N/A (Older run)";
                seoDescPart2.textContent = "N/A";
                seoTagsPart2.innerHTML = `<span style="color: var(--text-muted); font-size: 13px;">No split parts in this run.</span>`;
            }
        } else {
            seoTitlePart1.textContent = "No SEO Title.";
            seoDescPart1.textContent = "No SEO Description.";
            seoTagsPart1.innerHTML = "";
            seoTitlePart2.textContent = "No SEO Title.";
            seoDescPart2.textContent = "No SEO Description.";
            seoTagsPart2.innerHTML = "";
        }

        // Render Script Text
        if (detail.script) {
            const escapedScript = detail.script
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
            
            const formattedScript = escapedScript.replace(
                /\[SPLIT POINT\]/g,
                `<div class="split-point-divider">
                    <span class="split-line"></span>
                    <span class="split-badge"><i class="fa-solid fa-scissors"></i> SHORTS SPLIT POINT</span>
                    <span class="split-line"></span>
                 </div>`
            );
            scriptContentBox.innerHTML = formattedScript;
        } else {
            scriptContentBox.innerHTML = `<span style="color: var(--text-muted);">No script text found (script.txt missing).</span>`;
        }

        // Reveal Pane
        emptyState.classList.add("hidden");
        detailPane.classList.remove("hidden");
    }

    // Select a run and update details
    function selectRun(dateStr) {
        currentSelectedRunDate = dateStr;
        
        // Highlight in sidebar
        document.querySelectorAll(".run-card").forEach(card => {
            if (card.getAttribute("data-date") === dateStr) {
                card.classList.add("active");
            } else {
                card.classList.remove("active");
            }
        });

        // Fetch details
        fetchRunDetail(dateStr);
    }

    // --------------------------------------------------------------------------
    // EVENTS & CONTROLS
    // --------------------------------------------------------------------------

    // Tab switcher
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");
            
            tabButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            document.getElementById(targetTab).classList.add("active");
        });
    });

    // Filtering tabs toggling
    btnFilterUnreviewed.addEventListener("click", () => {
        btnFilterUnreviewed.classList.add("active");
        btnFilterAll.classList.remove("active");
        currentFilter = "unreviewed";
        renderRunsList();
    });

    btnFilterAll.addEventListener("click", () => {
        btnFilterAll.classList.add("active");
        btnFilterUnreviewed.classList.remove("active");
        currentFilter = "all";
        renderRunsList();
    });

    // Search bar filtering
    searchInput.addEventListener("input", (e) => {
        searchQuery = e.target.value;
        renderRunsList();
    });

    // Approve & Reject Event Handlers
    btnApprove.addEventListener("click", () => {
        if (currentSelectedRunDate) {
            updateRunStatus(currentSelectedRunDate, "approved");
        }
    });

    btnReject.addEventListener("click", () => {
        if (currentSelectedRunDate) {
            updateRunStatus(currentSelectedRunDate, "rejected");
        }
    });

    if (btnDelete) {
        btnDelete.addEventListener("click", async () => {
            if (!currentSelectedRunDate) return;
            
            const confirmed = confirm(`Are you sure you want to delete all files and database records for the run: ${currentSelectedRunDate}? This action cannot be undone.`);
            if (!confirmed) return;
            
            try {
                // Pause and clear video player & thumbnail sources to release browser file locks
                if (videoPlayer) {
                    videoPlayer.pause();
                    videoPlayer.removeAttribute("src");
                    videoPlayer.load();
                }
                if (thumbnailImg) {
                    thumbnailImg.removeAttribute("src");
                }
                
                // Allow a brief moment for browser and server to release file descriptors
                await new Promise(resolve => setTimeout(resolve, 200));
                
                btnDelete.disabled = true;
                btnDelete.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Deleting...`;
                
                const response = await fetch(`/api/runs/${currentSelectedRunDate}`, {
                    method: "DELETE"
                });
                
                if (!response.ok) {
                    const errDetail = await response.json();
                    throw new Error(errDetail.detail || "Failed to delete the run.");
                }
                
                // Remove from local runs state
                runs = runs.filter(r => r.date !== currentSelectedRunDate);
                currentSelectedRunDate = null;
                
                // Reset detail view and reveal empty state
                detailPane.classList.add("hidden");
                emptyState.classList.remove("hidden");
                
                // Refresh filters and sidebar
                populateSeriesFilter();
                renderRunsList();
                
            } catch (error) {
                console.error("Error deleting run:", error);
                alert(`Failed to delete run: ${error.message}`);
            } finally {
                btnDelete.disabled = false;
                btnDelete.innerHTML = `<i class="fa-solid fa-trash-can"></i> Delete Run`;
            }
        });
    }

    // Set default date input value to today
    const today = new Date().toISOString().split("T")[0];
    generateDate.value = today;

    // Toggle Generator Widget Body collapse/expand
    btnToggleGenerator.addEventListener("click", () => {
        generatorBody.classList.toggle("hidden");
        btnToggleGenerator.classList.toggle("open");
    });

    // Start generation click listener
    btnStartGeneration.addEventListener("click", () => {
        startGeneration();
    });

    if (seriesFilter) {
        seriesFilter.addEventListener("change", () => {
            renderRunsList();
        });
    }

    // Initial Fetch & Active run checks
    fetchRuns();
    checkActiveGeneration();
});
