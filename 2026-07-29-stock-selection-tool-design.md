# 选股工具讨论结论整理

## 1. 文档目的

本文档用于整理当前关于“选股工具”的讨论结论，作为后续继续细化需求、设计筛选规则、拆实现计划的统一基线。

当前阶段目标不是立即开发完整系统，而是先把产品目标、模块范围、分析框架、筛选逻辑和样本复盘结论沉淀清楚，确保后续可以按“标准版先闭环，后续持续迭代”的方式推进。

## 2. 项目定位

### 2.1 产品形态

- 第一阶段产品形态：`本地分析工具`
- 使用方式：以手动触发为主，不做自动调度
- 面向对象：以单人使用为主，不做多人协作

### 2.2 核心目标

围绕 A 股为主、港股预留的股票研究流程，形成一个可持续迭代的分析闭环：

1. 筛选符合要求的股票清单
2. 对清单中的单只股票按既定框架进行基本面分析
3. 生成分析报告并存档
4. 将分析结论回写到股票清单
5. 支持股票池刷新和单股分析的手动执行

### 2.3 数据边界

- A 股主要数据源：`Tushare`
- 港股：第一期先预留结构，后续可补公司公告、港交所披露、财报摘要等数据源

## 3. 第一阶段范围

### 3.1 已确认范围

- 本地化使用
- A 股优先，港股结构预留
- 以基本面分析为主
- 输出形式包含：`结论 + 评分`
- 支持长期、频繁、小步快跑式迭代

### 3.2 明确不做

- 不做自动定时刷新
- 不做多人协作
- 不做高频交易或量化交易系统
- 不以技术面作为第一阶段核心
- 不追求一开始就覆盖全部市场、全部因子、全部策略

## 4. 产品模块拆分

当前讨论下，产品建议拆为以下模块：

1. `股票池筛选模块`
   - 根据不同模板筛出候选股票
   - 支持手动刷新

2. `股票清单管理模块`
   - 管理重点观察池、观察池
   - 保存关键结论、评分和风险标签

3. `单股分析模块`
   - 按分析框架对单只股票展开分析
   - 重点分析财报、行业、估值、风险和跟踪变量

4. `分析报告模块`
   - 形成结构化结论
   - 支持存档和回看历史分析

5. `结论回写模块`
   - 将报告中的核心结论更新回股票清单
   - 便于后续统一查看

6. `手动执行模块`
   - 清单刷新手动触发
   - 单股分析手动触发

7. `规则配置与迭代模块`
   - 为后续持续优化筛选模板、评分逻辑和分析框架预留配置能力

## 5. 关于“什么股票值得被筛出来”的核心共识

从前面的讨论看，用户关注的并不是“最便宜的股票”，而是“值得长期跟踪、值得等待买点、基本面能持续验证的股票”。

因此，值得进入筛选范围的股票，通常同时满足以下几个方向：

1. `生意本身过关`
   - 商业模式能看懂
   - 需求逻辑相对清晰
   - 行业里有一定竞争优势或稀缺性

2. `财报能验证`
   - 业绩不是纯故事
   - 收入、利润、现金流、分红、ROE 等指标能印证判断

3. `关键变量可跟踪`
   - 有清晰的后续观察点
   - 能通过季报、半年报、行业数据、公告持续验证

4. `风险能够说清`
   - 不是没有风险
   - 而是风险来源明确，可被持续监控

5. `即使暂时不买，也值得持续观察`
   - 说明公司和行业本身具备研究价值
   - 买点问题和公司质量问题需要分开看

## 6. 股票池筛选模块的设计方向

### 6.1 采用一套通用首版规则

经过后续讨论，首版不再拆成多套独立模板，而是统一采用：

`一套通用硬过滤 + 一套通用综合评分`

原因是：

1. 首版目标是先从成千上万只股票中筛出几十只值得继续看的股票
2. 这个阶段更需要 `通用、量化、可代码实现` 的规则
3. 个股差异、行业差异、复杂风险，留到第二阶段人工分析再展开

所以，首版不再区分 `成长质量池` 和 `优质低估池` 两套模板，而是统一用一套规则先完成初筛与排序。

### 6.2 入池方式

采用：`硬条件过滤 + 综合评分排序`

即：

1. 先用硬条件剔除明显不符合要求的股票
2. 再对剩余股票按综合评分排序
3. 根据分数进入不同清单层级

### 6.3 候选清单建议分层

首版股票池最终收敛为两层：

1. `重点观察池`
   - 基本面强、逻辑清晰、跟踪变量明确

2. `观察池`
   - 公司值得持续跟踪
   - 但估值、节奏、争议变量或风险折价尚未处理完毕

## 7. 首版筛选规则的取向结论

首版筛选规则不再试图一开始就把股票分成“成长模板”和“低估模板”分别处理，而是先统一回答一个更重要的问题：

`什么股票值得进入长期跟踪体系`

从前面的讨论和样本复盘看，首版规则更适合筛出以下类型的股票：

1. `生意能看懂`
   - 商业模式清晰
   - 主引擎明确
   - 不依赖模糊概念叙事

2. `财报能验证`
   - 收入、利润、现金流、分红、ROE 等指标能相互印证
   - 不是“故事好听但报表跟不上”

3. `未来 2-4 个季度有继续验证的抓手`
   - 例如扩产、价格、行业景气、第二曲线、股东回报等

4. `适合用通用量化规则做第一轮筛选`
   - 可以用硬过滤和统一评分先筛出来
   - 个股层面的复杂风险留到第二阶段人工分析

因此，首版规则的取向不是：

- 找“当前最便宜”的股票
- 找“当前涨得最快”的股票
- 找“最有故事感”的股票

而是：

`找值得继续研究、继续等待、继续跟踪的股票`


## 8. 5 只样本股票复盘后的结论

本轮样本包括：

- 紫金矿业
- 农夫山泉
- 众兴菌业
- 携程集团
- 泡泡玛特

研究口径升级到：

- `2025 年报`
- `2026 年一季报`
- `2026 年半年报预告 / 经营更新`
- `2026 年行业信息`

### 8.1 样本共同点

这 5 只股票的共同点不是“都便宜”，而是：

1. `公司基本面具备研究价值`
2. `关键变量能持续跟踪`
3. `市场会反复重估其定价`
4. `值得放进长期观察体系`

### 8.2 样本差异带来的启发

#### 紫金矿业

- 属于高质量周期成长
- 不是单纯“低估”，而是“产量兑现 + 资源价格 + 分红托底”
- 启发：周期股也可以纳入成长框架，但必须跟踪产量、资源价格和资本开支兑现

#### 农夫山泉

- 属于高质量消费龙头
- 生意模式强，品牌力强，茶饮成长增强第二曲线
- 启发：优质消费股重点不是便宜，而是估值是否高到透支未来增长

#### 众兴菌业

- 属于低估修复型 + 小盘波动型样本
- 财报修复明显，但仍有小盘、周期、波动和治理层面的折价
- 启发：小盘股不能只看 PB / PE，还要单独打流动性与波动折扣

#### 携程集团

- 属于优秀平台型公司，但监管事件会重塑利润率预期
- 启发：平台型龙头需要单独跟踪政策和监管变量，不能只看历史利润率

