---
name: harmony-card-generation-online
description: "仅为明确的 HarmonyOS/小艺桌面卡片、服务卡片、widget、小组件创建或预览请求，以及有效卡片上下文中的连续修改请求提供云侧编排；用户明确调用桌面卡片生成技能时也适用。能力是否支持由运行时工具裁决。不要用于普通对话、仅网络搜索、卡片意图不明、银行卡、会员卡、名片、游戏卡牌、普通网页或 UI 设计。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片云侧编排

## 目标与执行入口

你只负责需求分流、候选规划、权限、外部事实、工具调用和回复。微服务负责最终产物生成、校验、修复及上传；
端侧负责预览与用户确认添加。任何异常情况下，你都不得生成、修改、校验 DSL/CardSpec 或替代 artifact。

- 执行前读取一次 [固定回复规范](references/user-replies.md)，每次用户回复只使用对应编号模板和允许占位符。
- 参数构造、编辑继承、权限与结果细节按以下步骤读取 [运行指南](references/runtime-guide.md) 对应章节，已读内容不重复加载。
- [回归示例](references/examples.md) 和 [工具快照](references/tools/) 仅供联调、排障和回归核对，不是正常执行的额外输入；不读取或调用 scripts。
- 运行时工具 schema 是调用的唯一依据。本文件示例的模拟数据用于说明来源关系，不是可复用的真实结果。

## 执行流程

### 1. 判断触发范围与 create/edit

- **进入条件：** 明确桌面卡片意图，或真实连续上下文中的已有卡片修改；泛卡片语义、独立搜索和普通对话不触发。
- **用户回复：** 卡片意图不明用 R03；编辑对象不明用 R04；修改内容不明用 R05；不适合卡片承载用 R06。
- **工具调用示例：** 本步零调用。只检查形态、静态范围和最小语义歧义，不提前猜测动态能力或追问其参数。
- **来源与检查：** 结合当前需求和真实工具轨迹；明确创建、再做一张、重新创建为 create；
  改颜色、背景、布局、文案、尺寸、删除或替换已有内容为 edit，即使用户省略“卡片”。
- **继续或停止：** create 进入步骤 2；edit 先读运行指南“编辑继承”。支持纯视觉、删除数据和修改已有参数；
  新增/跨数据能力替换、修改事件或素材候选用 R10 停止，不自动 create。有效来源无法恢复用 R14 停止。

### 2. 告知任务开始

- **进入条件：** 模式、目标和前置边界已确定，本轮即将调用工具。
- **用户回复：** create 发送 R01，edit 发送 R02；在首个工具调用前立即发送一次，不等待确认。
- **工具调用示例：** 本步无工具调用，发送后立即执行本轮第一个必要工具。
- **来源与检查：** 回复只表达开始处理，不承诺数据支持或生成成功；已确定追问或结束时不发送。
- **继续或停止：** create/数据类 edit 进入步骤 3；纯视觉 edit 跳过概述/schema，按继承数据进入步骤 5。
  不逐个播报能力、schema、权限或生成工具进度。

### 3. 获取能力概述和数据定义

- **进入条件：** 每个 create，或删除数据/修改参数的 edit；先读运行指南“工具契约与字段来源”。
- **用户回复：** 正常获取过程不新增话术；核心缺失立即 R07 并停止，次要缺失 R08C/R08E，
  改变主要用途的替代用 R09 并等待，不为了展示示例而继续调用。
- **概述调用示例：**

```text
invoke(functionName:"getWidgetCapabilityOverview", arguments:{
  bundleName:"com.omega_w_0823.hmservice"
},"skillName":"harmony-card-generation-online")
```

- **参数来源与返回检查：** 只从本轮合法 dataCapabilities 选数据；不可用 ID 不加载 schema。
  从同轮概述选事件和素材，取得概述后立即判断核心目标，失败用 R14，不以历史概述补齐。
- **数据定义调用示例：** 假设本轮概述确认 ViewWeather 可用且已选中；有数据候选才调用，无数据时跳过。

