# 校园运动会赛事成绩管理系统 - 发布候选版本最终工程验收报告
## Release Candidate Verification & Pre-Production Acceptance Report

- **验收日期**：2026-09-01
- **验收环境**：Windows 本地测试环境 / 生产仿真沙箱
- **负责角色**：Senior Full-Stack QA Engineer + Backend Engineer + Database Engineer + Security Reviewer + Test Automation Engineer + Software Release Engineer
- **验收结论**：**READY FOR RELEASE (准予发布)**

---

## 1. 验收测试环境与配置

| 类别 | 运行环境参数 |
|---|---|
| **操作系统** | Windows 11 (PowerShell / cmd) |
| **后端运行栈** | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, SQLite 3 |
| **前端运行栈** | Node.js 22, Vue 3, TypeScript, Vite, Element Plus, Pinia |
| **测试框架** | pytest (后端单元/集成), Vitest (前端单测), Playwright (E2E 浏览器测试) |
| **测试隔离策略** | 生产库 `data/sports_meet.db`；自动化集成测试使用独立临时库，Playwright 使用独立端口及沙箱数据库，互不干扰污染 |
| **持久化引擎** | SQLite（单机本地存储，不使用 Docker、MySQL 或 LocalStorage 作为主数据存储） |

---

## 2. Alembic 数据库迁移验收 (Migration Result)

### 2.1 迁移版本与结构健全性
- **当前 Alembic 版本**：`20260901_0009` (HEAD)
- **迁移链条**：`20260824_0001` → `0002` → `0003` → `0004` → `0005` → `0006` → `0007` → `0008` → `0009`（无断裂、分叉或缺失版本）
- **修复与加固**：
  - 修复 `backend/alembic/env.py` 动态读取 `sqlalchemy.url` 与设置，彻底支持 Windows 绝对/相对路径。
  - 在批处理 DDL 中针对 SQLite 特性增加了 `_alembic_tmp_results` 临时表残留清理，并添加了列存在的幂等性检查，杜绝反复执行迁移时的中断异常。

### 2.2 三场景自动化迁移回归验证 (`../测试/migration/verify_alembic_3scenarios.py`)
使用独立沙箱对三种高风险现实发布场景进行全面测试，均 100% 成功：

| 验证场景 | 初始状态 | 升级过程 | 最终状态 | 完整性与外键校验 | 结果 |
|---|---|---|---|---|---|
| **Scenario A (全新库初始化)** | 空数据库文件 | 从 0001 依次线性升级至 0009 | 拥有 24 张核心表，版本为 `20260901_0009` | `integrity_check = ok`<br>`foreign_key_check = []` (0违规) | **PASS** |
| **Scenario B (历史老库增量升级)** | 预置 0001 真实历史业务数据 | 从 0001 增量升级至 0009 | 升级至 `20260901_0009`，保留既有历史数据 | `integrity_check = ok`<br>`foreign_key_check = []` (0违规) | **PASS** |
| **Scenario C (结构超前版本滞后)** | 实体模型已建表但 alembic 未 stamp | 执行 upgrade head 自动补齐版本 | 统一收敛至 `20260901_0009` | `integrity_check = ok`<br>`foreign_key_check = []` (0违规) | **PASS** |

---

## 3. 正式数据库连接与安全检查 (Database Result)

对正式数据库 `data/sports_meet.db` 及后端 SQLAlchemy 运行连接进行只读深度探测：

1. **SQLAlchemy 核心连接 Pragma 验证**：
   - `PRAGMA foreign_keys`：**`1`**（强制开启，每个连接建立时通过事件自动激活，确保外键约束生效）
   - `PRAGMA journal_mode`：**`wal`**（预写日志模式，支持读写并发，杜绝读写锁死）
   - `PRAGMA busy_timeout`：**`30000`**（30 秒并发忙等待，极大缓解瞬时高负载争用）
2. **正式库健康度核验**：
   - `SELECT version_num FROM alembic_version`：`20260901_0009`（与最新代码完全同步）
   - `PRAGMA integrity_check`：**`ok`**（物理存储无损、无损坏页）
   - `PRAGMA foreign_key_check`：**`[]`**（无孤儿行、无外键悬空）