#### 泡泡玛特

- 属于高增速 IP 消费公司
- 成长极强，但市场担心单一爆款 IP 的持续性
- 启发：高成长消费股不能只看业绩增速，还要看增长来源是否过于集中

## 9. 从样本反推出来的筛选规律

综合前述样本，后续筛选规则建议优先识别以下特征：

1. `有明确兑现路径`
   - 未来 2-4 个季度有清晰验证点

2. `至少有一个主引擎，最好有第二增长曲线`
   - 避免只靠单一短期故事支撑估值

3. `财报与逻辑相互印证`
   - 不能只靠行业叙事

4. `行业顺风仍在，或至少没有明显逆转`
   - 公司再强，也不能完全脱离行业环境

5. `核心风险可量化跟踪`
   - 例如监管、单一 IP、产能释放、周期价格、小盘股流动性

6. `估值判断必须匹配行业类型`
   - 资源、消费、平台、IP 类公司不能用同一把估值尺子

## 10. 股票池规则框架草案

### 10.1 硬过滤条件建议

首版硬过滤不再引入复杂、主观、难以统一编码的规则，只保留 `通用、量化、可代码实现` 的过滤条件。

核心方向包括：

1. `合规异常`
   - ST / *ST
   - 审计意见异常

2. `持续经营`
   - 扣非归母净利润连续恶化
   - 主业经营下台阶

3. `现金流质量`
   - 经营现金流长期弱于利润
   - 累计现金转化率过低

4. `资产负债结构`
   - 资产负债率过高
   - 短债压力过大

5. `流动性`
   - 总市值过小
   - 日均成交额过低

6. `重大处罚 / 异常事件`
   - 首版不纳入自动过滤
   - 留到第二阶段个股分析处理

### 10.2 综合评分维度建议

首版综合评分最终收敛为 4 个一级维度：

1. `业务质量`
   - 毛利率
   - 近 3 年平均 ROE
   - 近 3 年平均净利率
   - 行业相对地位代理指标

2. `成长兑现度`
   - 近 3 年营收复合增速
   - 近 3 年扣非归母净利润复合增速
   - 近 3 年股东回报率

3. `财务质量`
   - 现金流质量
   - 资产负债结构
   - 资本回报稳定性

4. `估值匹配度`
   - PE
   - PB
   - 近 3 年平均股息率

说明：

- 首版不再单独设置 `风险与可跟踪性` 作为一级评分维度
- 复杂风险放到第二阶段个股分析中处理
- 首版只在自动筛选阶段保留通用量化风险过滤与预警标签

## 11. 产品迭代建议

### 11.1 标准版先做的事

标准版优先形成最小闭环：

1. 股票池筛选
2. 清单管理
3. 单股分析
4. 报告生成
5. 结论回写

### 11.2 后续增强方向

后续可迭代增强：

- 模板数量扩充
- 港股数据接入增强
- 评分权重可配置
- 历史回测式复盘
- 报告模板细分
- 行业看板和关键变量监控

## 12. 当前阶段的最终结论

当前关于选股工具的讨论，已经形成以下明确共识：

1. 第一阶段做本地分析工具，不做自动化平台
2. 先聚焦 A 股，港股结构预留
3. 以基本面分析为主，输出结论和评分
4. 核心闭环是“筛选 - 分析 - 报告 - 回写”
5. 股票池筛选必须按类型拆模板，不能只有一套规则
6. 采用“硬条件过滤 + 综合评分排序”的方法
7. 通过 5 只真实样本股的复盘，已经明确：
   - 该工具筛选的不是“最便宜的股票”
   - 而是“值得持续跟踪、可验证、可等待买点、风险能说清”的股票

## 13. 后续建议

下一步最适合继续推进的内容是：

1. 把第一阶段 `硬过滤规则` 细化成字段级定义
2. 把 4 个一级评分维度细化成字段级定义与计算口径
3. 明确清单字段设计，定义哪些结论需要回写
4. 在此基础上再拆实现计划

## 14. 可执行筛选规则（第一版）

本节目标是把前面的讨论，从“方向正确”推进到“可以实际落表执行”的层面。

第一版规则不追求一次覆盖全部行业，而是先解决一个更关键的问题：

`什么股票值得进入长期跟踪体系`

换句话说，筛选规则的目标不是找“今天最便宜的股票”，而是找：

- 生意能看懂
- 财报能验证
- 未来 2-4 个季度有验证点
- 风险能够被持续跟踪
- 即使暂时不买，也值得继续研究

### 14.1 一级分池结构

第一版建议只保留 2 个池：

1. `重点观察池`
   - 基本面强
   - 核心逻辑清晰
   - 未来验证点明确
   - 当前估值与风险状态相对可接受

2. `观察池`
   - 公司值得持续跟踪
   - 但当前估值、节奏或关键变量尚未合适
   - 包含原本需要单独分开的争议型、低估修复型、高估值等待型等股票

说明：

- 原 `核心候选池` 统一更名为 `重点观察池`
- 原 `观察池`、`争议跟踪池`、`低估修复池` 统一并入新的 `观察池`
- 差异不再通过额外池子表达，而是通过 `风险标签`、`当前状态标签`、`结论摘要` 来表达

### 14.2 通用硬过滤条件

先做通用剔除，再进入统一评分。

第一版硬过滤只保留`通用、量化、可代码实现`的规则，不直接判断复杂个股风险。

#### 14.2.1 合规异常

1. `ST / *ST`
   - 直接剔除

2. `审计意见 = 无法表示意见 / 否定意见`
   - 直接剔除

3. `审计意见 = 保留意见`
   - 不直接剔除
   - 标记 `人工复核`

4. `审计意见 = 标准无保留意见`
   - 通过

#### 14.2.2 持续经营

1. `最近 3 年里有 2 年扣非归母净利润为负`
   - 直接剔除

2. `最近 3 年里有 2 年扣非归母净利润同比下滑`
   - 直接剔除

#### 14.2.3 现金流质量

1. `最近 3 年中有 2 年经营现金流净额 < 扣非归母净利润`
   - 标记 `现金流偏弱`

2. `最近 3 年累计现金转化率 < 0.6`
   - 直接剔除

其中：

`近 3 年累计现金转化率 = 近 3 年经营现金流净额 / 近 3 年扣非归母净利润`

#### 14.2.4 资产负债结构

1. 使用 `最新财报口径`

2. `资产负债率 > 70%`
   - 直接剔除

3. `货币资金 / 一年内到期有息负债 < 1`
   - 标记 `短债压力预警`

#### 14.2.5 流动性

1. `总市值 < 30 亿元`
   - 直接剔除

2. `近 20 个交易日日均成交额 < 3000 万元`
   - 直接剔除

#### 14.2.6 重大处罚 / 异常事件

- 首版不纳入自动过滤
- 保留到第二阶段个股分析中处理

### 14.3 综合评分框架

第一版采用：`100 分制`

先通过硬过滤，再做 4 个一级维度评分。

#### 14.3.1 一级维度总权重

