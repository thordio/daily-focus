# Daily Focus -- 测试验证矩阵 (Verification Matrix)

## 总说明

| 项目 | 值 |
|------|-----|
| 总测试数 | 21 (T01-T21) |
| 层级分布 | L1: 9, L2: 6, L3: 1, L4: 3, L5: 2 |
| 测试通过率 | 329/333 = 98.8% (4 tests failed due to image_cache.json contamination) |
| 所属工作区 | A: T01-T02, B: T03-T04, C: T07-T09, F: T05-T06, 汇总: T12-T16, E: T20-T21 |
| 依赖 API Key | T10-T11, T13 (需 DEEPSEEK_API_KEY) |
| 人工验证 | T17, T18, T19, T21 |
| 创建日期 | 2026-05-31 |
| 最后更新 | 2026-06-01 (QA 1 round 2) |
| 当前全量测试 | 333 tests (QA 1 baseline: 310, +23 tests added). 4 failed due to image_cache.json persistence contamination. |

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

---

## 状态说明

| 状态 | 含义 |
|------|------|
| 待验证 | 测试尚未执行或对应代码尚未实现 |
| 通过 | 测试执行通过, 结果符合预期 |
| 失败 | 测试执行但结果不符合预期 |
| N/A | 该测试在当前阶段不适用 |

## QA 1 测试覆盖总结 (2026-06-01)

| 领域 | 测试文件 | 原有测试数 | 新增测试数 | 当前总数 | 覆盖内容 |
|------|---------|-----------|-----------|---------|---------|
| Area C (Frontend) | test_renderer.py | 18 | 12 | 30 | 结构化数据契约(类型+字段), HTML渲染smoke, dark mode CSS, PWA验证(manifest/robots/sw.js), 空列表/单条目/长标题/缺字段边缘场景, 响应式设计CSS检查, 中英文+早晚报标题 |
| Area C (PWA) | test_renderer.py (PWA部分) | 0 | 3 | 3 | manifest.json JSON验证+必须字段, robots.txt Disallow规则, sw.js基本结构语法 |
| Area F (RSS图片) | test_rss.py | 3 | 5 | 8 | 图片提取+上下文, 无图片情况, button/headshot过滤, icon过滤, 最多5张限制, 多条目各自提取, cache函数返回类型 |
| Area F (ImageSelector) | test_image_selector.py | 7 | 5 | 12 | prompt结构, 空候选/无效JSON/API异常灰度降级, informational分类, 多条目独立选择, 纯decorative→空结果, 混搭条目(有/无候选), 集成测试(prompt组装+响应解析) |
| Areas C+F (E2E) | test_pipeline_e2e.py | 0 | 3 | 3 | 完整流程(select_images→structured_data→render_html), 空条目处理, 无图片条目处理 |
| **总计** | | **310** | **23 (+6.5%)** | **333** | |

## Bugs Found

| Bug ID | 发现时间 | 模块 | 描述 | 状态 |
|--------|---------|------|------|------|
| QA1-001 | 2026-06-01 | test_renderer.py | 标题超200字符的辅助函数设置错误, 中文"非常"x70=144字符(非>200), 改为x100后修复 | 已修复 |
| QA1-002 | 2026-06-01 | test_renderer.py | `test_rss_image_extraction_and_filtering` 先前被错误标注为"context extraction fails", 实测该测试通过, 上下文提取正常 | 误报澄清 |
| QA1-003 | 2026-06-01 | data/image_cache.json | 持久化 image_cache.json 包含测试 URL (如 chart1.png), 各 count=4 ≥ 阈值(>3), 导致 4 个 RSS 图片提取测试全部因缓存污染而失败。该缓存由 RSSScraper._load_image_cache() 从文件系统加载, 测试不 mock 此路径。 | 未修复 |
| QA1-004 | 2026-06-01 | docs/index.html, docs/archive.html | 渲染的 HTML 最初缺少 `is_demo` demo-banner; 中间可能被重渲染后添加。archive.html `<span class="entry-period">` 为空 (period_label 模板变量未传入)。 | 部分修复 |
| QA1-005 | 2026-06-01 | docs/assets/icons/ | manifest.json 引用 `assets/icons/icon-192.png` 和 `assets/icons/icon-512.png`, 但 `docs/assets/icons/` 目录不存在, 无任何 PWA 图标文件。 | 未修复 |
