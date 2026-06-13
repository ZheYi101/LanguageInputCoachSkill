# english-input-coach

一个把真实语言输入转成结构化学习环节的 agent skill。

它不是背单词软件，不是课程平台，也不是一套大而全的语言学习系统。它更像一份交给 agent 的工作说明书：当学习者已经看过、听过、读过一份英文材料后，agent 不要只做摘要和查词，而要基于这份真实输入带他学、带他练、接住错误，并把这轮学习状态留下来，供后续复习继续使用。

## 为什么做这个

这个项目来自一个很实际的需求：

- 输入材料最好来自自己本来就会看的内容，而不是硬换成教材
- 学习过程不能只停在“看懂了”，还得能被组织成可练、可纠错、可复习的环节
- 很多输入材料都带强语境，尤其是直播闲聊字幕；如果切得太碎，后面的讲解和输出就会失真
- 如果长期使用，agent 需要记得你之前学过什么、哪里老出错、哪些东西值得复习

所以这个 skill 的目标不是替代老师，而是把一部分“备课、组织材料、设计练习、纠错、总结本轮能力变化”的工作交给 agent。

## 适合谁

更适合：

- 已经有一定英语输入能力的人
- 平时本来就会看英文视频、字幕、文章的人
- 想围绕真实语境学表达，而不是只刷题或只背词的人
- 愿意长期在一个固定学习工作区里沉淀材料和记录的人

当前不太适合：

- 完全零基础学习者
- 还很难靠输入大致跟上内容的人
- 主要目标是标准化考试模板训练的人

## 当前支持的输入分轨

v1 只支持两条轨道，而且调用时必须显式指定：

- `live_chat`
  - 适合 Vtuber、直播闲聊、双人聊天、强口语字幕
  - 重点放在口语理解、语块复用、语气识别、场景输出
- `article_reading`
  - 适合英文文章、博客、解释型文本
  - 重点放在论点理解、词义落点、改写精度、结构化输出

## 输入怎么来

这个 skill 从“你已经拿到文本”开始工作。字幕下载、ASR、OCR 不在 v1 范围内。

当前比较自然的输入来源：

- YouTube / Bilibili 英文字幕
- 英文文章、博客、长帖
- 手动截取的一段高价值 transcript

