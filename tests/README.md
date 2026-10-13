# 测试

从仓库根目录运行，测试数据写入 `tests/.runtime/`，不会修改正式数据库。

```powershell
python -B -m pytest tests/backend -q
python -B tests/migration/verify_alembic_3scenarios.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

后端测试覆盖账号、权限、赛事名单、跳绳表格、成绩发布和各项目赛制。浏览器测试需要 Microsoft Edge，使用独立的8001与5174端口。Windows一键启动测试在其他操作系统自动跳过。
