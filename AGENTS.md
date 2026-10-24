# NIKKE 工作站 · AI 协作总契约

> **本文件是全站唯一权威。** 任何 AI 工具（WorkBuddy / Codex / Trae / Cursor / Claude）在本工作区动手前，必须先读本文件。
> 详细架构：`F:\Codex\Nikke\Nikke_工作站架构_Prompt.md`（v3.0）
> 状态台账：`F:\Codex\Nikke\PROJECT_STATUS.md`
> 最后更新：2026-10-10

---

## 0. 一句话定位

`F:\Codex\Nikke` 是围绕手游《胜利女神：NIKKE》的**本地工具工作站**。

**核心模型**：一切以游戏资料为母体，向外衍生技能。

```
母体（资料库）→ 工位（子项目）→ 技能组（大技能）→ 技能点（子技能）
                     全部运行在 平台层 之上
```

**不是**单一应用仓库。动手前务必判断目标属于哪个母体/工位，不要跨边界乱改。

---

## 1. 两个母体（资料库）

| 母体 | 路径 | 提供 | 体量 |
| :--- | :--- | :--- | ---: |
| **A · 游戏 Wiki** | `Nikke_Wiki\` | **已上线内容**：199 角色词典、道具、剧情、素材 | 2.5 GB |
| **B · 拆包** | `Nikke_Skills\拆包\` | **未上线内容**：客户端资源、版本前瞻、HD Bundle | 16.2 GB |

**母体 A 核心资产**：`Nikke_Wiki\data\character_repository\canonical\characters.json`
- 199 个已确认可操作角色，schemaVersion 1
- 单角色 7 段式字段：`identity` / `core` / `combat` / `assets` / `availability` / `guides` / `sources`
- 这是全站**复用价值最高的资产**，新技能优先从这里取数

**母体 B 索引**：`Nikke_Skills\拆包\00_资源库\00_索引\资源总清单.md` + `角色代号中文名对照表.xlsx`

**母体维护准则**：`Nikke_Wiki\AGENTS.md` + `SKILL.md`（采集优先级 P0-P4，已稳定，**只登记不改结构**）

---

## 2. 五个工位（子项目）

| # | 工位 | 路径 | 消费母体 | 技能组 | 进度 | 状态 |
| :-: | :--- | :--- | :--- | :-: | ---: | :-: |
| 1 | QQ 机器人 | `Nikke_Bot\` | A + B | 7 | 85% | 🟢 已上线 |
| 2 | 资源计算器 | `Nikke_Skills\等级计算\` | A | 5 Tab | 80% | 🟡 迭代中 |
| 3 | 头像框预览 | `Nikke_Skills\头像框预览\` | B（+A） | 4 阶段 | 75% | 🟡 迭代中 |
| 4 | 群公告 | `Nikke_Skills\群公告\` | A | 1 | 70% | 🟡 待治理 |
| 5 | 配队器 | `Nikke_Skills\配队器\` | A | 5 | 60% | 🟢 第一阶段完成（2026-09-27 验收通过；2026-10-06 由归档区迁入） |

> 原工位 5「定制模组统计」已于 2026-10-06 裁决 Q3-A **转入归档区**（见 §4）。2026-10-21 按用户指示物理位置迁入 `Nikke_Skills\定制模组统计\`，**仅位置变更，⚪ 归档/只读状态不变，不进工位编号**。
>
> ⚠️ **工位 5 状态更正（2026-10-06）**：Q4 裁决基于「只看到占位 AGENTS.md」判定为空目录。同日核查发现真实实现一直在归档区 `Nikke\_Skills\配队器\`（1419 文件、2026-09-27 已验收），已迁入本表所示路径。**Q4 的「不删除」结论不变，改的是「并非空目录」。**

---

## 3. 平台层（服务全部工位，不消费资料库）

| 设施 | 路径 | 作用 | 进度 | 状态 |
| :--- | :--- | :--- | ---: | :-: |
| MAA_Next | `Nikke_MAA_Next\` | 安卓自动化 → 未来提升采集效率 | 79% | ⚪ 暂停归档（Q5-B） |
| EpinelPS | `Nikke_EpinelPS\` | 私服环境部署与恢复 | 95% | 🟢 可用 |
| 程序异常缩放 | `Nikke_Skills\程序异常缩放\` | 客户端可运行性保障 | 100% | 🟢 已完成 |
| 工具箱 | `Nikke_工具箱\` | NIKKE 工具箱客户端（Electron 外壳，外读站点目录） | — | 🟡 开发中（2026-10-10 登记） |

**MAA_Next 归档状态**（2026-10-06 裁决 Q5-B）：阻塞点（未加载 NIKKE 资源、未连 MaaCore controller、root 连接器未接 `app_process`、原生桥仅 JNI `ping` 占位）**全部冻结**，技术瓶颈 NIKKE v6 资源契约不再推进。重启前置与已保留成果见 `Nikke_MAA_Next\核心目录\agent\agent.md`「零、归档说明」。

---

## 4. 归档区（只读）

| 目录 | 说明 |
| :--- | :--- |
| `Nikke_MAA\` | 历史安卓 MAA，独立 GitHub 仓，为 MAA_Next 提供蒸馏源 |
| `Nikke\` | 历史混合工作区（PC 自动化脚手架、联盟突袭早期区、抓包原料）。2026-10-06 补建 `核心目录\`/`log\`/`回收站\`；`_Skills\配队器\` 已迁出至工位 5。**保留受引用资产**：`outputs\`（≡`正式产物\`，50+ 处硬引用）、`tools\`、`_ref_*\`、`.tmp_MAA-Meow\`（含独立 `.git`） |
| `Nikke_Skills\定制模组统计\` | 原工位 5（**2026-10-21 由根层迁入 `Nikke_Skills`，仅位置变更**）。独立单文件工具（70 KB，**已上线 GitHub Pages**），与工位 2 集成版（39 KB）**功能互补非新旧**。2026-10-06 裁决 Q3-A 冻结只读，不做代码合并，不动线上站点。说明见其 `归档说明.md` |

---

## 5. 跨母体契约（数据流边）

| # | 边 | 传递物 | 契约载体 | 状态 |
| :-: | :--- | :--- | :--- | :-: |
| E1 | 母体B → 工位3 | 原生 HD Bundle | `拆包\输出\_android\catalogs\*.json` + SHA-256 | ✅ |
| E2 | 母体A → 工位1 | 标准化角色词典 | `canonical\characters.json` | ✅ |
| E3 | 母体A → 工位1 | 养成库 | `sync_meta.py` → `character_meta.json` | ✅ |
| E5 | 母体A → 工位2 | 箱体图标 | `Nikke_Wiki\计算器识图素材\官方Icon` | ✅ |
| E6 | 母体B → 工位1 | `[Skill]拆包分析` | `skills\registry.json`（status: `planned`） | ⚠️ 登记未实现 |
| E7 | 母体A → 工位4 | 公告内容 | 人工 | ✅ |
| E8 | 母体A → 母体B | 角色中文名对照 | `拆包\00_资源库\00_索引\` | ✅ |

> **E4 已移除（2026-10-06 裁决 Q8-A）**：原「母体B → 工位2 · 词条/战力数据」契约**不成立**——母体 B 不产词条数据，两处归属也写错了。已改登记为**工位 2 内部数据管线**，见下方说明。跨母体契约现为 **7 条**。

**E6 是唯一剩余断链**，优先修复。

### E4 处理结果（2026-10-06 裁决 Q8-A）

**裁决**：承认词条数据不是资料库产物，从跨母体契约中**移除**。

**核查依据**：
1. 原载体 `Nikke\outputs\词条*战力*` 位于 ⚪ **归档区**历史工作区，不是母体 B。
2. 母体 B `00_资源库\` 11 个分类全为素材类（立绘/皮肤/头像框/称号/个突/剧情插画/剧情背景/UI图标/其他UI/名片装饰/技能资源/工具包），搜「词条/affix」**零命中** → 母体 B 不产词条数据。

**E4 改登记为工位 2 内部管线**：

| 项 | 值 |
| :--- | :--- |
| 名称 | P1 · 词条战力数据管线（**工位 2 内部**） |
| 输入 | pcap 静态响应 + 客户端静态表反解（`EquipmentOptionTable` / `StateEffectTable` / `FunctionTable`） |
| 现资产 | `Nikke\outputs\词条阶数战力统计\*.xlsx`（3 个）+ `Nikke\outputs\词条战力拆包研究\正式结果\`（换算说明 + 接口增量表 + 静态表反解 8 表 json + 静态表分析 4 产物） |
| 分析脚本 | `Nikke\outputs\词条战力拆包研究\临时\分析pcap静态响应.py` |
| 消费方 | 工位 2「洗词条计算器」Tab |
| 待办 | 资产仍在归档区，未迁入工位 2；形式化（统一为版本化 JSON）待做 |

### E6 现状说明（2026-10-06 核查，已裁决 Q9-A 处理）

E6 的下游曾指向一个**已过时的技能副本**。**已于 2026-10-06 整合完毕**：

| 位置 | 名称 | 状态 |
| :--- | :--- | :--- |
| `~\.workbuddy\skills\nikke-asset-extract\` | `nikke-asset-extract` | ✅ **唯一权威**（2026-09-17 主体双链路 + 2026-10-06 整合旧版 5 项有效内容） |
| `Nikke_Skills\拆包\02_Skills\nikke-asset-extractor\` | — | ✅ **已改为指路牌**（旧版原文备份在 `拆包\05_回收站\cleanup_20261006-1624\`） |

**整合带走的旧版有效内容**：① 新增资源发现排除法 ② 6 条 Windows 环境坑（`-LiteralPath` / `%04d` 取模 / `putpalette` / FASTOCTREE 丢 alpha / GIF 1-bit 透明 / ffmpeg 裁剪 / 国服 NKAB v4 需 NAU）③ 工具链清单。

**E6 剩余待办**：`registry.json` 的 `runtime` 文案**已改为** `对接 nikke-asset-extract（全局权威：~/.workbuddy/skills/nikke-asset-extract）`；剩 `[Skill]拆包分析` 的运行时代码未实现（X2）。

### ✅ 工位 2 产物错位 —— 已解决（2026-10-06 裁决 Q7-A）

原问题：工位 2 真实产物在 C 盘，仓库内 `nikke-planner-web\` 是 2026-09-17 陈旧副本。

**已于 2026-10-06 执行整体搬迁**：C 盘 `…\WorkBuddy\2026-08-05-14-55-15\nikke_src\` → `Nikke_Skills\等级计算\nikke-planner-web\`（含 `.git` 与全部未提交改动）。

**验证**：文件数 + md5 逐项比对通过；CDP 端到端（5 Tab / 真实计算 / 零外部请求 / 零 4xx / 零 JS 错误）全绿。`pinkuro_server.py` 经查**不含密钥**（Key 由前端每次请求传入，服务端不落地；日志亦跳过 query string），搬运无泄密风险。陈旧副本已移入 `等级计算\回收站\cleanup_20261006-1635\`。

**后续纪律**：工位 2 的开发基准目录现已回到仓库内，**不再有例外**。红线第 4 条（禁写 C 盘）恢复为无例外。

---

## 6. 目录契约

每个工位/设施的标准结构（空目录不建）：

```
<工位根>/
├─ AGENTS.md              # 【必需】边界/入口/端口/验证顺序/技能表
├─ 核心目录/
│  ├─ agent/agent.md      # 【必需】记忆：目标与结果/关键决策及理由/踩坑/遗留待办
│  ├─ Skills/             # 按需：技能点（每个含 SKILL.md）
│  └─ 错误日志/           # 按需
├─ 正式产物/              # 仅放已验收交付物
├─ 临时车间/              # 草稿、中间件、一次性脚本
├─ log/                   # 运行/构建日志
└─ 回收站/                # 删除缓冲，带 cleanup_YYYYMMDD-HHMM/，禁止物理删除
```

**别名映射（不重命名，只登记，避免破坏脚本引用）**：

| 中文标准名 | 英文等价别名 | 已在用 |
| :--- | :--- | :--- |
| `正式产物/` | `outputs/` | `Nikke_MAA` `Nikke_MAA_Next` `Nikke_Wiki` |
| `临时车间/` | `tools/`、`_tmp_*`、`temp/`、`临时/`、`临时文件/` | `Nikke_MAA` `Nikke\` `配队器` |
| ⚠️ `临时文件/` 两处例外 | ① `等级计算/临时文件/` —— **不可归并**（外部 TRAE SOLO 实时工作区，见下「第三类例外」）② `配队器/临时文件/` —— 与 `配队器/临时/` 同为该项目自有临时车间（**登记不改**） | — |
| `支持依赖/` | `supports/` | `Nikke_MAA` `Nikke_MAA_Next`（预编译依赖，**受控例外不迁移**） |
| `log/` | `03_log/` | `拆包` `Nikke_EpinelPS` |
| `回收站/` | `05_回收站/`、`垃圾箱/` | `拆包` `Nikke_MAA` |

**已稳定结构，只登记不改**：`Nikke_Wiki`（`data/character_repository/*`、`assets/`〔已按来源分类〕、`cache/`、`docs/`、`obsidian_character_database/`、`scripts/`、`计算器识图素材/` — README 已声明角色；**`exports/` 已于 2026-10-06 按内容三分撤销**）、`Nikke_Bot`（`host|skills|knowledge_base`）、`Nikke\`（**归档区**：`outputs/`〔≡`正式产物/`，50+ 处硬引用〕、`tools/`〔≡`临时车间/`〕、`临时车间/`、`log/`、`核心目录/`、`回收站/`、`_ref_*/`、`.tmp_MAA-Meow/`〔含独立 `.git`〕、`.tmp_MaaNikke/`〔空占位〕、`cn_nikke_screenshots/`〔运行时输出，空是常态〕 + 根文件见其 `AGENTS.md` 与 `核心目录/agent/agent.md`）、`拆包`（`00_资源库`~`05_回收站`，**四目录范例**；`NAU/`、`Doro_Repacker_EX/`、`_保留小开关/`、`.trae/` 为 agent.md 明列的**保持原位项**）、`Nikke_EpinelPS`（`upstream*`/`official_build_*`/`clean_*`/`candidate_release`/`rollback_artifacts`/`startup_validation_*`/`backups`/`config_backups`/`build_*` + `_launcher_*.cmd` + `restore_log_*.txt` … — 构建与回滚链专用，**不套用五目录**）、`Nikke_MAA`（`tools/`/`supports/`/`docs/`/`outputs/` — 归档只读）、`Nikke_MAA_Next`（`app/`/`docs/`/`outputs/`/`resources/`/`scripts/`/`supports/` — Gradle 工程，归档只读）、`攻略采集`（`from-images/`/`templates/`/`zoom/`/`config/`/`dicts/`/`prompts/`/`skills/`/`agents/` — 脚本按名硬编码引用）、`配队器`（`源码/数据/素材/素材索引/测试/日志/输出/归档/说明/临时/临时文件/` — 中文目录自述，**16 个脚本含 `PROJECT_ROOT` 绝对路径常量，再搬迁须同步改写**）。

> ⚠️ **第四类约定：资源类素材汇总（2026-10-06 新增）**
> **所有资源类目录（图片/素材/图标）必须汇总到单一父目录并内部按类分子目录**，不得在工位顶层平铺。
> - 已有合格范例：`Nikke_Wiki/assets/`（按来源分 7 类）、`头像框预览/资源采集/`（静态/动态/角色头像）、`等级计算/nikke-planner-web/assets/`
> - 新统一父目录名：**`资源库/`** —— 按期隔离的用 `资源库/<YYYYMMDD>/<素材类型>/`（群公告范例）；不按期的直接用 `<素材类型>/`
> - 🚫 例外：`攻略采集/from-images/` `templates/` `zoom/` 虽为英文名且未汇总，但被 ≥6 脚本字面量硬编码 → **保持原位只登记**（受引用者不动）

> ⚠️ **第三类例外：他方活跃会话占用（2026-10-06 新增）**
> `等级计算/临时文件/` 是**外部 TRAE SOLO 会话的实时工作区**（`agent-tool-host.exe` 在其中运行 `g23_*` 诊断脚本，路径为脚本内硬编码常量）。曾三度移走三度再生，最终判定**不可归并**，登记为受保护目录。
> **通用规则**：移动任何目录前，除 `grep` 引用外**必须再查进程占用**（`Get-CimInstance Win32_Process` 匹配命令行 + 逐文件写句柄探测）。**若移动被拒或目录在移走后自动再生，即为「有他方正在使用」的信号 —— 正确动作是登记例外并撤退，不得杀进程或建链接绕过。**

**工位内新增标准子目录（2026-10-06 S2 补做 + 全站归集，可复用）**：

| 子目录 | 落点 | 用途 |
| :--- | :--- | :--- |
| `核心目录/迭代记录/` | 工位 2、3 | 历史 Prompt、编号文档、评估记录 |
| `核心目录/证据截图/` | 工位 2 | 验证截图、参照图 |
| `核心目录/历史脚本/` | 工位 4 | 逐期一次性脚本归档 |
| `核心目录/报告/` | 平台 EpinelPS | 历史分析报告 md |
| `临时车间/迭代探针_*/` | 工位 2 | CDP/E2E 探针脚本与中间产物（按轮次分批：`_202607-09`、`_R22-R23`） |
| `临时车间/历史打包含/` | 工位 2 | 旧版本 zip |
| `临时车间/IDE分享包/` | 工位 2、1、母体A、母体B | Trae 等 IDE 生成的 html.zip |
| `资源库/<日期>/` | 工位 4（及需要按期隔离素材的工位） | **资源类素材汇总父目录**，内分素材类型子目录（如群公告 `官号素材`/`定稿素材`/`原始素材`）。2026-10-06 起为新约定 |

---

## 7. 技能体系

```
母体 → 工位 → 技能组（大技能）→ 技能点（子技能）
```

**归属规则**：技能组**跟随主项目**，不独立成子项目。

**机器人技能唯一事实源**：`Nikke_Bot\skills\registry.json`
- 7 个技能组，`[Skill]` 前缀
- manager WebUI「指令速查」、群内 `/指令` `/技能` 均从此读取
- **新增/修改技能必须同时登记 `skills[]` 数组与其 `commands`**

| 技能组 | status | 能力点 |
| :--- | :-: | :--- |
| `[Skill]系统指令` | ready | 指令速查 / 帮助菜单 |
| `[Skill]会战服务` | ready | 出战与出刀 / 结算与盘点 / 进度截图 |
| `[Skill]角色百科` | ready | 角色卡 / 关键词检索 |
| `[Skill]养成查询` | ready | 养成建议 |
| `[Skill]装备词条` | ready | 导入维护 / 查询统计 / 导出 |
| `[Skill]会战桥接` | ready | — |
| `[Skill]拆包分析` | **planned** | 未实现 |

**技能生长三路径**：① 母体纵向深化（母体加 SKILL.md，下游受益）② 母体横向衍生（工位新能力，登记技能表）③ 跨工位复用（服务 ≥2 工位 → 提升到 `F:\Codex\Skills\`）。

### 7.1 工位技能表落点

各工位契约（`<工位>\AGENTS.md`）末尾均有 `## 技能表` 段，是本工位技能的唯一可读入口。已覆盖：

