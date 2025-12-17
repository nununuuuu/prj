// static/js/main.js

let mainChart = null;
let lockedDatasets = [];
let lastChartData = null;
let currentMode = 'basic'; // 'basic' or 'advanced'

// 定義策略選項與參數
// 這裡的 key 必須對應到 backend strategy.py 的 check_signal
const STRATEGY_DEFINITIONS = {
    // 進場
    'ENTRY': {
        'SMA_CROSS': { name: '均線黃金交叉', params: [{ k: 'n_short', l: '短MA', v: 10 }, { k: 'n_long', l: '長MA', v: 60 }] },
        'RSI_OVERSOLD': { name: 'RSI 超賣', params: [{ k: 'period', l: '週期', v: 14 }, { k: 'threshold', l: '閾值 <', v: 30 }] },
        'MACD_GOLDEN': { name: 'MACD 黃金交叉', params: [{ k: 'fast', l: '快線', v: 12 }, { k: 'slow', l: '慢線', v: 26 }, { k: 'signal', l: 'Signal', v: 9 }] },
        'KD_GOLDEN': { name: 'KD 黃金交叉', params: [{ k: 'period', l: '週期', v: 9 }, { k: 'threshold', l: 'D值 <', v: 20 }] },
        'BB_BREAK': { name: '布林通道突破', params: [{ k: 'period', l: '週期', v: 20 }, { k: 'std', l: '標準差', v: 2.0 }] }
    },
    // 出場
    'EXIT': {
        'SMA_DEATH': { name: '均線死亡交叉', params: [{ k: 'n_short', l: '短MA', v: 10 }, { k: 'n_long', l: '長MA', v: 60 }] },
        'RSI_OVERBOUGHT': { name: 'RSI 超買', params: [{ k: 'period', l: '週期', v: 14 }, { k: 'threshold', l: '閾值 >', v: 70 }] },
        'MACD_DEATH': { name: 'MACD 死亡交叉', params: [{ k: 'fast', l: '快線', v: 12 }, { k: 'slow', l: '慢線', v: 26 }, { k: 'signal', l: 'Signal', v: 9 }] },
        'KD_DEATH': { name: 'KD 死亡交叉', params: [{ k: 'period', l: '週期', v: 9 }, { k: 'threshold', l: 'D值 >', v: 80 }] },
        'BB_REVERSE': { name: '布林通道反轉', params: [{ k: 'period', l: '週期', v: 20 }, { k: 'std', l: '標準差', v: 2.0 }] }
    }
};

document.addEventListener('DOMContentLoaded', function () {
    console.log("System Ready: Smart Investment Dashboard v4.0 (Advanced Mode)");

    // 日期初始化
    const formatDate = (date) => {
        const d = new Date(date);
        let month = '' + (d.getMonth() + 1);
        let day = '' + d.getDate();
        const year = d.getFullYear();
        if (month.length < 2) month = '0' + month;
        if (day.length < 2) day = '0' + day;
        return [year, month, day].join('-');
    };

    const today = new Date();
    const start = new Date();
    start.setFullYear(today.getFullYear() - 3);

    const endDateInput = document.getElementById('end_date');
    const startDateInput = document.getElementById('start_date');

    if (endDateInput && startDateInput) {
        endDateInput.value = formatDate(today);
        startDateInput.value = formatDate(start);
    }

    const tickerInput = document.getElementById('ticker');
    if (tickerInput) tickerInput.addEventListener('input', handleTickerInput);

    const lockBtn = document.getElementById('lockBtn');
    if (lockBtn) lockBtn.addEventListener('click', handleLockChart);

    window.addEventListener('themeChanged', function () {
        if (lastChartData) {
            setTimeout(() => {
                renderMainChart(lastChartData.priceData, lastChartData.trades, lastChartData.equityData, lastChartData.bhData);
            }, 50);
        }
    });

    // 初始化下拉選單
    initStrategySelects();
});

function initStrategySelects() {
    const fills = [
        { id: 'entry_strategy_1', type: 'ENTRY' },
        { id: 'entry_strategy_2', type: 'ENTRY' },
        { id: 'exit_strategy_1', type: 'EXIT' },
        { id: 'exit_strategy_2', type: 'EXIT' }
    ];

    fills.forEach(item => {
        const sel = document.getElementById(item.id);
        const opts = STRATEGY_DEFINITIONS[item.type];
        for (const [key, val] of Object.entries(opts)) {
            const opt = document.createElement('option');
            opt.value = key;
            opt.text = val.name;
            sel.appendChild(opt);
        }
    });
}