| 一级维度 | 权重 |
| --- | --- |
| 业务质量 | 30% |
| 成长兑现度 | 25% |
| 财务质量 | 25% |
| 估值匹配度 | 20% |

#### 14.3.2 业务质量

业务质量优先奖励“生意结构本身就好”的公司，而不是优先奖励已经站在聚光灯下的行业强者。

二级指标如下：

1. `毛利率`
   - 使用行业分位数打分

2. `近 3 年平均 ROE`
   - 使用行业分位数打分

3. `近 3 年平均净利率`
   - 使用行业分位数打分

4. `行业相对地位代理指标`
   - 营收行业分位数 `40%`
   - 扣非净利润行业分位数 `40%`
   - 总市值行业分位数 `20%`

内部权重如下：

| 二级指标 | 权重 |
| --- | --- |
| 毛利率 | 30% |
| 近 3 年平均 ROE | 25% |
| 近 3 年平均净利率 | 25% |
| 行业相对地位代理指标 | 20% |

#### 14.3.3 成长兑现度

成长兑现度优先看“增长有没有真正兑现到利润与股东回报上”。

二级指标如下：

1. `近 3 年营收复合增速`
   - 使用行业分位数打分

2. `近 3 年扣非归母净利润复合增速`
   - 使用行业分位数打分

3. `近 3 年股东回报率`
   - 使用行业分位数打分

其中：

`近 3 年股东回报率 = (近 3 年分红 + 回购) / 近 3 年归母净利润`

内部权重如下：

| 二级指标 | 权重 |
| --- | --- |
| 近 3 年营收复合增速 | 30% |
| 近 3 年扣非归母净利润复合增速 | 40% |
| 近 3 年股东回报率 | 30% |

#### 14.3.4 财务质量

财务质量优先看“利润能不能变成现金、财务结构是否稳、资本回报是否长期靠谱”。

二级指标如下：

1. `现金流质量`
   - 指标：`近 3 年累计现金转化率`
   - 打分：行业分位数

2. `资产负债结构`
   - 指标：`最新财报资产负债率`
   - 打分：行业分位数

3. `资本回报稳定性`
   - `近 3 年平均 ROE 行业分位数` `60%`
   - `相对行业 ROE 波动优势分位数` `40%`

其中：

- 个股近 3 年 ROE 波动值 = 近 3 年 ROE 标准差
- 行业 ROE 波动基准 = 同行业个股近 3 年 ROE 标准差的中位数
- 相对行业 ROE 波动优势 = 行业 ROE 波动基准 - 个股 ROE 波动值

内部权重如下：

| 二级指标 | 权重 |
| --- | --- |
| 现金流质量 | 40% |
| 资产负债结构 | 25% |
| 资本回报稳定性 | 35% |

#### 14.3.5 估值匹配度

估值匹配度不是单纯找“最便宜”的股票，而是看当前估值与盈利、净资产、现金回报是否匹配。

二级指标如下：

1. `PE`
   - 使用行业分位数打分

2. `PB`
   - 使用行业分位数打分

3. `近 3 年平均股息率`
   - 使用行业分位数打分

内部权重如下：

| 二级指标 | 权重 |
| --- | --- |
| PE | 40% |
| PB | 30% |
| 近 3 年平均股息率 | 30% |

### 14.4 统一口径与异常值处理

#### 14.4.1 行业口径

- 所有行业分位数统一使用 `申万一级行业`

#### 14.4.2 异常值处理

首版采用严格版：

- 关键指标 `无意义 / 不可用 / 无法计算`
  - 该项记最低分
  - 同时打上异常标签

示例：

- `PE <= 0`
  - `PE` 记最低分
  - 标签：`pe_invalid`

- `PB <= 0`
  - `PB` 记最低分
  - 标签：`pb_invalid`

- 分母 `<= 0` 导致比率无法计算
  - 对应指标记最低分
  - 标签：`metric_invalid`

- 分红 / 回购数据缺失
  - 对应指标记最低分
  - 标签：`data_missing`

### 14.5 分池规则

1. `总分 >= 80`
   - 进入 `重点观察池`

2. `总分 < 80`
   - 进入 `观察池`

### 14.6 展示规则

1. `重点观察池`
   - 按总分从高到低排序
   - 默认展示：
     - 总分
     - 业务质量
     - 成长兑现度
     - 财务质量
     - 估值匹配度
     - 申万一级行业标签
     - 行业综合评分排名

2. `观察池`
   - 按总分从高到低排序
   - 默认展示：
     - 总分
     - 业务质量
     - 成长兑现度
     - 财务质量
     - 估值匹配度
     - 申万一级行业标签
     - 行业综合评分排名

3. `行业相关展示`
   - 结果页支持按 `申万一级行业` 切换页签
   - 行业页签至少包含：
     - `全部`
     - 各 `申万一级行业`
   - 行业排名基于 `该行业全部股票` 计算，而不是只基于通过硬过滤后的股票
   - 行业排名默认展示为：`名次 + 总数`
     - 示例：`行业排名 3/48`
   - 行业页签进入后，只显示 `当前池子` 的股票
   - 在 `当前池子 + 当前行业页签` 内，默认仍按 `总分从高到低` 排序

### 14.7 字段级定义（第一版）

第一版字段设计采用：

`一股一行，保存当前最新结果`

这样做的目的不是一开始就把历史版本、快照、宽表拆表全部做完，而是先保证：

- 当前结果可查询
- 评分逻辑可追溯
- 展示层可直接读取
- 后续可以平滑扩展到历史快照

#### 14.7.1 设计原则

1. `ts_code` 作为系统内部统一主键
   - 存标准化代码
   - 展示层如有需要，再单独格式化成更友好的代码样式

2. 所有分数字段统一采用：
   - `decimal(5,2)` 或 `decimal(6,2)`
   - 分值范围默认为 `0-100`

3. 原始值字段与得分字段分开存储
   - 原始值字段用于保留真实计算结果
   - 得分字段用于保留行业分位数后的结果

4. 首版保留最小可追溯计算过程
   - 既能解释总分来源
   - 又不把结构做得过重

#### 14.7.2 基础标识字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `ts_code` | 股票唯一代码 | `varchar(32)` | 标准化证券代码，例如 `601899.SH`、`002772.SZ`、`09633.HK` | 作为主键使用 |
| `stock_name` | 股票名称 | `varchar(64)` | 当前证券简称 | 名称变更时按最新值更新 |
| `market` | 市场类型 | `varchar(16)` | 例如 `A股`、`港股` | 首版用于区分数据源与展示口径 |
| `sw_level1_industry` | 申万一级行业 | `varchar(64)` | 统一使用申万一级行业 | 行业分位数计算基于该字段 |
| `list_status` | 上市状态 | `varchar(16)` | 当前上市状态 | 可用于辅助排除退市、暂停等异常标的 |
| `latest_report_period` | 最新财报期 | `varchar(16)` | 当前使用的最新财报报告期，例如 `2026Q1`、`2025FY` | 用于解释评分时点 |

