// static/js/main.js

let mainChart = null;
let lockedDatasets = [];
let lastChartData = null;

document.addEventListener('DOMContentLoaded', function () {
    console.log("System Ready: Smart Investment Dashboard v3.4 (All Functions Restored)");

    // 1. 日期初始化
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
});

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
    if (!ticker) { alert("請輸入股票代碼"); return; }

    const btn = document.getElementById('runBtn');
    const originalText = btn.innerHTML;
    const chartContainer = document.getElementById('chartContainer');

    btn.disabled = true;
    btn.innerHTML = `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> 運算中...`;
    chartContainer.classList.add('opacity-50', 'pointer-events-none');
    document.body.style.cursor = 'wait';

    const payload = {
        ticker: ticker,
        start_date: document.getElementById('start_date').value,
        end_date: document.getElementById('end_date').value,
        cash: parseFloat(document.getElementById('cash').value),
        ma_short: parseInt(document.getElementById('ma_short').value),
        ma_long: parseInt(document.getElementById('ma_long').value),
        rsi_period_entry: parseInt(document.getElementById('rsi_period_entry').value),
        rsi_buy_threshold: parseInt(document.getElementById('rsi_buy_threshold').value),
        rsi_period_exit: parseInt(document.getElementById('rsi_period_exit').value),
        rsi_sell_threshold: parseInt(document.getElementById('rsi_sell_threshold').value),
        sl_pct: parseFloat(document.getElementById('sl_pct').value),
        tp_pct: parseFloat(document.getElementById('tp_pct').value),
        buy_fee_pct: parseFloat(document.getElementById('buy_fee').value),
        sell_fee_pct: parseFloat(document.getElementById('sell_fee').value)
    };

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
    document.getElementById('res_trades').innerText = data.total_trades;

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

