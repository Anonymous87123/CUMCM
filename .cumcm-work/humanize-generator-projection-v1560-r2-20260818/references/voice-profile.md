# 作者 Voice Profile 合同

## 目录

1. 目的与边界
2. 样本准入
3. 样本优先级
4. 建档流程
5. Profile 字段
6. 置信等级
7. 默认声线
8. 应用规则
9. 冲突与保护
10. 场景适配
11. 更新与版本
12. 验收清单
13. Profile 模板

## 1. 目的与边界

从作者已提供的真实写作样本中提取稳定的表达习惯，使 Humanize 后的文本保留作者自己的节奏，而不是被统一改成 Skill 的“标准自然腔”。

只学习以下风格维度：

- 句子长短和停顿位置；
- 段落疏密和重点展开方式；
- 常用但不过密的句首、回指和转场；
- 第一人称、无主句和对象主语的偏好；
- 解释、定义、举例、比较和收尾的方式；
- 标题、列表、括号、冒号和分号的使用习惯；
- 公式、图表和代码外叙述的密度；
- 正式程度、判断力度和限定方式。

不要从样本推断作者身份、性格、教育背景或学术能力。不要评价样本内容是否正确。不要把 Voice Profile 用于规避检测。

## 2. 样本准入

### 2.1 只纳入作者文本

只从标记为 `author` 的内容学习。排除：

- `quoted`：直接引语、法规原文、文献原句、访谈原话；
- `exam-original`：题干、题面、给定材料；
- `OCR`：乱码、识别不确定文本；
- `code`：代码、命令、日志和配置；
- `math`：公式和数学环境；
- 模板自带的固定标题、声明和格式样例；
- 多作者文档中无法确认归属的段落；
- 其他模型刚生成且未经作者改动的文本。

允许学习作者对公式、引语、题干和代码的外围叙述，但不要学习保护区内部形式。

### 2.2 要求最低样本量

使用以下样本等级：

| 可读作者正文 | 用法 |
|---|---|
| 少于 300 个汉字 | 不建立个人 Profile；使用场景默认声线 |
| 300 至 999 个汉字 | 建立低置信临时 Profile；只采用显著习惯 |
| 1000 至 4999 个汉字 | 建立中置信 Profile；应用句法、节奏和语气习惯 |
| 5000 个汉字及以上，且覆盖至少 3 个完整文本单元 | 建立高置信 Profile；允许建立分场景子档案 |

不要把同一段复制多次来满足样本量。按规范化后的唯一作者段落计数。

### 2.3 处理样本冲突

若样本明显来自不同用途，先按 `COURSE / MODELING / RESEARCH / GENERAL` 分组。不要把课堂讲解中的轻提示强行迁移到期刊正文。若无法分组，降低置信等级并只保留跨样本稳定习惯。

## 3. 样本优先级

按以下顺序选择样本：

1. 用户明确指定为“这是我写的”的同场景文本；
2. 用户明确指定的其他场景作者文本；
3. 当前文档中可确认由作者亲写且未要求 Humanize 的章节；
4. 用户授权使用的历史作者文本；
5. 场景默认声线。

最新样本不自动压过旧样本。只有用户明确表示写作偏好已变化，或新样本数量足以显示稳定变化时，才更新 Profile。

## 4. 建档流程

按以下顺序建立 Profile：

1. 固定样本文件、范围和来源角色；
2. 去除保护区、重复段落和明显模板文本；
3. 按场景与文体功能分组；
4. 连续阅读完整段落，不只统计词频；
5. 提取候选习惯；
6. 检查候选习惯是否跨至少 3 个位置出现；
7. 区分“稳定偏好”“可选变体”和“偶发痕迹”；
8. 记录反例和不应模仿项；
9. 给出置信等级；
10. 用保留样本做一次盲对照；
11. 保存 Profile，并记录样本范围和版本。

不要把高频词直接等同于作者声线。把统计用于定位，再通过连续阅读确认其功能。

## 5. Profile 字段

### 5.1 基本信息

记录：

```yaml
profile_id:
version:
created_at:
sample_scope:
sample_scenes:
readable_author_chars:
unique_units:
confidence: LOW | MEDIUM | HIGH | DEFAULT
```

不要保存无关个人信息。路径只保留完成任务所需的本地定位。

### 5.2 节奏字段