#### 14.7.3 池子结果字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `current_pool` | 当前所属池子 | `varchar(16)` | 可选值：`重点观察池` / `观察池` | 由总分阈值规则生成 |
| `total_score` | 最终总分 | `decimal(5,2)` | 四个一级维度按总权重加总，范围 `0-100` | 用于池子划分与排序 |
| `industry_rank` | 行业内综合评分排名 | `int` | 基于所属申万一级行业全部股票的综合评分排名 | 展示时与 `industry_total` 拼接 |
| `industry_total` | 行业内股票总数 | `int` | 所属申万一级行业股票总数 | 例如 `48` |
| `global_rank` | 全市场综合评分排名 | `int` | 当前市场范围内按总分排序得到 | 用于全市场比较 |

#### 14.7.4 一级维度分数字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `biz_quality_score` | 业务质量分 | `decimal(5,2)` | 业务质量内部二级指标加权汇总 | 范围 `0-100` |
| `growth_delivery_score` | 成长兑现度分 | `decimal(5,2)` | 成长兑现度内部二级指标加权汇总 | 范围 `0-100` |
| `financial_quality_score` | 财务质量分 | `decimal(5,2)` | 财务质量内部二级指标加权汇总 | 范围 `0-100` |
| `valuation_fit_score` | 估值匹配度分 | `decimal(5,2)` | 估值匹配度内部二级指标加权汇总 | 范围 `0-100` |

#### 14.7.5 二级指标原始值字段

**业务质量**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `gross_margin_avg_3y` | 近 3 年平均毛利率 | `decimal(8,4)` | 最近 3 个完整年度毛利率均值 | 原始值保留，不直接截断到分数 |
| `roe_avg_3y` | 近 3 年平均 ROE | `decimal(8,4)` | 最近 3 个完整年度 ROE 均值 | 用于行业分位数评分 |
| `net_margin_avg_3y` | 近 3 年平均净利率 | `decimal(8,4)` | 最近 3 个完整年度净利率均值 | 用于行业分位数评分 |
| `industry_position_score_raw` | 行业相对地位原始合成值 | `decimal(5,2)` | `revenue_pct_in_industry * 0.4 + nonrec_np_pct_in_industry * 0.4 + market_cap_pct_in_industry * 0.2` | 为行业相对地位的原始综合值 |
| `revenue_pct_in_industry` | 营收行业分位数 | `decimal(5,2)` | 最近一期营收在所属申万一级行业中的分位数 | 范围 `0-100` |
| `nonrec_np_pct_in_industry` | 扣非净利润行业分位数 | `decimal(5,2)` | 最近一期扣非归母净利润在行业中的分位数 | 范围 `0-100` |
| `market_cap_pct_in_industry` | 总市值行业分位数 | `decimal(5,2)` | 当前总市值在行业中的分位数 | 范围 `0-100` |

**成长兑现度**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `revenue_cagr_3y` | 近 3 年营收复合增速 | `decimal(8,4)` | 最近 3 年营收 CAGR | 用于行业分位数评分 |
| `nonrec_np_cagr_3y` | 近 3 年扣非归母净利润复合增速 | `decimal(8,4)` | 最近 3 年扣非归母净利润 CAGR | 若分母或起点无意义，记异常 |
| `shareholder_return_ratio_3y` | 近 3 年股东回报率 | `decimal(8,4)` | `(近3年分红 + 近3年回购) / 近3年归母净利润` | 若分母 `<= 0`，该项按异常处理 |
| `dividend_sum_3y` | 近 3 年现金分红合计 | `decimal(18,2)` | 最近 3 年现金分红金额求和 | 单位保持与财务口径一致 |
| `buyback_sum_3y` | 近 3 年回购金额合计 | `decimal(18,2)` | 最近 3 年股份回购金额求和 | 缺失时打 `data_missing` |
| `parent_np_sum_3y` | 近 3 年归母净利润合计 | `decimal(18,2)` | 最近 3 年归母净利润求和 | 用于股东回报率分母 |

**财务质量**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `cash_conversion_ratio_3y` | 近 3 年累计现金转化率 | `decimal(8,4)` | `近3年经营现金流净额 / 近3年扣非归母净利润` | 对应硬过滤阈值 `< 0.6` |
| `asset_liability_ratio_latest` | 最新财报资产负债率 | `decimal(8,4)` | 使用最新财报口径 | 对应硬过滤阈值 `> 70%` |
| `capital_return_stability_score_raw` | 资本回报稳定性原始合成值 | `decimal(5,2)` | 由 `近3年平均ROE` 的行业分位数与 `相对行业ROE波动优势` 的分位数按 `60% / 40%` 合成 | 用于后续得分落地 |
| `roe_std_3y` | 个股近 3 年 ROE 波动值 | `decimal(8,4)` | 最近 3 年 ROE 标准差 | 用于稳定性计算 |
| `industry_roe_std_median_3y` | 行业近 3 年 ROE 波动中位数 | `decimal(8,4)` | 所属申万一级行业全部股票 `roe_std_3y` 的中位数 | 行业稳定性基准 |
| `roe_stability_gap` | 相对行业 ROE 波动优势 | `decimal(8,4)` | `industry_roe_std_median_3y - roe_std_3y` | 大于 0 表示更稳 |

**估值匹配度**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `pe_ttm` | 市盈率 TTM | `decimal(10,4)` | 当前 TTM PE | `<= 0` 记异常最低分 |
| `pb_latest` | 最新 PB | `decimal(10,4)` | 当前 PB | `<= 0` 记异常最低分 |
| `dividend_yield_avg_3y` | 近 3 年平均股息率 | `decimal(8,4)` | 最近 3 年股息率均值 | 用于行业分位数评分 |

#### 14.7.6 二级指标得分字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `gross_margin_score` | 毛利率得分 | `decimal(5,2)` | `gross_margin_avg_3y` 的行业分位数得分 | 范围 `0-100` |
| `roe_score` | ROE 得分 | `decimal(5,2)` | `roe_avg_3y` 的行业分位数得分 | 范围 `0-100` |
| `net_margin_score` | 净利率得分 | `decimal(5,2)` | `net_margin_avg_3y` 的行业分位数得分 | 范围 `0-100` |
| `industry_position_score` | 行业相对地位得分 | `decimal(5,2)` | `industry_position_score_raw` 归一后的得分 | 范围 `0-100` |
| `revenue_cagr_score` | 营收复合增速得分 | `decimal(5,2)` | `revenue_cagr_3y` 的行业分位数得分 | 范围 `0-100` |
| `nonrec_np_cagr_score` | 扣非净利润复合增速得分 | `decimal(5,2)` | `nonrec_np_cagr_3y` 的行业分位数得分 | 范围 `0-100` |
| `shareholder_return_score` | 股东回报得分 | `decimal(5,2)` | `shareholder_return_ratio_3y` 的行业分位数得分 | 范围 `0-100` |
| `cash_conversion_score` | 现金转化率得分 | `decimal(5,2)` | `cash_conversion_ratio_3y` 的行业分位数得分 | 范围 `0-100` |
| `asset_liability_score` | 资产负债结构得分 | `decimal(5,2)` | `asset_liability_ratio_latest` 的行业分位数得分 | 范围 `0-100` |
| `capital_return_stability_score` | 资本回报稳定性得分 | `decimal(5,2)` | 由 `近3年平均ROE行业分位数 60% + 相对行业ROE波动优势分位数 40%` 计算 | 范围 `0-100` |
| `pe_score` | PE 得分 | `decimal(5,2)` | `pe_ttm` 的行业分位数得分 | `PE <= 0` 记最低分 |
| `pb_score` | PB 得分 | `decimal(5,2)` | `pb_latest` 的行业分位数得分 | `PB <= 0` 记最低分 |
| `dividend_yield_score` | 股息率得分 | `decimal(5,2)` | `dividend_yield_avg_3y` 的行业分位数得分 | 范围 `0-100` |

