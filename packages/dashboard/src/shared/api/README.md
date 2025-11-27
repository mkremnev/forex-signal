# API Client & Data Fetching

This directory contains the API client configuration and data fetching utilities using axios and SWR.

## Structure

```
src/shared/api/
├── fetcher.ts          # Axios instance and fetcher functions
├── hooks/              # SWR hooks for data fetching
│   ├── usePairs.ts   # Example: Forex signals hooks
│   └── index.ts        # Hooks exports
├── index.ts            # Main exports
└── README.md           # This file
```

## Quick Start

### 1. Configure API Base URL

Create a `.env` file in the dashboard root:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 2. Basic Usage with SWR Hook

```tsx
import { useSignals } from '@/shared/api/hooks';

function SignalsPage() {
  const { signals, isLoading, isError } = useSignals();

  if (isLoading) return <div>Loading...</div>;
  if (isError) return <div>Error loading signals</div>;

  return (
    <ul>
      {signals?.map(signal => (
        <li key={signal.id}>{signal.message}</li>
      ))}
    </ul>
  );
}
```

### 3. Direct Fetcher Usage

```tsx
import { fetcher, fetcherWithParams } from '@/shared/api';

// Simple GET request
const data = await fetcher('/api/signals');

// GET with query params
const filteredData = await fetcherWithParams('/api/signals', {
  pair: 'EURUSD',
  timeframe: '4h'
});
```

### 4. Using Axios Instance Directly

```tsx
import { axiosInstance } from '@/shared/api';

// POST request
const response = await axiosInstance.post('/api/settings', {
  cooldown: 60,
  pairs: ['EURUSD', 'GBPUSD']
});

// PUT request
await axiosInstance.put('/api/settings/1', { cooldown: 120 });

// DELETE request
await axiosInstance.delete('/api/signals/123');
```

## Features

### Axios Instance Configuration

- **Base URL**: Configured via `VITE_API_BASE_URL` environment variable
- **Timeout**: 10 seconds default
- **Auth**: Automatically adds Bearer token from localStorage
- **Interceptors**: Request/response interceptors for auth and error handling

### Request Interceptor

Automatically adds authentication token to all requests:

```typescript
// Token is read from localStorage
const token = localStorage.getItem('auth_token');
// Added as: Authorization: Bearer <token>
```

### Response Interceptor

Handles common error scenarios:
- Server errors (4xx, 5xx)
- Network errors
- Timeout errors

### Fetcher Functions

1. **fetcher**: Basic GET request fetcher for SWR
2. **fetcherWithParams**: GET request with query parameters
3. **createFetchError**: Converts axios errors to SWR-compatible format

## Creating New Hooks

Follow this pattern for creating new SWR hooks:

```typescript
import useSWR, { SWRConfiguration } from 'swr';
import { fetcher, FetchError } from '../fetcher';

interface MyData {
  id: string;
  name: string;
}

export function useMyData(config?: SWRConfiguration) {
  const { data, error, isLoading, mutate } = useSWR<MyData[], FetchError>(
    '/api/my-endpoint',
    fetcher,
    {
      refreshInterval: 30000, // 30 seconds
      revalidateOnFocus: true,
      ...config,
    }
  );

  return {
    data,
    isLoading,
    isError: error,
    mutate,
  };
}
```

## SWR Configuration Options

Common SWR options used in this project:

- `refreshInterval`: Auto-refresh data every N milliseconds
- `revalidateOnFocus`: Refetch when window regains focus
- `revalidateOnReconnect`: Refetch when network reconnects
- `dedupingInterval`: Dedupe requests within this interval
- `errorRetryCount`: Number of retry attempts on error

## Error Handling

Errors are typed as `FetchError`:

```typescript
interface FetchError extends Error {
  status?: number;  // HTTP status code
  info?: any;       // Response data
}
```

Example error handling:

```tsx
const { signals, isError } = useSignals();

if (isError) {
  console.error('Status:', isError.status);
  console.error('Info:', isError.info);
  console.error('Message:', isError.message);
}
```

## Best Practices

1. **Use hooks for data fetching**: Prefer SWR hooks over direct axios calls
2. **Handle loading states**: Always show loading indicators
3. **Handle errors gracefully**: Show user-friendly error messages
4. **Use TypeScript types**: Define interfaces for API responses
5. **Leverage SWR cache**: Use mutate for optimistic updates
6. **Configure refresh intervals**: Balance freshness with performance

## Example: Optimistic Updates

```tsx
const { signals, mutate } = useSignals();

const deleteSignal = async (id: string) => {
  // Optimistically update UI
  mutate(
    signals?.filter(s => s.id !== id),
    false // Don't revalidate immediately
  );

  try {
    await axiosInstance.delete(`/api/signals/${id}`);
    // Revalidate to sync with server
    mutate();
  } catch (error) {
    // Revert on error
    mutate();
  }
};
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000` |

## Authentication

The API client automatically handles JWT token authentication:

1. Token is stored in `localStorage` with key `auth_token`
2. Request interceptor adds `Authorization: Bearer <token>` header
3. Response interceptor handles 401 Unauthorized responses

To set the auth token:

```typescript
localStorage.setItem('auth_token', 'your-jwt-token');
```

To clear the auth token:

```typescript
localStorage.removeItem('auth_token');
```