描述而非只报均值：

- `sentence_rhythm`：短判断、普通说明和长句的实际组合；
- `paragraph_rhythm`：短段与展开段如何交替；
- `explanation_peaks`：作者通常在哪类位置放慢；
- `compression_zones`：作者通常在哪类位置略写；
- `pause_devices`：句号、分号、冒号、括号或独立短句的偏好；
- `closure_pattern`：作者常自然停在哪里，是否倾向显式小结。

使用“倾向、常见、偶尔、不常用”等描述。不要规定机械长度配额。

### 5.3 句法字段

记录：

- 常见主语位置：对象、动作、作者或无主句；
- 定义句、判断句、比较句和限定句的形态；
- 长句中从句的数量和排列习惯；
- 是否偏好先给现象、先给判断或先给条件；
- 是否使用问句、破折号式插入或括号补充；
- 并列项是否完整对称，还是常合并次要项；
- 公式前后如何回指，不学习公式本身。

### 5.4 语气字段

记录：

- 第一人称使用频率与功能；
- 判断力度：直接、克制、试探或条件化；
- 读者称呼和互动程度；
- 正式程度；
- 是否接受轻提示；
- 是否倾向管理、公文、说教、营销或答辩声线；
- 哪些错位腔调应删除，而不是模仿。

不要把样本中的明显 AI 套话登记为“作者习惯”后原样放大。将其列入 `do_not_amplify`。

### 5.5 衔接字段

记录：

- 段落靠对象延续、代词回指还是显式连接；
- 转折何时出现；
- 因果连接词的密度；
- 是否使用“这里、前式、上述结果”等局部回指；
- 哪些连接词真实常用；
- 哪些句壳虽出现过但不应跨段复制。

把单个常用词视为可选资源，不要设为每段必用模板。

### 5.6 版式字段

记录：

- 标题长短和名词化程度；
- 列表使用条件；
- 段落是否常带主题句；
- Markdown 加粗、引用和表格习惯；
- TeX 中 `\paragraph`、脚注、括号说明和图注叙述习惯；
- 中英文与数字之间的空格习惯；
- 中文标点偏好。

不要为了模仿版式破坏用户当前文件的格式约束。

### 5.7 词语字段

建立五类列表：

| 字段 | 用途 |
|---|---|
| `preferred` | 作者稳定使用且适合当前场景的表达 |
| `acceptable_variants` | 可交替使用但不必刻意轮换的表达 |
| `rare` | 作者很少使用，改写时谨慎引入 |
| `avoid` | 作者明确不喜欢或与声线明显冲突的表达 |
| `do_not_amplify` | 样本中偶见的模板词、口头禅或错位腔调 |

每个词项记录功能和适用场景。不要建立无条件的全局禁词表。

### 5.8 言语行为字段

记录作者如何完成以下行为：

- 命名或定义；
- 提出本节选择；
- 限定讨论范围；
- 比较两个对象；
- 报告结果或归属观察；
- 回指前文；
- 承认暂不展开；
- 引入公式或图表；
- 收束段落或章节。

改写时保留行为类型。不要把“称为”改成客观断言，不要把“本文只讨论”改成事实限制，不要把推测语气改成确定语气。

## 6. 置信等级

### 6.1 `LOW`

只应用至少出现 3 次且无明显反例的习惯。不要应用罕见词、标志性口头禅或复杂节奏推断。

### 6.2 `MEDIUM`

应用稳定句法、段落节奏、第一人称和衔接偏好。对场景迁移保持保守。

### 6.3 `HIGH`

允许使用分场景子档案和更细的段落节奏特征。仍不要复制整句、独特比喻或可识别片段。

### 6.4 `DEFAULT`

表示没有可用作者样本。只使用场景默认声线。必须在交付中披露：

```text
未提供足量、可归属于作者本人的写作样本；本次使用对应场景的默认声线，不声称复现作者个人文风。
```

## 7. 默认声线

样本不足时使用以下最小默认值：

| 场景 | 默认声线 |
|---|---|
| `COURSE` | 自然讲解、选择性展开、难点放慢、例行步骤简写 |
| `MODELING` | 务实直接、取舍可见、对象和结果靠前、设置不逐项旁白 |
| `RESEARCH` | 克制正式、论证有主次、避免答辩与宣传口吻、收尾不过度闭合 |
| `GENERAL` | 保留原文正式程度，只清除机械模板和均匀节奏 |