#### 14.7.7 异常与提示字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `manual_review_required` | 是否需要人工复核 | `boolean` | 命中保留意见审计等人工复核条件时为真 | 首版作为人工介入开关 |
| `is_filtered` | 是否被硬过滤剔除 | `boolean` | 命中任一硬过滤规则时为真 | `true` 时 `total_score` 置空 |
| `filter_reasons` | 硬过滤命中原因 | `json` | 例如 `["st_flag", "negative_nonrec_np_2of3y"]` | 用于展示具体过滤原因 |
| `cashflow_warning` | 现金流偏弱预警 | `boolean` | 最近 3 年中有 2 年 `经营现金流净额 < 扣非归母净利润` | 对应预警项 |
| `short_debt_warning` | 短债压力预警 | `boolean` | `货币资金 / 一年内到期有息负债 < 1` | 对应预警项 |
| `pe_invalid` | PE 无效标记 | `boolean` | `pe_ttm <= 0` 时为真 | 该项记最低分 |
| `pb_invalid` | PB 无效标记 | `boolean` | `pb_latest <= 0` 时为真 | 该项记最低分 |
| `data_missing` | 关键数据缺失标记 | `boolean` | 分红、回购、利润等关键字段缺失时为真 | 该项记最低分并打标签 |
| `warning_tags` | 预警标签汇总 | `json` | 例如 `["manual_review", "cashflow_warning", "short_debt_warning"]` | 用于展示与日志输出 |

#### 14.7.8 计算过程字段

为了保证后续排查、验证和解释分数来源，首版额外保存最小可追溯计算过程。

**二级指标加权结果字段**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `gross_margin_weighted_score` | 毛利率加权分 | `decimal(6,2)` | `gross_margin_score * 业务质量内权重30%` | 对一级维度贡献值 |
| `roe_weighted_score` | ROE 加权分 | `decimal(6,2)` | `roe_score * 业务质量内权重25%` | 对一级维度贡献值 |
| `net_margin_weighted_score` | 净利率加权分 | `decimal(6,2)` | `net_margin_score * 业务质量内权重25%` | 对一级维度贡献值 |
| `industry_position_weighted_score` | 行业相对地位加权分 | `decimal(6,2)` | `industry_position_score * 业务质量内权重20%` | 对一级维度贡献值 |
| `revenue_cagr_weighted_score` | 营收复合增速加权分 | `decimal(6,2)` | `revenue_cagr_score * 成长兑现度内权重30%` | 对一级维度贡献值 |
| `nonrec_np_cagr_weighted_score` | 扣非净利润复合增速加权分 | `decimal(6,2)` | `nonrec_np_cagr_score * 成长兑现度内权重40%` | 对一级维度贡献值 |
| `shareholder_return_weighted_score` | 股东回报加权分 | `decimal(6,2)` | `shareholder_return_score * 成长兑现度内权重30%` | 对一级维度贡献值 |
| `cash_conversion_weighted_score` | 现金转化率加权分 | `decimal(6,2)` | `cash_conversion_score * 财务质量内权重40%` | 对一级维度贡献值 |
| `asset_liability_weighted_score` | 资产负债结构加权分 | `decimal(6,2)` | `asset_liability_score * 财务质量内权重25%` | 对一级维度贡献值 |
| `capital_return_stability_weighted_score` | 资本回报稳定性加权分 | `decimal(6,2)` | `capital_return_stability_score * 财务质量内权重35%` | 对一级维度贡献值 |
| `pe_weighted_score` | PE 加权分 | `decimal(6,2)` | `pe_score * 估值匹配度内权重40%` | 对一级维度贡献值 |
| `pb_weighted_score` | PB 加权分 | `decimal(6,2)` | `pb_score * 估值匹配度内权重30%` | 对一级维度贡献值 |
| `dividend_yield_weighted_score` | 股息率加权分 | `decimal(6,2)` | `dividend_yield_score * 估值匹配度内权重30%` | 对一级维度贡献值 |

**一级维度加权结果字段**

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `biz_quality_weighted_score` | 业务质量总贡献分 | `decimal(6,2)` | `biz_quality_score * 一级维度权重30%` | 对总分贡献值 |
| `growth_delivery_weighted_score` | 成长兑现度总贡献分 | `decimal(6,2)` | `growth_delivery_score * 一级维度权重25%` | 对总分贡献值 |
| `financial_quality_weighted_score` | 财务质量总贡献分 | `decimal(6,2)` | `financial_quality_score * 一级维度权重25%` | 对总分贡献值 |
| `valuation_fit_weighted_score` | 估值匹配度总贡献分 | `decimal(6,2)` | `valuation_fit_score * 一级维度权重20%` | 对总分贡献值 |

#### 14.7.9 版本与时间字段

| 字段名 | 中文含义 | 类型 | 计算口径 | 备注 / 异常处理 |
| --- | --- | --- | --- | --- |
| `rule_version` | 规则版本 | `varchar(16)` | 本次评分使用的规则版本，例如 `v1.0` | 用于区分不同评分体系 |
| `data_version` | 数据口径版本 | `varchar(64)` | 本次评分使用的数据版本，例如 `2026Q1+2025FY+market_20260729` | 用于回溯结果来源 |
| `updated_at` | 记录更新时间 | `datetime` | 当前记录最后一次更新时间 | 行级更新时间 |
| `scored_at` | 评分完成时间 | `datetime` | 本次评分实际计算完成时间 | 用于区分写入时间与计算时间 |

### 14.8 首版数据表结构

基于当前字段定义，首版数据库不采用“全部字段塞进一张表”的方案，也不采用一开始就高度归一化的复杂方案。

首版采用：

`标准分层方案`

目标是同时满足 3 件事：

1. 首版开发足够直接，能尽快跑通闭环
2. 当前评分结果、规则版本、评分任务来源可回溯
3. 后续扩展历史快照、报告系统和页面交互时，不需要推倒重来

#### 14.8.1 首版 5 张核心表

1. `stocks_master`
   - 股票基础主档表
   - 存低频变化、可复用的基础信息

2. `stock_latest_scores`
   - 当前最新评分结果宽表
   - 一股一行
   - 首版最核心的结果表

3. `scoring_runs`
   - 每次评分任务运行记录表
   - 用于回溯本次结果由哪次跑分生成

4. `rule_versions`
   - 评分规则版本定义表
   - 用于保存规则快照，避免规则迭代后结果失去解释依据

5. `report_writebacks`
   - 单股人工分析回写结果表
   - 保存需要从分析报告回写到清单的核心结论

#### 14.8.2 表间关系

