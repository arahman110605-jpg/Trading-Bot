async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.status === "OFFLINE") return;

        // Update Status Badge
        const badge = document.getElementById('botStatusBadge');
        badge.innerText = data.status;
        badge.className = `badge badge-${data.status.toLowerCase()}`;

        // Update Balances
        if (data.balance) {
            document.getElementById('walletBalance').innerHTML = `$${data.balance.wallet_balance.toFixed(2)} <span class="currency">USDT</span>`;
            document.getElementById('totalEquity').innerHTML = `$${(data.balance.total_equity || data.balance.wallet_balance).toFixed(2)} <span class="currency">USDT</span>`;
            
            const pnlElem = document.getElementById('unrealizedPnl');
            const pnl = data.balance.unrealized_pnl || 0;
            pnlElem.innerText = `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
            pnlElem.className = pnl > 0 ? 'green' : (pnl < 0 ? 'red' : 'neutral');
        }

        // Update Tickers
        const tickerFeed = document.getElementById('tickerFeed');
        if (data.tickers && Object.keys(data.tickers).length > 0) {
            tickerFeed.innerHTML = Object.entries(data.tickers).map(([sym, price]) => `
                <div class="ticker-chip">
                    <span>${sym}</span>
                    <span class="green">$${price.toFixed(2)}</span>
                </div>
            `).join('');
        }

        // Update Positions Table
        const tableBody = document.getElementById('positionsTableBody');
        document.getElementById('activePositionsCount').innerText = data.positions.length;

        if (data.positions.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" class="text-center">No open positions</td></tr>`;
        } else {
            tableBody.innerHTML = data.positions.map(pos => {
                const isOption = pos.option_type || pos.symbol.includes('-');
                const typeText = pos.option_type ? `${pos.option_type} (${pos.side})` : pos.side;
                const entryPrem = pos.entry_premium !== undefined ? pos.entry_premium : pos.entry_price;
                const currPrem = pos.current_premium !== undefined ? pos.current_premium : pos.current_price;
                const sizeStrike = pos.strike ? `$${pos.strike} (${pos.contracts}x)` : pos.size;
                const greeksText = pos.delta !== undefined ? `Δ:${pos.delta} / Θ:${pos.theta}` : 'N/A';

                return `
                    <tr>
                        <td><strong>${pos.symbol}</strong></td>
                        <td class="${pos.side === 'BUY' || pos.option_type === 'CALL' ? 'green' : 'red'}"><strong>${typeText}</strong></td>
                        <td>${sizeStrike}</td>
                        <td>$${entryPrem.toFixed(2)}</td>
                        <td>$${currPrem.toFixed(2)}</td>
                        <td style="font-size:12px; color: var(--text-secondary);">${greeksText}</td>
                        <td class="${pos.unrealized_pnl >= 0 ? 'green' : 'red'}">$${pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}</td>
                    </tr>
                `;
            }).join('');
        }

        // Update Trade History Table
        const historyBody = document.getElementById('tradeHistoryTableBody');
        if (historyBody) {
            if (!data.trade_history || data.trade_history.length === 0) {
                historyBody.innerHTML = `<tr><td colspan="8" class="text-center">No completed trades yet</td></tr>`;
            } else {
                historyBody.innerHTML = data.trade_history.slice().reverse().map(tr => {
                    const pnl = tr.pnl !== undefined ? tr.pnl : tr.gross_pnl;
                    return `
                        <tr>
                            <td><strong>${tr.symbol}</strong></td>
                            <td class="${tr.option_type === 'CALL' || tr.side === 'BUY' ? 'green' : 'red'}">${tr.option_type || tr.side || 'OPTION'}</td>
                            <td>$${(tr.entry_premium || tr.price || 0).toFixed(2)}</td>
                            <td>$${(tr.exit_premium || tr.exit_price || 0).toFixed(2)}</td>
                            <td>$${(tr.fees || 0).toFixed(4)}</td>
                            <td class="${pnl >= 0 ? 'green' : 'red'}"><strong>$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</strong></td>
                            <td style="font-size:12px; color: var(--text-secondary);">${tr.reason || 'Closed'}</td>
                            <td style="font-size:12px; color: var(--text-secondary);">${tr.timestamp || ''}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // Update Signals Feed
        const signalsList = document.getElementById('signalsList');
        if (data.signals && data.signals.length > 0) {
            signalsList.innerHTML = data.signals.map(sig => `
                <div class="signal-item ${sig.action}">
                    <div>
                        <strong>[${sig.action}] ${sig.symbol}</strong> @ Spot $${sig.price.toFixed(2)}
                        <br><small style="color: var(--text-secondary);">${sig.reason} (${sig.strategy})</small>
                    </div>
                    <span style="font-size: 12px; color: var(--text-secondary);">${sig.timestamp}</span>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error("Error fetching status:", err);
    }
}

async function pauseBot() {
    await fetch('/api/control/pause', { method: 'POST' });
    fetchStatus();
}

async function resumeBot() {
    await fetch('/api/control/resume', { method: 'POST' });
    fetchStatus();
}

async function squareOffAll() {
    if (confirm("Are you sure you want to square off all active positions?")) {
        await fetch('/api/control/squareoff', { method: 'POST' });
        fetchStatus();
    }
}

fetchStatus();
setInterval(fetchStatus, 2000);
