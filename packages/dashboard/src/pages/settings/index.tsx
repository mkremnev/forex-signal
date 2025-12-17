import { Toaster } from "react-hot-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui";
import { useSettings } from "@/shared/api/hooks";
import { TelegramTab } from "./components/TelegramTab";
import { TradingTab } from "./components/TradingTab";
import { TimeframesTab } from "./components/TimeframesTab";
import { IndicatorsTab } from "./components/IndicatorsTab";
import { SystemTab } from "./components/SystemTab";

const Settings = () => {
  const { settings, isLoading, error } = useSettings();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Загрузка настроек...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-600">Ошибка загрузки настроек. Пожалуйста, попробуйте позже.</div>
      </div>
    );
  }

  if (!settings) {
    return null;
  }

  return (
    <div className="container mx-auto p-6">
      <Toaster position="top-right" />

      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Настройки</h1>
        <p className="text-gray-600 mt-2">Управление параметрами торгового агента</p>
      </div>

      <Tabs defaultValue="telegram" className="w-full">
        <TabsList className="grid w-full grid-cols-5 mb-6">
          <TabsTrigger value="telegram">Telegram</TabsTrigger>
          <TabsTrigger value="trading">Торговля</TabsTrigger>
          <TabsTrigger value="timeframes">Таймфреймы</TabsTrigger>
          <TabsTrigger value="indicators">Индикаторы</TabsTrigger>
          <TabsTrigger value="system">Система</TabsTrigger>
        </TabsList>

        <TabsContent value="telegram">
          <TelegramTab settings={settings} />
        </TabsContent>

        <TabsContent value="trading">
          <TradingTab settings={settings} />
        </TabsContent>

        <TabsContent value="timeframes">
          <TimeframesTab settings={settings} />
        </TabsContent>

        <TabsContent value="indicators">
          <IndicatorsTab settings={settings} />
        </TabsContent>

        <TabsContent value="system">
          <SystemTab settings={settings} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export const Page = Settings;
