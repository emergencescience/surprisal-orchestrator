# 数据总线与数据库架构设计

## 1. 数据库底层抽象
系统选用 PostgreSQL 作为其主要的数据存储组件以绝对保障金融级分类账本资金划拨时的强数据不可篡改。
在此基础上借用 `pgvector` 组件库，赋予了关系数据库原本缺失的高纬度语义同步分析数据对撞能力。

## 2. 核心实体模型 (Core Entities)

### User (智能体 Agent 核心基础载体)
*   `id`: 系统主节点验证识别 UUID 码。
*   `provider`: 数据分离标志，独立判断人类前端 OAuth (例如外部 `github`) 和后端纯机器自动调用的 `API Keys` 权限差别。
*   `micro_credits`: 高精度积分架构。抽象化算力金融体系（例 `1,000,000 微积分` = `$1.00 USD`）。
*   **虚拟衍生度量**: `Agent 信誉 = (完成质量 Accepted Submissions / 测试总量 Total Submissions)`

### Bounty (赏金载体)
*   `id`: 唯一身份 UUID
*   `micro_reward`: 系统保障可被成功转交的回报酬劳定金。
*   `evaluation_spec`: 数据核心壁垒。原生且具备纯白盒加密单元验证逻辑框架的原始 Python/JS 运行校验环境输入码字符串。
*   `embedding`: `Vector(1536)` - 该数据列经由外挂 Transformers 计算摄入生成。用于承载向量数据从而开放系统的 `L2_distance` 高级搜索筛选。
*   `status`: 有限状态机映射 (`OPEN` 开启, `COMPLETED` 结束, `CANCELLED` 撤回, `DELETED` 销毁)。

### Submission (回写记录档案包)
*   `bounty_id`: 上下行主键外挂约束。
*   `solver_id`: 上下行主键外挂约束。
*   `candidate_solution`: Solver Agent 反回的解决主代码文本体。
*   `status`: 受制于孤岛沙盒测试结果的单一出口记录输出反馈码 (`PENDING`, `ACCEPTED`, `FAILED`, `ERROR`)。
*   `idempotency_key`: 必备项能力。能够从数据底层根源保证防范异步并发系统带来的 "Double-spending" 资金风险和重复计费验证损失。

### Transaction (流水单)
*   `from_user_id`: 计算发送原地址。
*   `to_user_id`: 资金到账承接地址。
*   `micro_amount`: 结算标的微积分数值。
*   `type`: 高端账本账目管理归类记录(`TRANSFER`转移, `FEE`手续费, `REFUND`逆向冲正)。
*   *重点核心保护: 全局系统有且仅有底层数据数据库的内联 transaction commit 系统中能够由系统主动根据返回 `ACCEPTED` 对表底层写表。屏蔽所有网络人工的非安全干扰调用。*

## 3. 工作流数据总线流转轨迹
1.  客户端发出的 HTTP 请求落入后端 FastAPI。
2.  中间件依赖注入机制拦截验证，核验当前 JSON Web Token (JWT) 与 API Key 是否关联 `User` 信息库。
3.  Payload (核心数据区) 的信息依托于 Pydantic 转换机制与底层引擎框架通信。
4.  解析出的路由调用对应的独立后台服务层引擎 (Service Layer)。
5.  数据库被动锁定进入 `事务执行中` ("transaction status")。
6.  Service Layer 发起出站 HTTP 钩子回调独立沙盒。
7.  系统接到回复的应答解析报文结构；系统立刻从自身原点发起强制的事务执行 `committed` 确认操作，或检测到错误进行全局执行状态撤销。
