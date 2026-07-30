function $(id) {
  return document.getElementById(id);
}

function queryValue(name) {
  return new URLSearchParams(window.location.search).get(name);
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

function renderSimpleList(containerId, items, emptyText, badgeClass = "badge") {
  const box = $(containerId);
  box.innerHTML = (items || []).length
    ? items.map((item) => `<div class="${badgeClass}">${item}</div>`).join("")
    : `<div class="empty">${emptyText}</div>`;
}

function renderHeadline(report) {
  $("report-symbol").textContent = report.symbol || "评估报告";
  $("report-title").textContent = `${report.name || report.symbol} · ${report.rating || "N/A"}`;
  $("report-subtitle").textContent = `${report.industry || "行业待识别"} · 行情基准日 ${report.data_as_of_date || "--"} · 财报期 ${report.report_period || "--"}`;
  $("report-meta-badges").innerHTML = `
    <span class="rating-badge ${ratingClass(report.rating)}">评级 ${report.rating || "N/A"}</span>
    <span class="badge">规则 ${report.rule_version || "--"}</span>
    <span class="badge">指引 ${report.guidance_version || "--"}</span>
  `;
  $("headline-cards").innerHTML = `
    <div class="mini-card">
      <div class="small-label">综合得分</div>
      <div class="metric-value">${report.total_score == null ? "缺失" : `${report.total_score.toFixed(2)} 分`}</div>
      <div class="metric-subtitle">以当前可得指标自动计算</div>
    </div>
    <div class="mini-card">
      <div class="small-label">市场</div>
      <div class="metric-value">${report.market || "--"}</div>
      <div class="metric-subtitle">个人研究场景</div>
    </div>
    <div class="mini-card">
      <div class="small-label">扣分点</div>
      <div class="metric-value">${(report.deductions || []).length}</div>
      <div class="metric-subtitle">优先看最短板</div>
    </div>
    <div class="mini-card">
      <div class="small-label">数据完整度</div>
      <div class="metric-value">${report.data_completeness == null ? "--" : `${report.data_completeness.toFixed(1)}%`}</div>
      <div class="metric-subtitle">缺失 ${report.missing_indicator_count || 0} 项指标</div>
    </div>
    <div class="mini-card">
      <div class="small-label">结论可信度</div>
      <div class="metric-value">${report.confidence_level || "--"}</div>
      <div class="metric-subtitle">基于可得数据与口径完整度</div>
    </div>
  `;
  $("advice-text").innerHTML = `
    ${(report.conclusion_sections || [])
      .map(
        (item) => `
          <div style="margin-bottom:14px;">
            <div class="small-label" style="margin-bottom:6px;">${item.title}</div>
            <div>${item.content}</div>
          </div>
        `
      )
      .join("")}
    <div class="list">
      ${(report.deductions || []).map((item) => `<div class="badge warn">${item}</div>`).join("") || '<div class="badge">暂无扣分点</div>'}
    </div>
  `;
  $("signal-tags").innerHTML = (report.signal_tags || []).length
    ? report.signal_tags.map((item) => `<span class="chip good">${item}</span>`).join("")
    : '<span class="chip">暂无信号标签</span>';
}

function renderIndicators(report) {
  const body = $("indicator-body");
  const indicators = report.indicators || [];
  if (!indicators.length) {
    body.innerHTML = '<tr><td colspan="5">暂无指标数据</td></tr>';
    return;
  }
  body.innerHTML = indicators
    .map((item) => `
      <tr>
        <td>${item.dimension_name}</td>
        <td>${item.indicator_name}</td>
        <td>${item.display_text || "-"}</td>
        <td>${item.score == null ? "缺失" : item.score.toFixed(2)}</td>
        <td>${item.notes || "-"}</td>
      </tr>
    `)
    .join("");
}

function renderTags(report) {
  $("tag-list").innerHTML = (report.tags || []).length
    ? report.tags.map((item) => `<span class="chip good">${item}</span>`).join("")
    : '<span class="chip">暂无标签</span>';
}

function renderNotes(report) {
  const notes = report.notes || [];
  $("note-list").innerHTML = notes.length
    ? notes
        .map(
          (note) => `
            <div class="list-row">
              <div class="list-meta">${note.created_at}</div>
              <div>${note.content}</div>
            </div>
          `
        )
        .join("")
    : '<div class="empty">暂无研究笔记</div>';
}

function renderIndustryBaseline(report) {
  const baseline = report.industry_baseline || {};
  const entries = [
    ["样本数", baseline.sample_n],
    ["PE 中位数", baseline.pe_ttm_median],
    ["PB 中位数", baseline.pb_median],
    ["PS 中位数", baseline.ps_ttm_median],
  ].filter((item) => item[1] != null && item[1] !== "");
  $("industry-baseline").innerHTML = entries.length
    ? entries
        .map(
          ([label, value]) => `
            <div class="list-row">
              <div class="list-head">
                <div class="list-title">${label}</div>
                <div class="metric-value" style="font-size:20px;margin:0;">${typeof value === "number" ? value.toFixed(2) : value}</div>
              </div>
            </div>
          `
        )
        .join("")
    : '<div class="empty">当前行业基线仅接入估值参考，若数据源未返回则会显示为空。</div>';
}

function renderDimensionInsights(report) {
  const items = report.dimension_insights || [];
  $("dimension-insights").innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="mini-card">
              <div class="list-head">
                <div>
                  <div class="small-label">${item.name}</div>
                  <div class="metric-value" style="font-size:22px;margin-top:8px;">${item.score == null ? "缺失" : item.score.toFixed(2)}</div>
                </div>
                <span class="badge">${item.bucket}</span>
              </div>
              <div class="metric-subtitle" style="margin-top:14px;">权重 ${(item.weight * 100).toFixed(0)}%</div>
              <div style="margin-top:10px;line-height:1.7;">${item.comment}</div>
            </div>
          `
        )
        .join("")
    : '<div class="empty">暂无维度解读</div>';
}

function renderRadar(report) {
  const chart = echarts.init($("radar-chart"));
  const dims = report.dimension_scores || [];
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: {},
    radar: {
      radius: "65%",
      splitNumber: 5,
      axisName: { color: "#d5deeb" },
      splitArea: { areaStyle: { color: ["rgba(255,255,255,0.02)", "rgba(255,255,255,0.04)"] } },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.18)" } },
      indicator: dims.map((item) => ({ name: item.name, max: 100 })),
    },
    series: [{
      type: "radar",
      data: [{
        value: dims.map((item) => item.score || 0),
        areaStyle: { color: "rgba(73,220,177,0.18)" },
        lineStyle: { color: "#49dcb1", width: 2 },
        itemStyle: { color: "#49dcb1" },
      }],
    }],
  });
}

function renderHistory(items) {
  const chart = echarts.init($("history-chart"));
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 36, right: 18, top: 18, bottom: 32 },
    xAxis: {
      type: "category",
      data: items.map((item) => item.data_as_of_date || item.created_at || ""),
      axisLabel: { color: "#95a6bf" },
      axisLine: { lineStyle: { color: "rgba(255,255,255,0.12)" } },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: "#95a6bf" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
    },
    tooltip: { trigger: "axis" },
    series: [{
      type: "line",
      smooth: true,
      data: items.map((item) => item.total_score || 0),
      lineStyle: { color: "#f0c36b", width: 3 },
      itemStyle: { color: "#f0c36b" },
      areaStyle: { color: "rgba(240,195,107,0.12)" },
    }],
  });
}

async function loadHistory(symbol) {
  const history = await apiGet(`/api/v1/comparisons/history/${symbol}`);
  renderHistory(history.items || []);
}

async function saveTags(report) {
  const tags = $("tag-input").value
    .split(/,|，/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!tags.length) {
    window.alert("请输入至少一个标签。");
    return;
  }
  const data = await apiPost(`/api/v1/evaluations/${report.evaluation_id}/tags`, { tags });
  report.tags = data.tags || [];
  $("tag-input").value = "";
  renderTags(report);
}

async function saveNote(report) {
  const content = $("note-input").value.trim();
  if (!content) {
    window.alert("请输入笔记内容。");
    return;
  }
  await apiPost("/api/v1/notes", {
    symbol: report.symbol,
    evaluation_id: report.evaluation_id,
    content,
  });
  $("note-input").value = "";
  const refreshed = await apiGet(`/api/v1/evaluations/${report.evaluation_id}`);
  report.notes = refreshed.notes || [];
  renderNotes(report);
}

async function init() {
  const evaluationId = queryValue("evaluation_id");
  if (!evaluationId) {
    window.alert("缺少 evaluation_id 参数。");
    return;
  }
  const report = await apiGet(`/api/v1/evaluations/${evaluationId}`);
  renderHeadline(report);
  renderIndicators(report);
  renderTags(report);
  renderNotes(report);
  renderIndustryBaseline(report);
  renderSimpleList("strength-list", report.strengths, "暂无明显亮点", "badge good");
  renderSimpleList("risk-list", report.risks, "暂无显著风险提示", "badge bad");
  renderSimpleList("watch-list", report.watch_items, "暂无额外跟踪要点", "badge warn");
  renderDimensionInsights(report);
  renderRadar(report);
  await loadHistory(report.symbol);
  $("save-tag-btn").addEventListener("click", () => saveTags(report).catch((error) => window.alert(error.message)));
  $("save-note-btn").addEventListener("click", () => saveNote(report).catch((error) => window.alert(error.message)));
}

init().catch((error) => {
  console.error(error);
  window.alert(`加载失败：${error.message}`);
});
