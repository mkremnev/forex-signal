import axios, { AxiosError, type AxiosRequestConfig } from "axios";

// Create axios instance with default config
export const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth tokens, etc.
axiosInstance.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle common errors
    if (error.response) {
      // Server responded with error status
      console.error("API Error:", error.response.status, error.response.data);
    } else if (error.request) {
      // Request was made but no response
      console.error("Network Error:", error.message);
    } else {
      // Something else happened
      console.error("Error:", error.message);
    }
    return Promise.reject(error);
  }
);

// Generic fetcher for SWR
export const fetcher = async <T = never>(url: string, config?: AxiosRequestConfig): Promise<T> => {
  const response = await axiosInstance.get<T>(url, config);
  return response.data;
};

// Fetcher with query params support
export const fetcherWithParams = async <T = never>(url: string, params?: Record<string, never>): Promise<T> => {
  return fetcher<T>(url, { params });
};

// Type for SWR error
export interface FetchError extends Error {
  status?: number;
  info?: unknown;
}

// Helper to create error object
export const createFetchError = (error: AxiosError): FetchError => {
  const fetchError: FetchError = new Error(error.response?.statusText || error.message || "An error occurred");
  fetchError.status = error.response?.status;
  fetchError.info = error.response?.data;
  return fetchError;
};
