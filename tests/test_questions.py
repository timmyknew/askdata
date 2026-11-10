"""题库自检：标准 SQL 都能跑；对结果做“换个写法但意思一样”的变形，比对规则要认；改错一点，要能发现。"""
import pandas as pd
import pytest

from askdata.db import Database
from evaluation.compare import results_match
from evaluation.questions import QUESTIONS
from evaluation.run import OracleModel, gold_frames, grade
from askdata.agent import Agent


@pytest.fixture(scope="module")
def db():
    return Database.olist()


@pytest.fixture(scope="module")
def golds(db):
    return gold_frames(db)


def test_ids_unique_and_fields_present():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids)) and len(ids) >= 100
    for q in QUESTIONS:
        assert q["difficulty"] in {"easy", "medium", "hard"} and q["question"].strip()


def test_every_gold_returns_rows(golds):
    for qid, frames in golds.items():
        for frame in frames:
            assert len(frame) >= 1, qid


def _restyle(frame: pd.DataFrame) -> pd.DataFrame:
    """模型常见的“同义”写法：中文列名、多一列排名、行顺序打乱、小数保留两位。"""
    out = frame.sample(frac=1, random_state=0).reset_index(drop=True)
    out.columns = [f"列{i}" for i in range(len(out.columns))]
    for c in out.columns:
        if pd.api.types.is_float_dtype(out[c]) and out[c].abs().max() >= 1:
            out[c] = out[c].round(2)
    out.insert(0, "排名", range(1, len(out) + 1))
    return out


def test_restyled_answers_still_match(golds):
    for qid, frames in golds.items():
        assert results_match(frames[0], _restyle(frames[0])), qid


def test_wrong_answers_are_caught(golds):
    for qid, frames in golds.items():
        gold = frames[0]
        if len(gold) > 1:
            assert not results_match(gold, gold.iloc[:-1]), f"{qid} 少一行"
        numeric = [c for c in gold.columns if pd.api.types.is_numeric_dtype(gold[c])]
        if numeric and gold[numeric[0]].abs().sum() > 0:
            bad = gold.copy()
            bad[numeric[0]] = bad[numeric[0]] * 1.05 + 1
            assert not results_match(gold, bad), f"{qid} 数值错了"


