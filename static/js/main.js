// static/js/main.js

// 全域圖表變數 (Global Chart Instances)
let mainChart = null;
let lockedDataset = null;

// ==========================================
// 1. 初始化與事件監聽 (Initialization)
// ==========================================
document.addEventListener('DOMContentLoaded', function () {
    console.log("System Ready: Smart Investment Dashboard");

    // 設定預設日期 (最近 3 年)
    const today = new Date();
    const start = new Date();
    start.setFullYear(today.getFullYear() - 3);

    const endDateInput = document.getElementById('end_date');
    const startDateInput = document.getElementById('start_date');

    if (endDateInput && startDateInput) {
        endDateInput.value = today.toISOString().split('T')[0];
        startDateInput.value = start.toISOString().split('T')[0];
    }

    // 綁定「股票代碼輸入框」：自動偵測台股/美股並調整手續費
    const tickerInput = document.getElementById('ticker');
    if (tickerInput) {
        tickerInput.addEventListener('input', handleTickerInput);
    }

    // 綁定「鎖定按鈕」
    const lockBtn = document.getElementById('lockBtn');
    if (lockBtn) {
        lockBtn.addEventListener('click', handleLockChart);
    }
});

/**
 * 處理股票代碼輸入，自動調整手續費建議
 */
function handleTickerInput(e) {
    const val = e.target.value.trim().toUpperCase();
    const hint = document.getElementById('tickerHint');
    const buyInput = document.getElementById('buy_fee');
    const sellInput = document.getElementById('sell_fee');

    // 簡單判斷邏輯
    if (/^\d/.test(val) || val.endsWith('.TW')) {
        if (val.startsWith('00')) { // ETF
            buyInput.value = 0.1425;
            sellInput.value = 0.2425;
            hint.innerText = "偵測到: 台股 ETF";
        } else { // 個股
            buyInput.value = 0.1425;
            sellInput.value = 0.4425;
            hint.innerText = "偵測到: 台股 個股";
        }
    } else if (val.length > 0) { // 美股假設
        buyInput.value = 0.1;
        sellInput.value = 0.1;
        hint.innerText = "偵測到: 美股";
    } else {
        hint.innerText = "請輸入代碼...";
    }
}

// ==========================================
// 2. 核心回測執行邏輯 (Execution Logic)
// ==========================================

