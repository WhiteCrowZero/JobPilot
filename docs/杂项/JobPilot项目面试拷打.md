# JobPilot：招聘岗位情报与求职准备平台

> 补丁：本项目弃用额度控制，相关内容与实现放在 InsightVideo 项目中，本项目不做实现，相关理论解释保留。

**技术栈：** `FastAPI` `PostgreSQL` `Redis` `RabbitMQ` `Celery` `SQLAlchemy 2.0` `Alembic` `Pytest`

**项目简介：** 针对求职准备场景构建岗位情报与学习规划平台，围绕岗位采集、技能抽取、差距分析与学习任务生成，形成 **“岗位分析 →
技能匹配 → 学习准备”** 的后端业务闭环，辅助用户进行有针对性的面试准备。

- 设计 **Access Token + Refresh Token + User Session** 认证体系，支持 **Refresh Token Rotation、Access Token Blacklist
  与多设备会话管理**；结合 **Owner-based 权限校验**，实现用户私有资源隔离。
- 针对爬虫重跑、MQ 重复投递和多来源岗位重复问题，设计 **RawJobRecord 输入幂等 + 业务 fingerprint 去重** 方案，通过
  `raw_content_hash` 识别重复原始消息，并基于规范化岗位字段完成业务级去重。
- 引入 **Celery + RabbitMQ** 解耦多渠道岗位采集与后端导入链路，Worker 消费岗位消息并完成 **原始数据留痕、字段规范化、技能提取与岗位
  upsert**，支持重复消费幂等、失败重试与 DLQ 失败消息隔离。
- 设计 **JobPostSkill 岗位技能** 与 **UserSkill 用户技能画像** 模型，将岗位要求转化为结构化技能标签，并基于
  `skill_id + level` 计算 **matched / weak / missing** 技能差距，辅助生成更有针对性的学习任务。

## 认证与鉴权

> 设计 **Access Token + Refresh Token + User Session** 认证体系，支持 **Refresh Token Rotation、Access Token Blacklist
> 与多设备会话管理**；结合 **Owner-based 权限校验**，实现用户私有资源隔离。

在认证上，我没有只做一个长期 JWT，而是采用 Access Token + Refresh Token。Access Token 负责业务接口鉴权，包含
user_id、jti、token_type、exp 等字段；Refresh Token 负责续期，服务端只保存它的 HMAC hash，并通过 jti 和 user_sessions 绑定。刷新时旧
refresh token 会失效，再签发新的 token pair，用来降低重放风险，并支持单设备退出、全部退出和改密码踢下线。

权限上拆成三层。用户收藏、目标岗位、学习任务这类私有数据的用户隔离用 owner-based，通过 current_user.id 做隔离，不信任前端传来的
user_id；后台能力用 RBAC，比如题库审核、岗位导入、知识点维护；VIP 则单独做权益和额度控制，比如 AI 生成学习任务前会检查用户套餐、功能权限和
daily quota。

### 为什么要同时设计 Access Token 和 Refresh Token？

#### 回答

**核心回答**

Access Token 和 Refresh Token 的核心价值是职责分层，用短生命周期的 Access Token 承担高频业务鉴权，用长生命周期但受服务端管理的
Refresh Token 承担登录态续期，在安全性、用户体验和服务端性能之间取得平衡。

**延伸理解**

如果只使用一个长期 JWT，那么它一旦泄露，攻击者可以在较长时间内直接访问业务接口；而 JWT 默认是无状态的，服务端通常只校验签名和过期时间，天然不保存
token 状态，因此很难做到主动撤销。

Access Token 面向业务接口，特点是传输频率高、校验成本低、生命周期短。一般放在 Authorization: Bearer Token
中，每次请求都会携带。服务端验证签名、过期时间和 token_type，然后解析 user_id 或 sub，加载当前用户并继续做权限判断。

Refresh Token 面向登录态延续，使用频率低，但安全风险更高。因为它可以换取新的 Access Token，所以不能只依赖 JWT
自身的过期时间控制，而需要服务端状态管理。否则一旦 refresh token 泄露，攻击者就可以不断刷新出新的 access token。

因此生产环境通常会引入 refresh token hash、session 落库、refresh token rotation、主动撤销、设备管理等机制，实现长期登录和安全控制。

**项目落地**

在当前项目中，认证体系设计为 Access Token + Refresh Token + User Session。

Access Token 负责业务接口鉴权；Refresh Token 与 User Session 绑定，负责登录态续期。数据库中的 user_sessions 保存长期可信状态，例如
refresh_jti、refresh_token_hash、revoked_at、expires_at、last_used_at 等字段；Redis 负责缓存 Session 状态以及维护 Access
Token 黑名单。

刷新时，服务端先验证 Refresh Token，再根据 jti 找到对应 Session，校验是否过期、是否被撤销以及 hash 是否匹配。验证通过后签发新的
Access Token 和 Refresh Token，并更新 Session 信息，使旧 Refresh Token 失效。

退出当前设备时，撤销当前 Session，同时将当前 Access Token 的 jti 加入 Redis 黑名单，使其立即失效。踢出单个设备本质上是撤销对应
Session；退出全部设备则是撤销该用户下的所有 Active Session。

#### 补充问题

1. Refresh Token 轮换有什么用？（每次 refresh 都返回新的 refresh token，那攻击者不也能一直拿新的？refresh token rotation
   防的到底是什么？）

    - 让 refresh token 一次性使用，降低长期复用风险，并能检测 reuse
    - refresh token rotation 防的是 Refresh Token 被盗后长期续期，但并不能防止攻击者用新获取的 refresh token 继续刷新；
    - 但是把 refresh token 从“长期可重复使用”变成“一次性可使用”，如果一个 refresh token
      被发现重复使用，服务端就能判断出异常，用于风控；此外用户和攻击者只有一个人可以使用到 refresh
      token，同时竞争时用户也能及时发现异常，退出所有设备并重新登录

1. Refresh Token 存 Redis 够不够？为什么生产级要考虑 user_sessions 落库？如何实现多设备登录、单设备退出、全部退出？

    - 刷新时：

      ```text
      1. decode refresh token，拿到 user_id、session_jti、refresh_jti；
      2. 查 user_sessions，要求 session active、未过期、current_refresh_jti 匹配；
      3. 对比 refresh token hash；
      4. 在事务中把 current_refresh_jti 更新为新的 refresh_jti；
      5. Redis 同步更新热 key；
      6. 返回新的 token pair 令牌对。
      ```

      这样可以自然支持当前设备退出、踢某台特定设备、全部设备退出