不要给默认声线添加虚构个人经历、随意口语或固定口头禅。

## 8. 应用规则

### 8.1 先锁定，再模仿

先锁定来源角色、用户保留项和字面不变量，再应用 Profile。不要为了复现作者节奏改动保护区。

### 8.2 复现分布，不复制片段

复现作者对长短句、段落疏密、转场和收尾的选择方式。不要复制样本中的完整句子、独特例子或连续短语。

### 8.3 保留变体

从 `preferred` 和 `acceptable_variants` 中按上下文选择。不要把作者最常见的一个句首铺满全文。

### 8.4 不放大缺陷

对 Profile 中的 `do_not_amplify` 执行以下规则：

- 样本偶见、目标文本高频时，降低密度；
- 样本高频但用户明确要求去除时，服从用户要求；
- 属于模板路标或错位腔调时，不以“保留作者风格”为理由保留；
- 不用另一个固定句壳批量替换。

### 8.5 允许 `NO_CHANGE`

若目标段已符合 Profile 且没有可定位的模板问题，标 `NO_CHANGE`。不要为了证明已使用 Profile 而制造改动。

## 9. 冲突与保护

按以下顺序裁决：

1. 用户明确保留要求；
2. 来源角色保护；
3. 模式与改写强度；
4. 同场景高置信 Profile；
5. 跨场景高置信 Profile；
6. 中低置信 Profile；
7. 场景默认声线。

使用以下固定动作：

| 冲突 | 动作 |
|---|---|
| Profile 喜欢长句，但 `LIGHT` 下句子已超载 | 只在原句内部调整，不拆段 |
| Profile 常用“本文”，但目标文本密集重复 | 保留承担真实指代者，改写或删除其余重复句壳 |
| Profile 常用对称列表，但目标全文已形成规则网格 | 保留局部习惯，打破跨章节复制 |
| Profile 与当前场景正式程度冲突 | 保留句法节奏，降低不合场景的腔调迁移 |
| 样本内部相互冲突 | 只采用跨样本稳定项；其余标为可选变体 |
| 保护区与 Profile 冲突 | 不编辑保护区 |

## 10. 场景适配

### 10.1 `COURSE`

优先学习：

- 难点如何放慢；
- 例题中哪些步骤省略；
- 提示语和回指的自然程度；
- 复盘时是否使用第一人称；
- 小结何时出现、何时直接结束。

不要把作者在课堂口语中的轻松表达迁移到正式研究正文。

### 10.2 `MODELING`

优先学习：

- 模型对象、设置、结果和选择的出场顺序；
- 工程取舍如何表达；
- 参数与步骤旁白的压缩程度；
- 图表前后叙述的密度；
- 子问题之间是否使用同构结构。

不要把项目管理词误当成作者个性后批量保留。

### 10.3 `RESEARCH`

优先学习：

- 研究主张出现的位置；
- 判断力度和限定方式；
- 讨论段如何维持主次；
- 第一人称与无主句的分工；
- 结论如何收束而不复述全文。

不要把审稿答辩腔、创新表演或过度防御登记为高质量作者声线。

### 10.4 `GENERAL`

优先保留原文已有正式程度和稳定句法。只应用跨场景稳定 Profile，不移植任何场景专属口吻。

## 11. 更新与版本

每次更新 Profile 时：

1. 保留原版本；
2. 记录新增样本范围；
3. 列出新增、删除和降级的字段；
4. 说明置信等级变化；
5. 用同一保留样本比较新旧版本；
6. 只在新版本减少偏离时启用；
7. 不因单篇新稿重写整个 Profile。

不要把 Humanize 后的输出自动回灌为作者样本。只有用户确认并实际采用的文本才能进入后续样本集。

## 12. 验收清单

逐项确认：

- [ ] 样本均可归属于作者本人；
- [ ] 引语、题干、OCR、代码和公式未进入学习语料；
- [ ] 重复段落未放大某个习惯；
- [ ] 至少记录一个反例或 `do_not_amplify` 项；
- [ ] 没有从样本推断身份或能力；
- [ ] 没有把内容判断写入 Profile；
- [ ] 没有复制作者样本中的完整独特句；
- [ ] 当前场景使用了对应子档案或明确回退；
- [ ] 样本不足时已披露默认声线；
- [ ] 改写结果保留了原有言语行为；
- [ ] Profile 没有成为新的固定模板；
- [ ] `NO_CHANGE` 段落未被无意义改动。

