self.addEventListener('push', function (event) {
  var data = {};
  if (event.data) {
    data = event.data.json();
  }
  var title = data.title || 'Cviky';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || '',
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url =
    (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then(function (clientList) {
        var target = new URL(url, self.location.origin).href;
        for (var i = 0; i < clientList.length; i++) {
          var client = clientList[i];
          if (client.url === target && 'focus' in client) {
            return client.focus();
          }
        }
        if (self.clients.openWindow) {
          return self.clients.openWindow(url);
        }
      })
  );
});
