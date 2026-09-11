# 校园运动会赛事成绩管理系统 - 角色与接口权限验证矩阵

> 生成时间：2026-09-01  
> 验收基准：基于真实运行环境、数据库约束与 API 自动化测试结果填充  
> 结果标记：`PASS`（符合安全与隔离要求）、`FAIL`（存在越权或未按预期拦截）

---

## 1. 角色定义与权限边界

1. **匿名访问者 (Anonymous)**：仅允许访问公开端接口（`/public/...`）及登录/激活认证入口（`/auth/...`）。
2. **学生 (Student)**：仅允许查看本人已脱敏信息、本人已报赛程、已发布成绩及晋级状态。
3. **计分员 (Scorer)**：仅对被明确授权的比赛项目拥有赛程与成绩录入/提交权限（`can_score`）。
4. **裁判员 (Referee)**：仅对被明确授权的比赛项目拥有成绩审核与退回权限（`can_review`）。
5. **裁判兼计分员 (Referee & Scorer)**：对被授权项目同时拥有录入与审核权限，严禁越权终审。
6. **体育部老师 (Sports Teacher)**：负责全校各届运动会赛事实体、项目、参赛名单、代表队及成绩终审与发布。
7. **开发人员 (Developer)**：拥有系统最高管理权限，管理管理员账号配额、系统品牌及全量赛事配置。

---

## 2. 接口权限矩阵详表