## 13. Profile 模板

使用以下模板保存可复用档案：

```yaml
profile_id: author-style-001
version: 1
sample_scope: []
sample_scenes: []
readable_author_chars: 0
unique_units: 0
confidence: DEFAULT

rhythm:
  sentence_rhythm: ""
  paragraph_rhythm: ""
  explanation_peaks: []
  compression_zones: []
  pause_devices: []
  closure_pattern: ""

syntax:
  subject_preference: ""
  definition_pattern: ""
  comparison_pattern: ""
  clause_pattern: ""
  formula_narration: ""

voice:
  first_person: ""
  assertion_strength: ""
  reader_address: ""
  formality: ""

transitions:
  preferred_functions: []
  object_continuity: ""
  overused_shells: []

layout:
  headings: ""
  lists: ""
  punctuation: ""
  tex_markdown: ""

lexicon:
  preferred: []
  acceptable_variants: []
  rare: []
  avoid: []
  do_not_amplify: []

speech_acts:
  naming: ""
  section_choice: ""
  scoping: ""
  comparison: ""
  reporting_observation: ""
  reference_back: ""
  omission: ""
  formula_table_introduction: ""
  closure: ""

scene_overrides:
  COURSE: {}
  MODELING: {}
  RESEARCH: {}
  GENERAL: {}

default_disclosure: true
```

## 14. v12 可执行工件合同

说明性 YAML 仍可供人工阅读，但生产链路只消费经过 builder 与独立 validator 校验的 JSON 工件。固定产物为：

- `voice_sample_manifest.json`（`humanize-voice-sample-manifest/v2`）：样本路径、canonical sample-spec hash、字节 hash、角色范围、去重簇、计数和排除审计；不保存整段样本文本；
- `voice_profile.json`：Profile 身份、置信度、策略绑定、可重建 feature、负控和默认披露；不保存可复制原句；
- validator JSON：schema、自哈希、manifest 绑定与重建状态。

Profile 顶层 schema 固定为 `humanize-voice-profile/v1`，至少包含：

```json
{
  "profile_id": "author-style-001",
  "version": 1,
  "revision": 1,
  "profile_kind": "PERSONAL",
  "validation_status": "PASS",
  "confidence": "MEDIUM",
  "sample_binding": {},
  "policy_binding": {},
  "features": [],
  "negative_controls": [],
  "defaults": {},
  "claims": {},
  "profile_sha256": "<64-lowercase-hex>"
}
```

`profile_sha256` 对移除自身字段后的 canonical JSON 计算。canonical 视图固定为 UTF-8、键排序、紧凑分隔符、禁止浮点数、NaN、Infinity、重复 key 和过深嵌套。它是本地完整性与版本身份，不是外部签名，也不证明作者身份。

### 14.1 sample spec

sample spec 固定为 `humanize-voice-sample-spec/v1`：

```json
{
  "schema_version": "humanize-voice-sample-spec/v1",
  "samples": [
    {
      "sample_id": "sample-01",
      "locator": "samples/chapter.md",
      "origin": "USER_CONFIRMED_AUTHOR",
      "scene": "RESEARCH",
      "complete_unit": true,
      "default_role": "author",
      "role_ranges": [
        {"byte_start": 120, "byte_end": 260, "role": "quoted"}
      ]
    }
  ]
}
```

`locator` 必须相对 `--allowed-root`，不得穿越根目录。角色范围使用原始 UTF-8 字节半开区间，必须有序、无重叠、落在文件长度内。允许角色只有 `author/quoted/exam-original/ocr/code/math/template/unknown`。`UNKNOWN` 与 `MODEL_GENERATED` 来源不进入学习；用户明确确认并实际采用的模型旧稿只能标为 `USER_CONFIRMED_ADOPTED`，仍不得伪称身份已验证。manifest v2 保存整个 strict JSON sample spec 的 canonical SHA-256；冻结 spec 的来源角色、场景、范围或文件定位被修改后，即使调用方重算 prepare 完整性清单，finalize 也必须因 spec/manifest 绑定不一致而失败。