| 工位 | 契约 | 技能定义文件 |
| :--- | :--- | :--- |
| 母体 A · Wiki | `Nikke_Wiki\AGENTS.md` | `Nikke_Wiki\SKILL.md`（`nikke-character-dictionary-maintenance`） |
| 母体 B · 拆包 | `Nikke_Skills\拆包\AGENTS.md` | `Nikke_Skills\拆包\02_Skills\nikke-asset-extractor\SKILL.md` |
| 工位 1 · QQ Bot | `Nikke_Bot\AGENTS.md` | `Nikke_Bot\skills\registry.json`（机器可读唯一事实源） |
| 工位 2 · 等级计算 | `Nikke_Skills\等级计算\AGENTS.md` | `Nikke_Skills\等级计算\SKILL.md`（`nikke-level-resource-planner`） |
| 工位 3 · 头像框预览 | `Nikke_Skills\头像框预览\AGENTS.md` | 工位内 `agent.md`（技能表已覆盖，无独立 SKILL.md） |
| 工位 4 · MAA（Android 实验） | `Nikke_MAA\AGENTS.md` | 归档只读 |
| 工位 5 · 配队器 | `Nikke_Skills\配队器\AGENTS.md` | 技能表已覆盖（5 个 skill，均 ready），无独立 SKILL.md |
| 技能工位 · 群公告 | `Nikke_Skills\群公告\AGENTS.md` | 技能表已覆盖，无独立 SKILL.md |
| 技能工位 · 程序异常缩放 | `Nikke_Skills\程序异常缩放\AGENTS.md` | 技能表已覆盖，兼全站工程规范范例 |
| 技能工位 · 攻略采集 | `Nikke_Skills\攻略采集\AGENTS.md` | `Nikke_Skills\攻略采集\SKILL.md` |
| 附属 · EpinelPS 私服 | `Nikke_EpinelPS\AGENTS.md` | 运维型，无技能组 |
| 平台 · MAA_Next | `Nikke_MAA_Next\AGENTS.md` | 已归档（Q5-B），技能点全部冻结 |
| ⚪ 归档 · 定制模组统计 | `Nikke_Skills\定制模组统计\AGENTS.md` | 只读，说明见 `归档说明.md` |