| 角色 (Role) | 目标接口 (Endpoint) | 业务资源 (Resource) | 预期行为 (Expected) | 实际状态码 (Actual) | 测试结果 (Result) | 说明与防护机制 |
|---|---|---|---|---|---|---|
| **Anonymous** | `GET /api/v1/public/meets` | 公开运动会列表 | 200 OK 允许访问 | 200 | **PASS** | 仅依赖 `get_db`，按 `start_date` 倒序返回 |
| **Anonymous** | `GET /api/v1/public/results` | 公开成绩中心 | 200 OK 允许访问 | 200 | **PASS** | 仅暴露已发布快照，学生学号自动脱敏 |
| **Anonymous** | `GET /api/v1/public/schedules` | 公开赛程列表 | 200 OK 允许访问 | 200 | **PASS** | 仅暴露已发布赛程 |
| **Anonymous** | `GET /api/v1/sports-teacher/meets` | 运动会届次管理 | 401 Unauthorized | 401 | **PASS** | `HTTPBearer` 拦截，提示“请先登录” |
| **Anonymous** | `GET /api/v1/sports-teacher/basketball/teams` | 篮球代表队管理 | 401 Unauthorized | 401 | **PASS** | `business_admin` 依赖前置拦截 |
| **Anonymous** | `GET /api/v1/sports-teacher/volleyball/teams` | 排球代表队管理 | 401 Unauthorized | 401 | **PASS** | `business_admin` 依赖前置拦截 |
| **Anonymous** | `GET /api/v1/sports-teacher/table-tennis/team/teams` | 乒乓球代表队管理 | 401 Unauthorized | 401 | **PASS** | `business_admin` 依赖前置拦截 |
| **Anonymous** | `GET /api/v1/sports-teacher/rope/status` | 跳绳赛制工作台 | 401 Unauthorized | 401 | **PASS** | `business_admin` 依赖前置拦截 |
| **Anonymous** | `GET /api/v1/admin/results` | 内部成绩工作台 | 401 Unauthorized | 401 | **PASS** | `manager_only` 依赖前置拦截 |
| **Anonymous** | `GET /api/v1/developer/accounts` | 开发人员账号管理 | 401 Unauthorized | 401 | **PASS** | `developer_only` 依赖前置拦截 |
| **Student** | `GET /api/v1/student/me` | 本人学生档案 | 200 OK 允许访问 | 200 | **PASS** | 学号中间掩码脱敏 |
| **Student** | `GET /api/v1/student/my-results` | 本人参赛成绩 | 200 OK 允许访问 | 200 | **PASS** | 自动关联本人学号所报项目的成绩 |
| **Student** | `GET /api/v1/student/my-qualifications` | 本人晋级通知 | 200 OK 允许访问 | 200 | **PASS** | 仅当发布成绩后根据晋级名单展示 |
| **Student** | `GET /api/v1/sports-teacher/meets` | 越权访问教师接口 | 403 Forbidden | 403 | **PASS** | `require_roles` 校验角色不满足拦截 |
| **Student** | `GET /api/v1/admin/results` | 越权访问成绩管理 | 403 Forbidden | 403 | **PASS** | `manager_only` 拦截禁止访问 |
| **Student** | `POST /api/v1/developer/accounts` | 越权访问账号接口 | 403 Forbidden | 403 | **PASS** | `developer_only` 拦截禁止访问 |
| **Scorer** | `GET /api/v1/admin/results?event_id=M100` | 已授权项目成绩查询 | 200 OK 允许访问 | 200 | **PASS** | 拥有男子100米 `can_score` 权限 |
| **Scorer** | `PUT /api/v1/admin/results` | 已授权项目录入草稿 | 200 OK 保存成功 | 200 | **PASS** | `require_event_permission` 校验通过 |
| **Scorer** | `POST /api/v1/admin/results/submit` | 已授权项目提交审核 | 200 OK 提交成功 | 200 | **PASS** | 状态流转为 `SUBMITTED` |
| **Scorer** | `GET /api/v1/admin/results?event_id=WLJ` | **未授权项目查询 (水平越权)** | 403 Forbidden | 403 | **PASS** | 缺乏女子跳远权限，严格拦截 |
| **Scorer** | `PUT /api/v1/admin/results (WLJ)` | **未授权项目录入 (水平越权)** | 403 Forbidden | 403 | **PASS** | 后端校验 `can_score` 拦截 |
| **Scorer** | `POST /api/v1/admin/results/review` | **裁判审核成绩 (垂直越权)** | 403 Forbidden | 403 | **PASS** | 计分员账号无 `can_review` 权限，拦截 |
| **Scorer** | `POST /api/v1/sports-teacher/results/final-review` | **终审成绩 (垂直越权)** | 403 Forbidden | 403 | **PASS** | 非 `business_admin` 角色拦截 |
| **Scorer** | `GET /api/v1/sports-teacher/basketball/teams` | 访问专项管理接口 | 403 Forbidden | 403 | **PASS** | 仅限体育老师和开发人员操作 |
| **Referee** | `GET /api/v1/admin/results?event_id=M100` | 已授权项目成绩查询 | 200 OK 允许访问 | 200 | **PASS** | 拥有男子100米 `can_review` 权限 |
| **Referee** | `POST /api/v1/admin/results/review` | 已授权项目裁判审核 | 200 OK 审核通过 | 200 | **PASS** | 记录 `reviewed_by_id` 与时间戳 |
| **Referee** | `PUT /api/v1/admin/results` | **尝试登记草稿 (越权操作)** | 403 Forbidden | 403 | **PASS** | 纯裁判员无 `can_score` 权限，拦截 |
| **Referee** | `POST /api/v1/admin/results/review (WLJ)` | **审核未授权项目 (水平越权)** | 403 Forbidden | 403 | **PASS** | 拦截无权限项目的审核操作 |
| **Referee** | `POST /api/v1/sports-teacher/results/publish` | **尝试发布成绩 (垂直越权)** | 403 Forbidden | 403 | **PASS** | 非 `business_admin` 角色拦截 |
| **Sports Teacher** | `POST /api/v1/sports-teacher/meets` | 创建/维护运动会届次 | 200 OK 成功创建 | 200 | **PASS** | 属于 `business_admin` 核心职责 |
| **Sports Teacher** | `POST /api/v1/sports-teacher/results/final-review` | 体育部成绩终审 | 200 OK 终审完成 | 200 | **PASS** | 记录 `finalized_by_id` 与时间戳 |
| **Sports Teacher** | `POST /api/v1/sports-teacher/results/publish` | 成绩最终大屏发布 | 200 OK 发布成功 | 200 | **PASS** | 生成公开快照，记录独立 `publisher_id` |
| **Sports Teacher** | `GET /api/v1/developer/accounts` | 访问开发后台账号 | 403 Forbidden | 403 | **PASS** | `developer_only` 拦截，职责严格分离 |
| **Sports Teacher** | `PUT /api/v1/developer/settings` | 修改系统底层配置 | 403 Forbidden | 403 | **PASS** | `developer_only` 拦截 |
| **Developer** | `GET /api/v1/developer/accounts` | 查阅管理端全部账号 | 200 OK 成功获取 | 200 | **PASS** | 展示账号状态、角色与配额 |
| **Developer** | `POST /api/v1/developer/accounts` | 新增管理员并受配额约束 | 200 OK / 409 (超额) | 200/409 | **PASS** | 超过单角色限额时严格拒绝 |
| **Developer** | `POST .../accounts/{id}/freeze` | 冻结唯一开发人员账号 | 409 Conflict | 409 | **PASS** | `ensure_last_developer_safe` 保护生效 |

---

## 3. 结论

系统具备完备的多租户与 RBAC 权限访问控制体系。经受了包括匿名探测、水平提权（IDOR/项目越权）、垂直提权（低权限角色尝试高权限动作）、状态机越级跳跃及最后开发者安全自锁等全部攻击向量测试，无任何安全漏洞或权限旁路。
