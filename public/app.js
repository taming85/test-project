/* 배터리 계약 레이더 프런트엔드
   - Supabase REST(PostgREST)에서 직접 읽는다 (anon/publishable key + RLS select 전용)
   - 빌드 없음: 정적 파일 그대로 Vercel 배포 */
(function () {
  "use strict";

  var CFG = window.__RADAR_CONFIG__ || {};
  var BASE = (CFG.supabaseUrl || "").replace(/\/+$/, "");
  var KEY = CFG.supabaseAnonKey || "";

  var state = { rows: [], filters: { customer: "", category: "", period: 365, q: "" } };

  /* ---------- utils ---------- */
  function fmtWon(won) {
    if (won === null || won === undefined) return null;
    if (won >= 1e12) return (won / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 2 }) + "조원";
    if (won >= 1e8) return (won / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "억원";
    if (won >= 1e4) return (won / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "만원";
    return won.toLocaleString("ko-KR") + "원";
  }
  function fmtEok(won) { return Math.round((won || 0) / 1e8).toLocaleString("ko-KR"); }
  function daysAgo(n) {
    var d = new Date(); d.setDate(d.getDate() - n);
    return d.toISOString().slice(0, 10);
  }
  function el(html) {
    var t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }
  function attr(v) { return String(v === null || v === undefined ? "" : v); }
  function esc(s) {
    return attr(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------- data ---------- */
  async function fetchJSON(path) {
    var res = await fetch(BASE + path, {
      headers: { apikey: KEY, Authorization: "Bearer " + KEY, Accept: "application/json" }
    });
    if (!res.ok) throw new Error("HTTP " + res.status + " — " + (await res.text()).slice(0, 160));
    return res.json();
  }

  async function load() {
    if (!BASE || !KEY) {
      document.getElementById("rows").innerHTML =
        '<tr><td colspan="7" class="empty">config.js 에 Supabase 접속 정보가 없습니다.</td></tr>';
      return;
    }
    try {
      var [rows, runs] = await Promise.all([
        fetchJSON("/contracts?select=*&order=contract_date.desc"),
        fetchJSON("/crawl_runs?select=*&order=id.desc&limit=1").catch(() => [])
      ]);
      state.rows = rows;
      renderLastRun(runs && runs[0]);
      render();
    } catch (e) {
      document.getElementById("rows").innerHTML =
        '<tr><td colspan="7" class="empty">데이터 조회 실패: ' + esc(e.message) + "</td></tr>";
    }
  }

  function renderLastRun(run) {
    var node = document.getElementById("last-run");
    if (!run) { node.textContent = "수집 정보 없음"; return; }
    var t = run.finished_at ? new Date(run.finished_at) : new Date(run.started_at);
    node.textContent =
      "최근 수집 " + t.toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) +
      " · 기사 " + attr(run.articles) + "건 중 계약 " + attr(run.events) + "건 (신규 " + attr(run.new_events) + ")";
    document.getElementById("footer-meta").textContent =
      "Radar v0.1 · run #" + attr(run.id) + " · " + attr(run.status);
  }

  /* ---------- KPI ---------- */
  function renderKPI(rows) {
    var total = rows.length;
    var sum = rows.reduce((a, r) => a + (r.amount_won || 0), 0);
    var undisclosed = rows.filter(r => !r.amount_won).length;
    var equip = rows.filter(r => r.category === "equipment");
    var equipSum = equip.reduce((a, r) => a + (r.amount_won || 0), 0);
    var cutoff = daysAgo(90);
    var recent = rows.filter(r => r.contract_date >= cutoff);

    document.getElementById("kpi-count").textContent = total.toLocaleString("ko-KR") + "건";
    document.getElementById("kpi-count-sub").textContent =
      "공급사 " + new Set(rows.map(r => r.supplier)).size + "개사 · 미공개 " + undisclosed + "건";

    document.getElementById("kpi-amount").textContent = sum ? fmtWon(sum) : "–";
    document.getElementById("kpi-amount-sub").textContent =
      sum ? "계약 1건 평균 " + fmtWon(Math.round(sum / rows.filter(r => r.amount_won).length || 0)) : "";

    document.getElementById("kpi-equip").textContent =
      total ? Math.round((equip.length / total) * 100) + "%" : "–";
    document.getElementById("kpi-equip-sub").textContent =
      equip.length + "건 · " + (equipSum ? fmtWon(equipSum) : "금액 미공개");

    document.getElementById("kpi-recent").textContent = recent.length + "건";
    document.getElementById("kpi-recent-sub").textContent =
      "최근 계약 " + (rows[0] ? rows[0].contract_date : "–");
  }

  /* ---------- monthly chart ---------- */
  function renderChart(rows) {
    var host = document.getElementById("monthly-chart");
    host.innerHTML = "";
    var buckets = {};
    rows.forEach(function (r) {
      if (!r.amount_won) return;
      var k = r.contract_date.slice(0, 7);
      buckets[k] = (buckets[k] || 0) + r.amount_won;
    });
    var keys = Object.keys(buckets).sort();
    if (!keys.length) {
      host.appendChild(el('<p class="bar-empty">금액이 확인된 계약이 없습니다.</p>'));
      return;
    }
    var max = Math.max.apply(null, keys.map(k => buckets[k]));
    keys.forEach(function (k) {
      var v = buckets[k];
      var wrap = el('<div class="bar-wrap"></div>');
      var val = el('<div class="bar-val">' + fmtEok(v) + "</div>");
      var bar = el('<div class="bar" tabindex="0"></div>');
      bar.style.height = Math.max(3, Math.round((v / max) * 100)) + "%";
      bar.title = k + " — " + fmtWon(v);
      bar.setAttribute("aria-label", k + " 총 " + fmtWon(v));
      var label = el('<div class="bar-label">' + k.slice(2) + "</div>");
      wrap.appendChild(val); wrap.appendChild(bar); wrap.appendChild(label);
      host.appendChild(wrap);
    });
  }

  /* ---------- leaderboard ---------- */
  function renderLeaderboard(rows) {
    var host = document.getElementById("leaderboard");
    host.innerHTML = "";
    var agg = {};
    rows.forEach(function (r) {
      var a = agg[r.supplier] = agg[r.supplier] || { sum: 0, n: 0, last: "" };
      a.sum += r.amount_won || 0; a.n += 1;
      if (r.contract_date > a.last) a.last = r.contract_date;
    });
    var list = Object.keys(agg).map(k => ({ name: k, ...agg[k] }))
      .sort((a, b) => b.sum - a.sum || b.n - a.n).slice(0, 8);
    if (!list.length) { host.appendChild(el('<li class="muted">데이터 없음</li>')); return; }
    var max = Math.max.apply(null, list.map(x => x.sum)) || 1;
    list.forEach(function (x) {
      var li = el(
        '<li title="' + esc(x.name + " · " + x.n + "건 · 최근 " + x.last) + '">' +
        '<span class="name">' + esc(x.name) + "</span>" +
        '<span class="track"><span class="fill" style="width:' + Math.max(4, (x.sum / max) * 100) + '%"></span></span>' +
        '<span class="amt">' + (x.sum ? fmtWon(x.sum) : "미공개") + "</span></li>"
      );
      host.appendChild(li);
    });
  }

  /* ---------- table ---------- */
  function renderTable(rows) {
    var host = document.getElementById("rows");
    host.innerHTML = "";
    document.getElementById("row-count").textContent = rows.length;
    if (!rows.length) {
      host.appendChild(el('<tr><td colspan="7" class="empty">조건에 맞는 계약이 없습니다.</td></tr>'));
      return;
    }
    rows.forEach(function (r) {
      var amount = r.amount_won
        ? "<strong>" + fmtWon(r.amount_won) + "</strong>"
        : '<span class="undisclosed">미공개</span>';
      var cat = r.category === "equipment"
        ? '<span class="chip equipment">설비·장비</span>'
        : '<span class="chip parts">부품·모듈</span>';
      var d = r.detail || {};
      var extra = [];
      if (d.revenue_ratio) extra.push("매출액 대비 " + d.revenue_ratio + "%");
      if (d.region) extra.push("지역 " + d.region);
      if (d.usd) extra.push("약 " + Number(d.usd).toLocaleString("en-US") + " USD");
      if (d.hold_reason) extra.push("공시유보: " + d.hold_reason + (d.hold_until ? " (~" + d.hold_until + ")" : ""));
      var verified = r.source_kind === "dart";
      var badge = verified
        ? '<span class="chip dart" title="' + esc(extra.join(" · ") || "DART 공시 원문 확인") + '">공시 정본</span>'
        : '<span class="chip news" title="언론 보도 기반">보도</span>';
      var title = r.url
        ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.title || "") + "</a>"
        : esc(r.title || "");
      var tr = el(
        "<tr><td>" + esc(r.contract_date) + "</td>" +
        "<td><strong>" + esc(r.supplier) + "</strong></td>" +
        "<td>" + esc(r.customer) + "</td>" +
        '<td class="num">' + amount + "</td>" +
        "<td>" + cat + "</td>" +
        '<td class="title-cell">' + title +
        (extra.length ? '<div class="detail-line">' + esc(extra.join(" · ")) + "</div>" : "") +
        "</td>" +
        "<td>" + badge + "</td></tr>"
      );
      host.appendChild(tr);
    });
  }

  /* ---------- render / filters ---------- */
  function applyFilters(rows) {
    var f = state.filters;
    return rows.filter(function (r) {
      if (f.customer && r.customer.indexOf(f.customer) === -1) return false;
      if (f.category && r.category !== f.category) return false;
      if (f.period && r.contract_date < daysAgo(f.period)) return false;
      if (f.q) {
        var hay = (r.supplier + " " + (r.title || "") + " " + r.customer).toLowerCase();
        if (hay.indexOf(f.q.toLowerCase()) === -1) return false;
      }
      return true;
    });
  }

  function render() {
    var rows = applyFilters(state.rows);
    renderKPI(state.rows);
    renderChart(rows);
    renderLeaderboard(state.rows);
    renderTable(rows);
  }

  function bindFilters() {
    var map = [["f-customer", "customer"], ["f-category", "category"], ["f-period", "period"]];
    map.forEach(function (pair) {
      var node = document.getElementById(pair[0]);
      node.addEventListener("change", function () {
        state.filters[pair[1]] = pair[1] === "period" ? Number(node.value) : node.value;
        render();
      });
    });
    var q = document.getElementById("f-search");
    var timer;
    q.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { state.filters.q = q.value.trim(); render(); }, 200);
    });
  }

  function bindTheme() {
    var btn = document.getElementById("theme-toggle");
    var saved = null;
    try { saved = localStorage.getItem("radar-theme"); } catch (e) {}
    var initial = saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", initial);
    btn.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("radar-theme", next); } catch (e) {}
    });
  }

  bindTheme();
  bindFilters();
  load();
})();
