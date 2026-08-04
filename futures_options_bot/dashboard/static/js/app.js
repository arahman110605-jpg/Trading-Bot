document.addEventListener("DOMContentLoaded", () => {
    // Clock
    setInterval(() => {
        const now = new Date();
        document.getElementById("clock").innerText = now.toLocaleTimeString();
    }, 1000);

    // WebSocket connection
    const socket = io();

    socket.on("connect", () => {
        addLogEntry("[WEBSOCKET] Connected to F&O Trading Engine.", "success");
    });

    socket.on("disconnect", () => {
        addLogEntry("[WEBSOCKET] Disconnected from engine server.", "error");
    });

    socket.on("market_update", (data) => {
        updateMetrics(data);
        renderPositions(data.positions);
        fetchOptionChain();
    });
});

function updateMetrics(data) {
    if (data.capital !== undefined) {
        document.getElementById("val-capital").innerText = `₹${data.capital.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    }

    if (data.spot_prices) {
        if (data.spot_prices.NIFTY) {
            document.getElementById("val-nifty").innerText = data.spot_prices.NIFTY.toFixed(2);
        }
        if (data.spot_prices.BANKNIFTY) {
            document.getElementById("val-banknifty").innerText = data.spot_prices.BANKNIFTY.toFixed(2);
        }
    }

    if (data.total_pnl !== undefined) {
        const pnlElem = document.getElementById("val-open-pnl");
        const formatted = (data.total_pnl >= 0 ? "+" : "") + `₹${data.total_pnl.toFixed(2)}`;
        pnlElem.innerText = formatted;

        pnlElem.className = "card-value " + (data.total_pnl > 0 ? "pnl-positive" : data.total_pnl < 0 ? "pnl-negative" : "pnl-neutral");
    }

    if (data.positions) {
        document.getElementById("val-open-count").innerText = `${data.positions.length} Open Positions`;
        document.getElementById("positions-count").innerText = `${data.positions.length} Active`;
    }
}

function renderPositions(positions) {
    const tbody = document.getElementById("positions-table-body");
    if (!positions || positions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-text">No active open positions currently. Scanning market...</td></tr>`;
        return;
    }

    tbody.innerHTML = positions.map(pos => {
        const pnlClass = pos.pnl > 0 ? "pnl-positive" : pos.pnl < 0 ? "pnl-negative" : "pnl-neutral";
        const sign = pos.pnl >= 0 ? "+" : "";

        return `
            <tr>
                <td><strong>${pos.trading_symbol}</strong></td>
                <td><span class="badge">${pos.transaction_type} ${pos.option_type}</span></td>
                <td>${pos.lots}</td>
                <td>${pos.quantity}</td>
                <td>₹${pos.entry_price.toFixed(2)}</td>
                <td>₹${pos.current_price.toFixed(2)}</td>
                <td class="${pnlClass}">${sign}₹${pos.pnl.toFixed(2)}</td>
                <td class="${pnlClass}">${sign}${pos.pnl_pct.toFixed(2)}%</td>
                <td>${pos.timestamp || '--:--'}</td>
            </tr>
        `;
    }).join("");
}

async function fetchOptionChain() {
    try {
        const res = await fetch("/api/option_chain?symbol=NIFTY");
        const chain = await res.json();
        const tbody = document.getElementById("option-chain-body");

        if (!chain || chain.length === 0) {
            return;
        }

        tbody.innerHTML = chain.map(row => `
            <tr class="${row.is_atm ? 'atm-row' : ''}">
                <td>₹${row.ce.ltp.toFixed(2)}</td>
                <td>${row.ce.greeks.delta.toFixed(2)}</td>
                <td><strong>${row.strike}</strong> ${row.is_atm ? '<span class="badge">ATM</span>' : ''}</td>
                <td>${row.pe.greeks.delta.toFixed(2)}</td>
                <td>₹${row.pe.ltp.toFixed(2)}</td>
            </tr>
        `).join("");
    } catch (e) {
        console.error("Option chain fetch error:", e);
    }
}

function triggerSquareOff() {
    if (confirm("Are you sure you want to Emergency Square Off ALL open F&O positions?")) {
        fetch("/api/square_off", { method: "POST" })
            .then(res => res.json())
            .then(data => {
                addLogEntry(`[ALERT] ${data.message}`, "warn");
            });
    }
}

function addLogEntry(msg, type = "info") {
    const logBox = document.getElementById("trade-logs");
    const div = document.createElement("div");
    div.className = `log-entry log-${type}`;
    div.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logBox.prepend(div);
}