首版关系主线如下：

`stocks_master -> stock_latest_scores -> scoring_runs -> rule_versions`

同时保留一条人工分析回写链路：

`stocks_master -> report_writebacks`

具体关系说明：

- `stocks_master.ts_code = stock_latest_scores.ts_code`
- `stock_latest_scores.run_id = scoring_runs.run_id`
- `scoring_runs.rule_version = rule_versions.rule_version`
- `stocks_master.ts_code = report_writebacks.ts_code`

#### 14.8.3 表一：stocks_master

定位：

`股票基础主档表，只放低频变化、通用复用的基础信息`

主键：

- `ts_code`

核心字段：

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `ts_code` | `varchar(32)` | 主键，统一证券代码 |
| `stock_name` | `varchar(64)` | 股票名称 |
| `market` | `varchar(16)` | 市场类型，如 `A股`、`港股` |
| `sw_level1_industry` | `varchar(64)` | 申万一级行业 |
| `list_status` | `varchar(16)` | 上市状态 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

设计约定：

- `sw_level1_industry` 直接存储在主档表中
- `stock_name`、`sw_level1_industry`、`list_status` 等字段允许被最新数据覆盖更新

#### 14.8.4 表二：stock_latest_scores

定位：

`每只股票当前最新评分结果宽表`

主键：

- `ts_code`

关联字段：

- `run_id`

设计约定：

- 表中存在的一行，就是该股票的当前最新结果
- 首版不增加 `is_active` 之类的状态字段
- 为了提高结果页读取效率，冗余存储部分基础展示字段

字段分组：

1. `主键与关联字段`
   - `ts_code`
   - `run_id`

2. `基础展示冗余字段`
   - `stock_name`
   - `market`
   - `sw_level1_industry`

3. `池子结果字段`
   - `current_pool`
   - `total_score`
   - `industry_rank`
   - `industry_total`
   - `global_rank`

4. `一级维度分数字段`
   - `biz_quality_score`
   - `growth_delivery_score`
   - `financial_quality_score`
   - `valuation_fit_score`

5. `二级指标原始值字段`
   - 对应 `14.7.5`

6. `二级指标得分字段`
   - 对应 `14.7.6`

7. `异常与提示字段`
   - 对应 `14.7.7`

8. `计算过程字段`
   - 对应 `14.7.8`

9. `版本与时间字段`
   - `rule_version`
   - `data_version`
   - `updated_at`
   - `scored_at`

补充约定：

- 被硬过滤剔除的股票，仍然写入 `stock_latest_scores`
- 此时写入：
  - `is_filtered = true`
  - `filter_reasons`
  - `total_score = null`

#### 14.8.5 表三：scoring_runs

定位：

`每次评分任务的运行记录表`

主键：

- `run_id`

主键形式：

- 使用 `UUID / 字符串`

核心字段：

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | `varchar(64)` | 主键，评分任务唯一标识 |
| `rule_version` | `varchar(16)` | 本次任务使用的规则版本 |
| `data_version` | `varchar(64)` | 本次任务使用的数据口径版本 |
| `run_status` | `varchar(16)` | 运行状态 |
| `total_stocks` | `int` | 本次参与评分的股票总数 |
| `passed_filter_count` | `int` | 通过硬过滤的股票数 |
| `key_watch_count` | `int` | 进入重点观察池的股票数 |
| `watch_count` | `int` | 进入观察池的股票数 |
| `started_at` | `datetime` | 任务开始时间 |
| `finished_at` | `datetime` | 任务结束时间 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

状态枚举：

- `running`
- `success`
- `failed`

#### 14.8.6 表四：rule_versions

定位：

`评分规则版本定义表`

主键：

- `rule_version`

核心字段：

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `rule_version` | `varchar(16)` | 主键，规则版本号，如 `v1.0` |
| `rule_name` | `varchar(64)` | 规则名称 |
| `rule_snapshot` | `json` | 规则快照 |
| `is_active` | `boolean` | 是否为当前默认启用版本 |
| `created_at` | `datetime` | 创建时间 |
| `updated_at` | `datetime` | 更新时间 |

规则快照内容建议至少包含：

- 硬过滤条件
- 一级维度权重
- 二级指标权重
- 分池阈值
- 异常值处理规则

#### 14.8.7 表五：report_writebacks

定位：

`单股人工分析回写结果表`

更新策略：

- `一股一行，覆盖更新`

主键：

- `ts_code`

核心字段：

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `ts_code` | `varchar(32)` | 主键，对应股票代码 |
| `latest_view` | `text` | 最新总体判断 |
| `current_focus` | `text` | 当前关注点 |
| `action_tag` | `varchar(16)` | 当前动作标签 |
| `target_note` | `text` | 目标价、建仓区间或跟踪备注 |
| `source_report_path` | `varchar(255)` | 回写结论来源报告路径 |
| `updated_at` | `datetime` | 更新时间 |

`action_tag` 首版枚举：

- `重点跟踪`
- `继续观察`
- `等待买点`
- `暂不跟踪`

#### 14.8.8 首版建表优先级

首版优先级建议如下：

1. `必须先做`
   - `stocks_master`
   - `stock_latest_scores`

2. `建议首版一起做`
   - `scoring_runs`
   - `rule_versions`

3. `为分析闭环提前留口`
   - `report_writebacks`

原因是：

- `stocks_master + stock_latest_scores` 决定系统能不能先完成“筛选结果落库与展示”
- `scoring_runs + rule_versions` 决定结果能不能解释和回溯
- `report_writebacks` 决定后面“分析 -> 回写”的闭环能否顺利接上

### 14.9 首版评分脚本执行流程

首版评分脚本采用：

`全量重算 + 先批量拉齐数据 + 再统一计算 + 最后统一批量 upsert`

这样做的原因是：

- 全市场排名和行业分位数需要基于同一批数据
- 首版先追求逻辑清晰和结果稳定
- 不把增量更新、边算边写的复杂度提前引入

#### 14.9.1 执行模式

- 每次评分任务都对全市场候选股票执行一轮完整重算
- 不采用增量重算
- 不采用边算边展示

#### 14.9.2 执行主流程

1. `创建 scoring_run`
   - 脚本启动后立即生成 `run_id`
   - 在 `scoring_runs` 插入一条记录
   - 初始状态：
     - `run_status = running`
     - 写入 `rule_version`
     - 写入 `data_version`
     - 写入 `started_at`

2. `更新股票主档`
   - 全量拉取基础主档数据
   - 对 `stocks_master` 执行全量 `upsert`
   - 保证股票名称、行业、上市状态等基础信息同步到最新

3. `批量准备评分数据`
   - 首版最少准备以下 5 类数据：
     - `基础主档数据`
     - `财报数据`
     - `行情估值数据`
     - `分红 / 回购数据`
     - `行业映射数据`
   - 所有数据准备完成后，再进入统一计算阶段

4. `执行硬过滤`
   - 先对全市场候选股票执行硬过滤规则
   - 这一阶段先做剔除，不先计算全部评分