3. **备份脚本演练验证 (`backup-local.ps1`)**：
   - 执行本地备份：生成 `data/backups/sports_meet_20260901_114114_final-verification.db`。
   - 验证备份文件物理可用性：`PRAGMA integrity_check = ok`，文件大小完整，数据恢复演练校验成功。

---

## 4. 全业务 CRUD 与持久化验证 (CRUD Result)

详细矩阵见 [docs/CRUD_FUNCTION_MATRIX.md](docs/CRUD_FUNCTION_MATRIX.md)。核心特性如下：

1. **赛事与项目**：支持多届运动会并行管理；项目创建自动绑定初赛/晋级/决赛轮次；删除项目时自动级联清理关联轮次，外键无孤儿行。
2. **名单与代表队**：支持 Excel 批量导入与单条录入；学号唯一索引约束有效；学院代表队成员跨赛事/跨项目绑定限制有效（422 参数拒绝）。
3. **排道与赛程**：支持按组道规则自动抽签排道与手动调整；赛程增删改查时区自动感知并持久化。
4. **计分模型**：支持多套计分模型并存、克隆与启用；已绑定的计分模型具有外键删除保护。

---

## 5. 权限与安全审查 (Permission Result)

详细矩阵见 [docs/PERMISSION_VERIFICATION_MATRIX.md](docs/PERMISSION_VERIFICATION_MATRIX.md)。

1. **匿名访问防护**：
   - 所有 `/api/v1/sports-teacher/...`、`/api/v1/admin/...`、`/api/v1/developer/...` 接口均受 `HTTPBearer` 和角色拦截，匿名访问返回 **401 Unauthorized**。
   - 公开接口 `/api/v1/public/...` 允许匿名访问，返回 **200 OK**。
2. **垂直提权防护**：
   - 学生访问管理/教师接口返回 **403 Forbidden**。
   - 计分员尝试裁判审核、体育老师终审或发布，返回 **403 Forbidden**。
   - 体育老师尝试访问开发人员后台账号管理，返回 **403 Forbidden**。
3. **水平越权防护 (IDOR)**：
   - 计分员/裁判员仅能操作被明确授权的项目（通过 `EventAdminPermission` 表校验 `can_score` 或 `can_review`）；尝试操作未授权项目返回 **403 Forbidden**。
4. **开发人员安全保护**：
   - 系统检测最后一名活跃开发人员账号，禁止执行冻结或删除操作，返回 **409 Conflict**。

---

## 6. 成绩全生命周期与状态机闭环 (Workflow Result)

### 6.1 成绩状态机跃迁路径
严格按照如下状态机流转，禁止任何非法跨越：
$$\text{DRAFT} \xrightarrow{\text{录入/保存}} \text{SUBMITTED} \xrightarrow{\text{裁判审核}} \text{REVIEWED} \xrightarrow{\text{体育部终审}} \text{FINAL\_APPROVED} \xrightarrow{\text{发布}} \text{PUBLISHED}$$

- **非法跃迁拦截**：
  - `DRAFT` 尝试直接发布：返回 **409 Conflict**。
  - `SUBMITTED` 尝试直接终审或发布：返回 **409 Conflict**。
  - `REVIEWED` 绕过终审直接发布：返回 **409 Conflict**。
  - 裁判审核退回 (`RETURNED`)：打回草稿状态，修改后需重新提交。

### 6.2 职责分离与快照隔离
- **四独立责任人记录**：
  1. `recorder_id`（登记人）
  2. `reviewed_by_id`（裁判审核人）
  3. `finalized_by_id`（体育部终审人）
  4. `publisher_id`（最终发布人）
  四字段独立持久化，发布操作绝不覆盖 `finalized_by_id`。
- **已发布数据快照**：
  发布时在 `results` 表生成 `published_raw_value`、`published_rank`、`published_points`、`published_notes`、`published_competition_status` 等不可变快照字段。
  **真实快照防篡改测试**：成绩发布后，管理人员在后台重新修改内部草稿（改为 9.0 秒、状态 DNF），公开端接口仍稳定展示发布时的快照（10.0 秒、NORMAL 状态），杜绝内部修改影响公开大屏。

