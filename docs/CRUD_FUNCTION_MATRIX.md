# 校园运动会赛事成绩管理系统 - 核心业务 CRUD 功能验收矩阵

> 生成时间：2026-09-01  
> 验收标准：UI 操作 = API 接口 = 后端业务规则 = SQLite 数据库持久化 = 重新加载验证  
> 状态定义：`PASS`（通过验证并持久化确认）、`FAIL`（失败）、`N/A`（根据业务设计不适用）

---

## 1. 核心业务模块 CRUD 验证结果

| 业务模块 | 新建 (Create) | 查询/列表 (Read) | 修改 (Update) | 删除 (Delete) | SQLite 持久化验证 | 权限约束 | 综合结论 |
|---|---|---|---|---|---|---|---|
| **运动会届次 (Sports Meet)** | `POST /sports-teacher/meets` 支持设置名称、届次标识、起止日期与状态 (PASS) | `GET /sports-teacher/meets` 区分状态与届次；支持公开端过滤 (PASS) | `PUT /sports-teacher/meets/{id}` 允许更新名称、起止日期与状态 (PASS) | `DELETE /sports-teacher/meets/{id}` 级联检查并清理关联赛事项目 (PASS) | `sports_meets` 表真实写入，重载确认完整字段 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **比赛项目 (Event)** | `POST /sports-teacher/events` 支持个人/接力/集体赛制、单位、自动创建轮次 (PASS) | `GET /sports-teacher/events` 支持按届次、项目类型、性别组别过滤 (PASS) | `PUT /sports-teacher/events/{id}` 支持调整项目名称、资格数量及规则 (PASS) | `DELETE /sports-teacher/events/{id}` 级联删除关联轮次，外键无孤儿行 (PASS) | `events` & `event_rounds` 联动持久化；外键检查正常 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **学生基础档案 (Student Roster)** | 单条录入 `POST /sports-teacher/students` & Excel 批量导入 (PASS) | `GET /sports-teacher/students` 支持学号、姓名、学院模糊检索与分页 (PASS) | `PUT /sports-teacher/students/{id}` 允许维护姓名、班级、专业 (PASS) | `DELETE /sports-teacher/students/{id}` 仅限无成绩关联的档案 (PASS) | `student_rosters` 表持久化，学号唯一索引约束有效 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **学院代表队 (College Team)** | `POST /sports-teacher/college-teams` 支持一键批量生成各学院队伍 (PASS) | `GET /sports-teacher/college-teams` 严格隔离运动会届次 (PASS) | `PUT /sports-teacher/college-teams/{id}` 校验跨赛事绑定合法性 (PASS) | `DELETE /sports-teacher/college-teams/{id}` 联动清理空成员队伍 (PASS) | `college_teams` 表持久化，防跨届次污染 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **代表队成员 (Team Member)** | `POST .../members` & `POST .../members/batch` 单个或批量选拔队员 (PASS) | `GET .../members` 包含队员性别、班级及职务角色 (PASS) | `PUT .../members/{mid}` 更新角色标识（如主攻、摇绳者） (PASS) | `DELETE .../members/{mid}` 队员移出代表队 (PASS) | `college_team_members` 关联表持久化并保证唯一性 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **项目参赛名单 (Registration)** | `POST .../event-registrations/batch` 选拔个人或学院代表队入轮次 (PASS) | `GET .../event-registrations` 按项目与轮次清晰呈现分组排道状态 (PASS) | `PUT .../event-registrations/{id}` 更新检录状态、道次号及号码布 (PASS) | `DELETE .../event-registrations/{id}` 允许在赛前退赛或清理 (PASS) | `registrations` 表持久化，状态枚举与号码布严格校验 (PASS) | 体育部老师或具备该项目管理权限的裁判/计分员 (PASS) | **PASS** |
| **分组排道 (Lane Seeding)** | `POST .../event-registrations/seed` 按组道规则自动抽签/蛇形排道 (PASS) | 参赛名单及公开赛程均可实时读取道次 (PASS) | 支持手动单个调整组次与道次 (PASS) | 支持一键重新排道重置原有道次 (PASS) | `registrations.heat` / `registrations.lane` 批量持久化 (PASS) | 体育部老师或具备项目排道权限的角色 (PASS) | **PASS** |
| **赛程安排 (Event Schedule)** | `POST /admin/schedules` 录入检录时间、比赛时间、场地与组别 (PASS) | `GET /admin/schedules` & 公开端 `GET /public/schedules` (PASS) | `PUT /admin/schedules/{id}` 更新时间场地，支持变更通知 (PASS) | `DELETE /admin/schedules/{id}` 允许在未开赛前删除赛程 (PASS) | `event_schedules` 表持久化，时间格式带时区感知 (PASS) | 体育部老师或具备项目权限的裁判/计分员 (PASS) | **PASS** |
| **计分模型 (Scoring Model)** | `POST /sports-teacher/scoring-models` 支持自定义名次名额与分值 (PASS) | `GET /sports-teacher/scoring-models` 展示当前启用状态与引用数 (PASS) | `PUT .../scoring-models/{id}` 允许微调未锁定的模型 (PASS) | `DELETE .../scoring-models/{id}` 禁止删除已绑定正式项目的模型 (PASS) | `scoring_models` & `scoring_model_items` 级联写入 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **计分模型绑定 (Binding)** | `POST .../scoring-models/{id}/bind` 支持按届次或单项精准绑定 (PASS) | 读取项目时自动关联对应计分规则与倍率 (PASS) | 重新绑定覆盖原有映射 (PASS) | 解绑回退至默认 9~1 模型 (PASS) | `scoring_model_bindings` 关联持久化 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **成绩草稿与录入 (Result Entry)** | `PUT /admin/results` 支持录入原始成绩、状态 (正常/弃权/犯规) 与备注 (PASS) | `GET /admin/results` 按项目轮次展现草稿状态与计算名次 (PASS) | 录入新数值自动重新触发排名与积分重算 (PASS) | `DELETE /admin/results/{id}` 仅限草稿状态删除 (PASS) | `results` 表持久化，自动防并发版本控制 (PASS) | 仅限拥有该项目 `can_score` 权限的计分员/老师 (PASS) | **PASS** |
| **成绩审核与发布 (Workflow)** | 提交审核 (`SUBMIT`) -> 裁判审核 (`REVIEW`) -> 终审 (`FINAL`) -> 发布 (`PUBLISH`) | 管理端全生命周期跟踪；公开端仅可见已发布快照 (PASS) | 终审后不可直接改动公开结果，需通过重新提交流转 (PASS) | 发布后不可物理删除，支持撤回重新流转 (PASS) | `results` 记录四独立操作人 ID、时间戳及快照字段 (PASS) | 严格区分录入人、裁判审核人、终审人和发布人 (PASS) | **PASS** |
| **项目管理权限 (Event Permissions)** | `PUT /sports-teacher/permissions` 为指定管理员授予指定项目权限 (PASS) | `GET /sports-teacher/permissions` 树状列出人员与项目权限 (PASS) | 动态勾选 `can_score`、`can_review` 等独立权限标识 (PASS) | `DELETE /sports-teacher/permissions/{id}` 实时回收权限 (PASS) | `event_admin_permissions` 持久化，接口即刻生效 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **系统配置 (System Settings)** | `PUT /developer/settings` 更新系统名称、主色调、公开端标题 (PASS) | `GET /public/settings` 免鉴权公开读取 (PASS) | 更新配置支持即时响应并存库 (PASS) | 不提供物理删除，支持重置为默认值 (PASS) | `system_settings` 键值表持久化 (PASS) | 仅限开发人员 (`developer_only`) | **PASS** |
| **账号与配额 (Accounts)** | `POST /developer/accounts` 创建管理员，校验角色配额上限 (PASS) | `GET /developer/accounts` 分页检索与状态展示 (PASS) | 编辑基本信息、重置密码、冻结/解冻 (PASS) | 软删除或冻结，保护最后一名开发人员不可冻结/删除 (PASS) | `users` & `administrator_profiles` 联动持久化 (PASS) | 仅限开发人员 (`developer_only`) | **PASS** |
| **跳绳赛制 (Rope Skipping)** | `POST .../rope/initialize` 幂等创建项目与初始轮次 (PASS) | `GET .../rope/status` 跟踪 22 人代表队、阵容与各环节状态 (PASS) | `PUT .../rope/lineups` 校验男女比例及摇绳/跳绳角色唯一性 (PASS) | `N/A`（项目由赛事统一管理） | `rope_lineup_members` & `rope_result_details` (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **篮球循环与淘汰赛制 (Basketball)** | `POST .../basketball/quick-create-event` & 自动分组生成对阵 (PASS) | `GET .../basketball/matches` & `GET .../standings` 积分榜 (PASS) | `PUT .../matches/{id}` 录入比分，自动计算积分并生成半决赛/决赛 (PASS) | 允许重置未进行的淘汰赛赛程 (PASS) | `tournament_matches` 真实持久化比分、净胜分与归档成绩 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **排球单项赛制 (Volleyball)** | 快速建立小组赛、循环赛程与局分明细结构 (PASS) | 实时统计胜负局数、胜负分比率 (Z值/C值) 并动态排位 (PASS) | 支持单局比分修改，自动判定胜队并推进至淘汰赛 (PASS) | 允许赛事重置或单场清理 (PASS) | `tournament_matches` 持久化多局比分结构 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |
| **乒乓球单打/团体赛制 (Table Tennis)** | 支持五场三胜双打单打配置，支持单打种子抽签与单败淘汰 (PASS) | 赛程对阵树状图与各场次单项比分查询 (PASS) | 录入每盘盘分与局分，自动决出胜负并一键归档到成绩工作台 (PASS) | 赛前支持重新抽签并清理对阵 (PASS) | 比分与最终归档 `results` 记录完整持久化 (PASS) | 仅限开发人员及体育部老师 (`business_admin`) | **PASS** |

---

## 2. 结论

全系统 19 个核心业务模块的所有 Create、Read、Update、Delete、数据库事务提交、外键级联检查及状态约束全部达到发布标准，通过完整自动化回归验收。
