const VERSION = new URL(self.location.href).searchParams.get('v') || 'dev'

const CACHE_NAME = '3hk-app-v' + VERSION

// 【修改点1】从列表中删除了 '/'
// 首页必须实时请求，否则无法判断是否需要跳转 /main 或显示多账号登录
const ASSETS_TO_CACHE = ['/static/images/icon-192.png', '/static/images/icon-512.png', '/manifest.json']

self.addEventListener('install', (e) => {
  self.skipWaiting()
  e.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keyList) => {
      return Promise.all(
        keyList.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key)
          }
        }),
      )
    }),
  )
  return self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  // 1. API 请求：网络优先
  if (e.request.url.includes('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => new Response(JSON.stringify({ status: 'error', message: '网络已断开' }))),
    )
    return
  }

  // 【修改点2】页面导航请求（HTML）：强制网络优先
  // 解决 net::ERR_FAILED 的关键！
  // 只有走网络，浏览器才能正确处理 Flask 返回的 302 重定向
  if (e.request.mode === 'navigate' || e.request.headers.get('accept').includes('text/html')) {
    e.respondWith(fetch(e.request))
    return
  }

  // 2. 静态资源（CSS, JS, IMG）：缓存优先
  e.respondWith(
    caches.match(e.request).then((response) => {
      if (response) return response

      // 忽略参数匹配缓存 (主要用于静态资源版本号)
      return caches.match(e.request, { ignoreSearch: true }).then((res) => {
        return res || fetch(e.request)
      })
    }),
  )
})
