<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>One-time link</title>

<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial;
  background: #f4f6f8;
  margin: 0;
}

.container {
  max-width: 720px;
  margin: 60px auto;
  background: #fff;
  padding: 32px;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(0,0,0,.08);
}

h1 {
  margin-top: 0;
  font-size: 22px;
  color: #111827;
}

.form-row {
  display: flex;
  gap: 10px;
}

input[type="text"] {
  flex: 1;
  padding: 12px 14px;
  font-size: 15px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
}

button {
  padding: 12px 18px;
  border-radius: 10px;
  border: none;
  background: #4f46e5;
  color: #fff;
  font-size: 15px;
  cursor: pointer;
}

button:hover {
  background: #4338ca;
}

.result {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}

.result input {
  background: #f9fafb;
}

.history {
  margin-top: 28px;
}

.history h2 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #374151;
}

.history-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 10px;
}

.status-new { background: #facc15; }
.status-opened { background: #22c55e; }
.status-used { background: #ef4444; }

.history-url {
  font-size: 14px;
  color: #374151;
  word-break: break-all;
}

.history-time {
  font-size: 12px;
  color: #6b7280;
}
</style>
</head>

<body>

<div class="container">
  <h1>Генерация одноразовой ссылки</h1>

  <!-- ИСХОДНАЯ ССЫЛКА -->
  <form method="post" action="/create">
    <div class="form-row">
      <input
        type="text"
        name="target_url"
        placeholder="Вставьте ссылку"
        value="{{ target }}"
        required
      >
      <button type="submit">Сгенерировать</button>
    </div>
  </form>

  <!-- ОДНОРАЗОВАЯ ССЫЛКА -->
  {% if link %}
  <div class="result">
    <input
      id="result"
      type="text"
      value="{{ link }}"
      readonly
    >
    <button type="button" onclick="copyLink()">Скопировать</button>
  </div>
  {% endif %}

  <!-- ИСТОРИЯ -->
  <div class="history">
    <h2>История ссылок</h2>

    <div id="history">
      {% for code, item in links.items() %}
        <div class="history-item">
          <span class="status-dot
            {% if item.state == 'NEW' %}status-new
            {% elif item.state == 'OPENED' %}status-opened
            {% else %}status-used{% endif %}">
          </span>
          <div>
            <div class="history-url">
              {{ request.base_url }}l/{{ code }}
            </div>
            <div class="history-time">
              {{ item.created_at }}
            </div>
          </div>
        </div>
      {% endfor %}
    </div>
  </div>
</div>

<script>
function copyLink() {
  const input = document.getElementById('result');
  input.select();
  input.setSelectionRange(0, 99999);
  document.execCommand("copy");
}

/* автообновление истории */
setInterval(() => {
  fetch('/status')
    .then(r => r.json())
    .then(data => {
      const history = document.getElementById('history');
      if (!history) return;

      history.innerHTML = '';

      Object.keys(data).reverse().forEach(code => {
        const item = data[code];
        let cls = 'status-new';
        if (item.state === 'OPENED') cls = 'status-opened';
        if (item.state === 'USED') cls = 'status-used';

        history.innerHTML += `
          <div class="history-item">
            <span class="status-dot ${cls}"></span>
            <div>
              <div class="history-url">
                ${location.origin}/l/${code}
              </div>
              <div class="history-time">
                ${item.created_at || ''}
              </div>
            </div>
          </div>`;
      });
    });
}, 4000);
</script>

</body>
</html>