即使调用方把全文件声明为 `author`，builder 仍自动剔除可确定的 Markdown/TeX 代码、数学、块引语、直接引语和模板结构。显式保护范围与自动保护冲突时，保护优先。无法安全解码、含控制字符或边界不确定的样本进入审计排除，不通过上下文补字。

### 14.2 去重与阈值

字数、unit 数和 feature 支持只统计去重代表单元。先做 NFC 与字母数字规范化的 exact dedup；对不少于 40 个规范字符的段落再用字符 5-gram 检查近重复。Jaccard 不低于 0.90，或短段对长段 containment 不低于 0.95 时建立近重复边；最终簇必须取全部 exact/near 边的连通分量，而不是按先读到的代表做贪心星形归并。代表内容、簇数、作者字数、完整单元数和置信等级不得随 sample spec 排序变化。去重视图只用于判断独立性，实际风格测量仍使用未压平标点和节奏的作者视图。

PERSONAL `validation_status=PASS` 还要求贡献证据的唯一场景等于 `binding_scene`。纯 COURSE 样本不能通过显式 `--scene RESEARCH` 重标为研究声线；混合或跨场景证据在当前单 Profile 工件中保持 `REVIEW`，直到有独立子档案与跨场景适配门。

置信门固定为：

- `<300`：`DEFAULT`；
- `300–999`：`LOW`；
- `1000–4999`：`MEDIUM`；
- `>=5000` 且至少 3 个去重完整文本单元：`HIGH`；
- `>=5000` 但完整单元少于 3：最高 `MEDIUM`。

同一段复制 30 次仍只计一个代表单元。字符总量不能替代逐 feature 证据；feature 至少跨 3 个去重分析单元，必须记录 opportunity、support、counterexample、位置 hash 和 feature-level confidence。无法机械重建的“论证主次”“解释峰值”“作者判断力”等语义候选不得以 `PASS` feature 发布，只能进入人工审阅材料。

### 14.3 DEFAULT 的强制语义

四个场景各自有独立、版本化、hash 不同的 DEFAULT。DEFAULT 必须满足：

- `profile_kind=DEFAULT`、`confidence=DEFAULT`、`features=[]`；
- `use_scene_default=true`；
- `disclosure_required=true`；
- `personal_voice_claim_allowed=false`；
- `validation_status=PASS` 仅表示安全回退工件有效，不表示个人声线有效。

未传 Profile 与显式传入 DEFAULT 都不得写成“已复现作者风格”。`AUTO` 长文由独立逐 unit 路由器选择 `GENERAL/COURSE/MODELING/RESEARCH`，同时物化四个 hash 不同的 DEFAULT Profile set；强歧义保持 `UNRESOLVED`，中性 unit 不得仅凭 document prior 越权继承。AUTO 暂不接受单一 supplied Profile，不能借一个 PERSONAL/DEFAULT 覆盖全部场景。

### 14.4 CLI 与退出状态

```powershell
python "$skillRoot\scripts\build_humanize_voice_profile.py" `
  --sample-spec voice_samples.spec.json `
  --allowed-root <workspace-root> `
  --profile-id author-style-001 `
  --scene AUTO `
  --manifest-out voice_sample_manifest.json `
  --output voice_profile.json `
  --format json

python "$skillRoot\scripts\validate_humanize_voice_profile.py" voice_profile.json `
  --manifest voice_sample_manifest.json `
  --sample-spec voice_samples.spec.json `
  --allowed-root <workspace-root> `
  --rebuild-evidence `
  --format json
```

退出码：`0=PASS`，`1=FAIL`，`2=REVIEW`。schema、自哈希、路径越界、角色范围伪造、manifest/Profile/spec 错配属于 `FAIL`；来源归属或模板边界不能可靠裁决时为 `REVIEW`。对 PERSONAL 或证据绑定 DEFAULT，只传 Profile、或只验证 manifest 而不执行 `--rebuild-evidence` 时，`profile_validation_status` 可以是 `PASS`，但顶层 `production_admission_status/status` 必须是 `REVIEW/2`；只有证据重建完成后才可生产准入。代码注册表产生的确定性零样本 DEFAULT 可直接 `PASS/0`，仍必须披露默认声线。

### 14.5 长文消费规则

