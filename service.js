const cacheName = 'my-app-cache';
const filesToCache = [
    '/basic_user_home.html',
    // Add other files to cache here
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(cacheName)
            .then(cache => {
                return cache.addAll(filesToCache);
            })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    // If the user is authenticated, serve the cached file
                    return response || fetch(event.request);
                }
                return fetch(event.request);
            })
    );
});