1. 为什么要原子消费？（浏览器多标签页并发刷新怎么办？）

    - 因为 refresh 接口可能被并发调用。比如浏览器多个标签页同时发现 access token 过期，同时调用
      refresh。如果不是原子消费，可能两个请求都读到旧 refresh token 有效，然后都签发新 token pair。`GETDEL`
      或数据库事务中的条件更新可以保证只有一个请求成功。

1. 注册成功但 Redis 写 refresh token 失败怎么办？

    - 注册流程实际涉及两个资源：关系型数据库插入用户、用户信息、认证信息数据，Redis：保存 refresh token hash。普通数据库事务只能保证
      PostgreSQL 内部多表一致，不能保证 Redis 也一起提交或回滚。这是分布式事务边界问题。
    - 账号创建和登录态签发可以拆成两个业务结果。账号创建成功就是成功；token 签发失败可以要求重新登录。不值得为 refresh
      token 写入失败引入复杂分布式事务。

1. Access Token 过期时间设置多久合适？

    - 没有绝对值，取决于安全和体验。常见取舍：

      | 场景 | access token | refresh token |
                  | --- | ---: | ---: |
      | 普通 Web 应用 | 15～30 分钟 | 7～30 天 |
      | 管理后台 | 5～15 分钟 | 数小时～数天 |
      | 高安全系统 | 1～5 分钟 | 短期 + 二次验证 |
      | 移动端 | 15～60 分钟 | 数周，但绑定设备和风控 |

    - 不是固定一个数，而是根据业务风险设定。JobPilot 求职学习系统不是金融支付，access token 可以设置十几分钟到半小时，refresh
      token 设置数天到数周。高危操作可以要求重新认证。

1. refresh token 为什么只存 hash，不存明文？

    - 因为 Redis 或数据库也不能假设绝对安全。如果服务端存明文 refresh token，一旦 Redis dump、日志、运维界面或数据库泄露，攻击者可以直接拿
      token 去刷新。

#### 注意点

1. 没有额外处理，logout 后 JWT 不会立刻失效。
    - 无状态 access token 默认不会因为 logout 自动失效，除非引入黑名单、token_version、session 校验等机制。
    - logout 如果只删除 refresh token，access token 仍等到 exp。
1. payload 默认可见，只是因为服务端签名不能被篡改。
1. token_version 不能精确踢某台设备。token_version 更适合全量失效；单设备控制需要 session 维度。
1. token 有效不代表用户一定有效。分三层认证：
    - token 状态：签名是否正确、是否过期、类型是否正确；
    - session 状态：refresh/session 是否 active、是否 revoked、是否过期；
    - user 状态：用户是否 active、disabled、deleted。

### Cookie + Session 和 JWT Token 方案有什么区别？

#### 回答

**核心回答**

Cookie + Session 和 JWT Token 的核心区别在于：前者是服务端保存登录状态，客户端只保存一个 session_id；后者通常是客户端保存
token，服务端通过签名校验 token 的合法性。Session 方案的状态控制能力更强，天然适合主动失效、踢人、设备管理；JWT Access Token
校验更轻量，更适合前后端分离和 REST API，但如果完全无状态，主动撤销能力较弱。实际生产经常结合使用：用短期 Access Token
做业务鉴权，用服务端 Session 或 Refresh Token 记录长期登录态。

**延伸理解**

传统 Cookie + Session 方案的优点是状态都在服务端，撤销和管理很方便；缺点是分布式部署时需要共享 session 存储，而且 Cookie
自动携带，浏览器场景下要重点防 CSRF。

JWT Token 方案中，JWT payload 默认只是编码不是加密，不能放敏感信息；并且无状态 JWT 一旦签发，在过期前默认难以主动撤销，需要黑名单、token_version
或 session 校验补充。

**当前项目处理**

在当前项目中，采用的就是混合方案：Access Token 使用短生命周期 JWT，负责业务接口鉴权；Refresh Token 绑定
user_sessions，负责长期登录态续期和设备维度管理。这样既保留了 JWT 在 API 鉴权上的轻量优势，又通过服务端 session 弥补了 JWT
主动失效能力弱的问题。

具体来说，user_sessions 表保存 refresh_jti、refresh_token_hash、revoked_at、expires_at、last_used_at 等长期可信状态；Redis
用于缓存 session 状态、保存短期黑名单或加速 refresh 校验。刷新时根据 refresh token 的 jti 找到对应 session，校验未过期、未撤销且
hash 匹配后再签发新的 token pair。退出登录、踢掉单设备或全部设备，本质上都是撤销对应 session；如果要求 Access Token 立即失效，再把
access token 的 jti 加入 Redis 黑名单，并设置为剩余有效期的 TTL。

#### 补充问题

1. token 放 localStorage 有什么风险？

    - 主要是 XSS。一旦页面被注入脚本，localStorage 中的 token 可以被读取并发送到攻击者服务器。
1. token 放 HttpOnly Cookie 就绝对安全吗？
    - HttpOnly 可以防止 JS 读取 cookie，但会有cookie本身的问题，即前后端考虑CSRF。

### 如何设计生产级 user_sessions 表和刷新流程？

#### 回答

**核心回答**

生产级认证不能只把 Refresh Token 当成一个孤立的凭证，应该把它提升为“用户会话 Session”来管理。Refresh Token 本质上只是某个
Session 的续期凭证，真正需要控制的是：这个 Session 属于哪个用户、来自哪个设备、是否被撤销、何时过期、最近什么时候使用。这样才能支持单设备退出、全部设备退出、刷新轮换、重放检测和登录审计。

**延伸理解**

表设计

核心：session_jti、refresh_jti、refresh_token_hash、revoked_at

```sql
CREATE TABLE user_sessions
(
    id                 BIGSERIAL PRIMARY KEY,
    user_id            BIGINT       NOT NULL,
    session_jti        VARCHAR(64)  NOT NULL UNIQUE,
    refresh_jti        VARCHAR(64)  NOT NULL UNIQUE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    device_id          VARCHAR(128),
    device_name        VARCHAR(128),
    user_agent         TEXT,
    ip_address         VARCHAR(64),
    status             VARCHAR(20)  NOT NULL DEFAULT 'active',
    revoked_at         TIMESTAMP NULL,
    revoked_reason     VARCHAR(50) NULL,
    expires_at         TIMESTAMP    NOT NULL,
    last_used_at       TIMESTAMP NULL,
    created_at         TIMESTAMP    NOT NULL,
    updated_at         TIMESTAMP    NOT NULL
);

CREATE INDEX idx_user_sessions_user_status
    ON user_sessions (user_id, status, expires_at);
```

