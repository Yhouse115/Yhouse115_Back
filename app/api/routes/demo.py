from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Demo Testing Page"])

DEMO_HTML_CONTENT = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WhyHouse REST API (API 1~5) Testing Page</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-color: #0b0f19;
      --card-bg: rgba(22, 29, 45, 0.9);
      --card-border: rgba(255, 255, 255, 0.1);
      --accent-color: #3b82f6;
      --accent-hover: #2563eb;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --success-color: #10b981;
      --code-bg: #030712;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', system-ui, sans-serif; }
    body { background-color: var(--bg-color); color: var(--text-main); padding: 24px; max-width: 1200px; margin: 0 auto; line-height: 1.5; }

    header { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border); }
    .header-title h1 { font-size: 1.6rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
    .header-title p { font-size: 0.9rem; color: var(--text-muted); margin-top: 4px; }

    /* Quick Nav */
    .nav-bar { display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; position: sticky; top: 0; background: var(--bg-color); padding: 8px 0; z-index: 10; }
    .nav-link { background: rgba(255, 255, 255, 0.05); border: 1px solid var(--card-border); color: var(--text-muted); text-decoration: none; padding: 8px 14px; border-radius: 6px; font-size: 0.84rem; font-weight: 500; transition: all 0.2s; }
    .nav-link:hover { background: var(--accent-color); color: #fff; border-color: var(--accent-color); }

    /* Standalone API Section Card */
    .api-card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 20px; margin-bottom: 28px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3); }
    .api-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--card-border); padding-bottom: 12px; }
    .api-title { font-size: 1.1rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }
    .method-badge { background: #10b981; color: #000; font-weight: 700; font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; }
    .endpoint-url { font-family: monospace; color: #60a5fa; font-size: 0.95rem; }

    /* Form Layout */
    .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .form-group label { display: block; font-size: 0.8rem; font-weight: 500; color: var(--text-muted); margin-bottom: 4px; }
    .form-control { width: 100%; background: #111827; border: 1px solid rgba(255, 255, 255, 0.15); color: #fff; padding: 8px 10px; border-radius: 6px; font-size: 0.85rem; outline: none; }
    .form-control:focus { border-color: var(--accent-color); }

    .btn-exec { background: var(--accent-color); color: #fff; border: none; padding: 10px 20px; border-radius: 6px; font-size: 0.875rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    .btn-exec:hover { background: var(--accent-hover); }

    .quick-btn { background: rgba(255,255,255,0.08); border: 1px solid var(--card-border); color: var(--text-muted); padding: 2px 6px; border-radius: 4px; font-size: 0.72rem; cursor: pointer; margin-top: 4px; margin-right: 4px; }
    .quick-btn:hover { color: #fff; background: rgba(255,255,255,0.2); }

    /* Result Display */
    .result-box { margin-top: 16px; background: var(--code-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; }
    .result-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 0.8rem; color: var(--text-muted); }
    .status-badge { font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .status-200 { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .status-err { background: rgba(239, 68, 68, 0.2); color: #f87171; }

    pre { font-family: monospace; font-size: 0.8125rem; color: #e5e7eb; overflow-x: auto; max-height: 350px; white-space: pre-wrap; word-break: break-all; }
  </style>
</head>
<body>

  <header>
    <div class="header-title">
      <h1>WhyHouse API Testing Page</h1>
      <p>API #1 ~ API #5 독립형 개별 테스트 & 디버깅 페이지 (.me/api_dev.md 명세 기준)</p>
    </div>
  </header>

  <!-- Quick Nav -->
  <div class="nav-bar">
    <a href="#api-1" class="nav-link">API #1 (/summary/inventory)</a>
    <a href="#api-2" class="nav-link">API #2 (/summary/transaction-count)</a>
    <a href="#api-3" class="nav-link">API #3 (/transactions/trades)</a>
    <a href="#api-4" class="nav-link">API #4 (/transactions/rents)</a>
    <a href="#api-5" class="nav-link">API #5 (/developments)</a>
  </div>

  <!-- API #1 -->
  <div id="api-1" class="api-card">
    <div class="api-header">
      <div class="api-title">
        <span class="method-badge">GET</span>
        <span>API #1 - 행정동 내 주거 부동산 유형 구성</span>
      </div>
      <span class="endpoint-url">/summary/inventory</span>
    </div>
    <form onsubmit="event.preventDefault(); callApi1();">
      <div class="form-grid">
        <div class="form-group">
          <label>admin_dong_code (행정동 10자리 코드)</label>
          <input type="text" id="api1_dong" class="form-control" value="1147051000">
          <div>
            <button type="button" class="quick-btn" onclick="document.getElementById('api1_dong').value='1147051000'; callApi1();">목1동</button>
            <button type="button" class="quick-btn" onclick="document.getElementById('api1_dong').value='1147062000'; callApi1();">신정1동</button>
            <button type="button" class="quick-btn" onclick="document.getElementById('api1_dong').value='1147064000'; callApi1();">신정3동</button>
          </div>
        </div>
      </div>
      <button type="submit" class="btn-exec">API #1 요청 전송</button>
    </form>
    <div class="result-box">
      <div class="result-header">
        <span id="api1_status" class="status-badge status-200">READY</span>
        <span id="api1_time">0 ms</span>
      </div>
      <pre id="api1_result">// API #1 결과가 여기에 표시됩니다...</pre>
    </div>
  </div>

  <!-- API #2 -->
  <div id="api-2" class="api-card">
    <div class="api-header">
      <div class="api-title">
        <span class="method-badge">GET</span>
        <span>API #2 - 거래량 불러오기</span>
      </div>
      <span class="endpoint-url">/summary/transaction-count</span>
    </div>
    <form onsubmit="event.preventDefault(); callApi2();">
      <div class="form-grid">
        <div class="form-group">
          <label>admin_dong_code</label>
          <input type="text" id="api2_dong" class="form-control" value="1147051000">
        </div>
        <div class="form-group">
          <label>period_start (YYYY-MM-DD)</label>
          <input type="date" id="api2_start" class="form-control" value="2026-05-14">
        </div>
        <div class="form-group">
          <label>period_end (YYYY-MM-DD)</label>
          <input type="date" id="api2_end" class="form-control" value="2026-08-12">
        </div>
        <div class="form-group">
          <label>transaction_type (콤마구분)</label>
          <input type="text" id="api2_txtype" class="form-control" value="TRADE,JEONSE" placeholder="TRADE,JEONSE,MONTHLY">
        </div>
        <div class="form-group">
          <label>building_type (콤마구분)</label>
          <input type="text" id="api2_bldtype" class="form-control" value="APT,OFFICETEL" placeholder="APT,TOWNHOUSE,OFFICETEL">
        </div>
      </div>
      <button type="submit" class="btn-exec">API #2 요청 전송</button>
    </form>
    <div class="result-box">
      <div class="result-header">
        <span id="api2_status" class="status-badge status-200">READY</span>
        <span id="api2_time">0 ms</span>
      </div>
      <pre id="api2_result">// API #2 결과가 여기에 표시됩니다...</pre>
    </div>
  </div>

  <!-- API #3 -->
  <div id="api-3" class="api-card">
    <div class="api-header">
      <div class="api-title">
        <span class="method-badge">GET</span>
        <span>API #3 - 매매 실거래가 리스트 조회</span>
      </div>
      <span class="endpoint-url">/transactions/trades</span>
    </div>
    <form onsubmit="event.preventDefault(); callApi3();">
      <div class="form-grid">
        <div class="form-group">
          <label>admin_dong_code (선택)</label>
          <input type="text" id="api3_dong" class="form-control" value="1147062000">
        </div>
        <div class="form-group">
          <label>period_start (필수)</label>
          <input type="date" id="api3_start" class="form-control" value="2025-01-01">
        </div>
        <div class="form-group">
          <label>period_end (필수)</label>
          <input type="date" id="api3_end" class="form-control" value="2026-08-12">
        </div>
        <div class="form-group">
          <label>building_type</label>
          <input type="text" id="api3_bldtype" class="form-control" value="APT" placeholder="APT, TOWNHOUSE">
        </div>
        <div class="form-group">
          <label>apt_name (검색어)</label>
          <input type="text" id="api3_apt" class="form-control" placeholder="예: 목동, 센트럴">
        </div>
        <div class="form-group">
          <label>min_deal_amount (만원)</label>
          <input type="number" id="api3_min_amt" class="form-control" placeholder="최소 매매가">
        </div>
        <div class="form-group">
          <label>max_deal_amount (만원)</label>
          <input type="number" id="api3_max_amt" class="form-control" placeholder="최대 매매가">
        </div>
        <div class="form-group">
          <label>page</label>
          <input type="number" id="api3_page" class="form-control" value="1">
        </div>
        <div class="form-group">
          <label>size</label>
          <input type="number" id="api3_size" class="form-control" value="5">
        </div>
      </div>
      <button type="submit" class="btn-exec">API #3 요청 전송</button>
    </form>
    <div class="result-box">
      <div class="result-header">
        <span id="api3_status" class="status-badge status-200">READY</span>
        <span id="api3_time">0 ms</span>
      </div>
      <pre id="api3_result">// API #3 결과가 여기에 표시됩니다...</pre>
    </div>
  </div>

  <!-- API #4 -->
  <div id="api-4" class="api-card">
    <div class="api-header">
      <div class="api-title">
        <span class="method-badge">GET</span>
        <span>API #4 - 전월세 실거래가 리스트 조회</span>
      </div>
      <span class="endpoint-url">/transactions/rents</span>
    </div>
    <form onsubmit="event.preventDefault(); callApi4();">
      <div class="form-grid">
        <div class="form-group">
          <label>admin_dong_code (선택)</label>
          <input type="text" id="api4_dong" class="form-control" value="1147062000">
        </div>
        <div class="form-group">
          <label>period_start (필수)</label>
          <input type="date" id="api4_start" class="form-control" value="2026-05-14">
        </div>
        <div class="form-group">
          <label>period_end (필수)</label>
          <input type="date" id="api4_end" class="form-control" value="2026-08-12">
        </div>
        <div class="form-group">
          <label>rent_type (JEONSE / MONTHLY)</label>
          <select id="api4_renttype" class="form-control">
            <option value="">전체</option>
            <option value="JEONSE" selected>JEONSE (전세)</option>
            <option value="MONTHLY">MONTHLY (월세)</option>
          </select>
        </div>
        <div class="form-group">
          <label>building_type</label>
          <input type="text" id="api4_bldtype" class="form-control" value="APT">
        </div>
        <div class="form-group">
          <label>apt_name (검색어)</label>
          <input type="text" id="api4_apt" class="form-control" placeholder="예: 목동파크">
        </div>
        <div class="form-group">
          <label>min_deposit (만원)</label>
          <input type="number" id="api4_min_dep" class="form-control" placeholder="50000">
        </div>
        <div class="form-group">
          <label>max_deposit (만원)</label>
          <input type="number" id="api4_max_dep" class="form-control" placeholder="90000">
        </div>
        <div class="form-group">
          <label>page</label>
          <input type="number" id="api4_page" class="form-control" value="1">
        </div>
        <div class="form-group">
          <label>size</label>
          <input type="number" id="api4_size" class="form-control" value="5">
        </div>
      </div>
      <button type="submit" class="btn-exec">API #4 요청 전송</button>
    </form>
    <div class="result-box">
      <div class="result-header">
        <span id="api4_status" class="status-badge status-200">READY</span>
        <span id="api4_time">0 ms</span>
      </div>
      <pre id="api4_result">// API #4 결과가 여기에 표시됩니다...</pre>
    </div>
  </div>

  <!-- API #5 -->
  <div id="api-5" class="api-card">
    <div class="api-header">
      <div class="api-title">
        <span class="method-badge">GET</span>
        <span>API #5 - 정비사업 이력 조회</span>
      </div>
      <span class="endpoint-url">/developments</span>
    </div>
    <form onsubmit="event.preventDefault(); callApi5();">
      <div class="form-grid">
        <div class="form-group">
          <label>admin_dong_code (선택)</label>
          <input type="text" id="api5_dong" class="form-control" value="1147064000">
        </div>
        <div class="form-group">
          <label>dev_type (REDEVELOPMENT / RECONSTRUCTION)</label>
          <select id="api5_devtype" class="form-control">
            <option value="">전체</option>
            <option value="REDEVELOPMENT" selected>REDEVELOPMENT (재개발)</option>
            <option value="RECONSTRUCTION">RECONSTRUCTION (재건축)</option>
          </select>
        </div>
        <div class="form-group">
          <label>project_name (검색어)</label>
          <input type="text" id="api5_proj" class="form-control" placeholder="예: 신정1-1">
        </div>
        <div class="form-group">
          <label>stage_code (단계 코드)</label>
          <select id="api5_stage" class="form-control">
            <option value="">전체 단계</option>
            <option value="STAGE_1">STAGE_1 (정비구역지정)</option>
            <option value="STAGE_2">STAGE_2 (조합설립인가)</option>
            <option value="STAGE_3">STAGE_3 (사업시행인가)</option>
            <option value="STAGE_4">STAGE_4 (관리처분인가)</option>
            <option value="STAGE_5">STAGE_5 (착공·분양)</option>
            <option value="STAGE_6">STAGE_6 (준공·입주완료)</option>
          </select>
        </div>
        <div class="form-group">
          <label>page</label>
          <input type="number" id="api5_page" class="form-control" value="1">
        </div>
        <div class="form-group">
          <label>size</label>
          <input type="number" id="api5_size" class="form-control" value="5">
        </div>
      </div>
      <button type="submit" class="btn-exec">API #5 요청 전송</button>
    </form>
    <div class="result-box">
      <div class="result-header">
        <span id="api5_status" class="status-badge status-200">READY</span>
        <span id="api5_time">0 ms</span>
      </div>
      <pre id="api5_result">// API #5 결과가 여기에 표시됩니다...</pre>
    </div>
  </div>

  <script>
    const API_BASE = window.location.origin;

    async function executeFetch(url, statusId, timeId, resultId) {
      const statusEl = document.getElementById(statusId);
      const timeEl = document.getElementById(timeId);
      const resultEl = document.getElementById(resultId);

      statusEl.className = "status-badge status-200";
      statusEl.innerText = "LOADING...";
      resultEl.innerText = "Fetching data...";

      const t0 = performance.now();
      try {
        const res = await fetch(url);
        const t1 = performance.now();
        timeEl.innerText = `${Math.round(t1 - t0)} ms`;

        statusEl.innerText = `${res.status} ${res.statusText || 'OK'}`;
        if (res.ok) {
          statusEl.className = "status-badge status-200";
        } else {
          statusEl.className = "status-badge status-err";
        }

        const json = await res.json();
        resultEl.innerText = JSON.stringify(json, null, 2);
      } catch (err) {
        timeEl.innerText = "ERROR";
        statusEl.className = "status-badge status-err";
        statusEl.innerText = "FAILED";
        resultEl.innerText = `Fetch Error: ${err.message}\nTarget URL: ${url}`;
      }
    }

    function callApi1() {
      const dong = document.getElementById("api1_dong").value.trim();
      const url = `${API_BASE}/summary/inventory?admin_dong_code=${dong}`;
      executeFetch(url, "api1_status", "api1_time", "api1_result");
    }

    function callApi2() {
      const dong = document.getElementById("api2_dong").value.trim();
      const start = document.getElementById("api2_start").value;
      const end = document.getElementById("api2_end").value;
      const txtype = document.getElementById("api2_txtype").value.trim();
      const bldtype = document.getElementById("api2_bldtype").value.trim();

      const params = new URLSearchParams({ admin_dong_code: dong, period_start: start, period_end: end });
      if (txtype) params.append("transaction_type", txtype);
      if (bldtype) params.append("building_type", bldtype);

      const url = `${API_BASE}/summary/transaction-count?${params.toString()}`;
      executeFetch(url, "api2_status", "api2_time", "api2_result");
    }

    function callApi3() {
      const dong = document.getElementById("api3_dong").value.trim();
      const start = document.getElementById("api3_start").value;
      const end = document.getElementById("api3_end").value;
      const bldtype = document.getElementById("api3_bldtype").value.trim();
      const apt = document.getElementById("api3_apt").value.trim();
      const minAmt = document.getElementById("api3_min_amt").value;
      const maxAmt = document.getElementById("api3_max_amt").value;
      const page = document.getElementById("api3_page").value || 1;
      const size = document.getElementById("api3_size").value || 5;

      const params = new URLSearchParams({ period_start: start, period_end: end, page, size });
      if (dong) params.append("admin_dong_code", dong);
      if (bldtype) params.append("building_type", bldtype);
      if (apt) params.append("apt_name", apt);
      if (minAmt) params.append("min_deal_amount", minAmt);
      if (maxAmt) params.append("max_deal_amount", maxAmt);

      const url = `${API_BASE}/transactions/trades?${params.toString()}`;
      executeFetch(url, "api3_status", "api3_time", "api3_result");
    }

    function callApi4() {
      const dong = document.getElementById("api4_dong").value.trim();
      const start = document.getElementById("api4_start").value;
      const end = document.getElementById("api4_end").value;
      const renttype = document.getElementById("api4_renttype").value;
      const bldtype = document.getElementById("api4_bldtype").value.trim();
      const apt = document.getElementById("api4_apt").value.trim();
      const minDep = document.getElementById("api4_min_dep").value;
      const maxDep = document.getElementById("api4_max_dep").value;
      const page = document.getElementById("api4_page").value || 1;
      const size = document.getElementById("api4_size").value || 5;

      const params = new URLSearchParams({ period_start: start, period_end: end, page, size });
      if (dong) params.append("admin_dong_code", dong);
      if (renttype) params.append("rent_type", renttype);
      if (bldtype) params.append("building_type", bldtype);
      if (apt) params.append("apt_name", apt);
      if (minDep) params.append("min_deposit", minDep);
      if (maxDep) params.append("max_deposit", maxDep);

      const url = `${API_BASE}/transactions/rents?${params.toString()}`;
      executeFetch(url, "api4_status", "api4_time", "api4_result");
    }

    function callApi5() {
      const dong = document.getElementById("api5_dong").value.trim();
      const devtype = document.getElementById("api5_devtype").value;
      const proj = document.getElementById("api5_proj").value.trim();
      const stage = document.getElementById("api5_stage").value;
      const page = document.getElementById("api5_page").value || 1;
      const size = document.getElementById("api5_size").value || 5;

      const params = new URLSearchParams({ page, size });
      if (dong) params.append("admin_dong_code", dong);
      if (devtype) params.append("dev_type", devtype);
      if (proj) params.append("project_name", proj);
      if (stage) params.append("stage_code", stage);

      const url = `${API_BASE}/developments?${params.toString()}`;
      executeFetch(url, "api5_status", "api5_time", "api5_result");
    }

    window.onload = () => {
      callApi1();
    };
  </script>
</body>
</html>
"""

@router.get("/demo", response_class=HTMLResponse)
async def get_demo_page():
    return HTMLResponse(content=DEMO_HTML_CONTENT)
