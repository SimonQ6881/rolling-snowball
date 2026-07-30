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

function ratingClass(rating) {
  return rating ? `rating-${rating}` : "rating-D";
}

function buildQuery() {
  const params = new URLSearchParams();
  const symbol = $("filter-symbol").value.trim();
  const rating = $("filter-rating").value.trim();
  const industry = $("filter-industry").value.trim();
  if (symbol) params.set("symbol", symbol);
  if (rating) params.set("rating", rating);
  if (industry) params.set("industry", industry);
  return params.toString();
}

function renderGroups(items) {
  $("group-list").innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="list-row">
              <div class="list-title">${item.name}</div>
              <div class="list-meta">${item.memo || "未填写说明"}</div>
            </div>
          `
        )
        .join("")
    : '<div class="empty">尚未创建分组</div>';
}

function renderAssets(items) {
  $("asset-list").innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="list-row clickable" onclick="window.location.href='/stock-evaluation/report.html?evaluation_id=${item.evaluation_id}'">
              <div class="list-head">
                <div>
                  <div class="list-title">${item.name}</div>
                  <div class="list-meta">${item.symbol} · ${item.industry || "行业待识别"} · ${item.created_at}</div>
                </div>
                <div class="badge-row">
                  <span class="rating-badge ${ratingClass(item.rating)}">${item.rating || "N/A"}</span>
                  <span class="badge">${item.total_score == null ? "缺失" : `${item.total_score.toFixed(2)} 分`}</span>
                </div>
              </div>
            </div>
          `
        )
        .join("")
    : '<div class="empty">当前条件下暂无历史评估</div>';
}

async function loadGroups() {
  const data = await apiGet("/api/v1/groups");
  renderGroups(data.items || []);
}

async function loadAssets() {
  const query = buildQuery();
  const data = await apiGet(`/api/v1/evaluations${query ? `?${query}` : ""}`);
  renderAssets(data.items || []);
}

async function createGroup() {
  const name = $("group-name").value.trim();
  const memo = $("group-memo").value.trim();
  if (!name) {
    window.alert("请输入分组名称。");
    return;
  }
  await apiPost("/api/v1/groups", { name, memo });
  $("group-name").value = "";
  $("group-memo").value = "";
  await loadGroups();
}

function exportCsv() {
  window.open("/api/v1/analysis/export?dataset=evaluations&format=csv", "_blank");
}

async function init() {
  await Promise.all([loadGroups(), loadAssets()]);
  $("save-group-btn").addEventListener("click", () => createGroup().catch((error) => window.alert(error.message)));
  $("filter-btn").addEventListener("click", () => loadAssets().catch((error) => window.alert(error.message)));
  $("export-btn").addEventListener("click", exportCsv);
}

init().catch((error) => {
  console.error(error);
  window.alert(`加载失败：${error.message}`);
});