其中 session_jti 表示一次登录会话的稳定 ID，access token 和 refresh token 都可以携带它；refresh_jti 表示当前有效 refresh
token 的唯一 ID，每次刷新都会更新；refresh_token_hash 用于避免服务端保存明文 token。

Refresh Token 刷新流程属于安全关键路径，不能只依赖 Redis 缓存或 JWT 自身校验来判断是否合法。应该先在数据库中查询验证，并更新；事务提交后，再删除对应
Redis 缓存，避免旧缓存继续参与后续判断。

在 Refresh Token Rotation 模式下，为了避免并发刷新导致同一个 Refresh Token
被重复使用，更新会话状态时通常需要配合行锁（select ... for update）或乐观锁（token version），保证旧 Refresh Token
最多只能成功刷新一次。如果发现旧 refresh_jti 被重复使用，可以认为存在重放风险，直接撤销该 session，并记录 reuse_detected。

**当前项目处理**

在当前项目中，整体设计为 Access Token + Refresh Token + user_sessions。登录成功后创建一条 user_session，生成 access token 和
refresh token。access token 携带 user_id、session_jti、jti、token_type=access、exp；refresh token 携带
user_id、session_jti、jti、token_type=refresh、exp。数据库保存当前 refresh_jti 和 refresh_token_hash，Redis 可以缓存 session
状态或 refresh 校验数据，但长期可信状态以数据库为准。

刷新时，服务端校验 refresh token 后，根据 session_jti 查询 session，校验状态和 hash，通过后在同一个事务中更新新的
refresh_jti、refresh_token_hash、last_used_at，并返回新的 token pair，使旧 refresh token 失效。当前设备退出时撤销当前
session，并清理 Redis 缓存；如果要求 access token 立即失效，可以把 access token 的 jti 加入 Redis 黑名单，TTL
设置为剩余有效期。全部设备退出则撤销该 user_id 下所有 active sessions。

### 权限隔离怎么做？

**核心回答**

JobPilot 的权限体系可以按业务语义拆成三层：用户私有数据隔离用 owner-based access control，后台管理能力用 RBAC，会员功能和额度用
entitlement / quota。三者解决的问题不同，不能混在一起。

**延伸理解**

owner-based 主要解决“用户不能访问别人数据”的问题。实现上，收藏、目标岗位、用户技能、学习任务、作答记录这些表都带 `user_id`
，查询、更新、删除时都要加 `Model.user_id == current_user.id`。即使用户手动改 URL 里的 `task_id` 或 `target_id`
，也只会在当前用户的数据范围内查找，查不到就返回 404。

RBAC 更适合后台系统，比如管理员、运营、题库审核员、超级管理员，不同角色拥有不同后台权限，例如题库审核、岗位导入、知识点维护、用户管理。

VIP不属于管理权限，而是产品权益，因此需要单独设计相关的数据库表进行控制。这部分通过 `subscription + entitlement + quota`
判断，而不是通过 RBAC 判断。

**当前项目处理**

在当前项目中，普通业务接口以 owner-based 为主。接口层通过 access token 解析 `current_user`，service 层只接收
`current_user.id`，repository 层所有私有资源查询都强制带 user_id 条件。

后台管理单独引入 RBAC，通过 `user -> roles -> permissions` 判断是否允许题库审核、岗位导入、知识点维护等操作。

VIP有设计 subscription_plans、user_subscriptions、feature_entitlements、feature_usage_records 来管理控制用户使用量和使用权限。

以“生成学习任务”为例。首先通过 token 拿到 current_user，不能从请求参数里拿 user_id。然后查询目标岗位时必须带
`target.user_id == current_user.id`，保证这个目标岗位是当前用户自己的，这是 owner-based。接着生成学习任务属于 AI
高成本功能，所以会调用 EntitlementService 检查当前用户是否有 `ai_task_generate`
权益，以及当天额度是否足够。如果额度足够，会在事务里更新使用次数，然后才真正生成学习任务。后台管理员权限不参与这个接口，因为这是普通用户业务接口，不需要
RBAC。

**表设计**

```text
subscription_plans
- plan_code:
  - free
  - pro
  - premium
- name
- status

user_subscriptions
- user_id
- plan_code
- status:
  - active
  - expired
  - canceled
  - trialing
- starts_at
- expires_at

feature_entitlements
- plan_code
- feature_key
- enabled
- quota_limit
- quota_window

feature_usage_records
- user_id
- feature_key
- usage_window
- window_start
- used_count
```

#### 补充问题

1. 为什么不全部用 RBAC？（VIP 为什么不设计成 role=vip？）

    - RBAC 管角色，owner-based 管归属，VIP 管权益和额度。
    - 因为 RBAC 解决的是角色权限，不适合解决用户之间的数据归属问题。用户 A 和用户 B 都是普通用户，role 都是 user，但用户 A
      不能访问用户 B 的学习任务，这不是 role 能区分的，而是资源 owner 的问题。所以普通用户数据隔离用 owner-based。RBAC
      我只用于后台管理，比如管理员、审核员、运营人员。
    - VIP/Pro 也不放进 RBAC，因为它是产品权益和额度，不是后台权限（因为 VIP 和 admin 不是同一个维度）。一个 Pro
      用户不应该拥有后台权限，一个管理员也不一定是 Pro 用户。所以我把它们拆开：RBAC 负责后台权限，subscription/entitlement
      负责会员权益。

1. 额度如何防止并发超用？

    - 额度扣减不能先查再改，否则并发请求下可能超用。我的做法是把额度记录放在 `feature_usage_records` 表里，并按
      `user_id + feature_key + usage_window + window_start` 做唯一约束，保证同一个用户、同一个功能、同一个周期只有一条计数记录。
    - 扣减额度时不在代码里先查 `used_count` 再判断，而是使用带条件的原子 `UPDATE`。如果影响行数等于 1，说明扣减成功；如果等于
      0，说明额度已经用完。这样“判断额度是否足够”和“扣减额度”在同一条 SQL 里完成，数据库会保证同一行的并发更新串行执行，从而避免超额使用。
    - 如果后续接口 QPS 很高，可以把额度扣减前置到 Redis Lua 中做原子判断，再异步同步数据库；但在当前项目里，数据库原子
      UPDATE 已经足够稳定。

