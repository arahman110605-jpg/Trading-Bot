//+------------------------------------------------------------------+
//|                                     ActiveBot_VisualOverlay.mq5   |
//|               Visual Real-Time Chart Overlay for Trading Bot     |
//+------------------------------------------------------------------+
#property copyright "Antigravity AI"
#property link      "https://antigravity.google"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

// Indicator Inputs
input int InpEMA20_Period   = 20;     // Fast Dynamic Mean EMA
input int InpEMA50_Period   = 50;     // Medium Structure EMA
input int InpEMA200_Period  = 200;    // Macro Trend Baseline EMA

int handle_ema20;
int handle_ema50;
int handle_ema200;

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize EMA Handles
   handle_ema20  = iMA(_Symbol, _Period, InpEMA20_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_ema50  = iMA(_Symbol, _Period, InpEMA50_Period, 0, MODE_EMA, PRICE_CLOSE);
   handle_ema200 = iMA(_Symbol, _Period, InpEMA200_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(handle_ema20 == INVALID_HANDLE || handle_ema50 == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles");
      return(INIT_FAILED);
   }

   ChartSetInteger(0, CHART_SHOW_TRADE_LEVELS, true);
   EventSetTimer(1); // Update HUD every second
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, "AB_HUD_");
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   UpdateHUD();
   return(rates_total);
}

//+------------------------------------------------------------------+
//| Timer Event function                                             |
//+------------------------------------------------------------------+
void OnTimer()
{
   UpdateHUD();
}

//+------------------------------------------------------------------+
//| Render Live Bot HUD Overlay on Chart                             |
//+------------------------------------------------------------------+
void UpdateHUD()
{
   double ema20[], ema50[], ema200[];
   ArraySetAsSeries(ema20, true);
   ArraySetAsSeries(ema50, true);
   ArraySetAsSeries(ema200, true);
   
   CopyBuffer(handle_ema20, 0, 0, 3, ema20);
   CopyBuffer(handle_ema50, 0, 0, 3, ema50);
   CopyBuffer(handle_ema200, 0, 0, 3, ema200);
   
   MqlTick last_tick;
   SymbolInfoTick(_Symbol, last_tick);
   double close_curr = last_tick.bid;
   
   string macro_trend = (close_curr > ema200[0]) ? "BULLISH (UPTREND)" : "BEARISH (DOWNTREND)";
   color macro_col    = (close_curr > ema200[0]) ? clrLimeGreen : clrTomato;
   
   string m5_state    = (close_curr > ema20[0]) ? "ABOVE 20 EMA (BULLISH)" : "BELOW 20 EMA (BEARISH)";
   color m5_col       = (close_curr > ema20[0]) ? clrLimeGreen : clrTomato;

   // Count Open Positions
   int open_trades = 0;
   double total_pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         open_trades++;
         total_pnl += PositionGetDouble(POSITION_PROFIT);
      }
   }

   // Draw HUD Box
   DrawLabel("AB_HUD_Title", "=== ACTIVE BOT LIVE COCKPIT ===", 20, 30, clrGold, 11, true);
   DrawLabel("AB_HUD_Symbol", "Symbol: " + _Symbol + " | Timeframe: M5", 20, 50, clrWhite, 9, false);
   DrawLabel("AB_HUD_Macro",  "Macro Trend (200 EMA): " + macro_trend, 20, 70, macro_col, 9, true);
   DrawLabel("AB_HUD_Micro",  "Micro Momentum (20 EMA): " + m5_state, 20, 90, m5_col, 9, false);
   
   string pos_str = (open_trades > 0) ? StringFormat("Active Trades: %d | Floating P&L: $%.2f", open_trades, total_pnl) : "Active Trades: 0 (Scanning for Entry)";
   color pos_col  = (open_trades > 0) ? ((total_pnl >= 0) ? clrLimeGreen : clrTomato) : clrDeepSkyBlue;
   DrawLabel("AB_HUD_Pos", pos_str, 20, 110, pos_col, 10, true);
   
   DrawLabel("AB_HUD_Status", "Auto-Trading Status: BOT RUNNING 24/7", 20, 130, clrLimeGreen, 9, false);
}

//+------------------------------------------------------------------+
//| Helper to render clean GUI labels                                |
//+------------------------------------------------------------------+
void DrawLabel(string name, string text, int x, int y, color col, int font_size, bool bold)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
}
