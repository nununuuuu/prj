// Global chart instance
let equityChart = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('backtestForm');
    form.addEventListener('submit', handleSubmit);
});

/**
 * Handle form submission
 */
async function handleSubmit(event) {
    event.preventDefault();
    
    // Get form data
    const formData = new FormData(event.target);
    const data = {
        symbol: formData.get('symbol'),
        start_date: formData.get('start_date') || null,
        end_date: formData.get('end_date') || null,
        initial_cash: parseFloat(formData.get('initial_cash')),
        commission: parseFloat(formData.get('commission')) / 100  // Convert percentage to decimal
    };
    
    // Show loading state
    showLoading(true);
    hideError();
    hideResults();
    
    try {
        // Send request to backend
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Backtest failed');
        }
        
        if (result.success) {
            displayResults(result.data);
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        showError(error.message);
    } finally {
        showLoading(false);
    }
}

/**
 * Display backtest results
 */
function displayResults(data) {
    // Update metrics
    document.getElementById('metricReturn').textContent = `${data.return}%`;
    document.getElementById('metricReturn').className = 
        `metric-value ${data.return >= 0 ? 'positive' : 'negative'}`;
    
    document.getElementById('metricSharpe').textContent = data.sharpe_ratio.toFixed(2);
    document.getElementById('metricSharpe').className = 
        `metric-value ${data.sharpe_ratio >= 0 ? 'positive' : 'negative'}`;
    
    document.getElementById('metricDrawdown').textContent = `${data.max_drawdown}%`;
    document.getElementById('metricDrawdown').className = 'metric-value negative';
    
    document.getElementById('metricTrades').textContent = data.trades;
    document.getElementById('metricTrades').className = 'metric-value';
    
    document.getElementById('metricWinRate').textContent = `${data.win_rate}%`;
    document.getElementById('metricWinRate').className = 
        `metric-value ${data.win_rate >= 50 ? 'positive' : 'negative'}`;
    
    // Draw equity curve
    drawEquityCurve(data.equity_curve);
    
    // Show results container
    showResults();
}

/**
 * Draw equity curve using Chart.js
 */
function drawEquityCurve(equityCurve) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (equityChart) {
        equityChart.destroy();
    }
    
    // Prepare data
    const labels = equityCurve.map((point, index) => index);
    const equityData = equityCurve.map(point => point.Equity);
    
    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
    
    // Create chart
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Equity',
                data: equityData,
                borderColor: '#6366f1',
                backgroundColor: gradient,
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#6366f1',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(26, 31, 58, 0.95)',
                    titleColor: '#f1f5f9',
                    bodyColor: '#94a3b8',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return `Equity: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        color: 'rgba(45, 50, 80, 0.5)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxTicksLimit: 10
                    }
                },
                y: {
                    display: true,
                    grid: {
                        color: 'rgba(45, 50, 80, 0.5)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    }
                }
            }
        }
    });
}

/**
 * UI Helper Functions
 */
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.classList.add('active');
    } else {
        loading.classList.remove('active');
    }
}

function showResults() {
    document.getElementById('resultsContainer').style.display = 'block';
}

function hideResults() {
    document.getElementById('resultsContainer').style.display = 'none';
}

function showError(message) {
    const errorElement = document.getElementById('errorMessage');
    errorElement.textContent = message;
    errorElement.classList.add('active');
}

function hideError() {
    const errorElement = document.getElementById('errorMessage');
    errorElement.classList.remove('active');
}