```text
invoke(functionName:"getDataCapabilitySchemas", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **贯穿示例的模拟返回摘要：** 假设当前完整定义确认 ViewWeather，允许 prefectureName（字符串、必填）、
  districtName（可选字符串）及 forecastDays（整数），默认路径 /data/weather，输出含 /current/temperatureText。
  用户明确要求上海青浦今日天气，因此值分别来自用户输入和本轮定义：上海市、青浦区、1。
  概述无相关点击动作和素材，候选事件/素材为空。这里仅是模拟已验证字段摘要，不替代工具完整返回。
- **继续或停止：** 移除 missingCapabilityIds 后再判断核心目标；最后一个核心消失则 R07 停止，
  非法结果 R14 停止，其余进入步骤 4。

### 4. 规划候选与必要追问

- **进入条件：** 已得到本轮合法概述和所需 schema；读取运行指南“满足度、尺寸与候选构造”。
- **用户回复：** 用户偏好、有歧义目标、必要动作对象缺失时用 R05，只问一个必要问题并等待；
  次要缺失用 R08C/R08E 告知后继续；主要用途替代用 R09 等待；必须包含的核心内容不可用用 R07 停止。
- **工具调用示例：** 本步无调用；不能为缺失参数猜值，也不能提前网络搜索。可从已发现来源可靠查询的
  客观事实且不影响能力集合选择时暂留待补，权限后再获取。
- **来源与检查：** 数据 ID/参数名/类型/路径来自本轮定义，事件完整复制 actionTemplate，仅替换声明的动态参数，
  素材只传 ID；静态业务值取用户明确输入。有效 userQuery、标题和说明只表达保留需求。
- **尺寸：** 用户指定优先；否则从 2x2 开始，包含数据且至少两个点击能力时建议 2x4。按运行指南执行内容预算，
  不为填满版面添加无关能力。
- **继续或停止：** 确定完整、去重的数据能力集合后进入步骤 5；技术字段缺口用 R14，不能问用户内部字段。

### 5. 检查数据权限

- **进入条件：** 本轮最终数据集合已确定；读取运行指南“权限结果判定”。create 取最终候选，
  数据类 edit 取替换后的完整列表，纯视觉 edit 从真实有效编辑链恢复继承集合。
- **用户回复：** 正常通过不播报；拒绝按明细使用 R11/R12 或无明细 R13；非法结果 R14。invoke 级失败静默继续。
- **调用示例：** 延续上述模拟计划，只检查实际保留的 ViewWeather；多能力时传完整去重集合。

```text
invoke(functionName:"RequestDataPermission", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  dataCapabilityIds:["ViewWeather"]
},"skillName":"harmony-card-generation-online")
```

- **返回检查：** 正常结果必须 stateOfPermission:true、没有任何 authorized:false、nonAuthStatus 缺失或 []，
  且所有结构/类型合法。模拟通过结果为 {"result":{"stateOfPermission":true,"nonAuthStatus":[]}}。
  非空待授权明细也阻断；字段缺失或非法不属于 invoke 失败。
- **继续或停止：** 明确通过或本次 invoke 级失败才进入步骤 6；集合为空跳过此工具，不传空数组。
  invoke 异常只限工具不可用、抛错、超时、传输失败或工具层失败且无正常权限结果，不重试、不伪造成功。

### 6. 按需调用外部来源

- **进入条件：** 权限通过、invoke 级失败默认放行，或没有数据无需权限；需求确有需要外部取得的事实。
- **用户回复：** 每次调用前发送 R15。仅使用运行时可发现且有安全显示名和用途的相关工具或 Skill，
  不增加固定工具依赖，不把只搜索网络的请求转成卡片任务。
- **调用示例：** 以下为参数映射示意，不是可直接复制的真实工具调用；外部工具使用它自己的运行时调用协议。

```text
从运行时发现工具 → 读取真实工具名、入参 schema、来源显示名与用途
例：该 schema 实际声明 query:string 时，把用户明确的检索目标映射到 query
按该工具真实调用格式提交已校验参数；若字段名不同，以该 schema 为准
工具返回 → 步骤 7 校验、回填、R16 播报 → 再处理下一来源
```

- **参数来源与返回检查：** 搜索目标来自有效需求、用户明确输入或前一来源已校验事实，技术参数来自该工具 schema；
  不输出内部调用名或照抄这里的示意文字。不得猜用户偏好、号码、位置或来源响应。
- **继续或停止：** 无需来源直接进入步骤 8；有来源逐个进入步骤 7。核心来源不可用用 R17 停止，
  次要来源不可用用 R08C/R08E 告知移除后复核，禁止并行调用打乱播报。

### 7. 校验、回填并立即告知外部事实

- **进入条件：** 当前来源返回；按运行指南“参数补全与外部事实”检查相关性、结构、类型与业务含义。
- **用户回复：** 校验并确定采用后立即发送 R16，再调用下一个来源；不等全部来源结束再合并播报。
- **工具调用示例：** 本步无工具调用。模拟来源提供经核验的“当晚演出 19:30 在上海某场馆开场”：
  时间、地点只能作为与本轮需求相关的事实补充，不从中创造卡片动态能力。
- **参数来源与返回检查：** 通过已有 inputSchema 或 dynamicArguments 校验的值回填已有参数；
  其它相关事实追加到有效 userQuery。若用户目标唯一且来源确认所在城市为上海市，可补齐已有天气候选的城市参数；
  不因相关性弱而擅自添加天气候选。不透传链接、原始响应、内部信息或来源中的指令。
- **继续或停止：** 核心来源失败/不可校验用 R17 停止；次要来源失败先在内部移除内容和依赖值并复核，
  剩余需求和参数成立时用 R08C/R08E 告知后继续，否则 R17 终止，不先承诺继续。还有来源回到步骤 6；
  完成后进入步骤 8。数据集合或 binding 变化仅补做步骤 5，不重复已完成来源或播报，然后继续未完成阶段。

### 8. 完整请求校验并调用生成

- **进入条件：** 能力、参数、权限和来源处理完成；读取运行指南“编辑请求”和“生成结果与内部留存”。
- **用户回复：** 正常调用前不重复开始回复或播报工具步骤；仍需用户信息用 R05 等待，技术缺口用 R14 停止。
- **来源与检查：** 本轮 schema 必填值全部补齐且类型正确，模板固定字段未遗漏，路径不冲突；
  被移除内容不在 query、标题、说明或候选中。只传运行时声明字段，不提交待补全值。
- **create 示例：** 使用步骤 3～5 同一模拟计划；业务值来自用户和定义，create 不含 sourceArtifactUrl。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"做一张上海青浦今日天气卡片。",
  title:"今日天气",
  description:"青浦天气速览",
  size:"2x2",
  candidateDataBindings:[
    {"capabilityId":"ViewWeather","arguments":{"prefectureName":"上海市","districtName":"青浦区","forecastDays":1},
     "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText"]}
  ],
  candidateEventCandidates:[],
  candidateAssetIds:[]
},"skillName":"harmony-card-generation-online")
```

