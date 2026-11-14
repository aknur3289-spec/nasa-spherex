# SPHEREx

Офлайн-пайплайн на Python → статические файлы → веб-клиент.

- [pipeline/](pipeline/) — подготовка данных
- [web/](web/) — Vite, React и TypeScript
- [data/](data/) — манифест и готовые вырезки
- [docs/CONTRACT.md](docs/CONTRACT.md) — контракт данных
- [docs/DECISIONS.md](docs/DECISIONS.md) — журнал решений
- [poc/](poc/) — эксперименты
- [docs/BACKLOG.md](docs/BACKLOG.md) — задачи для GitHub Projects

## Запуск

С Node.js 22.12+ выполните из корня `npm --prefix web install`, затем `npm --prefix web run dev`. Для сборки выполните `npm --prefix web run build`.

## GitHub Pages

Загрузите файлы в `main`, включая `.github/workflows/pages.yml`. В Settings → Pages → Build and deployment выберите GitHub Actions. В Actions → Deploy Pages запустите Run workflow. Последующие изменения в `main` запускают деплой автоматически. Публичный адрес указан в результате успешного деплоя.
