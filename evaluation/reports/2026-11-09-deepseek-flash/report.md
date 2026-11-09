# 评测报告

运行日期：2026-11-09；题目 115 道（有标准答案的按结果判分，另有 2 道考察拒答）。
实际调用的模型版本：deepseek-flash → deepseek-flash。

## 总体准确率

| 模型 | 配置 | 准确率 | 95% 置信区间 | SQL 报过错 | 自动修正成功 | 平均调用次数 | 平均 tokens | 平均耗时 |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| deepseek-flash | 只给表名和列名，不纠错 | 86.7%（98/113） | 79.2% – 91.8% | 0 题 | 0 题 | 2.0 | 2,400 | 2.6 秒 |
| deepseek-flash | 加上中文字段说明和业务口径 | 97.3%（110/113） | 92.5% – 99.1% | 0 题 | 0 题 | 2.0 | 6,520 | 2.8 秒 |
| deepseek-flash | 再加报错自动修正（线上配置） | 98.2%（111/113） | 93.8% – 99.5% | 0 题 | 0 题 | 2.0 | 6,559 | 2.7 秒 |

## 每一步带来多少提升

同一批题配对比较；p 值来自 McNemar 精确检验，小于 0.05 说明提升不太可能是偶然。

| 模型 | 变化 | 提升 | 改对 | 改错 | p 值 |
| --- | --- | ---: | ---: | ---: | ---: |
| deepseek-flash | 只给表名和列名，不纠错 → 加上中文字段说明和业务口径 | +10.6 个百分点 | 14 | 2 | 0.00418 |
| deepseek-flash | 加上中文字段说明和业务口径 → 再加报错自动修正（线上配置） | +0.9 个百分点 | 1 | 0 | 1 |

注意：deepseek-flash 在“再加报错自动修正（线上配置）”配置下没有一题的 SQL 执行出错，自动修正没有机会起作用，这一行的差别来自模型输出本身的随机波动。

## 按难度（再加报错自动修正（线上配置））

| 模型 | 易 | 中 | 难 |
| --- | ---: | ---: | ---: |
| deepseek-flash | 100.0%（33/33） | 100.0%（54/54） | 92.3%（24/26） |

## 数据里没有的问题：能否如实说明

| 模型 | 配置 | 正确拒答 |
| --- | --- | ---: |
| deepseek-flash | 只给表名和列名，不纠错 | 2/2 |
| deepseek-flash | 加上中文字段说明和业务口径 | 2/2 |
| deepseek-flash | 再加报错自动修正（线上配置） | 2/2 |

## 答错的题（再加报错自动修正（线上配置））

- **deepseek-flash · h02** 2018 年 2 到 8 月里，销售额环比增长最多的是哪个月？　结果和标准答案不一致
  - 模型的 SQL：`WITH m AS ( SELECT strftime(o.purchase_time, '%Y-%m') AS ym, SUM(oi.price) AS gmv FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status NOT IN ('canceled','unavailable') AND o.purchase_time >= TIMESTAMP '2018-01-01' AND o.purchase_time < TIMESTAMP '2018-09-01' GROUP BY 1 ) SEL`
- **deepseek-flash · r02** 差评（1 到 2 分）订单的平均配送天数，比好评（4 到 5 分）订单多几天？　结果和标准答案不一致
  - 模型的 SQL：`WITH r AS ( SELECT order_id, min(score) AS score FROM reviews GROUP BY order_id ), d AS ( SELECT o.order_id, date_diff('day', o.purchase_time, o.delivered_time) AS days FROM orders o WHERE o.delivered_time IS NOT NULL ) SELECT CASE WHEN r.score <= 2 THEN '差评(1-2分)' ELSE '好评(4-5分)' END AS "分组", count`