**同步纪律**：技能点变更必须同时更新 ①本表对应行的 status ②工位契约的技能表 ③`PROJECT_STATUS.md` 对应行。三处不一致时以工位契约的技能表为准（`Nikke_Bot` 除外，以 `registry.json` 为准）。

### Q3 归档处理结果（2026-10-06）

「定制模组统计」**不从「工位」编号中消失，而是转入归档区**：

| 项 | 结果 |
| :--- | :--- |
| 状态 | 🟢 100% 已完成 → ⚪ **归档/只读** |
| 工位编号 | 原工位 5 → 移到 §4 归档区；原工位 6「配队器」顺位为工位 5 |
| 归档说明 | 新建 `归档说明.md`（现随目录位于 `Nikke_Skills\定制模组统计\`），记录 6 项独有功能 + 7 项集成版独有功能 |
| 代码改动 | **零**。未改 HTML，未动线上站点 |
| 新增红线 | 第 11/12 条（禁改归档区、禁合并已归档代码） |

**核心事实**：本工具与工位 2 的集成版是**功能互补**，不是新旧替代。独立版偏「理论期望测算」（期望对比/平均日产/触发率/进度条/双服对照/离线），集成版偏「长期记录台账」（日历/分 BOSS/掉落区间/帮助面板）。两版 md5 不同、体积差近一倍（70 KB vs 39 KB）。

---

## 8. 红线（所有自动化必须遵守）

1. **禁猜标识符**：键名、路径、字段、API 先读现有文件证实。
2. **禁编造存在性**：API/参数/配置/依赖是否存在，唯一依据是已装依赖与现有代码。
3. **禁不确定表述**：不得以「应该/可能」下结论；未证实必须标注。
4. **禁写 C 盘**：缓存、日志、临时文件同禁。**无例外**（工位 2 的 C 盘产物已于 2026-10-06 迁回仓库内，见 §5）。
5. **禁物理删除**：只允许移入 `回收站/`，子目录带日期。
6. **禁跨盘迁移**：`D:\Codex` 在本机不存在，实际全集根为 `F:\Codex`。
7. **禁跨工位 import**：跨工位交互只走正式产物或脚本入口。
8. **禁改运行时配置**：端口、密钥、AstrBot/NapCat 配置不改。密钥不入库。
9. **可见窗口原则**：不做封包、注入、内存读取、登录绕过、反检测、盲目连点。
10. **保守默认**：涉购买/钻石/招募/升级/出刀/群消息，默认保守；调试模式默认只预览不真实执行。
11. **禁改归档区**：`Nikke\`、`Nikke_MAA\`、`Nikke_Skills\定制模组统计\` 均为只读存档。其中 `Nikke_Skills\定制模组统计\` 的 HTML **就是线上工具的源**，改它等于改线上——除非用户明确指示，否则不得改动。
12. **禁合并已归档代码**：不得把 `Nikke_Skills\定制模组统计\` 的代码合并进线上计算器（Q3-A 裁决）。

---

## 9. 关键入口与端口

| 用途 | 入口 |
| :--- | :--- |
| 本契约 | `F:\Codex\Nikke\AGENTS.md` |
| 对外入口 | `F:\Codex\Nikke\README.md` |
| 全站记忆 | `F:\Codex\Nikke\核心目录\agent\agent.md` |
| 迭代记录 | `F:\Codex\Nikke\核心目录\迭代记录\`（历史 Prompt / 迁移记录） |
| 架构总纲 | `F:\Codex\Nikke\Nikke_工作站架构_Prompt.md` |
| 状态台账 | `F:\Codex\Nikke\PROJECT_STATUS.md` |
| Bot 启动 | `Nikke_Bot\host\start-nikke-qq-bot-menu.bat` → `[1] 日常上线` |
| Bot WebUI | `http://127.0.0.1:6185` |
| 计算器线上 | `https://theifxzx666-blip.github.io/Nikke_Level/` |
| 母体A 词典 | `Nikke_Wiki\data\character_repository\canonical\characters.json` |
| 母体B 迁移对照 | `Nikke_Skills\拆包\迁移说明.md`（**唯一权威对照表范例**） |
| 母体B 迭代计划 | `Nikke_Skills\拆包\迭代计划.md` |

