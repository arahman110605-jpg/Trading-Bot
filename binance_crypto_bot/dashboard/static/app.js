async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        if (data.status === "OFFLINE") return;

        // ── Bot Status Badge ───────────────────────────────────────────────
        const badge = document.getElementById('botStatusBadge');
        badge.innerText = data.status;
        badge.className = `badge badge-${data.status.toLowerCase()}`;

        // ── Peak Window Badge ──────────────────────────────────────────────
        const peakBadge = document.getElementById('peakWindowBadge');
        if (peakBadge) {
            peakBadge.style.display = data.peak_window_active ? 'inline-block' : 'none';
            peakBadge.innerText = data.peak_window_active ? '🔥 US Peak Window Active (6:00-9:00 PM IST)' : '';
        }

        // ── Combined Balances ──────────────────────────────────────────────
        if (data.balance) {
            const b = data.balance;
            document.getElementById('walletBalance').innerHTML =
                `$${b.wallet_balance.toFixed(2)} <span class="currency">USDT</span>`;
            document.getElementById('totalEquity').innerHTML =
                `$${(b.total_equity || b.wallet_balance).toFixed(2)} <span class="currency">USDT</span>`;

            const pnlElem = document.getElementById('unrealizedPnl');
            const pnl = b.unrealized_pnl || 0;
            pnlElem.innerText = `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)}`;
            pnlElem.className = pnl > 0 ? 'green' : (pnl < 0 ? 'red' : 'neutral');
        }

        // ── Sub-broker balances ────────────────────────────────────────────
        if (data.sub_balances) {
            const spotEl = document.getElementById('spotBalance');
            const optEl  = document.getElementById('optionsBalance');
            if (spotEl && data.sub_balances.spot) {
                spotEl.innerText = `$${data.sub_balances.spot.total_equity.toFixed(2)}`;
                spotEl.style.color = data.sub_balances.spot.total_equity >= 700 ? '#00c896' : '#ff4b4b';
            }
            if (optEl && data.sub_balances.options) {
                optEl.innerText = `$${data.sub_balances.options.total_equity.toFixed(2)}`;
                optEl.style.color = data.sub_balances.options.total_equity >= 300 ? '#818cf8' : '#ff4b4b';
            }
        }

        // ── Tickers ────────────────────────────────────────────────────────
        const tickerFeed = document.getElementById('tickerFeed');
        if (data.tickers && Object.keys(data.tickers).length > 0) {
            tickerFeed.innerHTML = Object.entries(data.tickers).map(([sym, price]) => `
                <div class="ticker-chip">
                    <span>${sym}</span>
                    <span class="green">$${Number(price).toFixed(2)}</span>
                </div>
            `).join('');
        }

        // ── Active Positions Table (combined spot + options) ───────────────
        const tableBody = document.getElementById('positionsTableBody');
        document.getElementById('activePositionsCount').innerText = data.positions.length;

        if (data.positions.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="8" class="text-center">No open positions</td></tr>`;
        } else {
            tableBody.innerHTML = data.positions.map(pos => {
                const broker    = pos.broker || 'OPTIONS';
                const isSell    = pos.side === 'SELL';
                const isSpot    = broker === 'SPOT';
                const brokerTag = isSpot
                    ? `<span class="pos-broker-tag" style="background:rgba(0,200,150,0.15);color:#00c896;">SPOT</span>`
                    : isSell
                        ? `<span class="pos-broker-tag" style="background:rgba(251,146,60,0.15);color:#fb923c;">SELL</span>`
                        : `<span class="pos-broker-tag" style="background:rgba(99,102,241,0.15);color:#818cf8;">BUY OPT</span>`;

                const sym       = pos.symbol || pos.underlying || '—';
                const typeText  = pos.option_type
                    ? `${pos.option_type} (${pos.side})`
                    : pos.side || 'LONG';
                const entryVal  = pos.entry_premium !== undefined ? pos.entry_premium : (pos.entry_price || 0);
                const currVal   = pos.current_premium !== undefined ? pos.current_premium : (pos.current_price || 0);
                const sizeVal   = pos.strike
                    ? `$${pos.strike} (${pos.contracts}x)`
                    : (pos.qty ? `${pos.qty} units` : '—');
                const greeksTxt = pos.delta !== undefined
                    ? `Δ:${Number(pos.delta).toFixed(3)} / Θ:${Number(pos.theta).toFixed(4)}`
                    : '—';
                const upnl      = pos.unrealized_pnl || 0;
                const upnlColor = upnl >= 0 ? 'green' : 'red';

                return `
                    <tr>
                        <td>${brokerTag}</td>
                        <td><strong>${sym}</strong></td>
                        <td class="${pos.side === 'BUY' || pos.option_type === 'CALL' ? 'green' : pos.side === 'SELL' ? '' : 'red'}">
                            <strong>${typeText}</strong>
                        </td>
                        <td>${sizeVal}</td>
                        <td>$${Number(entryVal).toFixed(2)}</td>
                        <td>$${Number(currVal).toFixed(2)}</td>
                        <td style="font-size:12px; color: var(--text-secondary);">${greeksTxt}</td>
                        <td class="${upnlColor}"><strong>$${upnl >= 0 ? '+' : ''}${Number(upnl).toFixed(4)}</strong></td>
                    </tr>
                `;
            }).join('');
        }

        // ── Trade History Table ────────────────────────────────────────────
        const historyBody = document.getElementById('tradeHistoryTableBody');
        if (historyBody) {
            if (!data.trade_history || data.trade_history.length === 0) {
                historyBody.innerHTML = `<tr><td colspan="9" class="text-center">No completed trades yet</td></tr>`;
            } else {
                historyBody.innerHTML = data.trade_history.slice(0, 30).map(tr => {
                    const pnl    = tr.pnl !== undefined ? tr.pnl : (tr.gross_pnl || 0);
                    const broker = tr.broker || 'OPTIONS';
                    const isSpot = broker === 'SPOT';
                    const brokerTag = isSpot
                        ? `<span class="pos-broker-tag" style="background:rgba(0,200,150,0.12);color:#00c896;">SPOT</span>`
                        : `<span class="pos-broker-tag" style="background:rgba(99,102,241,0.12);color:#818cf8;">OPT</span>`;
                    const entryP = tr.entry_premium || tr.entry_price || tr.price || 0;
                    const exitP  = tr.exit_premium  || tr.exit_price  || 0;
                    const typeStr= tr.option_type   || (isSpot ? 'SPOT' : 'OPTION');

                    return `
                        <tr>
                            <td>${brokerTag}</td>
                            <td><strong>${tr.symbol || '—'}</strong></td>
                            <td class="${typeStr === 'CALL' ? 'green' : typeStr === 'PUT' ? 'red' : 'green'}">${typeStr}</td>
                            <td>$${Number(entryP).toFixed(2)}</td>
                            <td>$${Number(exitP).toFixed(2)}</td>
                            <td>$${Number(tr.fees || 0).toFixed(4)}</td>
                            <td class="${pnl >= 0 ? 'green' : 'red'}"><strong>$${pnl >= 0 ? '+' : ''}${Number(pnl).toFixed(4)}</strong></td>
                            <td style="font-size:11px; color:var(--text-secondary);">${tr.reason || '—'}</td>
                            <td style="font-size:11px; color:var(--text-secondary);">${tr.timestamp || ''}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        // ── Signals Feed ───────────────────────────────────────────────────
        const signalsList = document.getElementById('signalsList');
        if (data.signals && data.signals.length > 0) {
            signalsList.innerHTML = data.signals.map(sig => {
                const isConfirmed = sig.strategy && sig.strategy.includes('CONFIRM');
                const isVetoed    = sig.strategy && sig.strategy.includes('VETO');
                const isSpot      = sig.action === 'BUY' && !sig.symbol?.includes('-');
                const isSell      = sig.action === 'SELL_OPTION';
                const borderColor = isConfirmed ? '#00c896' : isVetoed ? '#ff4b4b' : '#888';
                const typeTag = isSpot
                    ? `<span class="strategy-badge badge-spot">SPOT</span>`
                    : isSell
                        ? `<span class="strategy-badge badge-sell">SELL</span>`
                        : `<span class="strategy-badge badge-options">OPT</span>`;

                return `
                <div class="signal-item ${sig.action}" style="border-left: 3px solid ${borderColor};">
                    <div>
                        ${typeTag}
                        <strong>[${sig.action}] ${sig.symbol || sig.action}</strong> @ $${Number(sig.price).toFixed(2)}
                        <br><small style="color: var(--text-secondary);">${sig.reason}</small>
                        <br><small style="color: ${borderColor}; font-weight:600;">${sig.strategy}</small>
                    </div>
                    <span style="font-size: 12px; color: var(--text-secondary);">${sig.timestamp}</span>
                </div>`;
            }).join('');
        }

        // ── AI Overseer Feed ───────────────────────────────────────────────
        const aiPanel = document.getElementById('aiDecisionFeed');
        if (aiPanel && data.ai_decision_logs && data.ai_decision_logs.length > 0) {
            aiPanel.innerHTML = data.ai_decision_logs.map(log => {
                const isConfirm = log.decision === 'CONFIRM';
                const color     = isConfirm ? '#00c896' : '#ff4b4b';
                const icon      = isConfirm ? '✅' : '🚫';
                const cpText    = log.cp_ratio !== undefined ? ` · C/P: ${log.cp_ratio}` : '';
                return `
                <div style="padding: 10px 12px; border-bottom: 1px solid var(--border); border-left: 3px solid ${color};">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:${color}; font-weight:700; font-size:13px;">${icon} ${log.decision} · ${log.action}</span>
                        <span style="font-size:11px; color:var(--text-secondary);">${log.timestamp}</span>
                    </div>
                    <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
                        <strong style="color:var(--text-primary);">${log.underlying || ''} ${log.symbol ? '(' + log.symbol + ')' : ''}</strong>
                        · Confidence: <strong style="color:${color}">${Math.round((log.confidence_score || 0) * 100)}%</strong>${cpText}
                    </div>
                    <div style="font-size:11px; color:var(--text-secondary); margin-top:4px; line-height:1.5;">${log.reasoning || ''}</div>
                </div>`;
            }).join('');
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
    if (confirm("Are you sure you want to square off ALL active positions?")) {
        await fetch('/api/control/squareoff', { method: 'POST' });
        fetchStatus();
    }
}

fetchStatus();
setInterval(fetchStatus, 2000);