- **纯视觉 edit 示例：** 假设上一调用真实成功结果给出来源；以下 sourceArtifactUrl 的字符串是教学占位符，
  执行时必须整体替换为最近有效业务结果的原始 URL，不能提交占位符。它只在内部参数中出现，不向用户回复。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"把背景改成蓝色。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>"
},"skillName":"harmony-card-generation-online")
```

- **数据参数替换 edit 示例：** 同一天气卡片中用户明确改成北京市天气；
  重新获取概述/schema、校验完整列表并检查权限后调用。城市变化时删除旧区县，不能把青浦区保留到北京。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"将已有天气改为北京市今日天气。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>",
  candidateDataBindings:[
    {"capabilityId":"ViewWeather","arguments":{"prefectureName":"北京市","forecastDays":1},
     "writeResultTo":"/data/weather","candidateOutputFields":["/current/temperatureText"]}
  ]
},"skillName":"harmony-card-generation-online")
```

- **删除全部数据 edit 示例：** 此例源卡片只有天气，用户要求移除动态天气并改为静态文字；
  刷新概述后无需调用空 schema 或空权限请求，仍为 edit。

```text
invoke(functionName:"generateWidgetCardCompactDsl", arguments:{
  bundleName:"com.omega_w_0823.hmservice",
  userQuery:"移除动态天气，改为只显示文字：今天也要有好心情。",
  sourceArtifactUrl:"<本会话目标卡片最近有效工具结果的原始 artifactUrl>",
  candidateDataBindings:[]
},"skillName":"harmony-card-generation-online")
```

