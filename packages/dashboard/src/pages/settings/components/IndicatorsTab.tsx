import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Label, Slider, Button } from "../../../shared/ui";
import { indicatorsSchema, type IndicatorsFormData } from "../lib/validation";
import { useSettings } from "../../../shared/api/hooks";
import type { AppConfig } from "../../../shared/api/types";

interface IndicatorsTabProps {
  settings: AppConfig;
}

export function IndicatorsTab({ settings }: IndicatorsTabProps) {
  const { updateSettings } = useSettings();

  const {
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
    setValue,
  } = useForm<IndicatorsFormData>({
    resolver: zodResolver(indicatorsSchema),
    defaultValues: {
      adx_threshold: settings.adx_threshold,
      rsi_overbought: settings.rsi_overbought,
      rsi_oversold: settings.rsi_oversold,
    },
  });

  const adxValue = watch("adx_threshold");
  const rsiOverboughtValue = watch("rsi_overbought");
  const rsiOversoldValue = watch("rsi_oversold");

  const onSubmit = async (data: IndicatorsFormData) => {
    await updateSettings(data);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-semibold mb-6">Пороговые значения индикаторов</h2>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        {/* ADX Threshold */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="adx_threshold">ADX Threshold</Label>
              <p className="text-sm text-gray-500 mt-1">
                Минимальное значение ADX для определения тренда
              </p>
            </div>
            <span className="text-2xl font-bold text-gray-900">
              {adxValue.toFixed(1)}
            </span>
          </div>
          <Slider
            id="adx_threshold"
            min={0}
            max={100}
            step={0.5}
            value={[adxValue]}
            onValueChange={(value) => setValue("adx_threshold", value[0])}
          />
          {errors.adx_threshold && (
            <p className="text-sm text-red-600">{errors.adx_threshold.message}</p>
          )}
          <div className="flex justify-between text-xs text-gray-500">
            <span>0 (слабый тренд)</span>
            <span>100 (сильный тренд)</span>
          </div>
        </div>

        {/* RSI Overbought */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="rsi_overbought">RSI Overbought</Label>
              <p className="text-sm text-gray-500 mt-1">
                Уровень перекупленности (сигнал продажи)
              </p>
            </div>
            <span className="text-2xl font-bold text-red-600">
              {rsiOverboughtValue.toFixed(1)}
            </span>
          </div>
          <Slider
            id="rsi_overbought"
            min={50}
            max={100}
            step={0.5}
            value={[rsiOverboughtValue]}
            onValueChange={(value) => setValue("rsi_overbought", value[0])}
          />
          {errors.rsi_overbought && (
            <p className="text-sm text-red-600">{errors.rsi_overbought.message}</p>
          )}
          <div className="flex justify-between text-xs text-gray-500">
            <span>50</span>
            <span>100</span>
          </div>
        </div>

        {/* RSI Oversold */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label htmlFor="rsi_oversold">RSI Oversold</Label>
              <p className="text-sm text-gray-500 mt-1">
                Уровень перепроданности (сигнал покупки)
              </p>
            </div>
            <span className="text-2xl font-bold text-green-600">
              {rsiOversoldValue.toFixed(1)}
            </span>
          </div>
          <Slider
            id="rsi_oversold"
            min={0}
            max={50}
            step={0.5}
            value={[rsiOversoldValue]}
            onValueChange={(value) => setValue("rsi_oversold", value[0])}
          />
          {errors.rsi_oversold && (
            <p className="text-sm text-red-600">{errors.rsi_oversold.message}</p>
          )}
          <div className="flex justify-between text-xs text-gray-500">
            <span>0</span>
            <span>50</span>
          </div>
        </div>

        {/* Validation Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="text-sm text-blue-800">
            <strong>Правило:</strong> RSI Overbought должен быть больше RSI Oversold.
            Текущий спред: {(rsiOverboughtValue - rsiOversoldValue).toFixed(1)} пунктов.
          </p>
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