function switchMode(mode) {
    currentMode = mode;
    const basicDiv = document.getElementById('basic-settings');
    const advDiv = document.getElementById('advanced-settings');
    const tabBasic = document.getElementById('tab-basic');
    const tabAdv = document.getElementById('tab-advanced');

    // 說明區塊與副標題
    const descBasic = document.getElementById('desc-basic');
    const descAdv = document.getElementById('desc-advanced');
    const subBasic = document.getElementById('subtitle-basic');
    const subAdv = document.getElementById('subtitle-advanced');

    if (mode === 'basic') {
        basicDiv.classList.remove('hidden');
        advDiv.classList.add('hidden');

        tabBasic.className = "flex-1 py-1.5 rounded-md shadow-sm bg-white dark:bg-slate-600 text-blue-600 dark:text-blue-400 transition-all";
        tabAdv.className = "flex-1 py-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-all";

        // 顯示基礎說明與副標題
        descBasic.classList.remove('hidden');
        subBasic.classList.remove('hidden');

        // 隱藏進階說明與副標題
        descAdv.classList.add('hidden');
        subAdv.classList.add('hidden');

    } else {
        basicDiv.classList.add('hidden');
        advDiv.classList.remove('hidden');

        tabBasic.className = "flex-1 py-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-all";
        tabAdv.className = "flex-1 py-1.5 rounded-md shadow-sm bg-white dark:bg-slate-600 text-blue-600 dark:text-blue-400 transition-all";

        // 隱藏基礎說明與副標題
        descBasic.classList.add('hidden');
        subBasic.classList.add('hidden');

        // 顯示進階說明與副標題
        descAdv.classList.remove('hidden');
        subAdv.classList.remove('hidden');
    }
}

// 動態產生參數輸入框
function renderParams(type, index) {
    const selectId = `${type}_strategy_${index}`;
    const containerId = `${type}_params_${index}_container`;

    const selectedValue = document.getElementById(selectId).value;
    const container = document.getElementById(containerId);
    container.innerHTML = ''; // 清空

    if (!selectedValue) return;

    const group = type === 'entry' ? 'ENTRY' : 'EXIT';
    const config = STRATEGY_DEFINITIONS[group][selectedValue];

    if (config && config.params) {
        config.params.forEach(p => {
            const div = document.createElement('div');

            const label = document.createElement('label');
            label.className = "block text-[10px] text-gray-500 dark:text-gray-400 mb-0.5";
            label.innerText = p.l;

            const input = document.createElement('input');
            input.type = "number";
            input.step = p.v % 1 === 0 ? "1" : "0.1"; // 整數或浮點
            input.value = p.v;
            input.className = "w-full border border-gray-200 dark:border-slate-600 rounded p-1 text-xs bg-white dark:bg-slate-700 dark:text-white param-input";
            input.dataset.key = p.k; // 存參數名

            div.appendChild(label);
            div.appendChild(input);
            container.appendChild(div);
        });
    }
}

function getDynamicParams(type, index) {
    const selectId = `${type}_strategy_${index}`;
    const containerId = `${type}_params_${index}_container`;
    const selectedValue = document.getElementById(selectId).value;

    if (!selectedValue) return [null, {}];

    const params = {};
    const inputs = document.querySelectorAll(`#${containerId} input`);
    inputs.forEach(inp => {
        params[inp.dataset.key] = parseFloat(inp.value);
    });

    return [selectedValue, params];
}

function handleTickerInput(e) {
    const val = e.target.value.trim().toUpperCase();
    const hint = document.getElementById('tickerHint');
    const buyInput = document.getElementById('buy_fee');
    const sellInput = document.getElementById('sell_fee');

    if (/^\d/.test(val) || val.endsWith('.TW')) {
        if (val.startsWith('00')) {
            buyInput.value = 0.1425; sellInput.value = 0.2425; hint.innerText = "偵測到: 台股 ETF";
        } else {
            buyInput.value = 0.1425; sellInput.value = 0.4425; hint.innerText = "偵測到: 台股 個股";
        }
    } else if (val.length > 0) {
        buyInput.value = 0.1; sellInput.value = 0.1; hint.innerText = "偵測到: 美股";
    } else {
        hint.innerText = "請輸入代碼...";
    }
}

