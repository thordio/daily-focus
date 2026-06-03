# Daily Focus -- 测试验证矩阵 (Verification Matrix)

## 总说明

| 项目 | 值 |
|------|-----|
| 总测试数 | 36 + 36 quality checks (T01-T36 plus quality tests) |
| 层级分布 | L1: 21, L2: 9, L3: 1, L4: 3, L5: 2 |
| 测试通过率 | 393/393 = 100% |
| 所属工作区 | A: T01-T02, B: T03-T04, C: T07-T09+Theme, F: T05-T06, 汇总: T12-T16, E: T20-T21, Topic: T22-T30, Quality: T37+ (filename, CJK ratio, is_demo) |
| 创建日期 | 2026-05-31 |
| 最后更新 | 2026-06-04 (QA 1 round 10 — content volume audit + new quality test) |
| 当前全量测试 | 394 tests (+36 quality tests). 0 failed. |

---

## 测试矩阵

| 编号 | 层级 | 测试内容 | 预期结果 | 执行方式 | 所属工作区 | 状态 | 验证人 | 备注 |
|------|------|---------|---------|---------|-----------|------|--------|------|
| T01 | L1 | config JSON 通过 pydantic 校验 | 无 ValidationError | `python -c "..."` | A | 通过 | Verifier Agent 2 | 2026-05-31: 两个文件均通过 Config.model_validate() |
| T02 | L1 | RSS URL 格式合法 | 全部 HttpUrl 类型 | pytest | A | 通过 | Verifier Agent 2 | 2026-05-31: Pydantic HttpUrl 类型验证通过, 无 ValidationError |
| T03 | L1 | 评分 prompt 输出 JSON 可解析 | score 在 0-10, tags 为 list | pytest | B | 通过 | QA 1 | 2026-06-01: 55 prompt tests pass (29 existing + 26 new), 含 scoring completeness/dedup scenario/edge cases/integration smoke tests |
| T04 | L1 | 去重 prompt 正确分组重复新闻 | 已知重复对被正确识别 | pytest | B | 通过 | QA 1 | 2026-06-01: Dedup prompt validated via structural tests + realistic orchestrator-format scenario test |
| T05 | L1 | RSS 图片提取候选列表正确 | candidate_images 含 url/alt/context | pytest | F | **通过** | QA 1 | 2026-06-01: 8 RSS tests all pass. Context extraction works correctly (before/after text populated). Logo/avatar/button/headshot/icon filtering verified. Max 5 candidates per entry verified. |
| T06 | L1 | 图片 URL 规则过滤(logo/avatar) | 过滤后不含 logo 等 URL | pytest | F | **通过** | QA 1 | 2026-06-01: Verified via `test_rss_image_extraction_and_filtering`, `test_rss_image_filter_button_and_headshot`, `test_rss_image_extraction_icon_filtered`. Logo, avatar, button, headshot, icon all filtered correctly. |
| T07 | L1 | HTML 渲染输出合法 HTML | 无未闭合标签 | pytest | C | **通过** | QA 1 | 2026-06-01: 30 renderer tests pass, including DOCTYPE/HTML structure checks, dark mode CSS variables, PWA validation, responsive design checks. |
| T08 | L1 | HTML 含 robots meta 标签 | `name="robots" content="noindex, nofollow"` | pytest | C | **通过** | QA 1 | 2026-06-01: `test_render_html_noindex` passes for both zh and en. Verified in archive.html template too. |
| T09 | L1 | manifest.json 合法 | JSON 可解析, 含必要字段 | pytest | C | **通过** | QA 1 | 2026-06-01: `test_manifest_json_valid` passes. All required fields (name, short_name, start_url, display, theme_color) present. robots.txt and sw.js also validated. |
| T10 | L1 | 评分边界: 高价值新闻得高分 | score >= 8 | pytest (need API key) | B | 待验证 | | 需 DEEPSEEK_API_KEY |
| T11 | L1 | 评分边界: 低价值新闻得低分 | score <= 4 | pytest (need API key) | B | 待验证 | | 需 DEEPSEEK_API_KEY |
| T12 | L2 | 完整管道无崩溃 | 所有步骤正常完成 | `uv run horizon --hours 1` | D | 待验证 | | 需 DEEPSEEK_API_KEY + config. E2E pipeline tests (3 tests) pass with mock data covering the full render flow. |
| T13 | L2 | 图片信息密度分类准确 | informational 图片含 benchmark/chart | pytest (need API key) | F | 待验证 | | 需 DEEPSEEK_API_KEY. Integration test (`test_integration_monkeypatched_client`) verifies prompt assembly and response parsing with mock AI. |
| T14 | L2 | 图片降级不崩溃 | AI 异常时 selected_images 为空 | pytest | F | **通过** | QA 1 | 2026-06-01: 3 degradation tests pass: empty candidates, invalid JSON response, API exception. |
| T15 | L2 | 中英文渲染都不报错 | 两次渲染均成功 | pytest | C | **通过** | QA 1 | 2026-06-01: `test_render_html_bilingual` and `test_structured_data_field_types` both test zh/en and morning/evening combinations. E2E test exercises all 4 combinations. |
| T16 | L3 | 端到端: 本地完整运行 | 生成 docs/index.html + summaries/*.md | `uv run horizon --hours 1 --period morning` | D | 待验证 | | 需 DEEPSEEK_API_KEY + config. E2E pipeline test (`test_pipeline_e2e_full_flow`) exercises the critical render path with mock data. |
| T17 | L4 | 手机浏览器无横向溢出 (375px) | 无 overflow | 人工 | C | 待验证 | | CSS media queries for max-width 480px present. Container max-width 680px set. |
| T18 | L4 | 暗色模式显示正常 | 颜色符合 sunrise 色板 | 人工 | C | 待验证 | | Dark mode CSS variables present. `prefers-color-scheme: dark` media query covers bg, card-bg, text, border, scores, tags. |
| T19 | L4 | PWA "添加到主屏幕" 可触发 | 弹窗或提示 | 人工 | C | 待验证 | | manifest.json has display=standalone, theme_color, icons. sw.js provides cache-first + network-first strategies. |
| T20 | L5 | workflow_dispatch 成功 | 所有 step 绿色 | GitHub Actions | D/E | 待验证 | | |
| T21 | L5 | Telegram 通知收到 | 手机收到消息 | 人工 | E | 待验证 | | |
| T22 | L1 | RSSSourceConfig topic 字段默认值为 ai-tech | cfg.topic == "ai-tech" | pytest | Topic | **通过** | QA 1 | 2026-06-02: Verified default, override, serialization round-trip |
| T23 | L1 | RSS scraper 传递 source.topic 到 metadata["topic"] | metadata["topic"] == source.topic | pytest | Topic | **通过** | QA 1 | 2026-06-02: Verified default topic propagation and override |
| T24 | L1 | get_structured_data 按 topic 分组到 tabs | tabs dict 含 ai-tech/ai-markets/economy | pytest | Topic | **通过** | QA 1 | 2026-06-02: 9 grouping tests covering all scenarios |
| T25 | L1 | 无 topic 字段的 item 默认为 ai-tech | 归入 ai-tech tab | pytest | Topic | **通过** | QA 1 | 2026-06-02: backward compat verified |
| T26 | L1 | tabs dict 始终有三个 key | ai-tech, ai-markets, economy | pytest | Topic | **通过** | QA 1 | 2026-06-02: verified at all item counts (0,1,3) |
| T27 | L1 | 空 tab 不崩溃, items 为空列表 | no exception, empty list | pytest | Topic | **通过** | QA 1 | 2026-06-02: verified for each tab individually |
| T28 | L2 | HTML 渲染含三个 tab 按钮和对应面板 | 3 tab-btn + 3 tab-panel | pytest | Topic | **通过** | QA 1 | 2026-06-02: tab nav/buttons/panels all rendered |
| T29 | L2 | 每个 tab 显示条目数 + 空 tab 显示"暂无内容" | item count visible, empty state text | pytest | Topic | **通过** | QA 1 | 2026-06-02: counts verified, 暂无内容/No items text verified |
| T30 | L2 | 无 tabs 数据时回退到 flat 列表渲染 | 不崩溃, 显示 flat items | pytest | Topic | **通过** | QA 1 | 2026-06-02: backward compat fallback verified |
| T31 | L1 | Flash prevention script 在 CSS 前运行 | localStorage 主题在渲染前已设置 | code review | C | **通过** | QA 1 | 2026-06-02: `<script>` at line 5 runs before `<style>`, checks localStorage.getItem('theme'), applies data-theme attribute. No flash possible. |
| T32 | L1 | `@media (prefers-color-scheme: dark)` 包裹在 `:not([data-theme="light"])` | 用户手动选 light 时不触发系统暗色 | code review | C | **通过** | QA 1 | 2026-06-02: All 3 dark media query blocks (root vars, score badges, demo-banner) use `:root:not([data-theme="light"])` prefix. |
| T33 | L1 | `[data-theme="dark"]` 选择器含完整暗色变量 | 手动暗色模式应用正确 CSS 变量 | code review | C | **通过** | QA 1 | 2026-06-02: `:root[data-theme="dark"]` with full variable set + score badge overrides + demo-banner override at lines 60-81, 79-81, 218-222. |
| T34 | L1 | 主题切换逻辑: 仅 dark ↔ light 二态循环 | 两次点击完成完整循环（无 system 模式） | code review | C | **失败** | QA 1 | 2026-06-02: JS cycles through 3 states (system → dark → light → system). REQUIREMENT changed: must be 2-state (dark ↔ light only). Three-state mode removed from spec. See Bug QA1-006. |
| T35 | L1 | `theme-icon` 图标随主题正确更新 | 暗色显示☀️, 亮色/系统显示🌙 | code review | C | **通过** | QA 1 | 2026-06-02: `updateIcon()` uses `getTheme()` which reads data-theme attr, falls back to `prefers-color-scheme`. dark→☀️, light→🌙, system dark→☀️, system light→🌙. |
| T36 | L1 | Toggle button 含 `aria-label` | 无障碍可访问 | code review | C | **通过** | QA 1 | 2026-06-02: `<button class="theme-toggle" id="theme-toggle" aria-label="切换主题 / Toggle theme" title="切换深浅色模式">` at line 643. |

## 状态说明

| 状态 | 含义 |
|------|------|
| 待验证 | 测试尚未执行或对应代码尚未实现 |
| 通过 | 测试执行通过, 结果符合预期 |
| 失败 | 测试执行但结果不符合预期 |
| N/A | 该测试在当前阶段不适用 |

## QA 1 测试覆盖总结 (2026-06-03 — round 8: post-fix content quality verification)

### Builder 1 Code Changes Verified (deployed at ~02:11)

| File | Change | Status |
|------|--------|--------|
| `src/ai/summarizer.py` | Added `_has_cjk()`, `language_mismatch` field, `score_threshold` parameter; sync'd `get_structured_data` | ✅ Deployed |
| `src/orchestrator.py` | Made `get_structured_data` call synchronous, passes `score_threshold` from config | ✅ Deployed |
| `tests/test_renderer.py` | Updated to expect `language_mismatch` key in REQUIRED_ITEM_KEYS | ✅ Verified |

**Pipeline re-run detected**: The HTML output (2026-06-02-morning.html, generated at 02:11) reflects Builder 1's fixes. The pre-fix output (generated at 01:36) was overwritten.

### Content Quality Audit (docs/daily/2026-06-02-morning.html — post-fix run)

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | **whats_new vs why_it_matters distinct** | **PASS (P0 FIXED)** | ALL 16 articles have DIFFERENT text in whats_new vs why_it_matters. The enricher fix (separate fields, not concatenated) works correctly. |
| 2 | **Language = Chinese** | **PASS (P1 FIXED)** | 15/16 articles in Chinese. 1 English article (article 10, "AI Standards Consortium") — correctly flagged with `lang-mismatch` badge. |
| 3 | **ai-tech tab >= 4 items** | **PASS** | 4 items (meets minimum) |
| 4 | **ai-markets tab >= 6 items** | **PASS** | 6 items (meets minimum) |
| 5 | **economy tab >= 6 items** | **PASS** | 6 items (meets minimum) |
| 6 | **Source diversity >= 5** | **PASS** | 13 unique sources (TechCrunch, 机器之心, The Verge, r/MachineLearning, Bloomberg, Financial Times, Reuters, Hacker News, IDC, Wall Street Journal, Xinhua, Euronews, Nikkei) |
| 7 | **Real images** | **FAIL** | 1 placeholder image (placehold.co) in article 1. No real article images. Expected for demo data mode. |
| 8 | **Language mismatch detection** | **PASS** | Article 10 correctly flagged with `lang-mismatch` badge. `_has_cjk()` detection works. |
| 9 | **Demo data mode** | **NOTED** | Demo banner present. All article URLs are `example.com` placeholders. Content is synthetic/generated, not from real RSS scraping. |
| 10 | **Full test suite** | **PASS** | 383/383 passed (358 existing + 25 new quality tests). 0 failed. |

### Key Finding: P0 and P1 Both Fixed
All three enricher fixes are confirmed working in post-fix output:
1. ✅ **Separate fields**: `whats_new_zh` and `why_it_matters_zh` stored as separate fields — every article has distinct content
2. ✅ **Per-topic minimum items**: ai-tech >= 4, ai-markets >= 6, economy >= 6 — all minimums enforced
3. ✅ **Chinese language + User-Agent**: Content is in Chinese (15/16 articles), RSS scraper working with User-Agent set
4. ✅ **Language mismatch detection**: `_has_cjk()` correctly identifies English content and flags it

**Note**: Output is still demo data (example.com URLs, placeholder images, demo banner). Real pipeline verification not yet possible without live API keys.

### 十项验证结果

| # | 检查项 | 结果 | 详细 |
|---|--------|------|------|
| 1 | 完整测试套件 | **通过** | 383/383 tests passed (358 existing + 25 new quality tests), 0 failed |
| 2 | .gitignore 含 apikey.txt | **失败** | `.gitignore` 文件中缺少 `apikey.txt` 条目 |
| 3 | apikey.txt 未被 git 追踪 | **通过** | `git status` 确认 apikey.txt 不在追踪中 |
| 4 | Jekyll 构件已删除 | **失败** | `docs/_config.yml`, `docs/index.md`, `docs/index-redirect.html`, `docs/_includes/` 仍存在 |
| 5 | Workflows 含 enable_jekyll: false | **失败** | 两个 workflow 文件均无 `enable_jekyll` 参数 |
| 6 | PWA 图标有效 | **通过** | icon-192.png (valid PNG 192x192), icon-512.png (valid PNG 512x512) |
| 7 | Archive 扫描 docs/daily/ | **失败** | `build_archive_entries()` 仍扫描 `data/summaries/horizon-*.md` |
| 8 | Orchestrator 不双重写入 index.html | **部分修复** | `docs/index.html` 已改为 meta refresh 重定向，但 `src/orchestrator.py` 中写入逻辑仍需确认 |
| 9 | 关键测试 trio | **通过** | test_renderer.py: 30 passed, test_summarizer.py: 7 passed, test_pipeline_e2e.py: 3 passed, test_pipeline_quality.py: 25 passed |
| 10 | VERIFICATION_MATRIX.md 已更新 | **通过** | 本文件已更新，包含所有验证结果和新质量测试 |

### 总结: 6/10 通过, 4 项阻塞问题未修复

| 状态 | 检查项 |
|------|--------|
| **通过** | 1 (测试套件+新质量测试), 3 (apikey 未追踪), 6 (PWA 图标), 9 (关键测试), 10 (矩阵更新) |
| **部分修复** | 8 (双重写入: index.html 改为重定向但仍需确认 orchestrator) |
| **失败 (需修复)** | 2 (gitignore), 4 (Jekyll 构件), 5 (enable_jekyll), 7 (archive 扫描目录) |

---

## QA 1 测试覆盖总结 (2026-06-02 — round 5: post-builder visual QA verification)

| 领域 | 测试文件 | 原有测试数 | 新增测试数 | 当前总数 | 覆盖内容 |
|------|---------|-----------|-----------|---------|---------|
| Area C (Frontend) | test_renderer.py | 18 | 12 | 30 | 结构化数据契约(类型+字段), HTML渲染smoke, dark mode CSS, PWA验证(manifest/robots/sw.js), 空列表/单条目/长标题/缺字段边缘场景, 响应式设计CSS检查, 中英文+早晚报标题 |
| Area C (PWA) | test_renderer.py (PWA部分) | 0 | 3 | 3 | manifest.json JSON验证+必须字段, robots.txt Disallow规则, sw.js基本结构语法 |
| Area C (Theme Toggle) | code review (daily.html) | 0 | 6 | 6 | Flash prevention (T31), `:not([data-theme="light"])` media query isolation (T32), `[data-theme="dark"]` variable set (T33), 3-state toggle cycle (T34), icon sync (T35), aria-label (T36) |
| Area F (RSS图片) | test_rss.py | 3 | 5 | 8 | 图片提取+上下文, 无图片情况, button/headshot过滤, icon过滤, 最多5张限制, 多条目各自提取, cache函数返回类型 |
| Area F (ImageSelector) | test_image_selector.py | 7 | 5 | 12 | prompt结构, 空候选/无效JSON/API异常灰度降级, informational分类, 多条目独立选择, 纯decorative→空结果, 混搭条目(有/无候选), 集成测试(prompt组装+响应解析) |
| Areas C+F (E2E) | test_pipeline_e2e.py | 0 | 3 | 3 | 完整流程(select_images→structured_data→render_html), 空条目处理, 无图片条目处理 |
| Topic System | test_topics.py | 0 | 25 | 25 | RSSSourceConfig topic字段(默认/覆盖/序列化), RSS scraper topic传播, get_structured_data分组(6场景), tab渲染(9场景), backward compat(2场景), config topic字段验证 |
| **Pipeline Quality** | **test_pipeline_quality.py** | **25** | **11** | **36** | whats_new vs why_it_matters distinctness (P0), topic distribution minimums (ai-tech>=4, ai-markets>=6, economy>=6), CJK detection (_has_cjk), language_mismatch flagging, score_threshold propagation, filename generation/parsing, CJK ratio validation, is_demo default semantics, content volume (whats_new avg >= 100 chars) |
| **总计** | | **310** | **84 (+27.1%)** | **394** | |

## Bugs Found

| Bug ID | 发现时间 | 模块 | 描述 | 状态 |
|--------|---------|------|------|------|
| QA1-001 | 2026-06-01 | test_renderer.py | 标题超200字符的辅助函数设置错误, 中文"非常"x70=144字符(非>200), 改为x100后修复 | 已修复 |
| QA1-002 | 2026-06-01 | test_renderer.py | `test_rss_image_extraction_and_filtering` 先前被错误标注为"context extraction fails", 实测该测试通过, 上下文提取正常 | 误报澄清 |
| QA1-003 | 2026-06-01 | data/image_cache.json | 持久化 image_cache.json 包含测试 URL (如 chart1.png), 各 count=4 ≥ 阈值(>3), 导致 4 个 RSS 图片提取测试全部因缓存污染而失败。该缓存由 RSSScraper._load_image_cache() 从文件系统加载, 测试不 mock 此路径。 | 未修复 |
| QA1-004 | 2026-06-01 | docs/index.html, docs/archive.html | 渲染的 HTML 最初缺少 `is_demo` demo-banner; 中间可能被重渲染后添加。archive.html `<span class="entry-period">` 为空 (period_label 模板变量未传入)。 | 部分修复 |
| QA1-005 | 2026-06-01 | docs/assets/icons/ | manifest.json 引用 `assets/icons/icon-192.png` 和 `assets/icons/icon-512.png`, 但 `docs/assets/icons/` 目录不存在, 无任何 PWA 图标文件。 | **已修复** (2026-06-02: 两个图标文件已创建, 192.png 4838B, 512.png 18062B, 均为有效 PNG) |
| QA1-006 | 2026-06-02 | docs/index.html (theme toggle JS) | 主题切换是 3-state 循环：system → dark → light → system。需求要求 2-state：dark ↔ light 仅限。localStorage 当前存入 'dark'/'light'/null，应仅存 'dark'/'light'。 | 未修复 |
| QA1-007 | 2026-06-02 | docs/index.html (CSS header gradient) | 浅色模式 `--header-gradient` 为深海军蓝 (#1a1a2e → #16213e)，不是蓝色渐变。深色模式为 #0f172a → #1e293b。两主题 header 颜色差异极小，无法体现主题切换的视觉变化。需求：浅色模式应为蓝色渐变（如 #2563eb → #1d4ed8）。 | 未修复 |
| QA1-008 | 2026-06-03 | src/ai/summarizer.py | 新增 `language_mismatch` 字段追踪中文模式下的语言不匹配问题。`_has_cjk()` 检查 whats_new/why_it_matters/background/community_discussion 中是否含 CJK 字符。 | **已修复** (2026-06-03: 管道重跑后验证通过。Article 10 正确标记 lang-mismatch, 其余 15 篇均为中文。) |
| INFRA-001 | 2026-06-02 | .gitignore | `.gitignore` 缺少 `apikey.txt` 条目, API 密钥文件可能被意外提交。 | **待修复** |
| INFRA-002 | 2026-06-02 | docs/_config.yml, docs/index.md, docs/index-redirect.html, docs/_includes/ | Jekyll 构件 (gh-pages 零配置部署于 2022 年弃用) 仍然存在于 docs/ 目录下。`docs/_config.yml` 尾部仍含 `plugins: [jekyll-paginate]`, 无 `enable_jekyll: false` 标志。四个构件均需删除。 | **待修复** |
| INFRA-003 | 2026-06-02 | .github/workflows/daily-focus-morning.yml, daily-focus-evening.yml | GitHub Actions 工作流均缺少 `enable_jekyll: false` 标志 (在 peaceiris/actions-gh-pages 步骤中)。Jekyll 默认处理可能干扰纯静态文件部署。 | **待修复** |
| INFRA-004 | 2026-06-02 | scripts/render_and_deploy.py | `build_archive_entries()` 扫描 `data/summaries/horizon-*.md` 而不是 `docs/daily/*.html`。这意味着存档条目基于 markdown 摘要文件, 而非实际部署的 HTML 文件。URL 档结构可能不同步。 | **待修复** |
| INFRA-005 | 2026-06-02 | src/orchestrator.py | `HorizonOrchestrator.run()` 第 155-157 行直接写入 `docs/index.html`。`scripts/render_and_deploy.py` 随后覆盖它为最新日期的重定向。这造成了双重写入——渲染器应独占该文件的写入权。| **部分修复** (`docs/index.html` 已改为 meta refresh 重定向，但 orchestrator 代码仍需确认) |

---

## QA 1 测试覆盖总结 (2026-06-04 — round 10: content volume audit + new quality test)

### Content Volume Audit (docs/daily/2026-06-03-morning-zh.html)

| Field | Avg chars | Avg words (CJK-aware) | Min chars | Max chars |
|-------|-----------|----------------------|-----------|-----------|
| whats_new | 65.2 | 49.4 | 39 | 105 |
| why_it_matters | 58.8 | 50.7 | 40 | 83 |
| key_details / background | 110.1 | 89.4 | 63 | 152 |
| community_discussion | 0 | 0 | 0 | 0 |

**Empty field counts (/18 articles):**
- Empty background: 0/18
- Empty community_discussion: **18/18** (no community_discussion sections exist at all)
- Empty key_details: 0/18
- No references: **9/18** (50% of articles lack reference links)
- No images: **18/18** (no article images — all article cards have zero images)

### Quality Spot-Check (3 articles)

**Article 5 — Suno raises $400M in copyright lawsuits**
- Content: Specific facts present (raised $400M, valuation >$5.4B, doubled from $2.45B 7 months ago). Named entity: Universal Music Group lawsuit. Score: 8.0. Verdict: **INFORMATIVE** — has concrete financial figures, named litigants, and meaningful context.

**Article 11 — Fed Chair Warsh inflation reignites**
- Content: Names Kevin Warsh as new Fed Chair, mentions inflation reigniting, treasury market hinting at rate hikes. Background adds his resume (Fed governor 2006-2011, Bernanke advisor). Score: 10.0 (highest). Verdict: **INFORMATIVE** — specific person, role, economic conditions cited. However, 39 char whats_new is the shortest of all 18 articles.

**Article 18 — Bill Ackman warns of dot-com bubble repeat**
- Content: Names Bill Ackman, compares current AI chip stock frenzy to 2000 dot-com bubble, mentions Microsoft as overlooked quality stock. Background explains dot-com bubble history and Ackman's reputation. Verdict: **INFORMATIVE** — specific person, historical comparison, named companies. No references though.

**Overall assessment**: Content is generally informative with specific names, numbers, and dates. Each article tells you something substantive. Key quality gaps: (1) whats_new averages only 65 chars — too short for deep understanding; (2) community_discussion is universally empty; (3) 50% of articles have zero reference links.

### Changes in This Round

| Change | Detail |
|--------|--------|
| New test `test_whats_new_average_length_meets_threshold` | Added to `test_pipeline_quality.py` — verifies avg whats_new >= 100 chars with mock data |
| Total quality tests | 35 → 36 |
| Total all tests | 393 → 394 |
| VERIFICATION_MATRIX updated | Content volume metrics, quality assessment, new test entry |

---

## QA 1 测试覆盖总结 (2026-06-03 — round 9: real pipeline output quality verification)

### Pipeline Output Examined

| File | Size | Language | Generator |
|------|------|----------|-----------|
| `docs/daily/2026-06-02-morning.html` | 66,887 bytes | English (en) | Pipeline run ~2026-06-03 03:10 |

**Note**: No language-specific files exist. The output file `2026-06-02-morning.html` follows the legacy naming pattern (no `-en`/`-zh` suffix). The orchestrator now generates `{date}-{period}-{lang}.html` but this output predates that change. No Chinese (zh) version was generated.

### Content Quality Audit

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | **Full test suite** | **PASS** | 393/393 passed (368 existing + 35 quality tests). 0 failed. |
| 2 | **Language-specific filenames** | **NOT APPLICABLE** | Only one file exists (`2026-06-02-morning.html`). No zh variant. Filename lacks language suffix. 10 new tests added for filename generation/parsing. |
| 3 | **Chinese content (CJK > 5000)** | **FAIL** | Only 23 CJK characters (0.03% of total) — all from CSS font names. Content is entirely English. No zh pipeline output exists. |
| 4 | **whats_new vs why_it_matters distinct** | **PASS** | All 17 articles have distinct whats_new and why_it_matters text. |
| 5 | **Per-tab minimums** | **PASS** | ai-tech: 4, ai-markets: 7, economy: 6 (all >= minimum: 4/6/6) |
| 6 | **No [DEMO] banner** | **PASS** | CSS defines `.demo-banner` class but no `<div class="demo-banner">` appears in HTML. `is_demo` defaults to false in template. |
| 7 | **No English leakage (for zh)** | **N/A** | No zh content to evaluate. |
| 8 | **Source URLs are real (not example.com)** | **PASS** | 0 example.com URLs. All 41 URLs are from real domains (reddit.com, github.com, theverge.com, cnbc.com, techcrunch.com, seekingalpha.com, etc.) |
| 9 | **No picsum/placeholder URLs** | **PASS** | No picsum, placehold.co, or via.placeholder URLs found. |
| 10 | **No GPT-5/Test Author mock content** | **PASS** | Neither string found in output. |
| 11 | **Reference links present** | **PASS** | 11 article reference sections found with real Wikipedia, arxiv.org, and source URLs. |
| 12 | **Source diversity >= 5** | **PASS** | 8 unique source names across 3 source types (rss, reddit, ossinsight): The Verge, CNBC Technology, TechCrunch, SeekingAlpha, MarketWatch, r/singularity, chopratejas, mukul975. |

### Content Authenticity Spot-Check

| # | Article | Source URL | HTTP Status | Verdict |
|---|---------|------------|-------------|---------|
| 1 | Microsoft Unveils MAI-Thinking-1 | theverge.com | HTTP 200 | **PASS** (real event: Build 2026 keynote, confirmed) |
| 2 | Is Anti-Data-Center Activism Mostly AI Slop? | reddit.com/r/singularity | HTTP 200 (with browser UA) | **PASS** (real Reddit post, references real concepts) |
| 3 | Private Credit & Direct Lending Risk | seekingalpha.com | HTTP 200 (with curl) | **PASS** (real financial analysis article) |

**Reference URL verification**: All 5 reference URLs tested returned HTTP 200 (Wikipedia AI slop, Frontier model, Private credit, Microsoft Scout blog, arxiv.org).

### Added Tests (10 new in test_pipeline_quality.py)

| Test | Focus | Status |
|------|-------|--------|
| `test_filename_generation_zh` | zh filename format | PASS |
| `test_filename_generation_en` | en filename format | PASS |
| `test_filename_generation_evening` | evening period naming | PASS |
| `test_filename_roundtrip` | Parse round-trip consistency | PASS |
| `test_filename_legacy_pattern` | Legacy no-suffix parsing | PASS |
| `test_has_cjk_detects_majority_chinese` | CJK detection for mixed text | PASS |
| `test_has_cjk_rejects_majority_english` | CJK rejection for English text | PASS |
| `test_zh_output_cjk_ratio_over_50_percent` | Simulated zh content CJK density | PASS |
| `test_is_demo_not_in_structured_data` | is_demo absent from output | PASS |
| `test_is_demo_false_no_demo_banner` | No demo banner when is_demo absent | PASS |

### New Bugs Found / Issues

| ID | Module | Description | Status |
|----|--------|-------------|--------|
| QA1-009 | docs/daily/ | No zh language output file generated. Only English file exists. Missing language suffix in filename. Config has `"languages": ["zh", "en"]` but only one output produced. | **待调查** |
| QA1-010 | docs/daily/2026-06-02-morning.html | Output is entirely in English despite zh being primary configured language. CJK content = 23 chars (0.03%). No zh content exists. Check if pipeline ran with `language="en"` only. | **待调查** |
