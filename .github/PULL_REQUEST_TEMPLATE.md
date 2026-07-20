## 变更说明

<!-- 简要描述这个 PR 做了什么 -->

## 变更类型

- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 重构
- [ ] 其他

## 检查清单

- [ ] 已运行后端测试：`cd backend && .venv/bin/pytest`
- [ ] 已运行后端 lint：`cd backend && .venv/bin/ruff check app tests`
- [ ] 已运行前端测试：`cd frontend && npm test`
- [ ] 已运行前端 lint：`cd frontend && npm run lint`
- [ ] 已运行前端构建：`cd frontend && npm run build`
- [ ] 未提交 `backend/.env`、`backend/auth_codes.json`、`.omo/` 等敏感文件
- [ ] 如修改了 API 行为，已同步更新 `docs/05-api-reference.md`
- [ ] 如修改了配置项，已同步更新 `.env.example` 和 `docs/03-configuration.md`

## 相关 Issue

<!-- 例如：Closes #123 -->

## 附加信息

<!-- 其他需要说明的内容 -->

- [ ] Coverage gates pass (`pytest --cov...`, `npm run test:coverage`)
- [ ] `python3 scripts/check_docs_consistency.py` and `python3 scripts/check_security_policy.py` pass
- [ ] Actions remain SHA-pinned; no deploy/SSH in release workflow
- [ ] No secrets, local-only override files, or `frontend/dist` staged