prepare 不接受“只给路径、由工具自己猜当前版本”。显式单场景 supplied Profile 必须同时提供路径和调用方 pin 的 `profile_sha256`。PERSONAL 还必须提供 manifest、sample spec 与 allowed root；prepare 当场重建全部证据，只有 `voice_evidence_status=REBUILT_PASS` 才能冻结。builder 因不足 300 字或无合格来源而生成的证据绑定 DEFAULT 也必须携带同一组证据，状态为 `REBUILT_DEFAULT_PASS`；只有代码注册表生成、`manifest_sha256` 为零值的确定性场景 DEFAULT 才能不带样本证据。只有自哈希、没有可重建 manifest/spec 的 PERSONAL 或证据绑定 DEFAULT 工件必须拒绝。AUTO 只接受内部生成的四场景 DEFAULT Profile set；set 顶层、每个场景 entry 和 metadata binding 都使用精确字段闭集，claims 固定 `identity_verified=false/personal_voice_claim_allowed=false`，即使同时重算 set hash 与 prepare 封条也不得夹带权限声明。prepare 把经验证的单 Profile 或 Profile set 写入 run metadata、unit、chunk、ledger 和完整性封条。

rewrite bundle 不得自行提交 Profile 正文、ID 覆盖值或版本覆盖值；它只回显当前 chunk 已给出的 `unit_id`、`chunk_binding_sha256` 与 `voice_profile_sha256`。finalize 先重建 Profile 与 canonical chunk，再检查 bundle：

- 缺 hash：`voice_profile_hash_missing`；
- 非 64 位小写十六进制：`voice_profile_hash_invalid`；
- 与该 unit 的冻结值不同：`voice_profile_hash_mismatch`。

unit/chunk 绑定另有 `bundle_unit_id_missing/invalid/mismatch` 与 `chunk_binding_hash_missing/invalid/mismatch`。文件名只是查找入口，不是证据；把第一单元的 bundle 改名为第二单元文件，或把旧 run 的 bundle 搬到同 Profile 新 run，都不得进入正文 validator。

三种情况都在正文 validator 前拒绝该 bundle，并把 unit 留在 `UNRESOLVED`。bundle 使用 strict UTF-8 JSON：重复 key、浮点数、非有限数字或过深结构直接失败，不能让后一个正确 hash 覆盖前一个错误 hash。finalize 还必须核对 manifest v2 的 `sample_spec_sha256` 与冻结 spec；prepare 封条可以重算，不是替代这项来源绑定的信任根。`voice_binding_status=PASS` 仅表示所有可处理 unit 的最终 bundle 精确回显了冻结 hash。独立全文门再对 protected-masked before/after 执行注册特征非回退：DEFAULT 只证明场景默认策略与 unit validator 闭合，个人状态为 `NOT_APPLICABLE`；PERSONAL 至少需要 6 个目标正文块，要求当前 extractor hash 与 Profile 证据一致，PREFER 特征不显著回退，`DO_NOT_AMPLIFY` 负控不增加。该 PASS 仍只覆盖机械注册特征，`identity_verified=false`，不能写成完整作者气质复现。`humanize_completion_claim_allowed` 还必须等待跨 unit 门和 fresh second pass。

### 14.6 本地一致性与来源信任边界

Profile、manifest、sample spec、chunk 与 prepare 封条的 SHA-256 只在 `allowed-root` 和其中
样本字节被调用方视为可信输入时提供错配、局部篡改和旧工件重放保护。若同一主体能够同时
改写样本源文件、sample spec、manifest、Profile 及所有自哈希，本地 validator 只能确认新
工件彼此自洽，不能证明这些字节历史上属于某个真人作者，也不能恢复被替换前的可信版本。

因此 PERSONAL 即使生产准入 `PASS/0`，仍必须保持 `claims.identity_verified=false`；准确表述
是“已从调用方确认并提供的当前样本字节重建 Profile”，不得写“已验证作者身份”“来源不可
伪造”或“哈希证明这是本人原作”。若业务需要抵抗完整一致性替换，必须在本地工具之外引入
代理无法访问私钥的签名信任根，至少绑定样本根、每个源文件 hash、角色范围、场景、签发者、
时间和撤销状态。当前 builder、validator、prepare 与 finalize 均不生成或消费这种签名证明；
没有外部 receipt 时，不得把本地一致性门提升为来源身份门。