1. 权限校验应该放在哪一层？

    - 我会分层放。认证放在接口依赖层，先解析 current_user。owner-based 的 user_id 条件必须下沉到 repository 查询里，不能只在
      service 查完后再判断，因为查完再判断容易误用，也可能造成数据泄露。RBAC 的后台权限可以通过 router dependency 做前置拦截。VIP
      权益校验放在 service 层，因为它和具体业务功能、额度扣减、事务强相关。

1. 如果管理员要看用户数据，owner-based 还生效吗？

    - 普通用户接口一定走 owner-based，只能看自己的数据。

    - 管理员查看用户数据不会复用普通用户接口，而是走后台接口。后台接口先做 RBAC 权限校验，比如 `user_data:read`，通过后才允许按
      user_id 查询指定用户数据。这样普通用户数据接口和后台管理接口是分开的，避免因为管理员需求破坏普通用户接口的隔离原则。
      ```text
      普通接口：
      /api/study-tasks/{id}
      只能 current_user.id

      后台接口：
      /admin/users/{user_id}/study-tasks
      需要 user_data:read 权限
      ```

#### 注意点

- 访问被人的资源时返回404；对私有资源，系统会返回 404，而不是 403，避免告诉攻击者“这个资源存在但不是你的”。

- 不接收前端传来的任意 user_id 作为资源归属依据。私有资源永远不信任前端传入的 user_id，必须从 access token 解析
  current_user，所有私有资源查询、更新、删除都带上 `user_id == current_user.id`。

- 权限隔离要分三层：

  ```text
  第一层：认证层识别当前用户是谁；
  第二层：资源归属层判断这条数据是不是他的（owner-based）；
  第三层：权限策略层判断他有没有某类操作权限（rbac / vip）。
  ```

- VIP 不要放进 RBAC，扣减额度要保证原子性。

### 额度预扣方案

防止VIP调用超限（每次调用还是和总额度比较，只是这个总额度先扣了预留额度，没成功就还回去）

两张表，一张额度汇总表（包含总额度、已使用额度、预留额度）、一张预留额度消耗流水表（reserved 预留中、consumed 已正式消耗、released
已释放）；两个表要在同一个事务中更新

执行流程

- 核心：
    - 先扣预留额度，总额度减下去；
    - 之后限流再比较总额度，不够就拒绝；

- 后续处理
    - 执行成功预留额度这边改成扣成功，这是单独的一条记录，另一张单独的表，专门用于预留扣费的；
    - 执行失败，这边改为失败；总额度再加回去

表设计：

额度汇总表

```text
user_quota
----------
user_id
total_quota
used_quota
reserved_quota
updated_at
```

可用额度：

```text
available = total_quota - used_quota - reserved_quota
```

预留：

```sql
UPDATE user_quota
SET reserved_quota = reserved_quota + :cost
WHERE user_id = :user_id
  AND total_quota - used_quota - reserved_quota >= :cost;
```

成功确认：

```sql
UPDATE user_quota
SET reserved_quota = reserved_quota - :cost,
    used_quota     = used_quota + :cost
WHERE user_id = :user_id
  AND reserved_quota >= :cost;
```

失败释放：

```sql
UPDATE user_quota
SET reserved_quota = reserved_quota - :cost
WHERE user_id = :user_id
  AND reserved_quota >= :cost;
```

流水表

```text
quota_transactions
------------------
id
user_id
request_id
task_id
type        reserve / confirm / release / refund
amount
status
created_at
```

具体业务场景就是调用AI进行学习任务评价

- 这里先完成扣额度的任务（预留额度扣除）；
- 然后再去处理AI学习任务评价（业务场景，中间也可以有多次业务相关的短事务）；
- AI任务完成后，保存AI结果（业务结果）和额度扣款的确认，要放在同一个短事务中

### access 黑名单与 session

redis access blacklist只是一层补丁，专门用于退出登录时当前access快速失效，短暂风控某个token，真正控制整个会话的是session

refresh rotation，主要保证只有一个refresh可以用，旧refresh token全部失效，同时可以保证检测出旧refresh复用的风险

session才是控制的核心，主要是特定提到某个设备，或者全部设备下线，直接设置`status = revoked`
；每次单独校验完JWT（是否正确、是否过期），都还要专门校验session的情况（一般存redis，更新就删除，下次访问重建）

## 岗位去重与幂等导入

> 针对爬虫重跑、MQ 重复投递和多来源岗位重复问题，设计 **RawJobRecord 输入幂等 + 业务 fingerprint 去重** 方案，通过
> `raw_content_hash` 识别重复原始消息，并基于规范化岗位字段完成业务级去重。

JobPilot 这个项目里，岗位数据会从不同来源导入，由多渠道不同平台的爬虫采集导入。做到这块以后我发现，核心问题不只是把数据插进数据库，而是多来源数据很容易重复：同一个岗位可能被不同平台采到，也可能因为
MQ 重试、爬虫重跑或者批量导入重复执行而被处理多次。

所以我把岗位导入拆成两层处理。第一层是原始输入幂等，用 source_id + raw_content_hash
这类字段判断同一条原始消息是不是被重复处理。第二层是业务对象去重，把岗位标题、公司、地点等字段规范化后生成
fingerprint，并在数据库上加唯一约束。导入时用 upsert，如果 fingerprint 不存在就插入新岗位，如果已存在就更新岗位状态、最近发现时间、出现次数等信息。

这个设计主要是为了保证岗位池质量，因为后续技能统计、岗位匹配和学习任务生成都依赖岗位数据。如果重复岗位太多，技能分析结果会被放大和污染。

### 导入幂等是怎么实现的？重复导入会发生什么？

#### 回答

**核心回答**

岗位导入的幂等分成两层：第一层是原始输入幂等，解决“同一个 MQ
消息、同一个导入行被重复处理”的问题，区分的是这条输入我是不是处理过”；第二层是业务对象幂等，解决“不同来源或不同批次的数据，其实指向同一个岗位”的问题，区分的是是否是同一个业务对象。

前者依赖 `source_id + raw_content_hash`，后者依赖规范化后的 `fingerprint`，并在数据库层加唯一约束兜底。

**延伸理解**

重复导入时，策略一般不是简单忽略，而是冲突更新。比如岗位薪资、招聘状态发生变化，需要更新主表；同时更新 `last_seen_at`、
`seen_count` 等字段，表示这个岗位最近又被来源平台发现过。如果来源显示岗位关闭，也要更新为 closed 或 expired。

