# NIKKE 角色字典（数据底座）

> 本仓库只跟踪**字典数据与构建脚本**，不含立绘、素材图、拆包中间产物与游戏本体。
> 工作站全貌见 `README.md`，AI 契约见 `AGENTS.md`。

胜利女神：NIKKE 的角色字典与代号对账数据，从国服 / 国际服客户端、GameKee、Prydwen 多源合成。

## 目录

```
Nikke_Wiki/
├─ data/                字典数据（JSON + CSV 双份）
├─ scripts/             构建、对账、导出脚本（Python 3.11+）
└─ 正式产物/             面向阅读的成品（角色辞典）
```

## 数据文件

| 文件 | 内容 |
|:---|:---|
| `Nikke_Wiki/data/nikke_character_dictionary.json` | 角色主字典（按中文名为键，含代号、阵营、稀有度、武器、技能等） |
| `Nikke_Wiki/data/nikke_character_dictionary_enhanced.json` | 增强字典：叠加 GameKee 详情、别名、素材路径后的完整版 |
| `Nikke_Wiki/data/nikke_character_aliases.json` | 别名表（玩家黑话 / 简称 → 标准中文名），约 550 条 |
| `Nikke_Wiki/data/character_id_registry.json` | 代号权威主表，371 个代号：国服 locale / 国际服名单 / 素材库三源对账 |
| `Nikke_Wiki/data/character_name_mapping.json` | 英文名 ↔ 中文名 ↔ 代号映射 |
| `Nikke_Wiki/data/cn_release_status.json` | 国服上线状态（可操作 / 预埋 / 未上） |
| `Nikke_Wiki/data/nikke_characters.json` | 国际服可操作角色名单（dotgg 快照） |
| `Nikke_Wiki/data/non_playable_character_cards.json` | 不可操作 NPC 卡片 |
| `Nikke_Wiki/正式产物/角色辞典.json` `.xlsx` | 面向阅读的成品，199 条、三档素材路径、80×80 头像 |

## 构建脚本入口

| 脚本 | 作用 |
|:---|:---|
| `scripts/build_character_id_registry.py` | 生成 `character_id_registry.json` 与对账报告 |
| `scripts/build_character_codex.py` | 生成 `角色辞典.json` / `.xlsx`（含三档素材路径） |
| `scripts/sync_character_aliases.py` | 把 xlsx 别名列并集同步进 `nikke_character_aliases.json` |
| `scripts/export_nikke_character_tables.py` | 导出 xlsx 字典表（`--write-dict` 回灌别名字段） |
| `scripts/audit_character_dictionary.py` | 字典完整性审计 |
| `scripts/fix_library_names.py` | 素材库命名纠错（默认 dry-run，备份落 `回收站/`） |

## 数据口径（重要）

- **代号**：以国服 `Locale_Character.lss` 的中文名为准。国际服名单只用来判断「是否已上线」，不用来定名。
- **占位槽**：locale 里只有 `name` 一个字段的条目是客户端预留 id 槽位，名字从别的角色复制（如 `E.H.` = c113 + c930），不能当正式角色入库。判错标要三条同时成立：占位槽 + 与真角色重名 + 国际服不可操作。
- **素材三档**：`icon` = 128² 官方方图（头像）、`avatar` = 256×512 半身像（编成卡 / 列表）、`portrait` = 1024²/2048² 立绘。三者不可混称。
- **别名**：xlsx「角色字典·别名」与「全汉化·常用别名」取并集后同步到 JSON，改完需重启依赖它的服务。
- **图像查重不可靠**：average hash / dhash 在透明背景立绘上误判严重，只信字节比较。

## 环境

脚本依赖 `openpyxl`、`Pillow`、`requests`。数据路径默认相对 `Nikke_Wiki/`，仓库放任意位置即可运行。