5. `处理被过滤股票`
   - 被硬过滤剔除的股票，仍写入 `stock_latest_scores`
   - 写入内容包括：
     - `is_filtered = true`
     - `filter_reasons`
     - `total_score = null`
   - 含义是：
     - 已参与本轮筛选
     - 但未进入评分阶段

6. `计算通过硬过滤股票的评分结果`
   - 对通过硬过滤的股票，按以下顺序计算：
     1. 二级指标原始值
     2. 行业分位数得分
     3. 一级维度分
     4. `total_score`

7. `统一计算排名`
   - 在全部通过样本的 `total_score` 计算完成后，再统一计算：
     - `global_rank`
     - `industry_rank`
     - `industry_total`

8. `划分池子`
   - 按分池规则执行：
     - `total_score >= 80` -> `重点观察池`
     - `total_score < 80` -> `观察池`

9. `统一批量写入结果表`
   - 本轮全部股票结果计算完成后
   - 统一批量 `upsert` 到 `stock_latest_scores`
   - 不采用边算边写

10. `收尾更新 scoring_runs`
   - 仅当 `stock_latest_scores` 成功写入后，才更新：
     - `passed_filter_count`
     - `key_watch_count`
     - `watch_count`
     - `finished_at`
     - `run_status = success`

#### 14.9.3 首版关键约定

1. `执行模式`
   - 采用 `全量重算`

2. `数据准备方式`
   - 采用 `先批量拉齐数据，再统一计算`

3. `结果写入方式`
   - 采用 `统一批量 upsert`

4. `成功判定`
   - 不是“算完就成功”
   - 而是“结果成功落库后，才更新本次任务为 success”

### 14.10 SQL 建表草案（PostgreSQL）

首版 SQL 草案统一按 `PostgreSQL` 方言编写。

类型约定：

- `json` 统一使用 `jsonb`
- 时间字段统一使用 `timestamptz`
- 小数字段统一使用 `numeric`

说明：

- 以下 SQL 以“首版可建库、可落表、可支撑脚本运行”为目标
- 先优先保证主键、外键、基础约束和字段完整性
- 更细的索引策略放到下一步单独讨论

#### 14.10.1 rule_versions

```sql
CREATE TABLE rule_versions (
    rule_version        varchar(16) PRIMARY KEY,
    rule_name           varchar(64) NOT NULL,
    rule_snapshot       jsonb NOT NULL,
    is_active           boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
```

#### 14.10.2 stocks_master

```sql
CREATE TABLE stocks_master (
    ts_code             varchar(32) PRIMARY KEY,
    stock_name          varchar(64) NOT NULL,
    market              varchar(16) NOT NULL,
    sw_level1_industry  varchar(64) NOT NULL,
    list_status         varchar(16) NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
```

#### 14.10.3 scoring_runs

```sql
CREATE TABLE scoring_runs (
    run_id                  varchar(64) PRIMARY KEY,
    rule_version            varchar(16) NOT NULL REFERENCES rule_versions(rule_version),
    data_version            varchar(64) NOT NULL,
    run_status              varchar(16) NOT NULL,
    total_stocks            integer,
    passed_filter_count     integer,
    key_watch_count         integer,
    watch_count             integer,
    started_at              timestamptz NOT NULL,
    finished_at             timestamptz,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_scoring_runs_status
        CHECK (run_status IN ('running', 'success', 'failed'))
);
```

#### 14.10.4 stock_latest_scores

```sql
CREATE TABLE stock_latest_scores (
    ts_code                                      varchar(32) PRIMARY KEY
                                                 REFERENCES stocks_master(ts_code),
    run_id                                       varchar(64) NOT NULL
                                                 REFERENCES scoring_runs(run_id),

    stock_name                                   varchar(64) NOT NULL,
    market                                       varchar(16) NOT NULL,
    sw_level1_industry                           varchar(64) NOT NULL,

    current_pool                                 varchar(16),
    total_score                                  numeric(5,2),
    industry_rank                                integer,
    industry_total                               integer,
    global_rank                                  integer,

    biz_quality_score                            numeric(5,2),
    growth_delivery_score                        numeric(5,2),
    financial_quality_score                      numeric(5,2),
    valuation_fit_score                          numeric(5,2),

    gross_margin_avg_3y                          numeric(8,4),
    roe_avg_3y                                   numeric(8,4),
    net_margin_avg_3y                            numeric(8,4),
    industry_position_score_raw                  numeric(5,2),
    revenue_pct_in_industry                      numeric(5,2),
    nonrec_np_pct_in_industry                    numeric(5,2),
    market_cap_pct_in_industry                   numeric(5,2),

    revenue_cagr_3y                              numeric(8,4),
    nonrec_np_cagr_3y                            numeric(8,4),
    shareholder_return_ratio_3y                  numeric(8,4),
    dividend_sum_3y                              numeric(18,2),
    buyback_sum_3y                               numeric(18,2),
    parent_np_sum_3y                             numeric(18,2),

    cash_conversion_ratio_3y                     numeric(8,4),
    asset_liability_ratio_latest                 numeric(8,4),
    capital_return_stability_score_raw           numeric(5,2),
    roe_std_3y                                   numeric(8,4),
    industry_roe_std_median_3y                   numeric(8,4),
    roe_stability_gap                            numeric(8,4),

    pe_ttm                                       numeric(10,4),
    pb_latest                                    numeric(10,4),
    dividend_yield_avg_3y                        numeric(8,4),

    gross_margin_score                           numeric(5,2),
    roe_score                                    numeric(5,2),
    net_margin_score                             numeric(5,2),
    industry_position_score                      numeric(5,2),
    revenue_cagr_score                           numeric(5,2),
    nonrec_np_cagr_score                         numeric(5,2),
    shareholder_return_score                     numeric(5,2),
    cash_conversion_score                        numeric(5,2),
    asset_liability_score                        numeric(5,2),
    capital_return_stability_score               numeric(5,2),
    pe_score                                     numeric(5,2),
    pb_score                                     numeric(5,2),
    dividend_yield_score                         numeric(5,2),

    manual_review_required                       boolean NOT NULL DEFAULT false,
    is_filtered                                  boolean NOT NULL DEFAULT false,
    filter_reasons                               jsonb NOT NULL DEFAULT '[]'::jsonb,
    cashflow_warning                             boolean NOT NULL DEFAULT false,
    short_debt_warning                           boolean NOT NULL DEFAULT false,
    pe_invalid                                   boolean NOT NULL DEFAULT false,
    pb_invalid                                   boolean NOT NULL DEFAULT false,
    data_missing                                 boolean NOT NULL DEFAULT false,
    warning_tags                                 jsonb NOT NULL DEFAULT '[]'::jsonb,

    gross_margin_weighted_score                  numeric(6,2),
    roe_weighted_score                           numeric(6,2),
    net_margin_weighted_score                    numeric(6,2),
    industry_position_weighted_score             numeric(6,2),
    revenue_cagr_weighted_score                  numeric(6,2),
    nonrec_np_cagr_weighted_score                numeric(6,2),
    shareholder_return_weighted_score            numeric(6,2),
    cash_conversion_weighted_score               numeric(6,2),
    asset_liability_weighted_score               numeric(6,2),
    capital_return_stability_weighted_score      numeric(6,2),
    pe_weighted_score                            numeric(6,2),
    pb_weighted_score                            numeric(6,2),
    dividend_yield_weighted_score                numeric(6,2),

    biz_quality_weighted_score                   numeric(6,2),
    growth_delivery_weighted_score               numeric(6,2),
    financial_quality_weighted_score             numeric(6,2),
    valuation_fit_weighted_score                 numeric(6,2),

    rule_version                                 varchar(16) NOT NULL
                                                 REFERENCES rule_versions(rule_version),
    data_version                                 varchar(64) NOT NULL,
    updated_at                                   timestamptz NOT NULL DEFAULT now(),
    scored_at                                    timestamptz NOT NULL,

    CONSTRAINT chk_stock_latest_scores_pool
        CHECK (
            current_pool IS NULL
            OR current_pool IN ('重点观察池', '观察池')
        ),
    CONSTRAINT chk_stock_latest_scores_total_score
        CHECK (
            total_score IS NULL
            OR (total_score >= 0 AND total_score <= 100)
        ),
    CONSTRAINT chk_stock_latest_scores_dimension_scores
        CHECK (
            (biz_quality_score IS NULL OR (biz_quality_score >= 0 AND biz_quality_score <= 100))
            AND (growth_delivery_score IS NULL OR (growth_delivery_score >= 0 AND growth_delivery_score <= 100))
            AND (financial_quality_score IS NULL OR (financial_quality_score >= 0 AND financial_quality_score <= 100))
            AND (valuation_fit_score IS NULL OR (valuation_fit_score >= 0 AND valuation_fit_score <= 100))
        )
);
```

