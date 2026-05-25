# media-pro systemd deploy

## 前端构建

发布前请执行：

```bash
cd web
pnpm install
pnpm build
```

如果跳过，FastAPI 启动后访问 `/admin` 会因为 `web/dist/` 不存在而 500。