async function executeBacktest() {
    console.log("Backtest started...");
    const tickerInput = document.getElementById('ticker');
    const ticker = tickerInput.value.trim();

    if (!ticker) {
        alert("請輸入股票代碼！");
        return;
    }

    // 鎖定按鈕避免重複點擊
    const btn = document.getElementById('runBtn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "運算中...";

    // --- 關鍵：抓取 HTML 上的數值 ---
    const payload = {
        ticker: ticker,
        start_date: document.getElementById('start_date').value,
        end_date: document.getElementById('end_date').value,
        cash: parseFloat(document.getElementById('cash').value),

        // 均線設定
        ma_short: parseInt(document.getElementById('ma_short').value),
        ma_long: parseInt(document.getElementById('ma_long').value),

        // RSI 設定
        rsi_period: parseInt(document.getElementById('rsi_period').value),
        rsi_overbought: parseInt(document.getElementById('rsi_overbought').value),

        // 風控與成本 (移除了 use_death_cross，因為是預設邏輯)
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

        // 成功取得資料，更新儀表板
        updateDashboard(data);

    } catch (err) {
        alert('錯誤: ' + err.message);
        console.error(err);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// ==========================================
// 3. UI 更新邏輯 (UI Updates)
// ==========================================

function updateDashboard(data) {
    // A. 更新上方績效卡片
    updateCard('res_ann_return', data.annual_return, true);
    updateCard('res_total_return', data.total_return, true);
    document.getElementById('res_bh_return').innerText = data.buy_and_hold_return + '%';
    document.getElementById('res_final_equity').innerText = '$' + data.final_equity.toLocaleString();
    document.getElementById('res_win_rate').innerText = data.win_rate + '%';
    document.getElementById('res_trades').innerText = data.total_trades;

    // B. 更新平均交易盈虧 (Average PnL)
    const pnlEl = document.getElementById('res_avg_pnl');
    const pnlVal = data.avg_pnl;

    // 格式化 PnL
    const sign = pnlVal > 0 ? '+' : '';
    pnlEl.innerText = `${sign}${pnlVal.toLocaleString()}`;

    // 設定 PnL 顏色
    pnlEl.className = "text-4xl font-bold tracking-tight transition-colors duration-300";
    if (pnlVal > 0) {
        pnlEl.classList.add("text-emerald-600"); // 綠色
    } else if (pnlVal < 0) {
        pnlEl.classList.add("text-red-500");     // 紅色
    } else {
        pnlEl.classList.add("text-gray-400");    // 灰色
    }

    // 更新最大連虧
    document.getElementById('res_consec_loss').innerText = data.max_consecutive_loss + " 次";

    // C. 顯示圖表區塊
    document.getElementById('chartPlaceholder').classList.add('hidden');
    const canvas = document.getElementById('mainChart');
    canvas.classList.remove('hidden');
    document.getElementById('chartContainer').classList.remove('bg-gray-50', 'border', 'border-dashed');

    // D. 繪製圖表與熱力圖
    renderMainChart(data.price_data, data.trades, data.equity_curve, data.buy_and_hold_curve);
    renderHeatmap(data.heatmap_data);

    // E. 繪製詳細交易列表 (新增功能)
    renderTradeList(data.detailed_trades);
}

// 輔助函式：更新數值顏色
function updateCard(id, value, isPct) {
    const el = document.getElementById(id);
    const suffix = isPct ? '%' : '';
    const prefix = (value > 0 && isPct) ? '+' : '';
    el.innerText = prefix + value + suffix;

    el.className = "text-2xl font-bold ";
    if (value > 0) el.classList.add("text-teal-600");
    else if (value < 0) el.classList.add("text-red-500");
    else el.classList.add("text-gray-600");
}

// ==========================================
// 4. Chart.js 繪圖邏輯 (Visualization)
// ==========================================

function renderMainChart(priceData, trades, equityData, bhData) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    if (mainChart) mainChart.destroy();

    const labels = priceData.map(d => d.time);

    // 1. 策略淨值曲線
    const strategyDataset = {
        label: '當前策略',
        data: equityData.map(d => d.value),
        borderColor: '#2563eb', // Blue
        backgroundColor: 'rgba(37, 99, 235, 0.05)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
        fill: true,
        yAxisID: 'y',
        order: 2
    };

    // 2. 買入持有基準線
    const bhDataset = {
        label: '買進並持有',
        data: bhData ? bhData.map(d => d.value) : [],
        borderColor: '#9ca3af', // Gray
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
        fill: false,
        yAxisID: 'y',
        order: 3
    };

    // 3. 買入點標記
    const buyMarkers = equityData.map(d => {
        const trade = trades.find(tr => tr.time === d.time && tr.type === 'buy');
        return trade ? d.value : null;
    });
    const buyDataset = {
        label: '買進訊號',
        data: buyMarkers,
        borderColor: '#ef4444', // Red
        backgroundColor: '#ef4444',
        pointStyle: 'triangle',
        pointRadius: 8,
        pointHoverRadius: 10,
        type: 'scatter',
        yAxisID: 'y',
        order: 1
    };

    // 4. 賣出點標記
    const sellMarkers = equityData.map(d => {
        const trade = trades.find(tr => tr.time === d.time && tr.type === 'sell');
        return trade ? d.value : null;
    });
    const sellDataset = {
        label: '賣出訊號',
        data: sellMarkers,
        borderColor: '#10b981', // Green
        backgroundColor: '#10b981',
        pointStyle: 'circle',
        pointRadius: 6,
        pointHoverRadius: 8,
        type: 'scatter',
        yAxisID: 'y',
        order: 1
    };

    let datasets = [strategyDataset, bhDataset, buyDataset, sellDataset];

    // 如果有鎖定的舊策略，也畫上去比較
    if (lockedDataset) {
        datasets.push(lockedDataset);
    }

    mainChart = new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 12 }
                },
                y: {
                    display: true,
                    position: 'right',
                    title: { display: true, text: '資產價值 (USD/TWD)' }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) { label += ': '; }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                },
                zoom: {
                    zoom: {
                        wheel: { enabled: true },
                        pinch: { enabled: true },
                        mode: 'x',
                    },
                    pan: {
                        enabled: true,
                        mode: 'x',
                    }
                }
            }
        }
    });
}