**端口**：AstrBot `6185` ｜ NapCat `6099` ｜ OneBot WS `6199` ｜ 桥接健康 `8793` ｜ 成员后台 `8788` ｜ Ollama `11434`

**排障顺序**（不要一上来重装 NapCat）：
Ollama(11434) → AstrBot(6185) → OneBot(6199) → NapCat(6099) → 插件 → 桥接(8793/health) → 群内触发

---

## 10. Git 与编码

- **独立 git 仓**：`Nikke\`、`Nikke_Bot\`、`Nikke_MAA\`、`Nikke_MAA_Next\`。搬移后各自 `git status` 确认改动范围。
- **禁止**：`git reset --hard`、强推，除非用户明确要求。
- **编码安全**：`.bat`/`.ps1` 不写非 ASCII 路径（中文路径破坏 bat 编码）；中文目录名只用于非脚本引用的归档层。
- **Windows 环境**：Git Bash 的 coreutils 不在 PATH，需先 `export PATH="/usr/bin:/bin:$PATH"`。

---

## 11. 工作流程

```
① 选题 → 读本文件定位工位 + 读该工位 核心目录/agent/agent.md 的「遗留待办」
② 计划 → 产出「步骤 → 验证」表；未确认不发车
③ 执行 → 只改必要内容；搬移前先记路径映射表
④ 验证 → 跑命令/测试，展示证据；「能跑起来」不算完成
⑤ 归档 → 更新 agent.md + PROJECT_STATUS.md
⑥ 沉淀 → 可复用工作流升级为 SKILL.md 并登记技能表
```

**冲突裁决**：与本文件冲突时以本文件为准，并在冲突项目的 `agent.md` 登记冲突条目。

---

## 12. 文档权威链

| 文档 | 状态 |
| :--- | :--- |
| `AGENTS.md`（本文件） | ✅ **唯一权威入口** |
| `Nikke_工作站架构_Prompt.md`（v3.0） | ✅ 架构总纲 |
| `PROJECT_STATUS.md` | ✅ 状态台账 |
| `README.md` | ✅ 对外入口（一行定位 + 指向本文件） |
| `核心目录\agent\agent.md` | ✅ 全站记忆（目标 / 决策 / 踩坑 / 待办） |
| `核心目录\迭代记录\历史Prompt\Nikke_项目管理架构_Prompt.md`（v2.0 四层模型） | ⚠️ 已被 v3 取代，历史留档 |
| `核心目录\迭代记录\历史Prompt\Nikke_项目整理_方案Prompt.md`（v1 结构治理） | ⚠️ 规范已吸收进 v3 |
| `核心目录\迭代记录\历史Prompt\PROJECT_BRIEF_PROMPT.md` | ⚠️ 精简转发版（原版内容曾过时） |
| `Nikke_Skills\拆包\拆包项目整理_Prompt.md` | ✅ 方法论来源 |