**当前项目处理**

在 JobPilot 中设计为 raw 记录层和 job_posts 业务层两段式导入。raw 层保存来源 payload、raw_content_hash、source_id
等字段，用于追踪来源数据、判断重复消息、支持失败重试和问题排查。规范化后基于公司、标题、地点等稳定内容字段生成  `fingerprint`
，并在 `fingerprint` 上建立唯一约束。导入时使用 `upsert`：如果 fingerprint 不存在就插入新岗位；如果已存在就更新岗位内容、状态、最后发现时间和发现次数。

先用 raw 幂等防重复消息，再用确定性 fingerprint 做强去重，只有 fingerprint 不确定或疑似重复时，才进入相似度召回和人工审核。

#### 补充问题

1. 岗位 fingerprint 是什么？如何生成的？

    - fingerprint 是岗位的业务内容指纹。把岗位标题、公司、地点等关键字段做规范化后，再生成 hash，用来判断不同来源的数据是否指向同一个岗位。
    - 主要风险是 fingerprint 规则不是绝对准确。规则太粗会误合并，规则太细会漏合并。后续需要实际的业务测试来调整到合适的边界。
1. 重复导入时应该忽略、更新还是覆盖？
    - 重复导入不等于直接丢弃。通常不新增重复岗位，但会针对不同的字段类型进行有选择的更新。
    - 三种更新计划：
        - 身份字段不覆盖，比如公司、标准化标题、地点；（fingerprint的计算字段）
        - 观测字段可以更新，比如 last_seen_at、seen_count；（运维审计字段）
        - 可变字段按规则更新，比如薪资、状态、描述，只有新值非空、来源优先级更高。（业务语义字段，按照优先级更新）

1. 为什么不用 embedding / 相似度直接做岗位去重？
    - embedding 或相似度去重可以处理更复杂的近似重复，但成本和风险也更高，目前阶段希望先采用规则化的方式处理掉大部分问题，起到兜底的作用。
    - 后续对规则 fingerprint 无法覆盖的近似重复问题，可以用 embedding 做候选召回，再通过规则或人工审核确认。
1. 整体的去重如何设计的？
    - 所有后端业务侧的去重，核心依赖都是数据库的唯一约束
    - 三层去重结构
        - 爬虫去重：source_id / url / raw_content_hash
        - 消息幂等：message_id(raw_content_hash)
        - 业务去重：fingerprint
1. 并发导入同一数据冲突处理
    - 一定不能“先查再插”，这是典型的错误
    - job_post并发导入同一数据，根据数据库fingerprint唯一约束，同样的数据只会有一份插入成功。
    - 主要依靠唯一约束，手段可以是行锁或者CAS。根据唯一键，只会创建一条记录；多个进程并发执行，只有一个会创建成功，其余根据唯一键冲突，要么do
      nothing，要么进行更新（具体如何更新看那业务规则）

#### 注意点

- `raw_content_hash` 不适合作为业务岗位唯一标识，它只能说明原始 payload 是否变化；同一个岗位内容变了，hash 就会变，但它仍然是同一个岗位。
- 应用层不能先查再插。并发下会竞态，必须有唯一约束兜底。应该使用 `upsert` 冲突更新。
- fingerprint 不是数据库主键，主键仍然可以是自增 ID。

### fingerprint 发生规则误判怎么办？

**核心回答**

理论上 Hash 算法都存在碰撞可能，但目前来说，实际业务中的碰撞概率几乎可以忽略。当前去重场景的核心在于 Fingerprint 规则设计是否合理。

**延伸理解**

规则误判是重要的业务问题，主要是 `fingerprint` 字段设计不合理导致的。

- 如果参与计算的业务信息太少，会导致误合并，不同的岗位被认为是同一个岗位；
- 参与计算的业务信息太多，会导致误拆分，即同一个招聘信息更新了岗位，却被理解成了两个单独的岗位。
- 因此这块需要根据实际业务不断调整和验证，找到稳定性和准确性之间的平衡。

整个的取舍本质就是其实是一个准确率和召回率的平衡问题。规则太宽松容易误合并，规则太严格容易误拆分，没有绝对正确的配置，需要结合实际数据不断调优。

**当前项目处理**

当前项目优先使用规则型 Fingerprint 去重，比如基于公司名称、岗位名称、工作地点等相对稳定的字段处理成标准化字符串，再计算
SHA256，作为 Fingerprint 值。如果后续发现误合并，说明规则太宽，需要增加更有区分度的字段；如果发现误拆分，说明规则太严，需要减少频繁变化字段，或者把这些字段改为更新内容而不是去重依据。

之后的演进中，如果要求严格且成本允许，可以把 Fingerprint 设计得偏严格，先尽量避免误合并；然后不同的 fingerprint 计算
embedding 相似度，相似度较低认为不相同，当成新的岗位处理；如果相似度很高，可以再交给人工进一步判断。

## MQ 解耦

> 引入 **Celery + RabbitMQ** 解耦多渠道岗位采集与后端导入链路，Worker 消费岗位消息并完成 **原始数据留痕、字段规范化、技能提取与岗位
> upsert**，支持重复消费幂等、失败重试与 DLQ 失败消息隔离。

生产主链路：

```text
┌──────────────────────────────────────────────┐
│                 Gerapy / Scrapyd              │
│  管理 Scrapy 项目、Spider 启停、定时任务        │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                Scrapy Crawlers                │
│  ali_spider / tencent_spider / jaabz_spider    │
│  scrapy-redis: URL 队列、请求去重、断点续爬      │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│            Scrapy Item Pipeline               │
│  轻量字段校验、source 标记、raw hash 生成       │
│  Celery send_task 投递岗位采集任务              │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                   RabbitMQ                    │
│  job_import queue / retry queue / dead queue   │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│             JobPilot Celery Worker            │
│  consume raw job task                          │
│  RawJobRecord 落库                             │
│  normalize + fingerprint                       │
│  JobPost upsert                                │
│  Skill extraction                              │
│  JobPostSkill upsert                           │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│             PostgreSQL / MySQL                │
│  raw_job_records                               │
│  job_posts                                     │
│  job_post_skills                               │
│  import_batches / crawl_sources                │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                  FastAPI                       │
│  查询状态 / 失败重试 / 后台管理 / 数据查看       │
└──────────────────────────────────────────────┘
```

