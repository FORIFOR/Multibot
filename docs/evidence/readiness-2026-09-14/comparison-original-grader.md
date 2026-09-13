## Attempt ledger
Snapshots must be supplied oldest first; use one grading version per report.

| mode | unique attempts | task/repetition pairs | failed | partial | total list-price estimate |
| --- | --- | --- | --- | --- | --- |
| team | 252 | 150 | 176 | 7 | $111.73 |
| single | 152 | 150 | 0 | 0 | $52.79 |

## Latest attempt per task/repetition
Earlier failed attempts remain included in the ledger above. Completion and programmatic grading are separate measures; neither establishes enterprise reliability.
| mode | runs | completed | correct (grader) | false completion (grader) | failed / partial / error-blocked | mean score | retries | cost mean / p95 | time mean / p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| team | 150 | 69 (46%) | **73 (49%)** | 1 | 76 / 5 / 0 | 0.49 | 14 | $0.73 / $2.38 | 3.5 / 10.5 min |
| single | 150 | 150 (100%) | **146 (97%)** | 4 | 0 / 0 / 0 | 0.99 | 0 | $0.35 / $0.91 | 1.2 / 3.6 min |

## By category
| category | mode | runs | correct | false completion | mean score | cost mean | time mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| analysis | team | 15 | 5 (33%) | 0 | 0.33 | $0.30 | 1.5 min |
| analysis | single | 15 | 15 (100%) | 0 | 1.00 | $0.24 | 0.8 min |
| code | team | 15 | 10 (67%) | 0 | 0.67 | $1.29 | 5.8 min |
| code | single | 15 | 15 (100%) | 0 | 1.00 | $0.43 | 1.5 min |
| customer_support | team | 15 | 5 (33%) | 0 | 0.33 | $0.36 | 1.9 min |
| customer_support | single | 15 | 12 (80%) | 3 | 0.96 | $0.22 | 0.9 min |
| data_transformation | team | 15 | 5 (33%) | 0 | 0.33 | $0.34 | 1.6 min |
| data_transformation | single | 15 | 15 (100%) | 0 | 1.00 | $0.26 | 0.8 min |
| document | team | 15 | 9 (60%) | 1 | 0.65 | $1.16 | 5.5 min |
| document | single | 15 | 14 (93%) | 1 | 0.99 | $0.20 | 0.7 min |
| marketing | team | 15 | 5 (33%) | 0 | 0.33 | $0.42 | 2.6 min |
| marketing | single | 15 | 15 (100%) | 0 | 1.00 | $0.36 | 1.5 min |
| planning | team | 15 | 5 (33%) | 0 | 0.33 | $0.42 | 2.0 min |
| planning | single | 15 | 15 (100%) | 0 | 1.00 | $0.26 | 0.9 min |
| research | team | 15 | 10 (67%) | 0 | 0.67 | $1.37 | 5.8 min |
| research | single | 15 | 15 (100%) | 0 | 1.00 | $0.89 | 3.1 min |
| spreadsheet | team | 15 | 10 (67%) | 0 | 0.67 | $0.92 | 4.6 min |
| spreadsheet | single | 15 | 15 (100%) | 0 | 1.00 | $0.23 | 0.7 min |
| web | team | 15 | 9 (60%) | 0 | 0.60 | $0.76 | 3.5 min |
| web | single | 15 | 15 (100%) | 0 | 1.00 | $0.40 | 1.5 min |