### 6.3 晋级与名次拆分
- **并列名次平均分算法**：两队并列第一时，自动各分得 $(9 + 7) / 2 = 8.0$ 分，下一名自动顺延为第 3 名。
- **下一轮晋级**：基于发布快照名次，自动生成半决赛/决赛的正选名单（`REGISTERED`）与候补名单（`ALTERNATE`）；学生端登录可即时收到晋级状态通知。

---

## 7. 真实端到端测试验证 (E2E Result)

通过 Playwright 自动化执行端到端真实浏览器用例（`npm.cmd --prefix frontend run test:e2e`）：

1. **用例 1：开发人员登录与工作区 (developer can log in and open the account workspace)**
   - 验证三入口认证、开发人员账号工作区加载、品牌标题呈现，耗时 3.0 秒（PASS）。
2. **用例 2：公开端届次隔离与学号掩码 (public results expose only published records and masked student numbers)**
   - 验证公开端下拉切换运动会届次，严格加载所选运动会的比赛成绩；验证学生学号自动脱敏为 `20******01`，耗时 2.5 秒（PASS）。
3. **用例 3：全生命周期业务闭环与 30 秒轮询 (core CRUD and result workflow persist through UI, API, public polling and student view)**
   - 包含：新建运动会 → 新建项目 → 录入学生 → 批量报名 → 自动排道 → 发布赛程 → 成绩录入保存草稿 → 提交审核 → 裁判审核 → 体育部终审 → 公开端 30 秒轮询免刷新呈现 → 生成下一轮晋级名单 → 学生登录查看晋级 → 成绩单 Excel 导出与 A4 打印样式验证 → 审计日志查询验证，耗时 39.8 秒（PASS）。

---

## 8. 修复的问题列表 (Bug List)

在工程验收与加固过程中，共发现并彻底修复了 13 个工程与业务缺陷：

| 编号 | 缺陷描述 | 严重级别 | 根因分析 | 修复方案 |
|---|---|---|---|---|
| **BUG-01** | 成绩流转允许绕过裁判审核 | **Critical** | 终审接口缺少对 `reviewed_by_id` 及状态的硬性校验 | 增加 `row.state != ResultState.REVIEWED or not row.reviewed_by_id` 409 拦截 |
| **BUG-02** | 成绩流转允许绕过终审直接发布 | **Critical** | 发布接口缺少对 `finalized_by_id` 的校验 | 增加 `row.finalized_by_id` 强校验，不满足时返回 409 |
| **BUG-03** | 发布人覆盖终审人字段 | **High** | 原代码发布时将 `finalized_by_id` 覆盖为当前发布人 | 增加独立的 `publisher_id` 字段及 Alembic 迁移，四人职责完全解耦 |
| **BUG-04** | 缺失不可变公开成绩快照 | **High** | 公开接口直接查询当前内部成绩字段，内部修改草稿导致公开端数据漂移 | 增加发布快照字段并在发布时固化快照，公开接口全量读取快照 |
| **BUG-05** | 跨赛事、跨项目代表队混乱关联 | **High** | 队伍报名时未校验代表队 `meet_id` / `event_id` 与目标项目的一致性 | 在报名和编辑接口增加跨赛事校验，非法关联返回 422 |
| **BUG-06** | 部分球类管理接口未鉴权 | **High** | 排球/乒乓球部分路由遗漏了角色依赖 | 统一注入 `_actor: User = Depends(business_admin)`，非授权访问直接 401/403 |
| **BUG-07** | 删除项目时外键级联失败 | **Medium** | 项目关联的自动生成轮次 `event_rounds` 存在外键依赖阻碍删除 | 模型配置 `cascade="all, delete-orphan"`，确保级联干净删除 |
| **BUG-08** | 鉴权依赖调整导致位置参数错位 | **Medium** | 修改路由依赖后内部调用参数签名未对齐 | 重构参数列表，确保依赖与路由处理函数签名一致 |
| **BUG-09** | 学生新增 UI 缺失必填字段 | **Medium** | 学生录入弹窗未完全暴露专业与班级输入项 | 前端补全表单项，并与后端校验规则对齐 |
| **BUG-10** | 赛程时间输入格式不完整 | **Medium** | 赛程弹窗提交时未校验检录时间必须早于比赛时间 | 后端增加 `check_in_at < competition_at` 校验及前端提示 |
| **BUG-11** | 公开端混合多届运动会数据 | **High** | 公开端未传递 `meet_id` 上下文导致查询全库成绩 | 前端增加运动会选择器和 strict meet scoping，后端全部按届次过滤 |
| **BUG-12** | UTC 与本地浏览器时区呈现偏差 | **Low** | ISO 时间戳缺少 'Z' 标识导致部分浏览器按本地时区重复偏移 | 统一采用 `utc_iso` 格式化，确保输出带时区感知的标准 ISO 字符串 |
| **BUG-13** | Alembic 动态 URL 缺失与批处理临时表冲突 | **High** | `env.py` 硬编码引擎，且 SQLite batch alter 遗留 `_alembic_tmp_results` | 改造 `env.py` 动态加载 URL，迁移脚本增加临时表清除与幂等列检查 |