如果是视频字幕，可以先用 [yt-dlp](https://github.com/yt-dlp/yt-dlp)：

```bash
yt-dlp --write-subs --write-auto-subs --sub-langs en --skip-download <video-url>
```

拿到 `.srt` 之后，不建议直接从原始字幕流开教。这个仓库当前的设计已经把“先清洗再教学”视为硬约束。

## 这份 skill 会做什么

每一轮 lesson 固定输出 6 段，避免退化成“解释很多，但不可练”：

1. `Scene Capsule`
2. `High-Value Chunks / Vocab`
3. `Comprehension Check`
4. `Error-Prone Rewrite`
5. `Contextual Output`
6. `Profile Delta + Review Candidates`

它的重点不是“把文本翻译给你”，而是把输入变成一轮真正能做的学习任务。

## 长期学习工作区

这个项目现在已经不是只面向一次性 prompt 了。当前设计支持在固定 `learning_root` 里长期学习。

采用的是混合存储：

- 文件系统保存原始材料、清洗文本、segments、lessons、answers、feedback
- SQLite 保存可查询状态，比如 `sources`、`segments`、`sessions`、`review_items`、`profile_events`
- JSON 保存工作区配置和当前学习者画像快照

这样做的原因很实际：

- 文本材料和 lesson 产物本来就适合按文件保存，便于人工查看和版本控制
- 复习状态、会话历史、画像证据更适合放进可查询状态层，而不是塞进一个越来越大的 profile 文件
- 学习者画像适合作为“可读快照”，但不适合做唯一事实来源

推荐目录结构见 [references/state-schema.md](references/state-schema.md)。

## 材料处理原则

这个 skill 现在明确要求：不同材料类型不能混着按同一套方式清洗和切分。

- `subtitle_transcript`
  - 先去掉字幕编号、时间戳、明显噪音
  - 保留互动场景
  - 按场景或互动单元做中等切分
- `spoken_transcript`
  - 尽量保留口语流和上下文
  - 不为了“整齐”把整段话切得七零八落
- `article`
  - 保留段落和论证结构
  - 按论点单元切分

当前默认偏向“中等切分”：

- 不直接把整场直播一股脑塞进一轮课
- 也不把材料拆到失去原场景

## 最小输入合同

最少要提供：

```json
{
  "input_type": "transcript",
  "track": "live_chat",
  "title": "VTuber opening segment",
  "text": "English text here"
}
```

可选字段：

```json
{
  "material_type": "subtitle_transcript",
  "learner_language": "zh-CN",
  "source_url": "https://example.com/video",
  "creator_or_channel": "Example Channel",
  "watched_or_read": true,
  "learning_root": "/path/to/learning-root"
}
```

## 最小使用方式

### 1. 一次性 lesson

```text
Use the english-input-coach skill.

input_type: transcript
track: live_chat
material_type: subtitle_transcript
title: VTuber opening segment
text:
[粘贴字幕或节选]

请先清洗文本，再按 skill 的六段结构带我学。
```

### 2. 长期工作区模式

```text
Use the english-input-coach skill.

learning_root: /path/to/learning-root
input_type: transcript
track: live_chat
material_type: subtitle_transcript
title: Demo livestream opening
text:
[粘贴原始字幕或清洗后的文本]

请先把材料入库。如果需要，先清洗和切分，再决定今天是新内容、复习优先还是混合模式。
```

### 3. 做完练习后继续纠错

```text
Use the english-input-coach skill.

这是我对上一轮 rewrite 和 contextual output 的回答：
[粘贴回答]

请直接纠错，并更新 Profile Delta + Review Candidates。
```

## 脚本层当前已经验证到哪一步

这份仓库目前还是草稿，但脚本层已经做过一轮本地自测。2026-06-13 在本地临时工作区里实际跑通过：

- `init-learning-root.py`
  - 能初始化 `learning_root`
  - 能创建 `.language-coach/`、`languages/` 和 `state.db`
- `write-sqlite-event.py`
  - 能按受控 JSON 操作写入 `sources`、`segments`、`sessions`、`review_items`、`profile_events`
- `rebuild-profile-snapshot.py`
  - 能从 `state.db` 重建 `learner_profile.json`
- `get-review-agenda.py`
  - 能按 `summary_first` 输出复习摘要
  - 能基于当前复习压力给出 `recommended_mode`
- `write-json-state.py`
  - 能安全覆写 JSON 文件
  - 覆写前会生成 `.bak`
- `migrate-learning-root.py`
  - 已做过基础迁移校验

这轮实际自测里，`get-review-agenda.py` 已经返回过类似结果：

```json
{
  "language": "en",
  "days_since_last_session": 0,
  "overdue_items": 1,
  "due_soon_items": 0,
  "focus_groups": [
    {
      "review_category": "live_chat_chunks",
      "count": 1,
      "max_priority": 9.5
    }
  ],
  "display_mode": "summary_first",
  "recommended_mode": "mixed"
}
```

这说明“长期工作区初始化 -> 写入状态 -> 重建画像 -> 拉取复习摘要”这条链路现在是能跑起来的。

## 一个真实的脚本调用样例

下面是当前 CLI 风格，不是伪代码：

```bash
python skills/english-input-coach/scripts/init-learning-root.py /path/to/learning-root
python skills/english-input-coach/scripts/get-review-agenda.py /path/to/learning-root/.language-coach/state.db --language en
```

`write-sqlite-event.py` 当前接收的是 JSON payload，不是 `--table` 这种参数式接口。也就是说，如果你以后要在 README 或别的文档里给示例，应该写成“传 JSON 操作”，而不是把它描述成 ORM 风格命令。

## 已验证，不等于已完全证明

当前可以说“已验证”的是：

- 工作区结构能落地
- 状态脚本确实能执行
- 复习摘要能从持久化数据读出来
- summary-first 这条 review 输出路线在脚本层成立

当前还不能说“已经充分证明”的是：

- lesson 质量在大量真实材料上都稳定
- 清洗和切分规则已经足够泛化
- 不同 agent 宿主都会稳定按同一方式执行这套 skill
- 多轮长期使用后的画像质量一定可靠

更准确的说法是：这是一份已经有脚本骨架、能跑通核心状态链路，但教学效果仍在持续验证中的 v1 草稿。

## 设计边界

当前状态层更偏向：

- 单学习者
- 本地或单 sandbox 使用
- agent 自动写入
- 中等切分
- 摘要优先的复习模式

暂时不适合直接拿来做：

- 多人同时写同一个数据库
- 远程共享数据库文件上的高并发协作
- 复杂多用户权限系统

## 外部依据

这份 skill 不是“论文实现版”，但它确实有外部依据来约束结构，不是纯拍脑袋。

学习设计相关：

- Dunlosky et al. 2013: [Improving Students’ Learning With Effective Learning Techniques](https://doi.org/10.1177/1529100612453266)
- Karpicke & Blunt 2011: [Retrieval Practice Produces More Learning than Elaborative Studying](https://doi.org/10.1126/science.1199327)
- Cepeda et al. 2006: [Distributed Practice in Verbal Recall Tasks](https://doi.org/10.1037/0033-2909.132.3.354)

这些依据主要支持：

- 不能只重读输入，还要有检索和输出
- lesson 顺序要优先考虑 noticing、retrieval、output
- 复习需要留接口，即使 v1 还没做完整 SRS

状态层与工作区边界相关：

- SQLite 官方关于使用场景的说明：[Appropriate Uses For SQLite](https://www.sqlite.org/whentouse.html)
- SQLite 官方关于网络文件使用边界的说明：[Use of SQLite Over a Network, Caveats and Considerations](https://www.sqlite.org/useovernet.html)
- ITS 结构概览，可用来理解为什么要把“材料、学习者状态、教学决策”分层看待：[Intelligent tutoring system](https://en.wikipedia.org/wiki/Intelligent_tutoring_system)

这个选择更偏向“本地应用 / 单工作区文件数据库”，而不是“很多客户端同时直连写一个远程数据库文件”。

## 当前状态

**这仍然是草稿版本。**

它已经适合：

- 自己边用边改
- 公开到 GitHub 供别人理解思路和试用
- 继续围绕真实输入材料迭代清洗、切分、lesson 和 review 逻辑

它还不适合：

- 对外声称“已经充分测试”
- 对所有类型英文输入都稳定有效
- 直接当成成熟通用产品来承诺体验

## 仓库结构

```text
english-input-coach/
|-- SKILL.md
|-- README.md
|-- agents/
|   `-- openai.yaml
|-- references/
|   |-- input-contract.md
|   |-- pedagogy.md
|   |-- profile-schema.md
|   |-- review-policy.md
|   |-- segmentation-policy.md
|   |-- state-schema.md
|   |-- text-normalization.md
|   |-- track-article-reading.md
|   |-- track-live-chat.md
|   `-- validation-rubric.md
`-- scripts/
    |-- get-review-agenda.py
    |-- init-learning-root.py
    |-- migrate-learning-root.py
    |-- rebuild-profile-snapshot.py
    |-- write-json-state.py
    `-- write-sqlite-event.py
```

## 反馈与迭代

欢迎：

- issue 反馈使用体验
- 提交失败案例
- 提出你觉得值得加入的 lesson 结构或验证方式

也欢迎 PR。

但这个项目会比较严格地看：

- 是否真的提高了效果
- 是否引入副作用
- 是否破坏原有使用体验

现阶段它更适合边用边改，而不是先把结构设计到过度复杂。