JobPilot 里有一块是岗位采集和导入链路。这个场景的核心问题不是简单把爬虫数据写进数据库，而是爬虫系统和后端业务系统的节奏不一样。

所以我引入 Celery + RabbitMQ，把多渠道爬虫采集和后端导入处理解耦。爬虫侧只负责采集并投递 raw job message，后端 Worker
异步消费消息，先写 RawJobRecord 做原始数据留痕，再进行字段规范化，生成岗位 fingerprint，最后通过 upsert 写入 job_posts。

这块我重点考虑了 MQ 至少一次投递带来的重复消费问题。因为消息可能因为 Worker 宕机、ack 失败、自动重试或者人工重放被重复处理，所以我在后端做了两层幂等：raw
层用 message_id、source_id + raw_hash 识别重复输入，业务层用 fingerprint 唯一约束保证同一岗位不会重复插入。失败任务则通过
retry 和 DLQ 做隔离，方便后续排查和补偿。

技术栈上，Scrapy 负责爬虫采集，scrapy-redis 用于分布式调度与去重，Celery + RabbitMQ 负责异步任务投递与消费执行，RawJobRecord
用于原始数据留痕与状态追踪。

### 为什么选择 Celery + RabbitMQ，而不是普通 RabbitMQ consumer？

#### 回答

**核心回答**

Celery 作为任务执行框架，RabbitMQ 作为消息中间件。

我选择 Celery + RabbitMQ，主要是因为当前项目的爬虫系统和后端系统都是 Python 技术栈，没有跨语言协作问题，而岗位导入本质上又是典型的异步任务场景。相比直接手写
RabbitMQ consumer，Celery 已经封装了任务投递、Worker 并发、任务路由、失败重试、超时控制和基本监控能力，选择 Celery 可以降低工程复杂度。

**延伸理解**

普通 RabbitMQ consumer 的优势是协议更通用、系统边界更清晰，Producer 只需要投递标准事件，比如 `job.collected`，Consumer
自己决定怎么处理，对跨语言、跨团队系统更友好。但缺点是很多任务治理能力要自己实现，比如手动
ack、失败重试、死信队列、并发模型、任务超时、任务路由、消费监控等。

Celery 本质上是在 RabbitMQ 之上提供了一层 Python 任务队列框架，更适合 Python 内部系统之间的异步任务调度。它的代价是会有一定框架耦合，Producer
需要知道 task name （任务名称）和 message schema （消息参数结构），所以不适合所有系统都强依赖它。

**当前项目处理**

在 JobPilot 中，Scrapy Pipeline 采集到岗位 raw item 后，通过 Celery `send_task` 投递 `jobpilot.tasks.import_raw_job`
，RabbitMQ 作为 Celery broker，后端 Celery Worker 负责消费任务，完成 raw 落库、字段规范化、fingerprint 生成和 `job_posts`
upsert。

如果后续项目发展成跨语言、跨团队的数据采集平台，我会把爬虫侧改成只发布标准领域事件，后端用普通 RabbitMQ consumer 消费，降低对
Celery task 协议的耦合。

#### 补充问题

1. Celery 会不会让爬虫和后端耦合？

    - 有一定耦合，因为爬虫要知道后端 task name 和 message schema，但当前项目规模下可以接受，换来开发效率和更完整的任务治理能力。

1. 为什么爬虫不直接调用后端接口，而是通过 MQ？

    - RabbitMQ 带来的价值：

        ```text
        1. 解耦采集和入库；
        2. 削峰填谷；
        3. 后端 Worker 可独立扩容；
        4. 失败可重试；
        5. 可做死信队列和人工补偿；
        6. 可以按队列拆分不同处理阶段。
        ```

#### 注意点

- Celery 不是 MQ，Celery 是任务框架，RabbitMQ 是 broker。

### RabbitMQ 的 ack、retry、DLQ 怎么处理？

#### 回答

**核心回答**

Worker 不应该一拿到任务就 ack，而是只有当业务逻辑真正完成之后才 ack，否则一旦 worker 宕机或异常退出，消息会被重新投递，保证“至少一次消费”。

失败时要区分可重试和不可重试。数据库临时异常、网络抖动可以 retry，超过最大重试次数的消息可以进入
DLQ；消息格式错误、字段缺失这类不可恢复错误应该直接进入DLQ，不需要重试，等待人工排查和重放。

**延伸理解**

ack 的本质是告诉 Broker 该消息已被成功处理并可以移除，因此必须延迟到业务最终成功，而不能在任务开始时就确认，否则会造成“业务失败但消息已丢失”的数据不一致问题。

失败处理通常需要区分两类场景：

- 一类是临时性失败，例如数据库连接异常、网络抖动、外部依赖超时，这类错误具有不确定性，可以通过 retry 机制进行重试，通常结合指数退避避免瞬时压力放大；
- 另一类是确定性失败，例如消息字段缺失、数据格式非法、业务校验不通过，这类任务即使重试也不会成功，应直接进入
  DLQ，避免无限重试消耗系统资源。

本质上，这套机制是在可靠性与系统稳定性之间做平衡：retry 负责最终一致性，DLQ 负责系统保护与异常隔离。

**当前项目处理**

在 JobPilot 中，爬虫通过 Celery 投递岗位导入任务，Worker 处理流程遵循“Raw 落库 → 数据清洗 → fingerprint 生成 → job_posts
upsert”的顺序。只有当 rawJobRecord 成功落库并且核心处理逻辑完成后，才认为任务成功，从而触发 ack。

对于失败情况，如果属于数据库或网络类临时异常，则由 Celery retry 机制进行重试；如果属于字段缺失或数据结构非法，则直接记录失败状态并进入
DLQ，避免重复消费。超过最大重试次数的任务同样会进入 DLQ。

#### 补充问题

1. RawJobRecord 为什么要先落库？
    - RawJobRecord 是后端导入链路的输入边界。它不只是为了去重，还用于保存原始 payload、记录 source_id、raw_hash、处理状态、错误原因和最终
      job_post_id。这样清洗失败、入库失败或者 Worker 重试时，都能知道原始数据是什么、失败在哪一步、能否重放。
    - 如果直接写 job_posts，中间失败后就很难排查，也没法稳定重试。

