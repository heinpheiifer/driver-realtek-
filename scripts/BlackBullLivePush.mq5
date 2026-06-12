//+------------------------------------------------------------------+
//|                                    BlackBullLivePush.mq5          |
//| Push live BlackBull OHLCV to Open Trader (Linux Wine MT5 OK)    |
//+------------------------------------------------------------------+
#property copyright "OpenTrader"
#property version   "1.00"
#property strict

input string InpSymbols     = "XRPUSD,EURUSD,BTCUSD,GBPUSD";
input string InpTimeframes  = "M1,M5,H1";
input int    InpBars        = 1500;
input int    InpIntervalSec = 60;
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

ENUM_TIMEFRAMES TfFromLabel(const string label)
{
   if(label == "M1")  return PERIOD_M1;
   if(label == "M5")  return PERIOD_M5;
   if(label == "M15") return PERIOD_M15;
   if(label == "M30") return PERIOD_M30;
   if(label == "H1")  return PERIOD_H1;
   if(label == "H4")  return PERIOD_H4;
   if(label == "D1")  return PERIOD_D1;
   return PERIOD_M5;
}

bool PushSymbol(const string symbol, const ENUM_TIMEFRAMES tf)
{
   if(!SymbolSelect(symbol, true))
   {
      Print("Symbol not found: ", symbol);
      return false;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(symbol, tf, 0, InpBars, rates);
   if(copied <= 0)
   {
      Print("CopyRates failed: ", symbol, " ", EnumToString(tf));
      return false;
   }

   string tf_label = TfLabel(tf);
   string clean = symbol;
   StringReplace(clean, "/", "");

   string body = "{";
   body += "\"symbol\":\"" + clean + "\",";
   body += "\"timeframe\":\"" + tf_label + "\",";
   body += "\"candles\":[";

   for(int i = copied - 1; i >= 0; i--)
   {
      if(i < copied - 1) body += ",";
      string ts = TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
      body += "{";
      body += "\"timestamp\":\"" + ts + "\",";
      body += "\"open\":" + DoubleToString(rates[i].open, 8) + ",";
      body += "\"high\":" + DoubleToString(rates[i].high, 8) + ",";
      body += "\"low\":" + DoubleToString(rates[i].low, 8) + ",";
      body += "\"close\":" + DoubleToString(rates[i].close, 8) + ",";
      body += "\"volume\":" + IntegerToString(rates[i].tick_volume);
      body += "}";
   }
   body += "]}";

   char post[];
   char result[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(body, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, StringLen(body));

   ResetLastError();
   int code = WebRequest("POST", InpOpenTraderUrl, headers, 5000, post, result, headers);
   if(code == -1)
   {
      Print("WebRequest failed err=", GetLastError(),
            " — add URL in MT5: Tools → Options → Expert Advisors → Allow WebRequest");
      return false;
   }
   if(code < 200 || code >= 300)
   {
      Print("HTTP ", code, " for ", symbol, " ", tf_label);
      return false;
   }

   Print("Pushed ", copied, " bars ", symbol, " ", tf_label, " → OpenTrader");
   return true;
}

void PushAll()
{
   string syms[];
   int ns = StringSplit(InpSymbols, ',', syms);
   string tfs[];
   int nt = StringSplit(InpTimeframes, ',', tfs);

   for(int s = 0; s < ns; s++)
   {
      string sym = syms[s];
      StringTrimLeft(sym);
      StringTrimRight(sym);
      if(StringLen(sym) == 0) continue;

      for(int t = 0; t < nt; t++)
      {
         string tf = tfs[t];
         StringTrimLeft(tf);
         StringTrimRight(tf);
         if(StringLen(tf) == 0) continue;
         PushSymbol(sym, TfFromLabel(tf));
      }
   }
}

int OnInit()
{
   EventSetTimer(MathMax(15, InpIntervalSec));
   PushAll();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   PushAll();
}

void OnTick() {}