async function executeBacktest() {
    console.log("Backtest started...");
    const tickerInput = document.getElementById('ticker');
    const ticker = tickerInput.value.trim();
    if (!ticker) { alert("請輸入股票代碼！"); return; }

    const btn = document.getElementById('runBtn');
    const originalText = btn.innerHTML;
    const chartContainer = document.getElementById('chartContainer');

    btn.disabled = true;
    btn.innerHTML = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> 運算中...`;
    chartContainer.classList.add('opacity-50', 'pointer-events-none');
    document.body.style.cursor = 'wait';

    // 基礎參數
    let payload = {
        ticker: ticker,
        start_date: document.getElementById('start_date').value,
        end_date: document.getElementById('end_date').value,
        cash: parseFloat(document.getElementById('cash').value),
        buy_fee_pct: parseFloat(document.getElementById('buy_fee').value),
        sell_fee_pct: parseFloat(document.getElementById('sell_fee').value),
        stop_loss_pct: parseFloat(document.getElementById('sl_pct').value),
        take_profit_pct: parseFloat(document.getElementById('tp_pct').value),
        trailing_stop_pct: parseFloat(document.getElementById('ts_pct').value) || 0,
        strategy_mode: currentMode
    };

    if (currentMode === 'basic') {
        payload.ma_short = parseInt(document.getElementById('ma_short').value);
        payload.ma_long = parseInt(document.getElementById('ma_long').value);
        payload.rsi_period_entry = parseInt(document.getElementById('rsi_period_entry').value);
        payload.rsi_buy_threshold = parseInt(document.getElementById('rsi_buy_threshold').value);
        payload.rsi_period_exit = parseInt(document.getElementById('rsi_period_exit').value);
        payload.rsi_sell_threshold = parseInt(document.getElementById('rsi_sell_threshold').value);
    } else {
        // Advanced Mode Data Gathering
        const [e1_name, e1_params] = getDynamicParams('entry', 1);
        const [e2_name, e2_params] = getDynamicParams('entry', 2);
        const [x1_name, x1_params] = getDynamicParams('exit', 1);
        const [x2_name, x2_params] = getDynamicParams('exit', 2);

        payload.entry_strategy_1 = e1_name;
        payload.entry_params_1 = e1_params;
        payload.entry_strategy_2 = e2_name;
        payload.entry_params_2 = e2_params;

        payload.exit_strategy_1 = x1_name;
        payload.exit_params_1 = x1_params;
        payload.exit_strategy_2 = x2_name;
        payload.exit_params_2 = x2_params;
    }

    try {
        const res = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "請求失敗");
        }

        const data = await res.json();
        updateDashboard(data);

    } catch (err) {
        alert('錯誤: ' + err.message);
        console.error(err);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
        chartContainer.classList.remove('opacity-50', 'pointer-events-none');
        document.body.style.cursor = 'default';
    }
}

function updateDashboard(data) {
    updateCard('res_total_return', data.total_return, true);
    const bhEl = document.getElementById('res_bh_return');
    bhEl.innerText = (data.buy_and_hold_return > 0 ? '+' : '') + data.buy_and_hold_return + '%';
    bhEl.className = "text-3xl font-bold mt-1 " + (data.buy_and_hold_return > 0 ? "text-teal-600 dark:text-teal-400" : (data.buy_and_hold_return < 0 ? "text-red-500 dark:text-red-400" : "text-gray-300 dark:text-gray-600"));

    document.getElementById('res_final_equity').innerText = '$' + data.final_equity.toLocaleString();

    const winRateEl = document.getElementById('res_win_rate');
    winRateEl.innerText = data.win_rate + '%';
    winRateEl.classList.remove('text-gray-300', 'dark:text-gray-600');
    winRateEl.classList.add('text-gray-900', 'dark:text-white');
    document.getElementById('res_trades').innerText = `${data.winning_trades} / ${data.total_trades}`;

    updateTableValue('tbl_total_return', data.total_return, true);
    updateTableValue('tbl_ann_return', data.annual_return, true);
    updateTableValue('tbl_sharpe', data.sharpe_ratio, true);

    const mddEl = document.getElementById('tbl_mdd');
    mddEl.innerText = Math.abs(data.max_drawdown) + '%';
    mddEl.className = "p-3 font-bold text-right text-red-500 dark:text-red-400";

    updateTableValue('tbl_win_rate', data.win_rate, true);

    const pnlEl = document.getElementById('res_avg_pnl');
    const pnlVal = data.avg_pnl;
    const sign = pnlVal > 0 ? '+' : '';
    pnlEl.innerText = `${sign}${pnlVal.toLocaleString()}`;
    pnlEl.className = "p-3 font-bold text-right " + (pnlVal >= 0 ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400");

    document.getElementById('res_consec_loss').innerText = data.max_consecutive_loss + " 次";

    document.getElementById('chartPlaceholder').classList.add('hidden');
    const canvas = document.getElementById('mainChart');
    canvas.classList.remove('hidden');
    document.getElementById('chartContainer').classList.remove('bg-gray-50', 'border', 'border-dashed');
    document.getElementById('chartContainer').classList.add('bg-white', 'dark:bg-slate-800');

    lastChartData = {
        priceData: data.price_data,
        trades: data.trades,
        equityData: data.equity_curve,
        bhData: data.buy_and_hold_curve
    };

    renderMainChart(data.price_data, data.trades, data.equity_curve, data.buy_and_hold_curve);
    renderHeatmap(data.heatmap_data);
    renderTradeList(data.detailed_trades);
}

function updateCard(id, value, isPct) {
    const el = document.getElementById(id);
    const suffix = isPct ? '%' : '';
    const prefix = (value > 0 && isPct) ? '+' : '';
    el.innerText = prefix + value + suffix;
    el.className = "text-3xl font-bold mt-1 ";
    if (value > 0) el.classList.add("text-teal-600", "dark:text-teal-400");
    else if (value < 0) el.classList.add("text-red-500", "dark:text-red-400");
    else el.classList.add("text-gray-300", "dark:text-gray-600");
}

function updateTableValue(id, value, isGreenRed) {
    const el = document.getElementById(id);
    const prefix = (value > 0) ? '+' : '';
    const suffix = (id.includes('rate') || id.includes('return')) ? '%' : '';
    el.innerText = prefix + value + suffix;
    if (isGreenRed) {
        el.className = "p-3 font-bold text-right " + (value >= 0 ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400");
    }
}

// ---------------------------------------------------------
//  圖表繪製 (維持之前修好的版本)
// ---------------------------------------------------------
function renderMainChart(priceData, trades, equityData, bhData) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    if (mainChart) mainChart.destroy();

    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#e2e8f0' : '#1f2937';
    const gridColor = isDark ? '#334155' : '#e5e7eb';
    const leftAxisColor = isDark ? '#94a3b8' : '#64748b';

    const labels = priceData.map(d => d.time);

    // 計算報酬率
    const initialEquity = equityData.length > 0 ? equityData[0].value : 1;
    const strategyReturnData = equityData.map(d => ((d.value - initialEquity) / initialEquity) * 100);

    const initialPrice = priceData.length > 0 ? priceData[0].value : 1;
    const bhReturnData = priceData.map(d => ((d.value - initialPrice) / initialPrice) * 100);

    const tradeMap = {};
    trades.forEach(t => { tradeMap[t.time] = { price: t.price, type: t.type }; });

    // 映射買賣點
    const buyMarkers = labels.map((date, index) => {
        const t = tradeMap[date];
        return (t && t.type === 'buy') ? strategyReturnData[index] : null;
    });

    const sellMarkers = labels.map((date, index) => {
        const t = tradeMap[date];
        return (t && t.type === 'sell') ? strategyReturnData[index] : null;
    });

    // --- 定義 Datasets ---
    const strategyDataset = {
        label: '當前策略 (%)', data: strategyReturnData,
        borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2, pointRadius: 0, tension: 0.1, fill: true,
        yAxisID: 'y1', order: 1, legendOrder: 10
    };
    const buyDataset = {
        label: '當前-買進', data: buyMarkers,
        borderColor: '#f62323', backgroundColor: '#f62323',
        pointStyle: 'triangle', rotation: 0, pointRadius: 6, pointHoverRadius: 8,
        type: 'scatter', yAxisID: 'y1', order: 0, legendOrder: 11
    };
    const sellDataset = {
        label: '當前-賣出', data: sellMarkers,
        borderColor: '#10b981', backgroundColor: '#10b981',
        pointStyle: 'triangle', rotation: 180, pointRadius: 6, pointHoverRadius: 8,
        type: 'scatter', yAxisID: 'y1', order: 0, legendOrder: 12
    };

    const bhDataset = {
        label: '買進並持有 (%)', data: bhReturnData,
        borderColor: '#9ca3af', borderWidth: 2, borderDash: [5, 5],
        pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y1', order: 2, legendOrder: 30
    };
    const priceDataset = {
        label: '股價 (Price)', data: priceData.map(d => d.value),
        borderColor: isDark ? '#475569' : '#e2e8f0',
        borderWidth: 1, pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y', order: 4, legendOrder: 31
    };

    let datasets = [strategyDataset, buyDataset, sellDataset, bhDataset, priceDataset];

    if (lockedDatasets.length > 0) {
        datasets.push(...lockedDatasets);
    }

    mainChart = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            stacked: false,
            scales: {
                x: { ticks: { maxTicksLimit: 12, color: textColor }, grid: { color: gridColor } },
                y: {
                    type: 'linear', display: true, position: 'left',
                    title: { display: true, text: '股價 (Price)', color: leftAxisColor, font: { weight: 'bold' } },
                    ticks: { color: leftAxisColor }, grid: { display: false }
                },
                y1: {
                    type: 'linear', display: true, position: 'right',
                    title: { display: true, text: '累積報酬率 (%)', color: '#3b82f6' },
                    ticks: { color: textColor, callback: (v) => v + '%' },
                    grid: { color: gridColor, drawOnChartArea: true }
                }
            },
            plugins: {
                legend: { display: false }, // 關閉預設，改用自定義
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label.includes('訊號') || label.includes('鎖定-') || label.includes('當前-')) {
                                const date = context.label;
                                if (label.includes('鎖定')) return `${label}: ${context.parsed.y.toFixed(2)}%`;
                                const t = tradeMap[date];
                                if (t) return `${label}: $${t.price} (@ ${context.parsed.y.toFixed(2)}%)`;
                            }
                            if (label) label += ': ';
                            if (context.parsed.y !== null) {
                                if (context.dataset.yAxisID === 'y1') {
                                    const val = context.parsed.y;
                                    const sign = val > 0 ? '+' : '';
                                    return label + sign + val.toFixed(2) + '%';
                                }
                                return label + context.parsed.y.toFixed(2);
                            }
                            return label;
                        }
                    }
                },
                zoom: {
                    zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                    pan: { enabled: true, mode: 'x' }
                }
            }
        }
    });

    updateCustomLegend(mainChart);
}

function updateCustomLegend(chart) {
    let legendDiv = document.getElementById('js-legend-container');
    if (!legendDiv) {
        const chartContainer = document.getElementById('chartContainer');
        legendDiv = document.createElement('div');
        legendDiv.id = 'js-legend-container';
        legendDiv.className = "w-full p-2 flex flex-wrap gap-4 justify-center bg-gray-50/80 dark:bg-slate-800/80 border-b border-gray-100 dark:border-slate-700 mb-2 rounded-t-xl z-20 absolute top-0 left-0";
        chartContainer.prepend(legendDiv);
    }
    legendDiv.innerHTML = '';

    const groups = {
        'current': { title: '當前策略', items: [] },
        'locked': { title: '鎖定策略', items: [] },
        'market': { title: '市場參考', items: [] }
    };

    chart.data.datasets.forEach((ds, index) => {
        const item = {
            text: ds.label,
            color: ds.borderColor || ds.backgroundColor,
            index: index,
            hidden: !chart.isDatasetVisible(index),
            pointStyle: ds.pointStyle,
            rotation: ds.rotation,
            order: ds.legendOrder || 99
        };

        if (item.order >= 10 && item.order < 20) groups.current.items.push(item);
        else if (item.order >= 20 && item.order < 30) groups.locked.items.push(item);
        else if (item.order >= 30) groups.market.items.push(item);
    });

    Object.keys(groups).forEach(key => {
        const group = groups[key];
        if (group.items.length === 0) return;

        const groupEl = document.createElement('div');
        groupEl.className = "flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-slate-700/50 rounded-lg shadow-sm border border-gray-200 dark:border-slate-600";

        const titleEl = document.createElement('div');
        titleEl.className = "text-[10px] font-bold text-gray-400 dark:text-gray-400 uppercase tracking-wider mr-1 border-r border-gray-200 dark:border-slate-500 pr-2";
        titleEl.innerText = group.title;
        groupEl.appendChild(titleEl);

        group.items.forEach(item => {
            const btn = document.createElement('button');
            btn.className = `flex items-center gap-1.5 text-xs font-medium transition-all duration-200 ${item.hidden ? 'opacity-40 grayscale decoration-slice' : 'opacity-100'}`;

            const icon = document.createElement('span');
            icon.className = "inline-block";

            if (item.pointStyle === 'triangle') {
                icon.style.width = '0';
                icon.style.height = '0';
                icon.style.borderLeft = '5px solid transparent';
                icon.style.borderRight = '5px solid transparent';
                if (item.rotation === 180) { // Down
                    icon.style.borderTop = `6px solid ${item.color}`;
                } else { // Up
                    icon.style.borderBottom = `6px solid ${item.color}`;
                }
            } else {
                icon.style.width = '8px';
                icon.style.height = '8px';
                icon.style.backgroundColor = item.color;
                icon.style.borderRadius = '50%';
                if (item.hidden) icon.style.border = `2px solid ${item.color}`;
            }

            let labelText = item.text
                .replace('當前-', '')
                .replace('鎖定-', '')
                .replace(' (%)', '')
                .replace('訊號', '');

            const textSpan = document.createElement('span');
            textSpan.className = "text-gray-700 dark:text-gray-200";
            textSpan.innerText = labelText;

            btn.appendChild(icon);
            btn.appendChild(textSpan);

            btn.onclick = () => {
                chart.setDatasetVisibility(item.index, !chart.isDatasetVisible(item.index));
                chart.update();
                updateCustomLegend(chart);
            };

            groupEl.appendChild(btn);
        });

        legendDiv.appendChild(groupEl);
    });
}

function handleLockChart() {
    if (!mainChart) { alert("請先執行回測再鎖定"); return; }

    const lineDs = mainChart.data.datasets.find(d => d.label === '當前策略 (%)');
    const buyDs = mainChart.data.datasets.find(d => d.label === '當前-買進');
    const sellDs = mainChart.data.datasets.find(d => d.label === '當前-賣出');

    if (!lineDs) return;

    const lockedLine = {
        label: '已鎖定策略 (%)',
        data: [...lineDs.data],
        borderColor: '#dd6917ff',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        borderWidth: 2, pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y1', order: 2, legendOrder: 20
    };

    const lockedBuy = {
        label: '鎖定-買進',
        data: [...buyDs.data],
        borderColor: '#620404',
        backgroundColor: '#620404',
        borderWidth: 1,
        pointStyle: 'triangle', rotation: 0,
        pointRadius: 5,
        type: 'scatter', yAxisID: 'y1', order: 1, legendOrder: 21
    };

    const lockedSell = {
        label: '鎖定-賣出',
        data: [...sellDs.data],
        borderColor: '#047857',
        backgroundColor: '#047857',
        borderWidth: 1,
        pointStyle: 'triangle', rotation: 180,
        pointRadius: 5,
        type: 'scatter', yAxisID: 'y1', order: 1, legendOrder: 22
    };

    lockedDatasets = [lockedLine, lockedBuy, lockedSell];

    const lockBtn = document.getElementById('lockBtn');
    lockBtn.classList.remove('bg-blue-50', 'text-blue-600', 'border-blue-100', 'dark:bg-blue-900/30', 'dark:text-blue-400', 'dark:border-blue-800');
    lockBtn.classList.add('bg-orange-100', 'text-orange-700', 'border-orange-300', 'dark:bg-orange-900/30', 'dark:text-orange-400', 'dark:border-orange-800');
    lockBtn.innerText = "已鎖定 (再按清除)";

    lockBtn.removeEventListener('click', handleLockChart);
    lockBtn.onclick = () => { location.reload(); };
}

function resetZoom() { if (mainChart) mainChart.resetZoom(); }

function renderHeatmap(data) {
    const tbody = document.getElementById('heatmapBody');
    tbody.innerHTML = '';
    const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    const years = Object.keys(data).sort((a, b) => b - a);

    if (years.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="p-4 text-gray-400 dark:text-gray-500">無交易數據</td></tr>'; return;
    }

    years.forEach(year => {
        const row = document.createElement('tr');
        row.innerHTML = `<td class="font-bold border dark:border-slate-700 bg-gray-50 dark:bg-slate-700 text-gray-700 dark:text-gray-200">${year}</td>`;
        let yearTotal = 0;
        months.forEach(m => {
            const val = data[year][m];
            if (val !== undefined) {
                yearTotal += val;
                let colorClass = '';
                if (val >= 5) colorClass = 'bg-green-600 text-white dark:bg-green-700';
                else if (val > 0) colorClass = 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
                else if (val <= -5) colorClass = 'bg-red-500 text-white dark:bg-red-700';
                else if (val < 0) colorClass = 'bg-red-50 text-red-800 dark:bg-red-900/40 dark:text-red-300';
                else colorClass = 'text-gray-400 dark:text-gray-600';
                row.innerHTML += `<td class="border dark:border-slate-700 ${colorClass} p-2 text-xs">${val.toFixed(1)}%</td>`;
            } else {
                row.innerHTML += `<td class="border dark:border-slate-700 bg-gray-50 dark:bg-slate-800 p-2 text-xs text-gray-300 dark:text-gray-600">-</td>`;
            }
        });
        const totalClass = yearTotal >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400';
        row.innerHTML += `<td class="border dark:border-slate-700 font-bold ${totalClass} bg-gray-100 dark:bg-slate-700">${yearTotal.toFixed(1)}%</td>`;
        tbody.appendChild(row);
    });
}

function renderTradeList(trades) {
    const container = document.getElementById('tradeListContainer');
    container.innerHTML = '';
    if (!trades || trades.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">無交易紀錄</p>'; return;
    }
    const sortedTrades = [...trades].reverse();
    sortedTrades.forEach(trade => {
        const isProfit = trade.pnl >= 0;
        const pnlColor = isProfit ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400';
        const sign = isProfit ? '+' : '';

        // --- 顯示後端傳來的說明文字 ---
        // 如果後端有傳 entry_note 就顯示，沒有就留空
        const entryCondition = trade.entry_note ? `(${trade.entry_note})` : '';
        const exitCondition = trade.exit_note ? `(${trade.exit_note})` : '';
        // --------------------------------------------------

        const html = `
        <div class="py-5 px-2 hover:bg-gray-50 dark:hover:bg-slate-700 transition duration-150">
            <div class="flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-mono text-gray-400 dark:text-gray-500">${trade.entry_date}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-300 rounded">買入</span>
                        <span class="font-bold text-gray-800 dark:text-gray-200 text-lg">${trade.entry_price}</span>
                        <span class="text-xs text-gray-500 dark:text-gray-400">${trade.size} 股</span>
                    </div>
                    <!-- 這裡顯示動態的進場理由 -->
                    <p class="text-xs text-gray-400 dark:text-gray-500 pl-1">${entryCondition}</p>
                </div>
                <div class="flex-1 md:text-right">
                     <div class="flex items-center gap-2 mb-1 md:justify-end">
                        <span class="text-xs font-mono text-gray-400 dark:text-gray-500">${trade.exit_date}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-300 rounded">賣出</span>
                        <span class="font-bold text-gray-800 dark:text-gray-200 text-lg">${trade.exit_price}</span>
                    </div>
                    <!-- 這裡顯示動態的出場理由 -->
                    <p class="text-xs text-gray-400 dark:text-gray-500 pr-1">${exitCondition}</p>
                </div>
                <div class="w-full md:w-32 text-right flex items-center justify-end">
                    <span class="text-lg font-bold ${pnlColor}">${sign}${trade.pnl}元</span>
                </div>
            </div>
        </div>`;
        container.innerHTML += html;
    });
}