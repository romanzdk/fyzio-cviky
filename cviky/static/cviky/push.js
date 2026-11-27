function urlBase64ToUint8Array(base64String) {
  var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  var rawData = window.atob(base64);
  var outputArray = new Uint8Array(rawData.length);
  for (var i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function getCookie(name) {
  var match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return match ? match.pop() : '';
}

document.addEventListener('DOMContentLoaded', function () {
  var button = document.getElementById('enable-push');
  var status = document.getElementById('push-status');
  if (!button) {
    return;
  }
  button.addEventListener('click', async function () {
    button.disabled = true;
    try {
      var permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        status.textContent = 'Upozornění byla zamítnuta.';
        button.disabled = false;
        return;
      }
      var registration = await navigator.serviceWorker.ready;
      var applicationServerKey = urlBase64ToUint8Array(button.dataset.vapidPublicKey);
      var subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey,
      });
      var response = await fetch('/push/odebirat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(subscription),
      });
      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }
      status.textContent = 'Upozornění zapnuta';
    } catch (error) {
      status.textContent = 'Upozornění se nepodařilo zapnout.';
      button.disabled = false;
    }
  });
});