@pytest.mark.parametrize("qid, sql", [
    ("t01", "SELECT date_trunc('month', purchase_time) AS 月份, count(order_id) AS 订单量 FROM orders "
            "WHERE purchase_time >= '2017-01-01' AND purchase_time < '2018-01-01' GROUP BY 1 ORDER BY 1"),
    ("e04", "SELECT round(100.0 * sum(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) / count(*), 2) AS 取消率 FROM orders"),
    ("j01", "WITH v AS (SELECT * FROM orders WHERE status <> 'canceled' AND status <> 'unavailable') "
            "SELECT p.category AS 类目, round(sum(oi.price), 2) AS 销售额 FROM v JOIN order_items oi ON oi.order_id = v.order_id "
            "JOIN products p ON p.product_id = oi.product_id WHERE p.category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),
    ("d02", "SELECT s.state_name AS 州, round(avg(date_diff('day', o.purchase_time, o.delivered_time)), 1) AS 平均天数 "
            "FROM orders o JOIN customers c ON o.customer_id = c.customer_id JOIN states s ON s.state = c.state "
            "WHERE o.delivered_time IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 1"),
    ("u01", "SELECT round(avg(CASE WHEN n > 1 THEN 1.0 ELSE 0 END), 4) AS 复购率 FROM "
            "(SELECT customer_unique_id, count(*) n FROM orders JOIN customers USING (customer_id) GROUP BY 1)"),
    ("d04", "SELECT round(avg(score) FILTER (WHERE delivered_time::date <= estimated_delivery_date), 2) AS 按时, "
            "round(avg(score) FILTER (WHERE delivered_time::date > estimated_delivery_date), 2) AS 延迟 "
            "FROM orders JOIN reviews USING (order_id) WHERE delivered_time IS NOT NULL"),
    # 下面这些来自真实评测（DeepSeek）里被误判的写法
    ("t04", "SELECT strftime(purchase_time, '%Y-%m') AS 月份, count(*) AS 订单量 FROM orders "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),  # 问“哪个月最多”，给了前 10 名
    ("u02", "SELECT c.customer_unique_id AS 用户, count(*) AS 订单数 FROM orders o JOIN customers c USING (customer_id) "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),
    ("t03", "SELECT '2018-Q' || quarter(purchase_time) AS 季度, count(*) AS 订单量 FROM orders "
            "WHERE year(purchase_time) = 2018 GROUP BY 1 ORDER BY 1"),
    ("t03", "SELECT date_trunc('quarter', purchase_time) AS 季度, COUNT(DISTINCT order_id) AS 订单量 FROM orders "
            "WHERE purchase_time >= '2018-01-01' AND purchase_time < '2019-01-01' GROUP BY 1 ORDER BY 1"),  # GLM 的写法
    ("d07", "SELECT round(avg(date_diff('day', estimated_delivery_date, CAST(delivered_time AS DATE))), 2) AS 平均提前天数 "
            "FROM orders WHERE delivered_time IS NOT NULL"),  # 负数表示提前
    ("j23", "SELECT count(*) AS 件数 FROM order_items i JOIN orders o USING (order_id) JOIN products p USING (product_id) "
            "WHERE p.category = '玩具' AND o.status NOT IN ('canceled', 'unavailable')"),  # 只算有效订单
    ("e26", "SELECT round(100.0 * count(*) FILTER (WHERE comment_title IS NOT NULL OR comment_message IS NOT NULL) "
            "/ count(*), 1) AS 有文字评价占比 FROM reviews"),  # 标题或正文有一个就算
    ("t13", "WITH m AS (SELECT month(purchase_time) AS mon, count(*) AS n FROM orders WHERE purchase_time >= '2018-07-01' "
            "AND purchase_time < '2018-09-01' GROUP BY 1) SELECT max(n) FILTER (WHERE mon = 7) AS 七月, "
            "max(n) FILTER (WHERE mon = 8) AS 八月, round(100.0 * (max(n) FILTER (WHERE mon = 8) "
            "- max(n) FILTER (WHERE mon = 7)) / max(n) FILTER (WHERE mon = 7), 1) AS 变化率 FROM m"),  # 中间数和结果都给
    ("r03", "WITH r AS (SELECT order_id, min(score) AS score FROM reviews GROUP BY 1) SELECT r.score AS 评分, count(*) AS 订单数, "
            "round(avg(date_diff('day', o.purchase_time, o.delivered_time)), 2) AS 平均天数 FROM r JOIN orders o USING (order_id) "
            "WHERE o.delivered_time IS NOT NULL GROUP BY 1 ORDER BY 1"),  # 按订单去重后再分组
    ("h09", "SELECT 96096 AS 用户数, 1796 AS 九十天内复购, 1.9 AS 占比"),  # 第二单要比首单晚（第二轮实测的结果）
])
def test_equivalent_sql_written_differently(db, golds, qid, sql):
    res = db.run(sql)
    assert res.ok, res.error
    assert any(results_match(g, res.data) for g in golds[qid])


@pytest.mark.parametrize("qid, sql", [
    ("e06", "SELECT count(DISTINCT customer_id) FROM customers"),  # 用错了用户 ID
    ("j01", "SELECT p.category, sum(i.price) FROM order_items i JOIN products p USING (product_id) "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 10"),  # 没排除取消订单：金额对不上
    ("t04", "SELECT strftime(purchase_time, '%Y-%m') AS 月份, count(*) FROM orders GROUP BY 1 ORDER BY 1"),  # 答案不在第一行
    ("p05", "SELECT count(*) FROM (SELECT order_id FROM payments GROUP BY order_id HAVING count(*) > 1)"),  # 多笔支付≠多种方式
    ("t13", "SELECT strftime(purchase_time, '%Y-%m') AS 月份, count(*) AS 订单量 FROM orders "
            "WHERE purchase_time >= '2018-07-01' AND purchase_time < '2018-09-01' GROUP BY 1 ORDER BY 1"),  # 只有中间数
    ("h03", "WITH t AS (SELECT p.category, sum(i.price) AS gmv FROM order_items i JOIN orders o USING (order_id) "
            "JOIN products p USING (product_id) WHERE o.status NOT IN ('canceled', 'unavailable') AND p.category IS NOT NULL "
            "GROUP BY 1) SELECT category, round(100.0 * gmv / (SELECT sum(gmv) FROM t), 1) FROM t "
            "ORDER BY gmv DESC LIMIT 5"),  # 分母漏掉了空类目的销售额
    ("r03", "WITH r AS (SELECT order_id, avg(score) AS score FROM reviews GROUP BY 1) SELECT r.score, "
            "avg(date_diff('day', o.purchase_time, o.delivered_time)) FROM r JOIN orders o USING (order_id) "
            "WHERE o.delivered_time IS NOT NULL GROUP BY 1"),  # 平均分去重，出现了 1.5 分这样的档
])
def test_common_mistakes_are_wrong(db, golds, qid, sql):
    res = db.run(sql)
    assert res.ok
    assert not any(results_match(g, res.data) for g in golds[qid])


def test_oracle_scores_full_marks(db, golds):
    agent = Agent(OracleModel(), db)
    for q in QUESTIONS:
        assert grade(q, agent.ask(q["question"]), golds), q["id"]