function renderHeatmap(data) {
    const tbody = document.getElementById('heatmapBody');
    tbody.innerHTML = '';
    const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    const years = Object.keys(data).sort((a, b) => b - a); // 年份倒序

    if (years.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="p-4 text-gray-400">無交易數據</td></tr>';
        return;
    }

    years.forEach(year => {
        const row = document.createElement('tr');
        row.innerHTML = `<td class="font-bold border bg-gray-50 text-gray-700">${year}</td>`;

        let yearTotal = 0;
        months.forEach(m => {
            const val = data[year][m];
            if (val !== undefined) {
                yearTotal += val;
                // 根據報酬率決定顏色深淺
                let colorClass = '';
                if (val >= 5) colorClass = 'bg-green-600 text-white';
                else if (val > 0) colorClass = 'bg-green-100 text-green-800';
                else if (val <= -5) colorClass = 'bg-red-500 text-white';
                else if (val < 0) colorClass = 'bg-red-50 text-red-800';
                else colorClass = 'text-gray-400';

                row.innerHTML += `<td class="border ${colorClass} p-2 text-xs">${val.toFixed(1)}%</td>`;
            } else {
                row.innerHTML += `<td class="border bg-gray-50 p-2 text-xs text-gray-300">-</td>`;
            }
        });

        const totalClass = yearTotal >= 0 ? 'text-green-600' : 'text-red-600';
        row.innerHTML += `<td class="border font-bold ${totalClass} bg-gray-100">${yearTotal.toFixed(1)}%</td>`;
        tbody.appendChild(row);
    });
}

// ==========================================
// 5. 交易紀錄列表渲染 (Trade List)
// ==========================================
function renderTradeList(trades) {
    const container = document.getElementById('tradeListContainer');
    container.innerHTML = '';

    if (!trades || trades.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-400 py-8 text-center">無交易紀錄</p>';
        return;
    }

    // 讓最新的交易排在最上面
    const sortedTrades = [...trades].reverse();

    sortedTrades.forEach(trade => {
        const isProfit = trade.pnl >= 0;
        const pnlColor = isProfit ? 'text-green-600' : 'text-red-500';
        const sign = isProfit ? '+' : '';

        // 格式化條件字串
        const exitCondition = `短SMA: ${trade.exit_sma_short} / 長SMA: ${trade.exit_sma_long}`;
        const entryCondition = `RSI: ${trade.entry_rsi}`;

        // 構建 HTML (仿照圖3的卡片式設計)
        const html = `
        <div class="py-5 px-2 hover:bg-gray-50 transition duration-150">
            <div class="flex flex-col md:flex-row gap-4">
                
                <!-- 第一行：買入資訊 -->
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-mono text-gray-400">${trade.entry_date}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold bg-red-100 text-red-600 rounded">買入</span>
                        <span class="font-bold text-gray-800 text-lg">${trade.entry_price}</span>
                        <span class="text-xs text-gray-500">${trade.size} 股</span>
                    </div>
                    <p class="text-xs text-gray-400 pl-1">(${entryCondition})</p>
                </div>

                <!-- 第二行：賣出資訊 -->
                <div class="flex-1 md:text-right">
                     <div class="flex items-center gap-2 mb-1 md:justify-end">
                        <span class="text-xs font-mono text-gray-400">${trade.exit_date}</span>
                        <span class="px-2 py-0.5 text-[10px] font-bold bg-green-100 text-green-600 rounded">賣出</span>
                        <span class="font-bold text-gray-800 text-lg">${trade.exit_price}</span>
                    </div>
                    <p class="text-xs text-gray-400 pr-1">(${exitCondition})</p>
                </div>
                
                <!-- 第三行：盈虧 -->
                <div class="w-full md:w-32 text-right flex items-center justify-end">
                    <span class="text-lg font-bold ${pnlColor}">
                        ${sign}${trade.pnl}元
                    </span>
                </div>
            </div>
        </div>
        `;
        container.innerHTML += html;
    });
}

// 處理鎖定比較圖表
function handleLockChart() {
    if (!mainChart) {
        alert("請先執行回測再鎖定！");
        return;
    }
    const currentDs = mainChart.data.datasets.find(d => d.label === '當前策略');
    if (!currentDs) return;

    // 複製當前數據到 lockedDataset
    lockedDataset = {
        label: '策略 A (已鎖定)',
        data: [...currentDs.data],
        borderColor: '#FF5809', // Orange
        backgroundColor: 'rgba(255, 88, 9, 0.1)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
        yAxisID: 'y'
    };

    const lockBtn = document.getElementById('lockBtn');
    lockBtn.classList.remove('bg-gray-100', 'text-gray-600', 'border-gray-200');
    lockBtn.classList.add('bg-orange-100', 'text-orange-700', 'border-orange-300');
    lockBtn.innerText = "已鎖定 (再按清除)";

    // 改變點擊行為：再次點擊則清除
    lockBtn.removeEventListener('click', handleLockChart);
    lockBtn.onclick = () => {
        location.reload(); // 簡單重整來清除
    };
}

// 供 HTML 按鈕呼叫的重置縮放
function resetZoom() {
    if (mainChart) {
        mainChart.resetZoom();
    }
}