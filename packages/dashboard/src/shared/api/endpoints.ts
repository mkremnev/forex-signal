// Backend API base URL from environment or default
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const endpoints = {
  // Auth
  register: `${API_BASE_URL}/api/v1/auth/register`,
  login: `${API_BASE_URL}/api/v1/auth/login`,
  me: `${API_BASE_URL}/api/v1/auth/me`,

  // Settings
  settings: `${API_BASE_URL}/api/v1/settings`,
  settingByKey: (key: string) => `${API_BASE_URL}/api/v1/settings/${key}`,
  mergedConfig: `${API_BASE_URL}/api/v1/settings/config`,
  bulkUpdate: `${API_BASE_URL}/api/v1/settings/bulk-update`,
  settingHistory: (key: string) => `${API_BASE_URL}/api/v1/settings/history/${key}`,
  resetSetting: (key: string) => `${API_BASE_URL}/api/v1/settings/reset/${key}`,

  // Legacy
  allPairs: "",
};
