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
                    if (localStorage.getItem('isLoggedIn')) {
                        return response;
                    } else {
                        // If not authenticated, redirect to index.html
                        return caches.match('/index.html');
                    }
                }
                return fetch(event.request);
            })
    );
});
