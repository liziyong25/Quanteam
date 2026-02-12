import axios from 'axios';

type RequestMeta = {
  startMs?: number;
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 20000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    (config as any).metadata = {
      ...(config as any).metadata,
      startMs: Date.now(),
    } satisfies RequestMeta;
    // 这里可以添加认证 token
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    const startMs = (response.config as any)?.metadata?.startMs as number | undefined;
    if (startMs) {
      const costMs = Date.now() - startMs;
      if (costMs > 1500) {
        console.warn(`[api] slow ${costMs}ms ${response.config.method?.toUpperCase()} ${response.config.url}`);
      }
    }
    return response.data;
  },
  (error) => {
    // 统一错误处理
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export default api;