## By task
| task | mode | correct | statuses | failed checks (first run with a failure) | cost mean | time mean |
| --- | --- | --- | --- | --- | --- | --- |
| ana-ab | team | 1/3 | completed, failed, failed | json:ab_result.json (missing or invalid JSON); json:ab_result.json (missing or invalid JSON) | $0.23 | 1.1 min |
| ana-ab | single | 3/3 | completed, completed, completed |  | $0.23 | 0.7 min |
| ana-cohort | team | 1/3 | completed, failed, failed | json:cohort.json (missing or invalid JSON) | $0.35 | 2.1 min |
| ana-cohort | single | 3/3 | completed, completed, completed |  | $0.23 | 0.8 min |
| ana-daily | team | 1/3 | completed, failed, failed | json:analysis.json (missing or invalid JSON); json:analysis.json (missing or invalid JSON) | $0.20 | 0.9 min |
| ana-daily | single | 3/3 | completed, completed, completed |  | $0.22 | 0.7 min |
| ana-logs | team | 1/3 | completed, failed, failed | json:error_rates.json (missing or invalid JSON) | $0.42 | 2.0 min |
| ana-logs | single | 3/3 | completed, completed, completed |  | $0.33 | 1.1 min |
| ana-survey | team | 1/3 | completed, failed, failed | json:counts.json (missing or invalid JSON) | $0.28 | 1.4 min |
| ana-survey | single | 3/3 | completed, completed, completed |  | $0.19 | 0.5 min |
| code-csv-stats | team | 2/3 | completed, completed, failed | exists:csv_stats.py; exists:test_csv_stats.py; hidden_tests:csv_stats.py (missing module) | $1.17 | 5.6 min |
| code-csv-stats | single | 3/3 | completed, completed, completed |  | $0.37 | 1.3 min |
| code-lru | team | 2/3 | completed, completed, failed | exists:lru_cache.py; exists:test_lru_cache.py; hidden_tests:lru_cache.py (missing module) | $0.89 | 4.1 min |
| code-lru | single | 3/3 | completed, completed, completed |  | $0.41 | 1.5 min |
| code-roman | team | 2/3 | completed, completed, failed | exists:roman.py; exists:test_roman.py; hidden_tests:roman.py (missing module) | $1.84 | 7.6 min |
| code-roman | single | 3/3 | completed, completed, completed |  | $0.29 | 1.0 min |
| code-slugify | team | 2/3 | completed, completed, failed | exists:slugify.py; exists:test_slugify.py; hidden_tests:slugify.py (missing module) | $0.96 | 4.7 min |
| code-slugify | single | 3/3 | completed, completed, completed |  | $0.28 | 0.9 min |
| code-wc-plus | team | 2/3 | completed, completed, failed | exists:wc_plus.py; exists:test_wc_plus.py; exists:README.md; hidden_tests:wc_plus.py (missing module) | $1.57 | 6.8 min |
| code-wc-plus | single | 3/3 | completed, completed, completed |  | $0.80 | 2.9 min |
| cs-classify | team | 1/3 | completed, failed, failed | json:classification.json (missing/invalid) | $0.30 | 1.6 min |
| cs-classify | single | 3/3 | completed, completed, completed |  | $0.21 | 0.7 min |
| cs-escalation | team | 1/3 | completed, failed, failed | exists:summary.md; regex:summary.md:経緯 (missing file); regex:summary.md:現状 (missing file); regex:summary.md:次のアクション (missing file); regex:summary.md:5522 (missi | $0.35 | 1.8 min |
| cs-escalation | single | 3/3 | completed, completed, completed |  | $0.23 | 0.8 min |
| cs-macros | team | 1/3 | completed, failed, failed | exists:macros.md; regex:macros.md:^##\s (missing file); regex:macros.md:\{\{name\}\} (missing file); regex:macros.md:14\s*日 (missing file); not_regex:macros.md: | $0.46 | 2.7 min |
| cs-macros | single | 3/3 | completed, completed, completed |  | $0.27 | 1.2 min |
| cs-policy-answer | team | 1/3 | completed, failed, failed | exists:answer.md; regex:answer.md:14\s*日 (missing file); regex:answer.md:5\s*営業日 (missing file); regex:answer.md:元の(?:お)?支払い方法|同じ(?:お)?支払い方法|お支 (missing file);  | $0.33 | 1.6 min |
| cs-policy-answer | single | 0/3 | completed, completed, completed | regex:answer.md:元の支払い方法|同じ支払い方法 (0 matches) | $0.20 | 0.7 min |
| cs-replies | team | 1/3 | completed, failed, failed | exists:replies.md; regex:replies.md:^##\s*T-101 (missing file); regex:replies.md:^##\s*T-102 (missing file); regex:replies.md:^##\s*T-103 (missing file); regex: | $0.37 | 2.0 min |
| cs-replies | single | 3/3 | completed, completed, completed |  | $0.22 | 1.0 min |
| doc-email | team | 1/3 | completed, completed, failed | regex:email.md:A\s*社|株式会社\s*A|貴社|御社 (0 matches) | $1.72 | 8.4 min |
| doc-email | single | 2/3 | completed, completed, completed | regex:email.md:A社|A 社 (0 matches) | $0.21 | 0.9 min |
| doc-faq | team | 2/3 | completed, completed, failed | exists:faq.md; regex:faq.md:^\s*(?:#+\s*)?(?:\*\*)?Q[:：] (missing file); regex:faq.md:^\s*(?:\*\*)?A[:：] (missing file); regex:faq.md:PDF (missing file); regex: | $0.64 | 3.1 min |
| doc-faq | single | 3/3 | completed, completed, completed |  | $0.21 | 0.7 min |
| doc-jd | team | 2/3 | completed, completed, failed | exists:jd.md; regex:jd.md:業務内容 (missing file); regex:jd.md:必須要件 (missing file); regex:jd.md:歓迎要件 (missing file); regex:jd.md:Docker (missing file); not_regex:jd | $0.69 | 3.6 min |
| doc-jd | single | 3/3 | completed, completed, completed |  | $0.23 | 0.9 min |
| doc-minutes | team | 2/3 | completed, completed, failed | exists:minutes.md; regex:minutes.md:決定事項 (missing file); regex:minutes.md:TODO (missing file); regex:minutes.md:次回 (missing file); regex:minutes.md:9/16|9月16日|2 | $0.95 | 4.5 min |
| doc-minutes | single | 3/3 | completed, completed, completed |  | $0.17 | 0.6 min |
| doc-release-notes | team | 2/3 | partial, partial, failed | exists:release-notes.md; regex:release-notes.md:新機能 (missing file); regex:release-notes.md:修正 (missing file); regex:release-notes.md:\(a1\) (missing file); rege | $1.81 | 7.9 min |
| doc-release-notes | single | 3/3 | completed, completed, completed |  | $0.17 | 0.4 min |
| mkt-ads | team | 1/3 | completed, failed, failed | json:ads.json (missing/invalid) | $0.38 | 2.0 min |
| mkt-ads | single | 3/3 | completed, completed, completed |  | $0.20 | 0.7 min |
| mkt-lp-posts | team | 1/3 | completed, failed, failed | exists:index.html; regex:index.html:<title> (missing file); regex:index.html:viewport (missing file); exists:posts.md; regex:posts.md:^\s*(?:##|\d+\.|[-*])\s (m | $0.65 | 3.5 min |
| mkt-lp-posts | single | 3/3 | completed, completed, completed |  | $0.93 | 4.3 min |
| mkt-newsletter | team | 1/3 | completed, failed, failed | exists:newsletter.md; regex:newsletter.md:\A\s*件名[:：] (missing file); regex:newsletter.md:\{\{CTA_URL\}\} (missing file); not_regex:newsletter.md:https?:// (mis | $0.44 | 3.9 min |
| mkt-newsletter | single | 3/3 | completed, completed, completed |  | $0.26 | 1.0 min |
| mkt-press | team | 1/3 | completed, failed, failed | exists:press.md; regex:press.md:株式会社ホシノ (missing file); regex:press.md:2026年10月1日|2026-10-01 (missing file); regex:press.md:pr@hoshino\.example (missing file);  | $0.30 | 1.6 min |
| mkt-press | single | 3/3 | completed, completed, completed |  | $0.19 | 0.6 min |
| mkt-x-posts | team | 1/3 | completed, failed, failed | json:posts.json (missing/invalid) | $0.35 | 2.1 min |
| mkt-x-posts | single | 3/3 | completed, completed, completed |  | $0.25 | 0.9 min |
| plan-agenda | team | 1/3 | completed, failed, failed | json:agenda.json (missing/invalid) | $0.32 | 1.6 min |
| plan-agenda | single | 3/3 | completed, completed, completed |  | $0.18 | 0.6 min |
| plan-milestones | team | 1/3 | completed, failed, failed | json:plan.json (missing/invalid) | $0.39 | 1.9 min |
| plan-milestones | single | 3/3 | completed, completed, completed |  | $0.27 | 0.9 min |
| plan-okr | team | 1/3 | completed, failed, failed | json:okr.json (missing/invalid) | $0.29 | 1.5 min |
| plan-okr | single | 3/3 | completed, completed, completed |  | $0.19 | 0.6 min |
| plan-risks | team | 1/3 | completed, failed, failed | json:risks.json (missing/invalid) | $0.38 | 2.0 min |
| plan-risks | single | 3/3 | completed, completed, completed |  | $0.27 | 1.3 min |
| plan-schedule | team | 1/3 | completed, failed, failed | json:schedule.json (missing/invalid) | $0.69 | 3.0 min |
| plan-schedule | single | 3/3 | completed, completed, completed |  | $0.37 | 1.3 min |
| research-3repos | team | 2/3 | completed, completed, failed | exists:research.md; regex:research.md:github\.com/langchain-ai/deepa (missing file); regex:research.md:github\.com/bytedance/deer-flo (missing file); regex:rese | $1.28 | 5.2 min |
| research-3repos | single | 3/3 | completed, completed, completed |  | $0.94 | 3.2 min |
| research-changelog | team | 2/3 | completed, completed, failed | exists:changelog-types.md; regex:changelog-types.md:keepachangelog\.com (missing file); regex:changelog-types.md:\bAdded\b (missing file); regex:changelog-types | $0.63 | 2.7 min |
| research-changelog | single | 3/3 | completed, completed, completed |  | $0.43 | 1.3 min |
| research-py313 | team | 2/3 | completed, failed, completed | exists:whatsnew.md; regex:whatsnew.md:docs\.python\.org/3/whatsnew/3 (missing file); regex:whatsnew.md:free.threaded|フリースレッド|GIL (missing file); regex:whatsnew. | $1.23 | 5.1 min |
| research-py313 | single | 3/3 | completed, completed, completed |  | $0.57 | 2.1 min |
| research-rfc8259 | team | 2/3 | completed, completed, failed | exists:json-spec.md; regex:json-spec.md:rfc-editor\.org/rfc/rfc8259|rf (missing file); regex:json-spec.md:\bnull\b (missing file); regex:json-spec.md:\bfalse\b  | $2.50 | 11.0 min |
| research-rfc8259 | single | 3/3 | completed, completed, completed |  | $2.12 | 7.5 min |
| research-uv | team | 2/3 | completed, completed, failed | exists:uv-guide.md; regex:uv-guide.md:docs\.astral\.sh/uv (missing file); regex:uv-guide.md:\buvx\b|uv tool run (missing file); regex:uv-guide.md:uv pip (missin | $1.20 | 5.1 min |
| research-uv | single | 3/3 | completed, completed, completed |  | $0.38 | 1.4 min |
| sheet-attendance | team | 2/3 | completed, completed, failed | json:attendance.json (missing or invalid JSON) | $0.77 | 4.8 min |
| sheet-attendance | single | 3/3 | completed, completed, completed |  | $0.21 | 0.7 min |
| sheet-dedupe | team | 2/3 | completed, completed, failed | csv:contacts_unique.csv (missing/invalid) | $0.94 | 4.3 min |
| sheet-dedupe | single | 3/3 | completed, completed, completed |  | $0.25 | 0.8 min |
| sheet-join | team | 2/3 | completed, completed, failed | csv:orders_enriched.csv (missing/invalid) | $1.00 | 5.5 min |
| sheet-join | single | 3/3 | completed, completed, completed |  | $0.28 | 0.8 min |
| sheet-sales-totals | team | 2/3 | completed, completed, failed | csv:summary.csv (missing/invalid) | $0.70 | 3.2 min |
| sheet-sales-totals | single | 3/3 | completed, completed, completed |  | $0.22 | 0.6 min |
| sheet-top3 | team | 2/3 | completed, completed, failed | json:top3.json (missing or invalid JSON) | $1.19 | 5.0 min |
| sheet-top3 | single | 3/3 | completed, completed, completed |  | $0.20 | 0.6 min |
| web-404 | team | 1/3 | completed, failed, failed | html:index.html (missing); html:404.html (missing); exists:styles.css; internal_links (index.html: missing; 404.html: missing); regex:404.html:href="(?:\./)?ind | $0.54 | 2.4 min |
| web-404 | single | 3/3 | completed, completed, completed |  | $0.38 | 1.4 min |
| web-a11y | team | 2/3 | completed, partial, failed | html:about.html (missing); a11y:lang_ja; a11y:one_h1; a11y:img_alt (0 imgs) | $0.65 | 3.1 min |
| web-a11y | single | 3/3 | completed, completed, completed |  | $0.39 | 1.7 min |
| web-contact-form | team | 2/3 | completed, partial, failed | html:index.html (missing); regex:index.html:<form (missing file); regex:index.html:<label (missing file); regex:index.html:type="email" (missing file); regex:in | $0.78 | 3.6 min |
| web-contact-form | single | 3/3 | completed, completed, completed |  | $0.35 | 1.4 min |
| web-docs-site | team | 2/3 | completed, completed, failed | html:index.html (missing); html:docs/getting-started.html (missing); html:docs/faq.html (missing); exists:styles.css; internal_links (index.html: missing; docs/ | $1.15 | 4.9 min |
| web-docs-site | single | 3/3 | completed, completed, completed |  | $0.63 | 2.3 min |
| web-pricing | team | 2/3 | completed, partial, failed | html:pricing.html (missing); regex:pricing.html:Free (missing file); regex:pricing.html:Team (missing file); regex:pricing.html:Enterprise (missing file); regex | $0.69 | 3.2 min |
| web-pricing | single | 3/3 | completed, completed, completed |  | $0.25 | 0.8 min |
| xform-csv-to-json | team | 1/3 | completed, failed, failed | json:inventory.json (missing or invalid JSON) | $0.31 | 1.5 min |
| xform-csv-to-json | single | 3/3 | completed, completed, completed |  | $0.30 | 1.0 min |
| xform-dates | team | 1/3 | completed, failed, failed | json:dates.json (missing or invalid JSON) | $0.55 | 2.6 min |
| xform-dates | single | 3/3 | completed, completed, completed |  | $0.29 | 1.0 min |
| xform-flatten | team | 1/3 | completed, failed, failed | json:flat.json (missing or invalid JSON) | $0.43 | 2.0 min |
| xform-flatten | single | 3/3 | completed, completed, completed |  | $0.22 | 0.7 min |
| xform-json-to-csv | team | 1/3 | completed, failed, failed | csv:people.csv (missing/invalid) | $0.26 | 1.3 min |
| xform-json-to-csv | single | 3/3 | completed, completed, completed |  | $0.28 | 0.8 min |
| xform-md-table | team | 1/3 | completed, failed, failed | json:cities.json (missing or invalid JSON) | $0.12 | 0.7 min |
| xform-md-table | single | 3/3 | completed, completed, completed |  | $0.19 | 0.5 min |