// =========================================================
//  核心圖表繪製 (支援雙軸、訊號映射、多重鎖定、圖例排序)
// =========================================================
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

    // 映射買賣點到策略線上 (y1軸)
    const buyMarkers = labels.map((date, index) => {
        const t = tradeMap[date];
        return (t && t.type === 'buy') ? strategyReturnData[index] : null;
    });

    const sellMarkers = labels.map((date, index) => {
        const t = tradeMap[date];
        return (t && t.type === 'sell') ? strategyReturnData[index] : null;
    });

    // --- 定義 Datasets (加入 legendOrder 參數來控制圖例順序) ---
    // 當前策略組: 10~19
    const strategyDataset = {
        label: '當前策略 (%)',
        data: strategyReturnData,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 2, pointRadius: 0, tension: 0.1, fill: true,
        yAxisID: 'y1', order: 1,
        legendOrder: 10 // 排序權重
    };
    const buyDataset = {
        label: '當前-買進', data: buyMarkers,
        borderColor: '#ef4444', backgroundColor: '#ef4444',
        pointStyle: 'triangle', rotation: 0, pointRadius: 6, pointHoverRadius: 8,
        type: 'scatter', yAxisID: 'y1', order: 0,
        legendOrder: 11 // 排在策略線後面
    };
    const sellDataset = {
        label: '當前-賣出', data: sellMarkers,
        borderColor: '#10b981', backgroundColor: '#10b981',
        pointStyle: 'triangle', rotation: 180, pointRadius: 6, pointHoverRadius: 8,
        type: 'scatter', yAxisID: 'y1', order: 0,
        legendOrder: 12
    };

    // 市場行情組: 30~39
    const bhDataset = {
        label: '買入持有 (%)', data: bhReturnData,
        borderColor: '#9ca3af', borderWidth: 2, borderDash: [5, 5],
        pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y1', order: 2,
        legendOrder: 30 // 排在最後
    };
    const priceDataset = {
        label: '股價 (Price)', data: priceData.map(d => d.value),
        borderColor: isDark ? '#475569' : '#e2e8f0',
        borderWidth: 1, pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y', order: 4,
        legendOrder: 31
    };

    let datasets = [strategyDataset, buyDataset, sellDataset, bhDataset, priceDataset];

    // 加入鎖定的 Datasets
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
                x: {
                    ticks: { maxTicksLimit: 12, color: textColor },
                    grid: { color: gridColor }
                },
                y: { // 左軸: 股價
                    type: 'linear', display: true, position: 'left',
                    title: {
                        display: true, text: '股價 (Price)',
                        color: leftAxisColor, font: { weight: 'bold' }
                    },
                    ticks: { color: leftAxisColor },
                    grid: { display: false }
                },
                y1: { // 右軸: 報酬率
                    type: 'linear', display: true, position: 'right',
                    title: { display: true, text: '累積報酬率 (%)', color: '#3b82f6' },
                    ticks: { color: textColor, callback: (v) => v + '%' },
                    grid: { color: gridColor, drawOnChartArea: true }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                        usePointStyle: true,
                        // [關鍵] 自定義排序邏輯：依照 legendOrder 大小排列
                        sort: function (a, b, data) {
                            const dsA = data.datasets[a.datasetIndex];
                            const dsB = data.datasets[b.datasetIndex];
                            return (dsA.legendOrder || 99) - (dsB.legendOrder || 99);
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label.includes('訊號') || label.includes('鎖定-')) {
                                const date = context.label;
                                if (label.includes('鎖定')) {
                                    return `${label}: ${context.parsed.y.toFixed(2)}%`;
                                }
                                const t = tradeMap[date];
                                if (t) return `${label}: $${t.price} (@ ${context.parsed.y.toFixed(2)}%)`;
                            }
                            if (label) { label += ': '; }
                            if (context.parsed.y !== null) {
                                if (context.dataset.yAxisID === 'y1') {
                                    const val = context.parsed.y;
                                    const sign = val > 0 ? '+' : '';
                                    label += sign + val.toFixed(2) + '%';
                                } else {
                                    label += context.parsed.y.toFixed(2);
                                }
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
}

function handleLockChart() {
    if (!mainChart) { alert("請先執行回測再鎖定"); return; }

    // 找出當前資料集
    const lineDs = mainChart.data.datasets.find(d => d.label === '當前策略 (%)');
    const buyDs = mainChart.data.datasets.find(d => d.label === '當前-買進');
    const sellDs = mainChart.data.datasets.find(d => d.label === '當前-賣出');

    if (!lineDs) return;

    // 建立鎖定 Datasets (加入 legendOrder: 20~29 讓它們排在當前策略後面)
    const lockedLine = {
        label: '已鎖定策略 (%)',
        data: [...lineDs.data],
        borderColor: '#dd6917ff', // Orange-500
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        borderWidth: 2, pointRadius: 0, tension: 0.1, fill: false,
        yAxisID: 'y1', order: 2,
        legendOrder: 20 // 鎖定組開頭
    };

    const lockedBuy = {
        label: '鎖定-買進',
        data: [...buyDs.data],
        borderColor: '#b91c1c', // Dark Red
        backgroundColor: '#b91c1c',
        borderWidth: 1,
        pointStyle: 'triangle', rotation: 0,
        pointRadius: 5,
        type: 'scatter', yAxisID: 'y1', order: 1,
        legendOrder: 21
    };

    const lockedSell = {
        label: '鎖定-賣出',
        data: [...sellDs.data],
        borderColor: '#047857', // Dark Green
        backgroundColor: '#047857',
        borderWidth: 1,
        pointStyle: 'triangle', rotation: 180,
        pointRadius: 5,
        type: 'scatter', yAxisID: 'y1', order: 1,
        legendOrder: 22
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
        const exitCondition = `短SMA: ${trade.exit_sma_short} / 出場RSI: ${trade.exit_rsi}`;
        const entryCondition = `進場RSI: ${trade.entry_rsi}`;
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
                    <p class="text-xs text-gray-400 dark:text-gray-500 pl-1">(${entryCondition})</p>
                </div>
                <div class="flex-1 md:text-right">
                     <div class="flex items-center gap-2 mb-1 md:justify-end">
                        <span class="text-xs font-mono text-gray-400 dark:text-gray-500">${trade.exit_date}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-300 rounded">賣出</span>
                        <span class="font-bold text-gray-800 dark:text-gray-200 text-lg">${trade.exit_price}</span>
                    </div>
                    <p class="text-xs text-gray-400 dark:text-gray-500 pr-1">(${exitCondition})</p>
                </div>
                <div class="w-full md:w-32 text-right flex items-center justify-end">
                    <span class="text-lg font-bold ${pnlColor}">${sign}${trade.pnl}元</span>
                </div>
            </div>
        </div>`;
        container.innerHTML += html;
    });
}