#### 14.10.5 report_writebacks

```sql
CREATE TABLE report_writebacks (
    ts_code              varchar(32) PRIMARY KEY
                         REFERENCES stocks_master(ts_code),
    latest_view          text,
    current_focus        text,
    action_tag           varchar(16) NOT NULL,
    target_note          text,
    source_report_path   varchar(255),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_report_writebacks_action_tag
        CHECK (action_tag IN ('重点跟踪', '继续观察', '等待买点', '暂不跟踪'))
);
```

#### 14.10.6 建表顺序建议

为了避免外键依赖问题，首版建议按以下顺序执行：

1. `rule_versions`
2. `stocks_master`
3. `scoring_runs`
4. `stock_latest_scores`
5. `report_writebacks`

## 15. 五只样本股票的规则演练

本节不是做严谨量化回测，而是做第一版规则演练，验证规则是否能合理解释这 5 只股票为何值得跟踪，以及为什么不应该被简单归入同一类。

### 15.1 样本演练总表

| 股票 | 硬过滤是否通过 | 基础判断 | 当前关注点 | 建议归属 |
| --- | --- | --- | --- | --- |
| 紫金矿业 | 通过 | 高质量周期成长 | 量价兑现、分红托底、资源组合成长 | 重点观察池 |
| 农夫山泉 | 通过 | 高质量消费龙头 | 公司质量强，但当前估值偏高 | 观察池 |
| 众兴菌业 | 通过 | 小盘低估修复型公司 | 主业可跟踪，但小盘折价与波动仍需观察 | 观察池 |
| 携程集团 | 通过 | 平台龙头 | 监管整改后利润率与议价权如何重定价 | 观察池 |
| 泡泡玛特 | 通过 | 高成长 IP 平台 | 核心 IP 热度与海外复制持续性 | 观察池 |

### 15.2 样本细分判断

#### 紫金矿业

1. `为什么通过筛选`
   - 资源品主引擎清晰，金铜是核心收入与利润来源
   - 财报兑现能力强
   - 扩产、并购、锂板块推进等变量可跟踪
   - 分红与现金流具备一定托底能力

2. `为什么进入重点观察池`
   - 核心不是“便宜”
   - 而是“量价兑现 + 分红托底 + 资源组合成长”

3. `规则启发`
   - 周期股只要量价兑现与股东回报清晰，也能进入重点观察体系

#### 农夫山泉

1. `为什么通过筛选`
   - 品牌力、渠道力、盈利能力都强
   - 茶饮已经成为第二增长曲线
   - 业务结构从“卖水”升级到“水 + 饮料双引擎”

2. `为什么先放观察池`
   - 公司质量强不等于当前买点合适
   - 高估值会压缩未来收益空间

3. `规则启发`
   - 好公司和好价格必须分开判断

#### 众兴菌业

1. `为什么通过筛选`
   - 主业能看懂
   - 财报修复有数据支撑
   - 双孢菇与金针菇经营情况可跟踪
   - 分红能力相对稳定

2. `为什么先留在观察池`
   - 小盘、波动、流动性、治理折价不能忽略
   - 新故事（冬虫夏草）尚未成为利润主引擎
   - 近期季度利润波动说明稳定性仍待验证

3. `规则启发`
   - 低估修复型公司可以先进入观察池，后续再靠总分和标签排序

#### 携程集团

1. `为什么通过筛选`
   - 平台型龙头，盈利能力和国际化布局都较强
   - 行业地位高，基本面研究价值很强

2. `为什么先留在观察池`
   - 反垄断处罚本身不是唯一问题
   - 更关键的是整改后利润率与议价权会不会重定价

3. `规则启发`
   - 平台股在首版工具中先靠通用规则入池，复杂监管变量留到第二阶段分析

#### 泡泡玛特

1. `为什么通过筛选`
   - 商业模式稀缺
   - 2025 年财报极强
   - 全球扩张与多 IP 运营具备平台潜力

2. `为什么先放观察池`
   - Labubu 等核心 IP 的热度持续性仍需验证
   - 海外增长能否持续复制仍是重点观察变量

3. `规则启发`
   - 高成长 IP 公司先靠通用规则入池，再在第二阶段跟踪“增长集中度”

### 15.3 样本反推出来的真正筛选标准

通过这 5 只股票可以进一步确认：

值得被筛选出来的股票，并不是：

- 当前最便宜
- 当前涨得最快
- 当前市场情绪最好

而是：

1. `有明确主引擎`
2. `财报能验证逻辑`
3. `未来 2-4 个季度有关键验证点`
4. `风险来源清楚且可跟踪`
5. `即使现在不买，也值得继续观察`

## 16. 本轮设计推进后的结论

到这里，第一版设计已经把“选股规则”从抽象原则推进到了可执行层：

1. 明确了 2 类分池结构
2. 明确了 6 类通用硬过滤条件
3. 明确了 4 个一级评分维度及其总权重
4. 明确了每个一级维度下的二级指标、内部权重与统一口径
5. 明确了异常值处理、分池阈值与展示规则
6. 明确了字段级定义、异常标签、计算过程字段、版本与时间字段
7. 明确了首版 5 张核心表、表间关系、评分脚本执行流程与 PostgreSQL 建表草案
8. 用 5 只真实样本股验证了分池逻辑的合理性

下一步最适合继续推进的内容是：

1. 明确分析报告中哪些结论需要回写到清单
2. 基于当前字段结构拆结果页、详情页和筛选交互
3. 设计索引、唯一约束和初始化数据脚本
4. 基于当前设计开始首版数据库建表与评分脚本实现
