// Backend API types matching Pydantic schemas

export interface TelegramConfig {
  bot_token: string;
  chat_id: string;
  message_cooldown_minutes: number;
}

export interface TimeframeJob {
  timeframe: string;
  poll_interval_seconds: number;
}

export interface BacktestConfig {
  enabled: boolean;
  lookback_bars: number;
}

export interface AppConfig {
  // Trading
  timezone: string;
  pairs: string[];
  notify_hourly_summary: boolean;

  // Timeframes
  timeframes: TimeframeJob[];

  // Telegram
  telegram: TelegramConfig;

  // Indicators
  adx_threshold: number;
  rsi_overbought: number;
  rsi_oversold: number;

  // System
  sqlite_path: string;
  backtest: BacktestConfig;
}

export interface Setting {
  id: string;
  key: string;
  value: unknown;
  value_type: "string" | "int" | "float" | "bool" | "json";
  is_user_override: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SettingHistory {
  id: string;
  setting_id: string;
  old_value: string;
  new_value: string;
  changed_by: string | null;
  changed_at: string;
}

export interface BulkUpdateRequest {
  updates: Record<string, unknown>;
}