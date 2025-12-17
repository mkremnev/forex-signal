import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label, Input, Switch, Button } from "../../../shared/ui";
import { tradingSchema, type TradingFormData } from "../lib/validation";
import { useSettings } from "../../../shared/api/hooks";
import type { AppConfig } from "../../../shared/api/types";
import { useState } from "react";

interface TradingTabProps {
  settings: AppConfig;
}

// Common currency pairs
const AVAILABLE_PAIRS = [
  "EUR_USD",
  "GBP_USD",
  "USD_JPY",
  "USD_CHF",
  "AUD_USD",
  "NZD_USD",
  "USD_CAD",
  "EUR_GBP",
  "EUR_JPY",
  "GBP_JPY",
];

export function TradingTab({ settings }: TradingTabProps) {
  const { updateSettings } = useSettings();
  const [newPair, setNewPair] = useState("");

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
    watch,
    setValue,
  } = useForm<TradingFormData>({
    resolver: zodResolver(tradingSchema),
    defaultValues: {
      pairs: settings.pairs,
      timezone: settings.timezone,
      notify_hourly_summary: settings.notify_hourly_summary,
    },
  });

  const pairs = watch("pairs");

  const onSubmit = async (data: TradingFormData) => {
    await updateSettings(data);
  };

  const addPair = (pair: string) => {
    if (pair && !pairs.includes(pair)) {
      setValue("pairs", [...pairs, pair]);
      setNewPair("");
    }
  };

  const removePair = (pair: string) => {
    setValue(
      "pairs",
      pairs.filter((p) => p !== pair)
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-semibold mb-6">Торговые параметры</h2>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Currency Pairs */}
        <div className="space-y-3">
          <Label>Валютные пары</Label>

          {/* Selected Pairs */}
          <div className="flex flex-wrap gap-2 min-h-[40px] p-2 border border-gray-300 rounded-md">
            {pairs.map((pair) => (
              <span
                key={pair}
                className="inline-flex items-center gap-1 bg-gray-900 text-white px-3 py-1 rounded-md text-sm"
              >
                {pair}
                <button
                  type="button"
                  onClick={() => removePair(pair)}
                  className="ml-1 hover:text-red-300"
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          {/* Quick Add Buttons */}
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_PAIRS.filter((p) => !pairs.includes(p)).map((pair) => (
              <button
                key={pair}
                type="button"
                onClick={() => addPair(pair)}
                className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-100"
              >
                + {pair}
              </button>
            ))}
          </div>

          {/* Custom Pair Input */}
          <div className="flex gap-2">
            <Input
              placeholder="Добавить свою пару (например, EUR_GBP)"
              value={newPair}
              onChange={(e) => setNewPair(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addPair(newPair);
                }
              }}
            />
            <Button
              type="button"
              onClick={() => addPair(newPair)}
              variant="outline"
            >
              Добавить
            </Button>
          </div>

          {errors.pairs && (
            <p className="text-sm text-red-600">{errors.pairs.message}</p>
          )}
          <p className="text-sm text-gray-500">
            Выберите валютные пары для мониторинга
          </p>
        </div>

        {/* Timezone */}
        <div className="space-y-2">
          <Label htmlFor="timezone">Часовой пояс</Label>
          <Input
            id="timezone"
            type="text"
            placeholder="Europe/Moscow"
            {...register("timezone")}
          />
          {errors.timezone && (
            <p className="text-sm text-red-600">{errors.timezone.message}</p>
          )}
          <p className="text-sm text-gray-500">
            Часовой пояс для временных меток (например, Europe/Moscow,
            America/New_York)
          </p>
        </div>

        {/* Hourly Summary */}
        <div className="flex items-center justify-between p-4 border border-gray-200 rounded-md">
          <div className="space-y-1">
            <Label htmlFor="notify_hourly_summary">
              Почасовые сводки в Telegram
            </Label>
            <p className="text-sm text-gray-500">
              Отправлять сводку каждый час
            </p>
          </div>
          <Controller
            name="notify_hourly_summary"
            control={control}
            render={({ field }) => (
              <Switch
                id="notify_hourly_summary"
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            )}
          />
        </div>

        {/* Submit Button */}
        <div className="pt-4">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Сохранение..." : "Сохранить изменения"}
          </Button>
        </div>
      </form>
    </div>
  );
}