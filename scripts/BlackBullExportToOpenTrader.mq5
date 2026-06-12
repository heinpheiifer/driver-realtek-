//+------------------------------------------------------------------+
//|                              BlackBullExportToOpenTrader.mq5      |
//| Exports OHLCV from BlackBull MT5 to Open Trader import folder   |
//+------------------------------------------------------------------+
#property script_show_inputs
input string InpSymbol = "BTCUSD";
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5;
input int InpBars = 800;
input string InpOpenTraderUrl = "http://127.0.0.1:8010/api/market/blackbull/import";

string TfLabel(const ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      default:         return "M5";
   }
}

bool ExportCsv(const string symbol, const ENUM_TIMEFRAMES tf, const int bars)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, tf, 0, bars, rates);
   if(copied <= 0)
   {
      Print("CopyRates failed for ", symbol);
      return false;
   }

   string tf_label = TfLabel(tf);
   string filename = StringFormat("blackbull_import\\%s_%s.csv",
      StringToLower(symbol), StringToLower(tf_label));

   int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("FileOpen failed: ", filename, " err=", GetLastError());
      return false;
   }

   FileWrite(handle, "timestamp", "open", "high", "low", "close", "volume");
   for(int i = copied - 1; i >= 0; i--)
   {
      string ts = TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
      FileWrite(handle, ts,
         DoubleToString(rates[i].open, _Digits),
         DoubleToString(rates[i].high, _Digits),
         DoubleToString(rates[i].low, _Digits),
         DoubleToString(rates[i].close, _Digits),
         DoubleToString(rates[i].tick_volume, 0));
   }
   FileClose(handle);
   Print("Exported ", copied, " bars to MQL5/Files/", filename);
   Print("Copy to Open Trader: trading_data/blackbull_import/");
   return true;
}

void OnStart()
{
   if(!SymbolSelect(InpSymbol, true))
   {
      Print("Symbol not found: ", InpSymbol);
      return;
   }
   ExportCsv(InpSymbol, InpTimeframe, InpBars);
}
