const state = {
  taskId: null,
  pollTimer: null,
};

function $(id) {
  return document.getElementById(id);
}

async function apiGet(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || "请求失败");
  }
  return payload.data;
}

async function apiPost(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || "请求失败");
  }
  return payload.data;
}

function splitCodes() {
  return $("code-input").value
    .split(/\n|,|，/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderGuidance(data) {
  $("guidance-version").textContent = data.version_id || "--";
  $("guidance-date").textContent = `数据日期 ${data.as_of_date || "--"}`;
  $("token-status").textContent = data.token_ready ? "已接线" : "未配置";
  const list = $("guidance-tracks");
  list.innerHTML = "";
  (data.tracks || []).forEach((text) => {
    const row = document.createElement("div");
    row.className = "list-row";
    row.innerHTML = `
      <div class="list-title">${text}</div>
      <div class="list-meta">${data.headline || ""}</div>
    `;
    list.appendChild(row);
  });
}

function renderValidation(items) {
  const box = $("validation-list");
  if (!items.length) {
    box.innerHTML = '<div class="empty">没有可展示的校验结果</div>';
    return;
  }
  box.innerHTML = items
    .map((item) => {
      const badge = item.ok ? '<span class="badge good">通过</span>' : '<span class="badge bad">失败</span>';
      const meta = item.ok
        ? `${item.symbol} · ${item.market || "--"} ${item.name ? `· ${item.name}` : ""}`
        : item.error_message;
      return `
        <div class="list-row">
          <div class="list-head">
            <div class="list-title">${item.input_code || "-"}</div>
            ${badge}
          </div>
          <div class="list-meta">${meta}</div>
        </div>
      `;
    })
    .join("");
}

function ratingClass(rating) {
  if (!rating) return "rating-D";
  return `rating-${rating}`;
}

function renderRecent(items) {
  const box = $("recent-evaluations");
  if (!items.length) {
    box.innerHTML = '<div class="empty">暂无历史评估记录</div>';
    return;
  }
  box.innerHTML = items
    .map((item) => {
      const scoreText = item.total_score == null ? "待完善" : `${item.total_score.toFixed(2)} 分`;
      return `
        <div class="mini-card">
          <div class="list-head">
            <div>
              <div class="small-label">${item.symbol}</div>
              <div class="list-title">${item.name}</div>
            </div>
            <span class="rating-badge ${ratingClass(item.rating)}">${item.rating || "N/A"}</span>
          </div>
          <div class="metric-value" style="font-size:24px;margin-top:18px;">${scoreText}</div>
          <div class="list-meta">${item.industry || "行业待识别"} · ${item.created_at || ""}</div>
          <div style="margin-top:16px;">
            <a class="badge good" href="/stock-evaluation/report.html?evaluation_id=${item.evaluation_id}">打开报告</a>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderTask(task) {
  const badgeMap = {
    pending: '<span class="badge warn">排队中</span>',
    running: '<span class="badge good">运行中</span>',
    success: '<span class="badge good">已完成</span>',
    partial: '<span class="badge warn">部分完成</span>',
    failed: '<span class="badge bad">失败</span>',
  };
  $("task-status-wrap").innerHTML = badgeMap[task.status] || '<span class="badge">未知</span>';
  const progress = task.total_count ? ((task.done_count + task.failed_count) / task.total_count) * 100 : 0;
  $("task-progress-panel").className = "";
  $("task-progress-panel").innerHTML = `
    <div class="list">
      <div class="list-row">
        <div class="list-head">
          <div class="list-title">任务 ${task.task_id}</div>
          <div class="list-meta">完成 ${task.done_count} / ${task.total_count}，失败 ${task.failed_count}</div>
        </div>
        <div class="task-bar"><span style="width:${progress.toFixed(2)}%"></span></div>
      </div>
      ${(task.items || [])
        .map((item) => {
          const action = item.evaluation_id
            ? `<a class="badge good" href="/stock-evaluation/report.html?evaluation_id=${item.evaluation_id}">查看报告</a>`
            : `<span class="badge bad">${item.error_msg || "失败"}</span>`;
          return `
            <div class="list-row">
              <div class="list-head">
                <div>
                  <div class="list-title">${item.name || item.symbol}</div>
                  <div class="list-meta">${item.symbol} ${item.total_score != null ? `· ${item.total_score} 分` : ""}</div>
                </div>
                ${action}
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

async function loadRecent() {
  const data = await apiGet("/api/v1/evaluations");
  renderRecent((data.items || []).slice(0, 6));
}

async function pollTask() {
  if (!state.taskId) return;
  const data = await apiGet(`/api/v1/evaluations/tasks/${state.taskId}`);
  renderTask(data);
  if (["success", "partial", "failed"].includes(data.status)) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
    await loadRecent();
  }
}

async function runValidation() {
  const codes = splitCodes();
  if (!codes.length) {
    window.alert("请先输入股票代码。");
    return;
  }
  const data = await apiPost("/api/v1/validation/stock-codes", { codes });
  renderValidation(data.items || []);
}

async function submitTask() {
  const codes = splitCodes();
  if (!codes.length) {
    window.alert("请先输入股票代码。");
    return;
  }
  await runValidation();
  const data = await apiPost("/api/v1/evaluations/tasks", { codes, force: false });
  state.taskId = data.task_id;
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
  }
  await pollTask();
  state.pollTimer = window.setInterval(pollTask, 1800);
}

async function init() {
  const guidance = await apiGet("/api/v1/guidance/latest");
  renderGuidance(guidance);
  await loadRecent();

  $("validate-btn").addEventListener("click", () => runValidation().catch((error) => window.alert(error.message)));
  $("submit-btn").addEventListener("click", () => submitTask().catch((error) => window.alert(error.message)));
  $("reset-btn").addEventListener("click", () => {
    $("code-input").value = "";
    renderValidation([]);
  });
}

init().catch((error) => {
  console.error(error);
  window.alert(`初始化失败：${error.message}`);
});
