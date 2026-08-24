/**
 * XM Smart Bot v6 - Full TP/SL + Dynamic Margin Sizing
 * Paste into Brave DevTools Console on the XM Competition tab
 */
(function () {
    'use strict';
    console.clear();
    console.log('%c[XM AUTO-BOT v6] TP/SL + Dynamic Margin Engine', 'color:#00ff88;font-size:16px;font-weight:bold');

    const CFG = {
        bridgeUrl: 'http://localhost:8765/signals',
        pollMs: 2000,
        confirmDelayMs: 900,
        executionCooldownMs: 5000,
        marginUsePct: 0.75,
        leverage: 100
    };

    let lastSignalKey = null;
    let lastExecutionTime = 0;
    let isExecuting = false;
    let lastSignalData = {};

    // ── Audio ──
    function playChime() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            [523.25, 659.25, 783.99].forEach((f, i) => {
                const o = ctx.createOscillator(), g = ctx.createGain();
                o.connect(g); g.connect(ctx.destination);
                o.type = 'sine'; o.frequency.value = f;
                g.gain.setValueAtTime(0.22, ctx.currentTime + i * 0.1);
                g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.1 + 0.2);
                o.start(ctx.currentTime + i * 0.1);
                o.stop(ctx.currentTime + i * 0.1 + 0.25);
            });
        } catch (e) {}
    }

    // ── UI ──
    const old = document.getElementById('xm-bot-v6');
    if (old) old.remove();
    const ui = document.createElement('div');
    ui.id = 'xm-bot-v6';
    ui.style.cssText = `position:fixed;top:15px;right:420px;z-index:2147483647;
        background:rgba(10,16,32,0.97);border:1.5px solid #00ff88;border-radius:14px;
        padding:14px 18px;color:#fff;font-family:-apple-system,BlinkMacSystemFont,sans-serif;
        font-size:13px;min-width:300px;box-shadow:0 12px 40px rgba(0,255,136,0.2)`;
    ui.innerHTML = `
        <style>@keyframes v6blink{0%,100%{opacity:1}50%{opacity:0.2}}</style>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <div>
                <div style="font-weight:800;color:#00ff88;font-size:14px">🎯 XM SMART BOT v6</div>
                <div style="font-size:10px;color:#475569">TP/SL Auto-Set | Dynamic Margin Sizing</div>
            </div>
            <div id="v6pulse" style="width:9px;height:9px;background:#00ff88;border-radius:50%;animation:v6blink 1.5s infinite"></div>
        </div>
        <div id="v6-info" style="background:#0f172a;border-radius:6px;padding:6px 10px;margin-bottom:10px;font-size:11px;color:#94a3b8;line-height:1.6">
            📊 Reading account info...
        </div>
        <div id="v6-signal" style="background:#0f172a;border-radius:6px;padding:6px 10px;margin-bottom:10px;font-size:11px;color:#64748b;line-height:1.6">
            ⏳ Waiting for strategy signal...
        </div>
        <div style="display:flex;gap:8px;margin-bottom:10px">
            <button id="v6-buy" style="flex:1;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0f172a;border:none;border-radius:8px;padding:9px;font-weight:800;cursor:pointer;font-size:12px">⚡ BUY NOW</button>
            <button id="v6-sell" style="flex:1;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;border:none;border-radius:8px;padding:9px;font-weight:800;cursor:pointer;font-size:12px">⚡ SELL NOW</button>
        </div>
        <div id="v6-status" style="background:#0f172a;border-radius:8px;padding:8px 10px;font-size:11px;color:#38bdf8;line-height:1.7">
            🟢 Bot active — waiting for signal...
        </div>`;
    document.body.appendChild(ui);

    function setStatus(html, color = '#38bdf8') {
        const el = document.getElementById('v6-status');
        if (el) { el.innerHTML = html; el.style.color = color; }
    }

    // ── React-safe input setter ──
    function setInputValue(el, val) {
        if (!el) return false;
        el.focus();
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (setter) setter.call(el, String(val));
        else el.value = String(val);
        el.dispatchEvent(new Event('input',  { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Tab' }));
        el.blur();
        return true;
    }

    function safeClick(el) {
        if (!el) return;
        ['mousedown','mouseup','click'].forEach(e =>
            el.dispatchEvent(new MouseEvent(e, { bubbles: true, cancelable: true, view: window })));
    }

    // ── Find input by nearby label text ──
    function findInputByLabel(...keywords) {
        const allInputs = Array.from(document.querySelectorAll('input[type="number"], input[type="text"], input:not([type])'));
        for (const inp of allInputs) {
            // Check placeholder
            const ph = (inp.placeholder || '').toLowerCase();
            if (keywords.some(k => ph.includes(k))) return inp;
            // Check aria-label
            const al = (inp.getAttribute('aria-label') || '').toLowerCase();
            if (keywords.some(k => al.includes(k))) return inp;
            // Check surrounding text (parent/sibling labels)
            const container = inp.closest('div, label, span, td') || inp.parentElement;
            const text = (container?.innerText || '').toLowerCase();
            if (keywords.some(k => text.includes(k))) return inp;
        }
        return null;
    }

    // ── Get account balance from XM page header ──
    function getBalance() {
        // XM competition header structure: Balance | Equity | Used Margin | Free Margin
        const header = document.querySelector('header, [class*="header"], [class*="topbar"], [class*="toolbar"], [class*="top-bar"], nav');
        if (header) {
            const nums = header.innerText.match(/[\d,]+\.\d{2}/g);
            if (nums && nums.length >= 1) {
                return parseFloat(nums[0].replace(',', ''));
            }
        }
        // Fallback: scan full page for balance pattern
        const all = document.body.innerText.match(/Balance[\s\S]{0,20}?([\d,]+\.\d{2})/i);
        if (all) return parseFloat(all[1].replace(',', ''));
        return 942; // last known
    }

    function calcLots(price) {
        const balance = getBalance();
        const available = balance * CFG.marginUsePct;
        const marginPerLot = (100000 * (price || 1.161)) / CFG.leverage;
        let lots = Math.floor((available / marginPerLot) / 0.01) * 0.01;
        lots = Math.round(Math.max(0.01, Math.min(lots, 5.0)) * 100) / 100;
        return { lots, balance };
    }

    // Update info bar every 3 seconds
    setInterval(() => {
        const { lots, balance } = calcLots(lastSignalData.price || 1.161);
        const info = document.getElementById('v6-info');
        if (info) info.innerHTML = `💰 Balance: <b>$${balance.toFixed(2)}</b> &nbsp;|&nbsp; Auto Lots: <b style="color:#00ff88">${lots}</b> &nbsp;|&nbsp; Margin: ${CFG.marginUsePct*100}%`;
    }, 3000);

    // ── CORE TRADE EXECUTOR ──
    async function executeTrade(action, sig = {}) {
        const now = Date.now();
        if (isExecuting || (now - lastExecutionTime) < CFG.executionCooldownMs) {
            const w = Math.ceil((CFG.executionCooldownMs - (now - lastExecutionTime)) / 1000);
            setStatus(`⏳ Cooldown — ${w}s...`, '#f59e0b');
            return;
        }
        isExecuting = true;
        lastExecutionTime = now;

        const price = sig.price || 1.161;
        const sl    = sig.stop_loss;
        const tp    = sig.take_profit;
        const { lots } = calcLots(price);
        const signalLots = sig.lots || lots;

        setStatus(`⚡ Preparing <b>${action} EURUSD</b> — ${signalLots} lots | TP/SL auto-set`, '#f59e0b');

        // ── STEP 1: Set Volume ──
        const volInput = findInputByLabel('volume', 'amount', 'quantity', 'lots', 'size')
            || Array.from(document.querySelectorAll('input')).find(i =>
                i.type === 'number' && parseFloat(i.value || '0') < 10);
        if (volInput) {
            setInputValue(volInput, signalLots);
            await new Promise(r => setTimeout(r, 200));
        }

        // ── STEP 2: Enable TP/SL toggle if it's off ──
        const tpslToggle = Array.from(document.querySelectorAll(
            'input[type="checkbox"], button[role="switch"], div[role="switch"], label[class*="toggle"], span[class*="toggle"], div[class*="switch"]'
        )).find(el => {
            const text = (el.closest('div,label,span')?.innerText || '').toLowerCase();
            return text.includes('tp') || text.includes('sl') || text.includes('stop') || text.includes('take');
        });

        if (tpslToggle) {
            // Only click if currently OFF
            const isOn = tpslToggle.checked || tpslToggle.getAttribute('aria-checked') === 'true'
                || tpslToggle.classList.contains('active') || tpslToggle.classList.contains('on');
            if (!isOn) {
                safeClick(tpslToggle);
                await new Promise(r => setTimeout(r, 400)); // wait for fields to appear
                setStatus(`🔘 TP/SL enabled — filling values...`, '#f59e0b');
            }
        }

        // ── STEP 3: Fill Stop Loss ──
        if (sl) {
            const slInput = findInputByLabel('stop loss', 'stop', 's/l', 'sl');
            if (slInput) {
                setInputValue(slInput, sl.toFixed(5));
                await new Promise(r => setTimeout(r, 200));
                setStatus(`🛡 SL set: ${sl.toFixed(5)}`, '#f59e0b');
            } else {
                console.warn('[BOT v6] SL input not found');
            }
        }

        // ── STEP 4: Fill Take Profit ──
        if (tp) {
            const tpInput = findInputByLabel('take profit', 'profit', 't/p', 'tp');
            if (tpInput) {
                setInputValue(tpInput, tp.toFixed(5));
                await new Promise(r => setTimeout(r, 200));
                setStatus(`🎯 TP set: ${tp.toFixed(5)}`, '#f59e0b');
            } else {
                console.warn('[BOT v6] TP input not found');
            }
        }

        // ── STEP 5: Click BUY or SELL tab ──
        const tab = Array.from(document.querySelectorAll('button, div[role="button"]')).find(b => {
            const t = (b.innerText || '').trim().toUpperCase();
            return action === 'BUY'
                ? (t === 'BUY' || (t.startsWith('BUY') && !t.includes('SELL')))
                : (t === 'SELL' || (t.startsWith('SELL') && !t.includes('BUY')));
        });
        if (tab) { safeClick(tab); await new Promise(r => setTimeout(r, 250)); }

        // ── STEP 6: Click Place Order ──
        const placeBtn = Array.from(document.querySelectorAll('button, div[role="button"]')).find(b => {
            const t = (b.innerText || '').trim().toUpperCase();
            return t.startsWith('PLACE ORDER AT') || t === 'PLACE ORDER';
        });
        if (!placeBtn) {
            setStatus('⚠️ Order panel not visible! Open the left trading panel.', '#ef4444');
            playChime(); isExecuting = false; return;
        }
        safeClick(placeBtn);
        setStatus(`⏱ Order placed — auto-confirming in ${CFG.confirmDelayMs}ms...`, '#f59e0b');

        // ── STEP 7: Delayed auto-confirm ──
        await new Promise(r => setTimeout(r, CFG.confirmDelayMs));
        const confirmBtn = Array.from(document.querySelectorAll('button')).find(b => {
            const t = (b.innerText || '').trim().toUpperCase();
            return (t === 'PLACE ORDER' || t === 'CONFIRM') && b.offsetWidth > 80;
        });
        if (confirmBtn) {
            safeClick(confirmBtn);
            playChime();
            setStatus(`✅ <b>${action} EURUSD — ${signalLots} lots</b><br>🎯 TP: ${tp?.toFixed(5) || 'n/a'} &nbsp; 🛡 SL: ${sl?.toFixed(5) || 'n/a'}`, '#00ff88');
            console.log(`[BOT v6] ✅ ${action} EURUSD @ ${signalLots} lots | TP: ${tp} | SL: ${sl}`);
        } else {
            playChime();
            setStatus(`🔔 Confirm manually — modal didn't appear`, '#f59e0b');
        }

        // Update signal info bar
        const sigEl = document.getElementById('v6-signal');
        if (sigEl) sigEl.innerHTML = `Last: <b style="color:${action==='BUY'?'#00ff88':'#ef4444'}">${action}</b> ${signalLots} lots | TP ${tp?.toFixed(5)} | SL ${sl?.toFixed(5)}`;

        setTimeout(() => { isExecuting = false; }, CFG.executionCooldownMs);
    }

    document.getElementById('v6-buy').onclick  = () => executeTrade('BUY',  lastSignalData);
    document.getElementById('v6-sell').onclick = () => executeTrade('SELL', lastSignalData);

    // ── Web Worker poller (no background throttle) ──
    const worker = new Worker(URL.createObjectURL(
        new Blob([`setInterval(()=>postMessage('tick'),${CFG.pollMs});`], { type: 'application/javascript' })
    ));
    worker.onmessage = async () => {
        try {
            const res = await fetch(CFG.bridgeUrl, { cache: 'no-store' });
            if (!res.ok) return;
            const data = await res.json();
            if (!data?.signals?.EURUSD) return;
            const sig = data.signals.EURUSD;
            lastSignalData = sig;
            const key = `${sig.signal}_${sig.price}_${Math.floor(sig.timestamp)}`;
            if (key === lastSignalKey) return;
            lastSignalKey = key;
            await executeTrade(sig.signal, sig);
        } catch (e) {}
    };

    // Bridge health
    setInterval(async () => {
        try {
            const r = await fetch('http://localhost:8765/status', { cache: 'no-store' });
            document.getElementById('v6pulse').style.background = r.ok ? '#00ff88' : '#ef4444';
        } catch { document.getElementById('v6pulse').style.background = '#ef4444'; }
    }, 5000);

    setStatus('🟢 Live | TP/SL engine ready...');
    console.log('%c[XM BOT v6] TP/SL + Margin Engine ONLINE!', 'color:#00ff88;font-weight:bold');
})();
