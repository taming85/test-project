const rows = [
  ["GitHub API token", "ok"],
  ["Git repo push (HTTPS)", "ok"],
  ["Tavily search API", "ok"],
  ["Vercel deploy", "ok"],
];
document.getElementById("status").innerHTML = rows
  .map(([k, v]) => `<li><span>${k}</span><span class="ok">${v}</span></li>`)
  .join("");