1. Worker 重复消费怎么办？
    - 重复消费可能来自很多场景：

      ```text
      1. Worker 处理成功但 ack 前宕机；
      2. RabbitMQ 没收到 ack；
      3. Celery 自动 retry；
      4. Worker 超时被杀死；
      5. 人工重放 failed 消息；
      6. 爬虫侧重复投递。
      ```

      所以 Worker 必须按重复执行安全来设计，不假设“MQ 只会消费一次”。

    - 项目按“至少一次消费”（at-least-once）来设计，也就是任务可能重复执行。做多层幂等：`message_id` 防重复消息，
      `source_id + raw_hash` 防重复原始输入，`fingerprint` 防重复业务岗位。最终靠数据库唯一约束和 upsert 兜底。

1. 为什么等业务处理完再手动 ack？

    - RabbitMQ 的 ack 本质是消费者告诉 broker：这条消息已经处理完成，可以从队列删除。
    - 如果 Worker 刚拿到消息就 ack，后面清洗或入库失败，RabbitMQ 会认为消息成功了，但业务数据没有落库，这就是消息丢失。所以重要业务任务应该“处理成功后再
      ack”。

#### 注意点

- MQ 不只是为了异步，更重要的是系统解耦、削峰、重试和消费端扩容。
- MQ 成功就不等于岗位入库成功，投递成功只代表消息进入队列；业务成功要看 Worker 处理状态，最后消费端是否 ack。
- MQ 可能重复投递，业务必须自己保证幂等。项目采用的就是 source_id + raw_content_hash。
- retry 不是万能的

#### MQ 消息幂等消费详细解释

message_id（raw_content_hash）负责识别幂等，但是并不负责发现重复事件之后的处理；

发现重复事件之后，要根据当前业务状态决定如何处理：

- 事件写入数据库，已经成功

    - 直接ack，无需处理

- 事件不可恢复失败

    - 直接ack，无需处理

- 事件正在处理，并且未超时

    - 直接ack，无需处理

- 事件可恢复失败，且未超过最大失败次数

    - CAS抢夺事件锁，修改状态为processing，开始重试处理

- 事件正在处理，但是已经超时

    - 认为另一个进程已经挂掉，CAS抢夺事件锁，重新开始处理

      ```sql
      UPDATE raw_job_records
      SET
          locked_by = :current_worker_id,
          locked_at = NOW(),
          heartbeat_at = NOW(),
          retry_count = retry_count + 1,
          updated_at = NOW()
      WHERE id = :raw_id
        AND status = 'processing'
        AND locked_at < NOW() - INTERVAL '10 minutes';
      ```

整体流程

```
MQ message delivered
        ↓
Worker receives message
        ↓
计算 message_id / source_id / raw_hash
        ↓
尝试插入 RawJobRecord(status=processing)
        ↓
┌─────────────────────────────┐
│ 插入成功                     │
│ 当前 Worker 获得处理权        │
└──────────────┬──────────────┘
               ↓
       清洗 + fingerprint
               ↓
       JobPost upsert
               ↓
       JobPostSkill upsert
               ↓
       RawJobRecord = succeeded
               ↓
       DB commit
               ↓
       MQ ack


如果 RawJobRecord 已存在：
        ↓
┌──────────────────────────────────────────┐
│ succeeded                                │
│ → 已处理过，直接 ack                       │
├──────────────────────────────────────────┤
│ processing + 未超时                       │
│ → 其他 Worker 处理中，当前消息 ack          │
├──────────────────────────────────────────┤
│ processing + 已超时                       │
│ → CAS 抢占，成功才处理，失败 ack            │
├──────────────────────────────────────────┤
│ failed + 可重试                           │
│ → CAS 改 processing，成功才处理，失败 ack   │
├──────────────────────────────────────────┤
│ failed + 不可重试                         │
│ → 记录失败已确定，ack / DLQ                │
└──────────────────────────────────────────┘
```

### 爬虫本身已经去重了，后端为什么还要去重？

#### 回答

**核心回答**

爬虫去重和后端去重解决的是不同层面的问题。

爬虫侧去重主要控制“采集阶段不重复抓取与投递”，而后端去重解决的是“数据进入系统后的幂等性与业务一致性问题”。因此即使爬虫已经去重，后端仍然必须做去重。

**延伸理解**

Scrapy 根据 request fingerprint 做 URL 去重，在请求层面避免同一个页面重复抓，减少重复数据进入
RabbitMQ。但这些都是采集侧的处理，无法保证端到端一致性。

在分布式链路中，从爬虫到 MQ 再到 Worker 存在多个不确定性因素：MQ 可能重复投递、Worker
可能消费失败后重试、任务可能被手动重放，这些都会导致“同一条业务数据被多次进入后端系统”。

因此后端必须建立第二层幂等机制。RawJobRecord 层通过 `message_id` 与 `source_id + raw_hash`
保证输入幂等，用于识别“是否已经处理过这条原始消息”。在业务层，再通过 fingerprint 对 JobPost
做去重判断，用来解决“同一岗位不同抓取源或不同时间抓取”的语义重复问题。

**当前项目处理**

在当前 JobPilot 设计中，爬虫侧使用 Scrapy-Redis 进行 URL 去重与断点续爬，保证同一页面不会重复进入 MQ。

后端在 RawJobRecord 层使用 `message_id` 与 `source_id + raw_hash` 做输入幂等，确保同一条消息无论重复投递或重试消费，都只会落一条原始记录。在
JobPost 层，则通过 fingerprint 做业务级去重，用于判断岗位是否为同一实体，从而支持 upsert 更新而不是重复插入。

通过“爬虫去重 + 消息幂等 + 业务 fingerprint 去重”的三层设计，保证从采集到落库的全链路一致性与可恢复性。

#### 补充问题

1. `source_id + raw_hash` 放爬虫侧还是后端侧？
    - 两边都可以有，但职责不同。爬虫侧用它做投递前去重，减少重复消息进入 MQ；
    - 后端侧仍然要用它做 RawJobRecord 唯一约束，保证即使 MQ 重复投递、Worker 重试或者人工重放，也不会重复处理同一份原始输入。
1. 爬虫侧去重会不会导致漏数据？
    - 有可能，所以爬虫侧去重不能设计得太激进。比如采用 URL 去重和 external_job_id 去重这种比较温和精准的方案

## 技能匹配与学习任务生成

> 设计 **JobPostSkill 岗位技能** 与 **UserSkill 用户技能画像** 模型，将岗位要求转化为结构化技能标签，并基于
> `skill_id + level` 计算 **matched / weak / missing** 技能差距，辅助生成更有针对性的学习任务。

