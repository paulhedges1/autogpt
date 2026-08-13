(() => {
  "use strict";

  const SECTION_DEFS = [
    { key: "introduction", label: "Overview" },
    { key: "lesson", label: "Lesson" },
    { key: "worked_example", label: "Worked example" },
    { key: "guided_practice", label: "Guided practice" },
    { key: "independent_challenge", label: "Independent challenge" },
    { key: "knowledge_check", label: "Knowledge check" },
    { key: "answers_feedback", label: "Answers & feedback" },
    { key: "confidence_reflection", label: "Confidence & reflection" },
    { key: "quick_reference", label: "Quick reference" },
  ];

  const STORAGE_PROGRESS = "dwta_progress_v1";
  const STORAGE_LEARNER = "dwta_learner_v1";

  const state = {
    content: null,
    progress: loadProgress(),
    learner: loadLearner(),
    currentModuleId: null,
    currentSection: "introduction",
    view: "module", // 'module' | 'capstone'
  };

  let saveTimer = null;

  // ---------- persistence ----------

  function loadProgress() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_PROGRESS)) || {};
    } catch {
      return {};
    }
  }

  function loadLearner() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_LEARNER)) || null;
    } catch {
      return null;
    }
  }

  function setProgress(key, value) {
    state.progress[key] = value;
    localStorage.setItem(STORAGE_PROGRESS, JSON.stringify(state.progress));
    scheduleSync(key, value);
  }

  function getProgress(key, fallback) {
    return Object.prototype.hasOwnProperty.call(state.progress, key) ? state.progress[key] : fallback;
  }

  let pendingSync = {};
  function scheduleSync(key, value) {
    if (!state.learner) return;
    pendingSync[key] = value;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSync, 900);
  }

  async function flushSync() {
    if (!state.learner || Object.keys(pendingSync).length === 0) return;
    const updates = pendingSync;
    pendingSync = {};
    try {
      await fetch(`/api/progress/${state.learner.code}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates }),
      });
    } catch {
      // offline: keep in localStorage, will retry on next change
      pendingSync = Object.assign(updates, pendingSync);
    }
  }

  async function pullFromServer(code) {
    const res = await fetch(`/api/progress/${code}`);
    if (!res.ok) throw new Error("code not found");
    const remote = await res.json();
    state.progress = Object.assign({}, remote, state.progress);
    localStorage.setItem(STORAGE_PROGRESS, JSON.stringify(state.progress));
  }

  // ---------- text formatting ----------

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function formatParagraph(text) {
    let html = escapeHtml(text);
    html = html.replace(/^([A-Z][A-Za-z0-9 ,'’]{2,40}:)(\s)/, "<strong>$1</strong>$2");
    return html;
  }

  // ---------- generic block rendering ----------

  function el(tag, className, html) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function renderBlock(block) {
    switch (block.type) {
      case "heading": {
        const lvl = Math.min(block.level + 1, 3); // doc H1->visual h2 etc, keep simple: map 1/2/3 -> our classes
        const tag = block.level === 1 ? "h2" : block.level === 2 ? "h3" : "h4";
        return el(tag, `block-heading-${block.level}`, escapeHtml(block.text));
      }
      case "paragraph":
        return el("p", "block-paragraph", formatParagraph(block.text));
      case "callout": {
        const wrap = el("div", "block-callout");
        const isRisk = /risk/i.test(block.label);
        wrap.appendChild(el("div", "callout-label" + (isRisk ? " risk" : ""), escapeHtml(block.label)));
        if (block.text) wrap.appendChild(el("div", "", formatParagraph(block.text)));
        return wrap;
      }
      case "table":
        return renderTable(block);
      case "checklist":
        return renderChecklist(block);
      case "input":
        return renderInput(block);
      case "confidence":
        return renderConfidence(block);
      default:
        return document.createDocumentFragment();
    }
  }

  function renderTable(block) {
    const wrap = el("div", "block-table-wrap");
    const table = el("table", "block-table");
    const rows = block.rows;
    if (rows.length > 1) {
      const thead = el("thead");
      const trh = el("tr");
      rows[0].forEach((cell) => trh.appendChild(el("th", "", escapeHtml(cell))));
      thead.appendChild(trh);
      table.appendChild(thead);
      const tbody = el("tbody");
      rows.slice(1).forEach((row) => {
        const tr = el("tr");
        row.forEach((cell) => tr.appendChild(el("td", "", escapeHtml(cell).replace(/\n/g, "<br>"))));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
    } else {
      const tbody = el("tbody");
      rows.forEach((row) => {
        const tr = el("tr");
        row.forEach((cell) => tr.appendChild(el("td", "", escapeHtml(cell).replace(/\n/g, "<br>"))));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
    }
    wrap.appendChild(table);
    return wrap;
  }

  function renderChecklist(block) {
    const ul = el("ul", "checklist");
    block.items.forEach((item, i) => {
      if (Array.isArray(item)) {
        item.forEach((opt, j) => ul.appendChild(checklistRow(`${block.id}.${i}.${j}`, opt)));
      } else {
        ul.appendChild(checklistRow(`${block.id}.${i}`, item));
      }
    });
    return ul;
  }

  function checklistRow(key, label) {
    const li = el("li", "checklist-item");
    const checked = !!getProgress(key, false);
    if (checked) li.classList.add("checked");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = checked;
    input.addEventListener("change", () => {
      setProgress(key, input.checked);
      li.classList.toggle("checked", input.checked);
      refreshSidebarProgress();
    });
    const span = el("span", "", escapeHtml(label));
    li.appendChild(input);
    li.appendChild(span);
    li.addEventListener("click", (e) => {
      if (e.target !== input) {
        input.checked = !input.checked;
        input.dispatchEvent(new Event("change"));
      }
    });
    return li;
  }

  function renderInput(block) {
    const wrap = el("div", "block-input-wrap");
    const ta = document.createElement("textarea");
    ta.className = "block-input";
    ta.value = getProgress(block.id, "");
    ta.placeholder = "Write your answer here…";
    let t;
    ta.addEventListener("input", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        setProgress(block.id, ta.value);
        refreshSidebarProgress();
      }, 350);
    });
    wrap.appendChild(ta);
    return wrap;
  }

  function renderConfidence(block) {
    const wrap = el("div", "confidence-widget");
    const row = el("div", "confidence-scale");
    const current = getProgress(block.id, null);
    block.scale.forEach((opt) => {
      const btn = el("button", "confidence-option");
      btn.type = "button";
      if (current === opt.value) btn.classList.add("selected");
      btn.innerHTML = `<span class="num">${opt.value}</span><span class="lbl">${escapeHtml(opt.label)}</span>`;
      btn.addEventListener("click", () => {
        setProgress(block.id, opt.value);
        row.querySelectorAll(".confidence-option").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        refreshSidebarProgress();
      });
      row.appendChild(btn);
    });
    wrap.appendChild(row);
    return wrap;
  }

  function renderOverview(rows) {
    if (!rows.length) return null;
    const dl = el("dl", "overview-grid");
    rows.forEach((r) => {
      const row = el("div", "overview-row");
      row.appendChild(el("dt", "", escapeHtml(r.label)));
      row.appendChild(el("dd", "", escapeHtml(r.value)));
      dl.appendChild(row);
    });
    return dl;
  }

  // ---------- knowledge check ----------

  function quizAnswerKey(moduleId, qNumber) {
    return `${moduleId}.kc.${qNumber}.answer`;
  }
  function quizCheckedKey(moduleId, qNumber) {
    return `${moduleId}.kc.${qNumber}.checked`;
  }
  function quizSelfMarkKey(moduleId, qNumber) {
    return `${moduleId}.kc.${qNumber}.selfmark`;
  }

  function questionAttempted(moduleId, q) {
    const ans = getProgress(quizAnswerKey(moduleId, q.number), null);
    if (q.options && q.options.length) return Array.isArray(ans) && ans.length > 0;
    return typeof ans === "string" && ans.trim().length > 0;
  }

  function renderKnowledgeCheck(module) {
    const kc = module.sections.knowledge_check;
    const container = document.createDocumentFragment();

    kc.intro_blocks.forEach((b) => container.appendChild(renderBlock(b)));

    const total = kc.questions.length;
    const attempted = kc.questions.filter((q) => questionAttempted(module.id, q)).length;
    const banner = el(
      "div",
      "quiz-score-banner",
      `<span>Knowledge check progress</span><span>${attempted} / ${total} answered</span>`
    );
    container.appendChild(banner);

    kc.questions.forEach((q) => container.appendChild(renderQuizQuestion(module.id, q)));
    return container;
  }

  function renderQuizQuestion(moduleId, q) {
    const wrap = el("div", "quiz-question");
    wrap.appendChild(el("div", "qnum", `Question ${q.number}${q.points ? ` · ${q.points} pts` : ""}`));
    wrap.appendChild(el("div", "quiz-prompt", formatParagraph(q.prompt)));
    if (q.free_text) {
      q.free_text.forEach((t) => wrap.appendChild(el("p", "block-paragraph", formatParagraph(t))));
    }

    const answerKey = quizAnswerKey(moduleId, q.number);
    const checkedKey = quizCheckedKey(moduleId, q.number);
    const feedbackHolder = el("div");

    if (q.options && q.options.length) {
      const selected = new Set(getProgress(answerKey, []));
      const optList = el("div", "quiz-options");
      q.options.forEach((opt, i) => {
        const row = el("label", "quiz-option");
        const input = document.createElement("input");
        input.type = q.multi ? "checkbox" : "radio";
        input.name = `q-${moduleId}-${q.number}`;
        input.checked = selected.has(i);
        input.addEventListener("change", () => {
          if (q.multi) {
            if (input.checked) selected.add(i); else selected.delete(i);
          } else {
            selected.clear();
            selected.add(i);
          }
          setProgress(answerKey, Array.from(selected));
          refreshSidebarProgress();
          if (getProgress(checkedKey, false)) renderQuizFeedback(moduleId, q, feedbackHolder, wrap);
        });
        row.appendChild(input);
        row.appendChild(el("span", "", escapeHtml(opt)));
        optList.appendChild(row);
      });
      wrap.appendChild(optList);
    } else {
      const ta = document.createElement("textarea");
      ta.className = "block-input";
      ta.placeholder = "Type your answer here…";
      ta.value = getProgress(answerKey, "");
      let t;
      ta.addEventListener("input", () => {
        clearTimeout(t);
        t = setTimeout(() => {
          setProgress(answerKey, ta.value);
          refreshSidebarProgress();
        }, 350);
      });
      wrap.appendChild(ta);
    }

    const actions = el("div", "quiz-actions");
    const checkBtn = el("button", "btn small", "Check my answer");
    checkBtn.type = "button";
    checkBtn.addEventListener("click", () => {
      setProgress(checkedKey, true);
      renderQuizFeedback(moduleId, q, feedbackHolder, wrap);
    });
    actions.appendChild(checkBtn);
    wrap.appendChild(actions);
    wrap.appendChild(feedbackHolder);

    if (getProgress(checkedKey, false)) {
      renderQuizFeedback(moduleId, q, feedbackHolder, wrap);
    }

    return wrap;
  }

  function renderQuizFeedback(moduleId, q, holder, questionEl) {
    holder.innerHTML = "";
    const answerKey = quizAnswerKey(moduleId, q.number);
    const selfMarkKey = quizSelfMarkKey(moduleId, q.number);
    const ans = getProgress(answerKey, q.options && q.options.length ? [] : "");

    if (q.options && q.options.length && q.correct_indices) {
      const selected = new Set(ans);
      const correct = new Set(q.correct_indices);
      const isRight =
        selected.size === correct.size && Array.from(selected).every((i) => correct.has(i));
      questionEl.querySelectorAll(".quiz-option").forEach((row, i) => {
        row.classList.remove("correct", "incorrect");
        if (correct.has(i)) row.classList.add("correct");
        else if (selected.has(i)) row.classList.add("incorrect");
      });
      const fb = el(
        "div",
        `quiz-feedback ${isRight ? "correct" : "incorrect"}`,
        isRight ? "Correct." : "Not quite — the correct option is highlighted above."
      );
      if (q.where_taught) fb.appendChild(el("span", "where", `Taught in: ${escapeHtml(q.where_taught)}`));
      holder.appendChild(fb);
      return;
    }

    // open / unmatched questions: reveal model answer, learner self-marks (mirrors the
    // workbook's own open-book self-marking design)
    const fb = el("div", "quiz-feedback info");
    fb.innerHTML = `<strong>Model answer:</strong> ${escapeHtml(q.correct_answer_text || "See the Answers and feedback section.")}`;
    if (q.where_taught) fb.appendChild(el("span", "where", `Taught in: ${escapeHtml(q.where_taught)}`));
    holder.appendChild(fb);

    const selfMark = el("div", "self-mark");
    const yesBtn = el("button", "btn small", "I got this right");
    const noBtn = el("button", "btn small", "I'll revise this");
    yesBtn.type = "button";
    noBtn.type = "button";
    const current = getProgress(selfMarkKey, null);
    if (current === true) yesBtn.style.outline = "2px solid var(--success)";
    if (current === false) noBtn.style.outline = "2px solid var(--warning)";
    yesBtn.addEventListener("click", () => {
      setProgress(selfMarkKey, true);
      refreshSidebarProgress();
      renderQuizFeedback(moduleId, q, holder, questionEl);
    });
    noBtn.addEventListener("click", () => {
      setProgress(selfMarkKey, false);
      refreshSidebarProgress();
      renderQuizFeedback(moduleId, q, holder, questionEl);
    });
    selfMark.appendChild(yesBtn);
    selfMark.appendChild(noBtn);
    holder.appendChild(selfMark);
  }

  // ---------- answers & feedback (gated) ----------

  function renderAnswersFeedback(module) {
    const frag = document.createDocumentFragment();
    const details = el("details", "answers-gate");
    const summary = el("summary", "", "Show model answers and feedback");
    details.appendChild(summary);
    const body = el("div");
    module.sections.answers_feedback.forEach((b) => body.appendChild(renderBlock(b)));
    details.appendChild(body);
    frag.appendChild(
      el(
        "p",
        "muted",
        "Try the guided practice, independent challenge and knowledge check first, then open this section to mark your own work."
      )
    );
    frag.appendChild(details);
    return frag;
  }

  // ---------- progress computation ----------

  function moduleProgress(module) {
    const parts = [];
    parts.push(getProgress(module.confidence_before.id, null) !== null ? 1 : 0);
    parts.push(getProgress(module.confidence_after.id, null) !== null ? 1 : 0);

    const cr = module.sections.confidence_reflection;
    const inputs = cr.filter((b) => b.type === "input");
    if (inputs.length) {
      const filled = inputs.filter((b) => (getProgress(b.id, "") || "").trim().length > 0).length;
      parts.push(filled / inputs.length);
    } else parts.push(0);

    const checklists = cr.filter((b) => b.type === "checklist");
    if (checklists.length) {
      let total = 0, checked = 0;
      checklists.forEach((cl) => cl.items.forEach((item, i) => {
        if (Array.isArray(item)) {
          item.forEach((_, j) => { total++; if (getProgress(`${cl.id}.${i}.${j}`, false)) checked++; });
        } else {
          total++; if (getProgress(`${cl.id}.${i}`, false)) checked++;
        }
      }));
      parts.push(total ? checked / total : 0);
    } else parts.push(0);

    const qs = module.sections.knowledge_check.questions;
    if (qs.length) {
      parts.push(qs.filter((q) => questionAttempted(module.id, q)).length / qs.length);
    } else parts.push(0);

    return Math.round((parts.reduce((a, b) => a + b, 0) / parts.length) * 100);
  }

  function overallProgress() {
    if (!state.content) return 0;
    const mods = state.content.modules;
    const sum = mods.reduce((acc, m) => acc + moduleProgress(m), 0);
    return Math.round(sum / mods.length);
  }

  // ---------- layout / navigation ----------

  function refreshSidebarProgress() {
    if (!state.content) return;
    document.querySelectorAll(".module-item").forEach((itemEl) => {
      const id = itemEl.dataset.moduleId;
      const module = state.content.modules.find((m) => m.id === id);
      if (!module) return;
      const pct = moduleProgress(module);
      itemEl.querySelector(".module-progress-fill").style.width = pct + "%";
    });
    const pct = overallProgress();
    document.getElementById("overallProgressLabel").textContent = pct + "%";
    document.getElementById("overallRing").style.background =
      `conic-gradient(var(--primary) ${pct * 3.6}deg, var(--border) 0deg)`;

    if (state.currentModuleId) {
      document.querySelectorAll(".section-tab").forEach((tab) => {
        const key = tab.dataset.section;
        if (key === "knowledge_check") {
          const module = state.content.modules.find((m) => m.id === state.currentModuleId);
          const qs = module.sections.knowledge_check.questions;
          const done = qs.length && qs.every((q) => questionAttempted(module.id, q));
          tab.querySelector(".tick")?.remove();
          if (done) tab.insertAdjacentHTML("beforeend", '<span class="tick">✓</span>');
        }
      });
    }
  }

  function buildSidebar() {
    const list = document.getElementById("moduleList");
    list.innerHTML = "";
    state.content.modules.forEach((m) => {
      const li = document.createElement("li");
      const btn = el("button", "module-item");
      btn.dataset.moduleId = m.id;
      btn.innerHTML = `
        <div class="module-item-top">
          <span class="module-num">${m.id}</span>
          <span class="module-title">${escapeHtml(m.title)}</span>
        </div>
        <div class="module-progress-track"><div class="module-progress-fill" style="width:${moduleProgress(m)}%"></div></div>
      `;
      btn.addEventListener("click", () => selectModule(m.id));
      li.appendChild(btn);
      list.appendChild(li);
    });

    const capBtn = document.getElementById("capstoneBtn");
    capBtn.textContent = "🏁 " + (state.content.capstone.title || "Volume 1 completion review");
    capBtn.addEventListener("click", selectCapstone);

    refreshActiveSidebarState();
  }

  function refreshActiveSidebarState() {
    document.querySelectorAll(".module-item").forEach((b) => {
      b.classList.toggle("active", state.view === "module" && b.dataset.moduleId === state.currentModuleId);
    });
    document.getElementById("capstoneBtn").classList.toggle("active", state.view === "capstone");
  }

  function selectModule(id, section) {
    state.view = "module";
    state.currentModuleId = id;
    state.currentSection = section || "introduction";
    refreshActiveSidebarState();
    renderModule();
    document.getElementById("content").focus();
  }

  function selectCapstone() {
    state.view = "capstone";
    refreshActiveSidebarState();
    renderCapstone();
  }

  function renderModule() {
    const module = state.content.modules.find((m) => m.id === state.currentModuleId);
    const content = document.getElementById("content");
    content.innerHTML = "";

    const header = el("div", "module-header");
    header.innerHTML = `<div class="eyebrow">Module ${module.id}</div><h1>${escapeHtml(module.title)}</h1>`;
    content.appendChild(header);

    const idx = state.content.modules.findIndex((m) => m.id === module.id);
    if (idx === state.content.modules.length - 1 && moduleProgress(module) >= 80) {
      const banner = el("div", "completion-banner", "🎉 Nearly there — once you've finished this module, visit the Volume 1 completion review.");
      content.appendChild(banner);
    }

    const tabs = el("div", "section-tabs");
    SECTION_DEFS.forEach((def) => {
      const tab = el("button", "section-tab", escapeHtml(def.label));
      tab.type = "button";
      tab.dataset.section = def.key;
      if (def.key === state.currentSection) tab.classList.add("active");
      tab.addEventListener("click", () => {
        state.currentSection = def.key;
        tabs.querySelectorAll(".section-tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        renderSection(module, def.key, sectionHost);
      });
      tabs.appendChild(tab);
    });
    content.appendChild(tabs);

    const sectionHost = el("div", "card");
    content.appendChild(sectionHost);
    renderSection(module, state.currentSection, sectionHost);
    refreshSidebarProgress();
  }

  function renderSection(module, key, host) {
    host.innerHTML = "";
    if (key === "introduction") {
      module.sections.introduction.forEach((b, i) => {
        host.appendChild(renderBlock(b));
        // insert confidence-before widget right after "Confidence before the module" heading
        if (b.type === "heading" && /confidence before/i.test(b.text)) {
          host.appendChild(renderBlock(module.confidence_before));
        }
      });
      const overview = renderOverview(module.overview);
      if (overview) host.insertBefore(overview, host.firstChild.nextSibling);
      return;
    }
    if (key === "knowledge_check") {
      host.appendChild(el("h2", "block-heading-1", "Check your learning"));
      host.appendChild(renderKnowledgeCheck(module));
      return;
    }
    if (key === "answers_feedback") {
      host.appendChild(el("h2", "block-heading-1", "Answers and feedback"));
      host.appendChild(renderAnswersFeedback(module));
      return;
    }
    if (key === "confidence_reflection") {
      module.sections.confidence_reflection.forEach((b) => {
        host.appendChild(renderBlock(b));
        if (b.type === "heading" && /confidence after/i.test(b.text)) {
          host.appendChild(renderBlock(module.confidence_after));
        }
      });
      return;
    }
    module.sections[key].forEach((b) => host.appendChild(renderBlock(b)));
  }

  function renderCapstone() {
    const content = document.getElementById("content");
    content.innerHTML = "";
    const header = el("div", "module-header");
    header.innerHTML = `<div class="eyebrow">Volume 1</div><h1>${escapeHtml(state.content.capstone.title)}</h1>`;
    content.appendChild(header);

    const summary = el("div", "card");
    summary.appendChild(el("h2", "block-heading-1", "Your progress across Volume 1"));
    const dl = el("dl", "overview-grid");
    state.content.modules.forEach((m) => {
      const row = el("div", "overview-row");
      row.appendChild(el("dt", "", escapeHtml(`${m.id} ${m.title}`)));
      row.appendChild(el("dd", "", `${moduleProgress(m)}% complete`));
      dl.appendChild(row);
    });
    summary.appendChild(dl);
    content.appendChild(summary);

    const card = el("div", "card");
    state.content.capstone.blocks.forEach((b) => card.appendChild(renderBlock(b)));
    content.appendChild(card);
  }

  // ---------- sync modal ----------

  function initSyncModal() {
    const backdrop = document.getElementById("syncModalBackdrop");
    const open = () => { backdrop.hidden = false; refreshSyncModal(); };
    const close = () => { backdrop.hidden = true; };
    document.getElementById("syncBtn").addEventListener("click", open);
    document.getElementById("closeSyncModal").addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });

    document.getElementById("createCodeBtn").addEventListener("click", async () => {
      const name = document.getElementById("learnerNameInput").value.trim();
      const status = document.getElementById("syncStatus");
      if (!name) { status.textContent = "Please enter a name."; status.className = "sync-status err"; return; }
      try {
        const res = await fetch("/api/learners", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        state.learner = { code: data.code, name: data.name };
        localStorage.setItem(STORAGE_LEARNER, JSON.stringify(state.learner));
        status.textContent = "Learner code created and progress syncing.";
        status.className = "sync-status ok";
        updateLearnerChip();
        flushAllProgress();
        refreshSyncModal();
      } catch {
        status.textContent = "Could not create a code right now. Please try again.";
        status.className = "sync-status err";
      }
    });

    document.getElementById("resumeBtn").addEventListener("click", async () => {
      const code = document.getElementById("resumeCodeInput").value.trim().toUpperCase();
      const status = document.getElementById("syncStatus");
      if (!code) { status.textContent = "Enter a learner code."; status.className = "sync-status err"; return; }
      try {
        const res = await fetch(`/api/learners/${code}`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        state.learner = { code: data.code, name: data.name };
        localStorage.setItem(STORAGE_LEARNER, JSON.stringify(state.learner));
        await pullFromServer(code);
        status.textContent = `Resumed as ${data.name}. Progress restored.`;
        status.className = "sync-status ok";
        updateLearnerChip();
        buildSidebar();
        if (state.view === "module") renderModule(); else renderCapstone();
        refreshSyncModal();
      } catch {
        status.textContent = "That code was not found.";
        status.className = "sync-status err";
      }
    });
  }

  function refreshSyncModal() {
    const noCode = document.getElementById("syncNoCode");
    const hasCode = document.getElementById("syncHasCode");
    if (state.learner) {
      noCode.hidden = true;
      hasCode.hidden = false;
      document.getElementById("codeDisplay").textContent = state.learner.code;
    } else {
      noCode.hidden = false;
      hasCode.hidden = true;
    }
  }

  function updateLearnerChip() {
    const chip = document.getElementById("learnerChip");
    if (state.learner) {
      chip.hidden = false;
      document.getElementById("learnerName").textContent = `${state.learner.name} · ${state.learner.code}`;
    } else {
      chip.hidden = true;
    }
  }

  function flushAllProgress() {
    if (!state.learner) return;
    pendingSync = Object.assign({}, state.progress, pendingSync);
    flushSync();
  }

  // ---------- boot ----------

  async function boot() {
    const res = await fetch("/api/content");
    state.content = await res.json();
    buildSidebar();
    updateLearnerChip();
    initSyncModal();
    selectModule(state.content.modules[0].id);
  }

  boot().catch((err) => {
    document.getElementById("content").innerHTML =
      `<div class="card"><h2>Could not load course content</h2><p class="muted">${escapeHtml(err.message)}</p></div>`;
  });
})();