---

## 9. 最终回归验证汇总 (Regression Result)

验收前执行全部回归命令，证据如下：

```text
==================================== 自动化验收总览 ====================================
1. 后端全量测试 (pytest):
   命令: python -m pytest ..\测试\backend -q
   结果: 24 passed, 0 failed in 80.88s (覆盖 7 个测试文件)

2. 前端单元测试 (Vitest):
   命令: npm.cmd --prefix frontend test
   结果: 1 test file passed, 2 tests passed, 0 failed in 496ms

3. 前端生产打包构建 (vue-tsc & vite build):
   命令: npm.cmd --prefix frontend run build
   结果: SUCCESS (2279 modules transformed, built in 24.93s)

4. Playwright 浏览器真实端到端验收:
   命令: npm.cmd --prefix frontend run test:e2e
   结果: 3 passed, 0 failed in 50.4s

5. Alembic 三大复杂场景迁移验证:
   命令: python ../测试/migration/verify_alembic_3scenarios.py
   结果:
     - Scenario A (Fresh DB): PASS (24 tables, integrity: ok, fk: 0)
     - Scenario B (Legacy DB): PASS (25 tables, integrity: ok, fk: 0)
     - Scenario C (Schema Ahead): PASS (24 tables, integrity: ok, fk: 0)

6. 物理数据库只读体检:
   - PRAGMA integrity_check: ok
   - PRAGMA foreign_key_check: empty
   - PRAGMA journal_mode: wal
   - alembic_version: 20260901_0009 (HEAD)
=======================================================================================
```

---

## 10. 残余风险评估 (Remaining Risks)

- **Vite 打包产物体积提示**：生产构建时输出 `dist/assets/index-Dounh4r3.js (2,476 kB)` 大于 500 kB 的警告。
  - **影响评估**：属于前端非阻塞提示（**Non-Blocking**）。该警告由于完整打包了 Element Plus、Pinia 与 ECharts 图表库所致，系统在本地局域网及学校服务器部署下加载速度极快，不影响系统功能与正确性。未来版本可根据需要引入路由懒加载与 CDN 拆包优化。

---

## 11. 发布建议 (Release Recommendation)

经全面审查，本项目满足所有工程质量与业务发布准则：
- 零未解决的 Critical / High 等级缺陷；
- 后端 pytest 100% 通过（24 passed, 0 failed）；
- 前端测试 100% 通过（2 passed, 0 failed）；
- 前端生产构建成功（Build SUCCESS）；
- 核心浏览器端到端 Playwright 100% 通过（3 passed, 0 failed）；
- SQLite 数据库处于 WAL 模式、外键强制启用、完整性良好、Alembic 版本严格对齐 HEAD；
- 具备完整的本地备份与恢复能力。

**正式判定**：**READY FOR RELEASE (准予发布)**