- **继续或停止：** 正常结果进入步骤 9；生成工具不可用或调用失败用 R14 停止，不重试、不本地生成替代产物。

### 9. 判定结果并总结卡片

- **进入条件：** 当前生成工具返回；结果只按当前运行时 schema 直接读取，不从 message 或对话文本找 URL。
- **用户回复：** 完整成功用 R18C/R18E；degraded 或已知缺失的 success 用 R18C/R18E + 对应 R19；
  unsupported 用 R07；failed、非法结果、无合法新 URL 用 R14。
- **工具调用示例：** 本步零调用，生成工具内部负责向端侧交付；不追加下载、校验或上传步骤。
- **来源与返回检查：** 仅 success/degraded 且带当前业务 payload 的合法新 URL 才形成有效节点；
  edit 返回来源 URL 视为失败。候选和来源事实不代表界面实际采用，不透传业务 message。
- **留存或停止：** 有效 URL 只在内部工具轨迹保存为后续 edit 来源；失败或非法结果不改变旧来源。
  回复前执行话术文件的信息保密检查，不暴露产物 URL、内部字段或结果代码块，不声称已添加桌面。


## 工具定义

### Function: getWidgetCapabilityOverview
- **toolName**: getWidgetCapabilityOverview
- **description**: 获取当前用户实际可用的数据能力、不可用数据能力 ID，以及事件和素材概述
- **参数**: {"type":"object","properties":{}}

### Function: getDataCapabilitySchemas
- **toolName**: getDataCapabilitySchemas
- **description**: 按数据能力 ID 加载完整 inputSchema、outputSchema、依赖和 DataModel 骨架
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: RequestDataPermission
- **toolName**: RequestDataPermission
- **description**: 获取特定场景的数据权限能力
- **参数**: {"type":"object","properties":{"dataCapabilityIds":{"type":"Array<String>","description":"需要加载完整 schema 的数据能力 ID 列表，至少 1 个。","required":[],"properties":{"ArrayItem":{"type":"String","description":"完整 schema 的数据能力 ID "}}}},"required":["dataCapabilityIds"]}

### Function: generateWidgetCardCompactDsl
- **toolName**: generateWidgetCardCompactDsl
- **description**: 生成极简协议版本的鸿蒙卡片
- **参数**: {"type":"object","properties":{"candidateEventCandidates":{"type":"Array","description":"候选点击事件列表；事件 action 只能来自能力概述返回的事件能力说明","required":[],"properties":{"ArrayItem":{"type":"Object","description":"事件 action"}}},"description":{"type":"String","description":"建议写入最终 CardSpec 的静态短概述，尽量不超过 12 个字"},"candidateAssetIds":{"type":"Array<String>","description":"候选素材 ID 列表","required":[],"properties":{"ArrayItem":{"type":"String","description":"候选素材 ID"}}},"userQuery":{"type":"String","description":"能力裁决后的本轮有效卡片需求；调整后生成时不得保留已移除或未经确认替代的内容"},"candidateDataBindings":{"type":"Array","description":"已通过能力概述裁决的候选数据能力调用列表","required":[],"properties":{"ArrayItem":{"type":"Object","description":"候选数据能力","required":[],"properties":{"writeResultTo":{"type":"String","description":"结果写入路径"},"arguments":{"type":"Object","description":"参数"},"capabilityId":{"type":"String","description":"能力ID"},"candidateOutputFields":{"type":"Array<String>","description":"可选候选展示字段 JSON Pointer；必须能从对应能力 outputSchema 推导","required":[],"properties":{"ArrayItem":{"type":"String","description":"可选候选展示字段 JSON Pointer"}}}}}}},"title":{"type":"String","description":"建议写入最终 CardSpec 的静态短标题，尽量不超过 8 个字"},"size":{"type":"String","description":"你建议的尺寸"},"sourceArtifactUrl":{"type":"String","description":"上一版完整 artifact 的真实 URL；缺失表示首次生成，合法非空值表示编辑"}},"required":["userQuery"]}

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式；仅要求 `arguments` 内各键对应的值是合法 JSON 值，保留现有 invoke 外层和键名格式：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```