JobPilot
这个项目里，核心业务闭环是岗位技能分析到学习任务生成。最开始我发现，如果只是收藏岗位，项目价值比较弱，所以我把岗位要求、用户技能和题库打通，做成“岗位目标 →
技能差距 → 学习任务”的流程。

这里我没有直接用大模型生成学习计划，而是先把技能结构化。系统内部有标准技能字典，岗位侧会生成 JobPostSkill，用户侧维护
UserSkill。匹配时只比较结构化的 skill_id 和等级，输出 matched、weak、missing。后续任务生成也是基于这个匹配结果，从题库里选择
skill_id 对应、难度合适、审核通过的题目。

技术上我主要关注几个点：第一是岗位技能和用户技能怎么建模；第二是匹配结果怎么稳定可解释；第三是学习任务生成怎么做幂等和快照；第四是用户完成任务后，怎么根据做题结果规则化更新用户技能等级。

### 岗位技能 JobPostSkill 是怎么得到的？

#### 回答

**核心回答**

`JobPostSkill` 的本质是将岗位描述中“非结构化的技能需求”转化为“结构化、可计算的数据模型”。它的来源分为两类：一类是已有结构化数据的直接映射，另一类是从
JD 文本中进行技能抽取后再结构化落库。

在已有结构化数据的情况下，例如爬虫或第三方平台已经提供 skills 字段，则直接通过标准技能字典（Skill Dictionary）进行归一化匹配，映射为内部
`skill_id`，并生成 `JobPostSkill`。

在只有 JD 文本的情况下，先通过轻量 NLP 的命名体识别从文本中识别技能实体，再与内置技能字典进行对齐，最终生成标准化的
`skill_id`。

**延伸理解**

技能抽取本质上都是两步：

1. **候选识别**：选取合适的词语（可以是规则或NER）
2. **语义归一化**：将候选词映射到统一技能字典（skill_id）

**当前项目处理**

在当前项目中，`JobPostSkill` 除了抽取 skill 标签，还会对标签进行评级和重要程度分类，供后续技能匹配业务使用。

这里用向量编码分类模型来辅助识别技能和判断等级，把岗位JD和技能编码成向量，进行分类预测，本质是一个回归问题。即经过
Sentence-BERT 的 encoder 得到向量，再做多分类。

其中 `required_level` 表示岗位对这个技能的要求等级，`importance` 区分 required 和 preferred。两者都通过多分类模型得到大致的等级划分。

#### 补充问题

1. 为什么这里 `required_level` 不使用连续的指标，比如0~1，而是离散的等级划分呢？
    - 因为该系统的核心使用场景是“匹配与决策”，而不是“精细评分”。
    - 连续的值表达更强，但是会因为过于精细，导致决策边界部分，可解释性差，业务计算复杂
    - 相交而言，使用简单的离散值分类，分类更稳定更可控，后续的业务计算也更加方便。
1. 用户技能 UserSkill 怎么得到？
    - 用户技能等级先由自评初始化，用户选择自己掌握的技能和等级，系统生成 `UserSkill`；后续在学习任务完成后，按 skill
      聚合作答结果，用规则更新 mastery_score，再映射为 proficiency_level。
    - 根据学习任务作答情况动态调整相关用户画像，方便下一次生成更符合用户需求的学习任务。
1. 学习任务完成后如何更新用户技能等级？
    - 系统保存一个更细的 `mastery_score`，这个字段专门用于用户技能评级的更新。任务完成后会按 skill 聚合作答结果，用规则更新
      `mastery_score`，再映射成 `proficiency_level`。
    - 根据结果，作对的加分，做错的扣分，跳过的忽略；当某一技能下相关非跳过题目数量超过最低阈值，才会认为作答结果有效，进行真正的更新；同时乘上难度权重；此外加入边界限制，防止大范围变化。
1. 技能匹配 matched / weak / missing 怎么计算？
    - 匹配阶段只比较结构化数据。岗位侧有 `skill_id` 和 `required_level`，用户侧有 `skill_id` 和 `proficiency_level`。
    - 如果用户没有该技能，就是 missing；如果用户有但等级低于岗位要求，就是 weak；如果用户等级达到要求，就是
      matched。后续学习任务的生成主要依赖 missing / weak。

#### 注意点

- 这里只是用 NER 进行抽取， Embedding 进行多分类，没有引入生成式大模型
- proficiency_level 等级粗，用于展示；mastery_score 细粒度，专门更新

### 学习任务问题

#### 补充问题

1. 学习任务怎么生成？

    - 学习任务基于前面的技匹配结果生成，只处理 weak 和 missing 技能。系统根据技能重要性、等级差距等计算优先级，选择 Top k
      个技能，然后从题库中筛选 skill_id 匹配、难度合适的题目，生成学习任务。整体是规则驱动的。
    - 其中如果题库中符合要求的题目不足，则跳过该技能并记录 skipped reason；如果不自动生成，用户也可以根据自己的需求从题库中选择题目生成自己的学习任务。

1. 为什么生成学习任务不用 RAG？

    - RAG 本质上是“检索 + 生成”的架构，它的核心能力是基于语义检索找到相关文本，再交给生成模型进行语言组织或答案生成。
    - 但目前任务生成这个场景，要求不是找到相关文本，而是依据用户画像从真实准确的题库中选择出合适的题目，是强约束的任务，要求稳定可以解释，而不是开放问题。因此不适合直接使用
      RAG 作为核心计算链路。

1. 如何避免重复生成学习任务？

    - 设计业务幂等 key：

        - JobPilot 的学习任务生成需要把 `source_key` 放在 `study_tasks` 表中，用于防止同一个用户、同一个岗位、同一组技能缺口重复生成任务。

      ```text
      source_key = user_id + taget_job_post_id + skill_ids + task_type
      ```

    - 生成流程：

      ```text
      1. 计算 source_key；
      2. 查询用户是否已有 pending / in_progress 的同源任务；
      3. 有则返回 reused；
      4. 没有则创建；
      5. 数据库层尽量加唯一约束或使用事务保证并发安全。
      ```

1. 为什么要保存任务快照？

    - 外键解决的是关联问题，快照解决的是历史解释稳定问题。岗位信息、用户技能等级、题目内容和任务生成规则都可能变化。如果任务完全依赖实时关联，用户以后回看任务时，数据可能不准确，技能匹配不上。
    - JobPilot 中 `StudyTaskSnapshot` 用于保存任务生成时的岗位和技能缺口上下文，避免历史任务解释随实时数据变化漂移。
