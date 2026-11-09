"""评测题库：每题一个中文问题和一条标准 SQL（gold），按查询结果判对错。

约定
- gold 只返回回答问题必需的列；模型多返回几列（比如顺带给出数量）不算错。
- 行的顺序不比较；排行题比较的是“前 N 名是哪些”。
- alt 是同样合理的其他口径（比如按日期还是按时间戳判断延迟），命中任意一个就算对。
- 难度：easy 单表；medium 多表关联或时间处理；hard 子查询、窗口函数或多步计算。
"""

VALID = "status NOT IN ('canceled', 'unavailable')"  # 有效订单，见 askdata/datasets.py 的业务口径

QUESTIONS: list[dict] = [
    # ---------------- 基础统计（单表）----------------
    dict(id="e01", difficulty="easy", topic="订单", question="一共有多少个订单？",
         gold="SELECT count(*) FROM orders"),
    dict(id="e02", difficulty="easy", topic="订单", question="已经送达的订单有多少个？",
         gold="SELECT count(*) FROM orders WHERE status = 'delivered'"),
    dict(id="e03", difficulty="easy", topic="订单", question="各个订单状态分别有多少个订单？",
         gold="SELECT status, count(*) FROM orders GROUP BY status"),
    dict(id="e04", difficulty="easy", topic="订单", question="被取消的订单占全部订单的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE status = 'canceled') / count(*) FROM orders"),
    dict(id="e05", difficulty="easy", topic="卖家", question="平台上一共有多少个卖家？",
         gold="SELECT count(*) FROM sellers"),
    dict(id="e06", difficulty="easy", topic="用户", question="平台一共有多少个不重复的用户？",
         gold="SELECT count(DISTINCT customer_unique_id) FROM customers"),
    dict(id="e07", difficulty="easy", topic="商品", question="商品表里一共有多少个商品？",
         gold="SELECT count(*) FROM products"),
    dict(id="e08", difficulty="easy", topic="商品", question="一共有多少个商品类目？",
         gold="SELECT count(DISTINCT category) FROM products"),
    dict(id="e09", difficulty="easy", topic="商品", question="商品数量最多的 5 个类目是哪些？各有多少个商品？",
         gold="SELECT category, count(*) FROM products WHERE category IS NOT NULL "
              "GROUP BY category ORDER BY count(*) DESC LIMIT 5"),
    dict(id="e10", difficulty="easy", topic="商品", question="订单明细里，单价最高的商品卖多少钱？",
         gold="SELECT max(price) FROM order_items"),
    dict(id="e11", difficulty="easy", topic="商品", question="订单明细里商品的平均单价是多少？",
         gold="SELECT avg(price) FROM order_items"),
    dict(id="e12", difficulty="easy", topic="物流", question="平均每件商品分摊的运费是多少？",
         gold="SELECT avg(freight_value) FROM order_items"),
    dict(id="e13", difficulty="easy", topic="支付", question="各种支付方式分别有多少笔支付记录？",
         gold="SELECT payment_type, count(*) FROM payments GROUP BY payment_type"),
    dict(id="e14", difficulty="easy", topic="支付", question="用信用卡支付的记录，平均分几期？",
         gold="SELECT avg(installments) FROM payments WHERE payment_type = 'credit_card'"),
    dict(id="e15", difficulty="easy", topic="支付", question="分期最多的一笔支付分了多少期？",
         gold="SELECT max(installments) FROM payments"),
    dict(id="e16", difficulty="easy", topic="评价", question="所有评价的平均分是多少？",
         gold="SELECT avg(score) FROM reviews"),
    dict(id="e17", difficulty="easy", topic="评价", question="1 到 5 分每个评分各有多少条评价？",
         gold="SELECT score, count(*) FROM reviews GROUP BY score"),
    dict(id="e18", difficulty="easy", topic="评价", question="5 分好评占全部评价的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE score = 5) / count(*) FROM reviews"),
    dict(id="e19", difficulty="easy", topic="卖家", question="卖家数量最多的 5 个州是哪些？各有多少个卖家？",
         gold="SELECT state, count(*) FROM sellers GROUP BY state ORDER BY count(*) DESC LIMIT 5",
         alt=["SELECT st.state_name, count(*) FROM sellers s JOIN states st USING (state) "
              "GROUP BY st.state_name ORDER BY count(*) DESC LIMIT 5"]),
    dict(id="e20", difficulty="easy", topic="用户", question="用户最多的城市是哪个？",
         gold="SELECT city FROM customers GROUP BY city ORDER BY count(DISTINCT customer_unique_id) DESC LIMIT 1"),
    dict(id="e21", difficulty="easy", topic="订单", question="2018 年一共有多少个订单？",
         gold="SELECT count(*) FROM orders WHERE year(purchase_time) = 2018"),
    dict(id="e22", difficulty="easy", topic="订单", question="数据里最早的一笔订单是什么时候下的？",
         gold="SELECT min(purchase_time) FROM orders"),
    dict(id="e23", difficulty="easy", topic="订单", question="在有商品明细的订单里，平均每个订单有几件商品？",
         gold="SELECT count(*) / count(DISTINCT order_id) FROM order_items"),
    dict(id="e24", difficulty="easy", topic="商品", question="重量超过 10 公斤的商品有多少个？",
         gold="SELECT count(*) FROM products WHERE weight_g > 10000"),
    dict(id="e25", difficulty="easy", topic="商品", question="商品平均有几张图片？",
         gold="SELECT avg(photos_qty) FROM products"),
    dict(id="e26", difficulty="easy", topic="评价", question="有文字评价内容的评价占全部评价的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE comment_message IS NOT NULL AND trim(comment_message) <> '') "
              "/ count(*) FROM reviews",
         alt=["SELECT 100.0 * count(comment_message) / count(*) FROM reviews"]),
    dict(id="e27", difficulty="easy", topic="卖家", question="卖家最多的城市是哪个？",
         gold="SELECT city FROM sellers GROUP BY city ORDER BY count(*) DESC LIMIT 1"),

    # ---------------- 时间趋势 ----------------
    dict(id="t01", difficulty="medium", topic="趋势", question="2017 年每个月的订单量是多少？",
         gold="SELECT strftime(purchase_time, '%Y-%m') AS m, count(*) FROM orders "
              "WHERE year(purchase_time) = 2017 GROUP BY m"),
    dict(id="t02", difficulty="medium", topic="趋势", question="每一年分别有多少个订单？",
         gold="SELECT year(purchase_time) AS y, count(*) FROM orders GROUP BY y"),
    dict(id="t03", difficulty="medium", topic="趋势", question="2018 年每个季度（1 到 4 季度）的订单量是多少？",
         gold="SELECT quarter(purchase_time) AS q, count(*) FROM orders WHERE year(purchase_time) = 2018 GROUP BY q"),
    dict(id="t04", difficulty="medium", topic="趋势", question="订单量最多的是哪个月份？",
         gold="SELECT strftime(purchase_time, '%Y-%m') AS m FROM orders GROUP BY m ORDER BY count(*) DESC LIMIT 1"),
    dict(id="t05", difficulty="medium", topic="趋势", question="一天里哪个小时下单的人最多？",
         gold="SELECT hour(purchase_time) AS h FROM orders GROUP BY h ORDER BY count(*) DESC LIMIT 1"),
    dict(id="t06", difficulty="medium", topic="趋势", question="2017 年 11 月 24 日（黑色星期五）当天有多少个订单？",
         gold="SELECT count(*) FROM orders WHERE CAST(purchase_time AS DATE) = DATE '2017-11-24'"),
    dict(id="t07", difficulty="medium", topic="销售", question="2017 年全年的销售额是多少？",
         gold=f"SELECT sum(i.price) FROM order_items i JOIN orders o USING (order_id) "
              f"WHERE year(o.purchase_time) = 2017 AND o.{VALID}"),
    dict(id="t08", difficulty="medium", topic="趋势", question="2018 年上半年（1 到 6 月）一共有多少个订单？",
         gold="SELECT count(*) FROM orders WHERE purchase_time >= '2018-01-01' AND purchase_time < '2018-07-01'"),
    dict(id="t09", difficulty="medium", topic="销售", question="2018 年 1 到 8 月每个月的销售额是多少？",
         gold=f"SELECT strftime(o.purchase_time, '%Y-%m') AS m, sum(i.price) FROM order_items i "
              f"JOIN orders o USING (order_id) WHERE o.purchase_time >= '2018-01-01' "
              f"AND o.purchase_time < '2018-09-01' AND o.{VALID} GROUP BY m"),
    dict(id="t10", difficulty="medium", topic="趋势", question="2017 年哪个月被取消的订单最多？",
         gold="SELECT strftime(purchase_time, '%Y-%m') AS m FROM orders WHERE status = 'canceled' "
              "AND year(purchase_time) = 2017 GROUP BY m ORDER BY count(*) DESC LIMIT 1"),
    dict(id="t11", difficulty="medium", topic="物流", question="2018 年 1 到 8 月每个月下单的订单，平均配送天数是多少？",
         gold="SELECT strftime(purchase_time, '%Y-%m') AS m, avg(date_diff('day', purchase_time, delivered_time)) "
              "FROM orders WHERE delivered_time IS NOT NULL AND purchase_time >= '2018-01-01' "
              "AND purchase_time < '2018-09-01' GROUP BY m"),
    dict(id="t12", difficulty="medium", topic="评价", question="按下单年份统计，每年订单的平均评分是多少？",
         gold="SELECT year(o.purchase_time) AS y, avg(r.score) FROM reviews r JOIN orders o USING (order_id) GROUP BY y"),
    dict(id="t13", difficulty="hard", topic="趋势", question="2018 年 8 月的订单量比 7 月变化了百分之多少？",
         gold="SELECT 100.0 * (count(*) FILTER (WHERE month(purchase_time) = 8) - count(*) FILTER (WHERE month(purchase_time) = 7)) "
              "/ count(*) FILTER (WHERE month(purchase_time) = 7) FROM orders WHERE year(purchase_time) = 2018"),
    dict(id="t14", difficulty="hard", topic="销售", question="2018 年 1 到 8 月的销售额，比 2017 年 1 到 8 月增长了百分之多少？",
         gold=f"WITH s AS (SELECT year(o.purchase_time) AS y, sum(i.price) AS gmv FROM order_items i "
              f"JOIN orders o USING (order_id) WHERE month(o.purchase_time) <= 8 AND o.{VALID} GROUP BY y) "
              f"SELECT 100.0 * (max(gmv) FILTER (WHERE y = 2018) / max(gmv) FILTER (WHERE y = 2017) - 1) FROM s"),
    dict(id="t15", difficulty="hard", topic="用户", question="2017 年每个月有多少新用户（第一次下单的用户）？",
         gold="WITH f AS (SELECT c.customer_unique_id, min(o.purchase_time) AS first_time FROM orders o "
              "JOIN customers c USING (customer_id) GROUP BY 1) "
              "SELECT strftime(first_time, '%Y-%m') AS m, count(*) FROM f WHERE year(first_time) = 2017 GROUP BY m"),
    dict(id="t16", difficulty="hard", topic="销售", question="2018 年 1 到 8 月，每个月的平均订单金额是多少？订单金额按商品价格合计，不含运费。",
         gold=f"WITH t AS (SELECT o.order_id, strftime(o.purchase_time, '%Y-%m') AS m, sum(i.price) AS amount "
              f"FROM order_items i JOIN orders o USING (order_id) WHERE o.purchase_time >= '2018-01-01' "
              f"AND o.purchase_time < '2018-09-01' AND o.{VALID} GROUP BY 1, 2) SELECT m, avg(amount) FROM t GROUP BY m"),

    # ---------------- 多表关联：类目、地区、卖家 ----------------
    dict(id="j01", difficulty="medium", topic="销售", question="销售额最高的 10 个商品类目是哪些？销售额分别是多少？",
         gold=f"SELECT p.category, sum(i.price) FROM order_items i JOIN products p USING (product_id) "
              f"JOIN orders o USING (order_id) WHERE o.{VALID} AND p.category IS NOT NULL "
              f"GROUP BY p.category ORDER BY 2 DESC LIMIT 10"),
    dict(id="j02", difficulty="medium", topic="商品", question="订单明细里出现次数最多的 5 个商品类目是哪些？各出现多少次？",
         gold="SELECT p.category, count(*) FROM order_items i JOIN products p USING (product_id) "
              "WHERE p.category IS NOT NULL GROUP BY p.category ORDER BY 2 DESC LIMIT 5"),
    dict(id="j03", difficulty="medium", topic="商品", question="“家具装饰”类目商品在订单明细里的平均单价是多少？",
         gold="SELECT avg(i.price) FROM order_items i JOIN products p USING (product_id) WHERE p.category = '家具装饰'"),
    dict(id="j04", difficulty="medium", topic="物流", question="哪个商品类目的平均运费最高？",
         gold="SELECT p.category FROM order_items i JOIN products p USING (product_id) WHERE p.category IS NOT NULL "
              "GROUP BY p.category ORDER BY avg(i.freight_value) DESC LIMIT 1"),
    dict(id="j05", difficulty="medium", topic="用户", question="用户最多的 5 个州是哪些？各有多少个用户？",
         gold="SELECT state, count(DISTINCT customer_unique_id) FROM customers GROUP BY state ORDER BY 2 DESC LIMIT 5",
         alt=["SELECT st.state_name, count(DISTINCT c.customer_unique_id) FROM customers c JOIN states st USING (state) "
              "GROUP BY st.state_name ORDER BY 2 DESC LIMIT 5"]),
    dict(id="j06", difficulty="medium", topic="地区", question="圣保罗州的用户下的订单，占全部订单的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE c.state = 'SP') / count(*) FROM orders o JOIN customers c USING (customer_id)"),
    dict(id="j07", difficulty="medium", topic="地区", question="里约热内卢州的用户一共下了多少个订单？",
         gold="SELECT count(*) FROM orders o JOIN customers c USING (customer_id) WHERE c.state = 'RJ'"),
    dict(id="j08", difficulty="medium", topic="地区", question="东南部大区的订单占全部订单的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE s.region = '东南部') / count(*) FROM orders o "
              "JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state"),
    dict(id="j09", difficulty="medium", topic="地区", question="巴西五个大区的销售额分别是多少？",
         gold=f"SELECT s.region, sum(i.price) FROM order_items i JOIN orders o USING (order_id) "
              f"JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state WHERE o.{VALID} GROUP BY s.region"),
    dict(id="j10", difficulty="medium", topic="卖家", question="销售额最高的卖家是哪个？给出卖家 ID。",
         gold=f"SELECT i.seller_id FROM order_items i JOIN orders o USING (order_id) WHERE o.{VALID} "
              f"GROUP BY i.seller_id ORDER BY sum(i.price) DESC LIMIT 1"),
    dict(id="j11", difficulty="hard", topic="卖家", question="有多少个卖家的销售额超过了 10 万？",
         gold=f"SELECT count(*) FROM (SELECT i.seller_id FROM order_items i JOIN orders o USING (order_id) "
              f"WHERE o.{VALID} GROUP BY i.seller_id HAVING sum(i.price) > 100000)"),
    dict(id="j12", difficulty="medium", topic="商品", question="“电脑配件”类目里，订单明细中单价最高的是哪个商品？给出商品 ID。",
         gold="SELECT i.product_id FROM order_items i JOIN products p USING (product_id) "
              "WHERE p.category = '电脑配件' ORDER BY i.price DESC LIMIT 1"),
    dict(id="j13", difficulty="easy", topic="卖家", question="哪个州的卖家最多？",
         gold="SELECT state FROM sellers GROUP BY state ORDER BY count(*) DESC LIMIT 1",
         alt=["SELECT st.state_name FROM sellers s JOIN states st USING (state) GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"]),
    dict(id="j14", difficulty="medium", topic="卖家", question="平均每个卖家卖出了多少件商品？",
         gold="SELECT count(*) / count(DISTINCT seller_id) FROM order_items"),
    dict(id="j15", difficulty="medium", topic="销售", question="“美妆健康”类目 2018 年 1 到 8 月每个月的销售额是多少？",
         gold=f"SELECT strftime(o.purchase_time, '%Y-%m') AS m, sum(i.price) FROM order_items i "
              f"JOIN orders o USING (order_id) JOIN products p USING (product_id) WHERE p.category = '美妆健康' "
              f"AND o.purchase_time >= '2018-01-01' AND o.purchase_time < '2018-09-01' AND o.{VALID} GROUP BY m"),
    dict(id="j16", difficulty="hard", topic="地区", question="订单明细中，买家和卖家在同一个州的占百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE c.state = s.state) / count(*) FROM order_items i "
              "JOIN orders o USING (order_id) JOIN customers c USING (customer_id) JOIN sellers s USING (seller_id)"),
    dict(id="j17", difficulty="medium", topic="支付", question="最常用的支付方式是哪种？这种方式的平均支付金额是多少？",
         gold="SELECT payment_type, avg(payment_value) FROM payments WHERE payment_type = "
              "(SELECT payment_type FROM payments GROUP BY 1 ORDER BY count(*) DESC LIMIT 1) GROUP BY payment_type"),
    dict(id="j18", difficulty="medium", topic="支付", question="支付金额合计最高的订单是哪个？给出订单 ID。",
         gold="SELECT order_id FROM payments GROUP BY order_id ORDER BY sum(payment_value) DESC LIMIT 1"),
    dict(id="j19", difficulty="easy", topic="支付", question="每种支付方式的平均支付金额是多少？",
         gold="SELECT payment_type, avg(payment_value) FROM payments GROUP BY payment_type"),
    dict(id="j20", difficulty="easy", topic="支付", question="用代金券支付过的订单有多少个？",
         gold="SELECT count(DISTINCT order_id) FROM payments WHERE payment_type = 'voucher'"),
    dict(id="j21", difficulty="medium", topic="商品", question="商品重量和运费的相关系数是多少？按订单明细计算。",
         gold="SELECT corr(p.weight_g, i.freight_value) FROM order_items i JOIN products p USING (product_id)"),
    dict(id="j22", difficulty="medium", topic="地区", question="用户最多的大区是哪个？",
         gold="SELECT s.region FROM customers c JOIN states s USING (state) GROUP BY s.region "
              "ORDER BY count(DISTINCT c.customer_unique_id) DESC LIMIT 1"),
    dict(id="j23", difficulty="medium", topic="商品", question="“玩具”类目一共卖出了多少件？",
         gold="SELECT count(*) FROM order_items i JOIN products p USING (product_id) WHERE p.category = '玩具'"),
    dict(id="j24", difficulty="medium", topic="卖家", question="圣保罗州的卖家一共有多少个？",
         gold="SELECT count(*) FROM sellers WHERE state = 'SP'"),

    # ---------------- 用户与复购 ----------------
    dict(id="u01", difficulty="medium", topic="用户", question="下过 2 单及以上的复购用户占全部用户的百分之多少？",
         gold="WITH u AS (SELECT c.customer_unique_id, count(*) AS n FROM orders o JOIN customers c USING (customer_id) "
              "GROUP BY 1) SELECT 100.0 * count(*) FILTER (WHERE n >= 2) / count(*) FROM u"),
    dict(id="u02", difficulty="medium", topic="用户", question="下单最多的那个用户一共下了几单？",
         gold="SELECT max(n) FROM (SELECT c.customer_unique_id, count(*) AS n FROM orders o "
              "JOIN customers c USING (customer_id) GROUP BY 1)"),
    dict(id="u03", difficulty="medium", topic="用户", question="有多少个用户下过 3 单及以上？",
         gold="SELECT count(*) FROM (SELECT c.customer_unique_id FROM orders o JOIN customers c USING (customer_id) "
              "GROUP BY 1 HAVING count(*) >= 3)"),
    dict(id="u04", difficulty="medium", topic="用户", question="平均每个用户下了几单？",
         gold="SELECT count(*) / count(DISTINCT c.customer_unique_id) FROM orders o JOIN customers c USING (customer_id)"),
    dict(id="u05", difficulty="hard", topic="用户", question="累计支付金额最高的用户一共付了多少钱？",
         gold="SELECT max(total) FROM (SELECT c.customer_unique_id, sum(p.payment_value) AS total FROM payments p "
              "JOIN orders o USING (order_id) JOIN customers c USING (customer_id) GROUP BY 1)"),
    dict(id="u06", difficulty="hard", topic="用户", question="2017 年下过单的用户里，有多少人在 2018 年也下过单？",
         gold="SELECT count(*) FROM (SELECT c.customer_unique_id FROM orders o JOIN customers c USING (customer_id) "
              "GROUP BY 1 HAVING bool_or(year(o.purchase_time) = 2017) AND bool_or(year(o.purchase_time) = 2018))"),
    dict(id="u07", difficulty="medium", topic="用户", question="各州用户的平均评价分是多少？列出平均分最低的 3 个州。",
         gold="SELECT c.state, avg(r.score) FROM reviews r JOIN orders o USING (order_id) JOIN customers c USING (customer_id) "
              "GROUP BY c.state ORDER BY 2 ASC LIMIT 3",
         alt=["SELECT s.state_name, avg(r.score) FROM reviews r JOIN orders o USING (order_id) "
              "JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state GROUP BY 1 ORDER BY 2 ASC LIMIT 3"]),
    dict(id="u08", difficulty="hard", topic="用户", question="复购用户（2 单及以上）的平均累计支付金额，是只下过 1 单用户的几倍？",
         gold="WITH u AS (SELECT c.customer_unique_id, count(DISTINCT o.order_id) AS n, sum(p.payment_value) AS total "
              "FROM orders o JOIN customers c USING (customer_id) JOIN payments p USING (order_id) GROUP BY 1) "
              "SELECT avg(total) FILTER (WHERE n >= 2) / avg(total) FILTER (WHERE n = 1) FROM u"),

    # ---------------- 物流时效 ----------------
    dict(id="d01", difficulty="medium", topic="物流", question="已送达的订单，从下单到签收平均要几天？",
         gold="SELECT avg(date_diff('day', purchase_time, delivered_time)) FROM orders WHERE delivered_time IS NOT NULL"),
    dict(id="d02", difficulty="medium", topic="物流", question="平均配送天数最长的是哪个州？",
         gold="SELECT c.state FROM orders o JOIN customers c USING (customer_id) WHERE o.delivered_time IS NOT NULL "
              "GROUP BY c.state ORDER BY avg(date_diff('day', o.purchase_time, o.delivered_time)) DESC LIMIT 1",
         alt=["SELECT s.state_name FROM orders o JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state "
              "WHERE o.delivered_time IS NOT NULL GROUP BY 1 "
              "ORDER BY avg(date_diff('day', o.purchase_time, o.delivered_time)) DESC LIMIT 1"]),
    dict(id="d03", difficulty="medium", topic="物流", question="已送达的订单里，晚于承诺日期送达的占百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE CAST(delivered_time AS DATE) > estimated_delivery_date) / count(*) "
              "FROM orders WHERE delivered_time IS NOT NULL",
         alt=["SELECT 100.0 * count(*) FILTER (WHERE delivered_time > estimated_delivery_date) / count(*) "
              "FROM orders WHERE delivered_time IS NOT NULL"]),
    dict(id="d04", difficulty="hard", topic="物流", question="延迟送达的订单和按时送达的订单，平均评分分别是多少？",
         # 只比较两个平均分：模型用“延迟/按时”文字标签、或者一行两列输出都算对
         gold="SELECT avg(r.score) FROM orders o JOIN reviews r USING (order_id) WHERE o.delivered_time IS NOT NULL "
              "GROUP BY CAST(o.delivered_time AS DATE) > o.estimated_delivery_date",
         alt=["SELECT avg(r.score) FROM orders o JOIN reviews r USING (order_id) WHERE o.delivered_time IS NOT NULL "
              "GROUP BY o.delivered_time > o.estimated_delivery_date"]),
    dict(id="d05", difficulty="medium", topic="物流", question="从下单到交给物流，平均要几天？",
         gold="SELECT avg(date_diff('day', purchase_time, shipped_time)) FROM orders WHERE shipped_time IS NOT NULL"),
    dict(id="d06", difficulty="medium", topic="物流", question="配送时间超过 30 天的订单有多少个？",
         gold="SELECT count(*) FROM orders WHERE date_diff('day', purchase_time, delivered_time) > 30",
         alt=["SELECT count(*) FROM orders WHERE delivered_time - purchase_time > INTERVAL 30 DAY",
              "SELECT count(*) FROM orders WHERE date_diff('day', CAST(purchase_time AS DATE), CAST(delivered_time AS DATE)) > 30"]),
    dict(id="d07", difficulty="medium", topic="物流", question="已送达的订单，平均比承诺日期提前几天送到？",
         gold="SELECT avg(date_diff('day', delivered_time, estimated_delivery_date)) FROM orders WHERE delivered_time IS NOT NULL",
         alt=["SELECT avg(date_diff('day', CAST(delivered_time AS DATE), estimated_delivery_date)) FROM orders "
              "WHERE delivered_time IS NOT NULL"]),
    dict(id="d08", difficulty="hard", topic="物流", question="2018 年 1 到 8 月，每个月下单的订单的延迟送达率是多少？",
         gold="SELECT strftime(purchase_time, '%Y-%m') AS m, 100.0 * count(*) FILTER "
              "(WHERE CAST(delivered_time AS DATE) > estimated_delivery_date) / count(*) FROM orders "
              "WHERE delivered_time IS NOT NULL AND purchase_time >= '2018-01-01' AND purchase_time < '2018-09-01' GROUP BY m",
         alt=["SELECT strftime(purchase_time, '%Y-%m') AS m, 100.0 * count(*) FILTER "
              "(WHERE delivered_time > estimated_delivery_date) / count(*) FROM orders "
              "WHERE delivered_time IS NOT NULL AND purchase_time >= '2018-01-01' AND purchase_time < '2018-09-01' GROUP BY m"]),
    dict(id="d09", difficulty="hard", topic="物流", question="延迟送达率最高的 5 个州是哪些？只看送达订单数至少 500 个的州。",
         gold="SELECT c.state, 100.0 * count(*) FILTER (WHERE CAST(o.delivered_time AS DATE) > o.estimated_delivery_date) "
              "/ count(*) FROM orders o JOIN customers c USING (customer_id) WHERE o.delivered_time IS NOT NULL "
              "GROUP BY c.state HAVING count(*) >= 500 ORDER BY 2 DESC LIMIT 5",
         alt=["SELECT c.state, 100.0 * count(*) FILTER (WHERE o.delivered_time > o.estimated_delivery_date) "
              "/ count(*) FROM orders o JOIN customers c USING (customer_id) WHERE o.delivered_time IS NOT NULL "
              "GROUP BY c.state HAVING count(*) >= 500 ORDER BY 2 DESC LIMIT 5"]),
    dict(id="d10", difficulty="medium", topic="物流", question="圣保罗州的已送达订单平均配送几天？",
         gold="SELECT avg(date_diff('day', o.purchase_time, o.delivered_time)) FROM orders o JOIN customers c USING (customer_id) "
              "WHERE c.state = 'SP' AND o.delivered_time IS NOT NULL"),
    dict(id="d11", difficulty="medium", topic="物流", question="各大区已送达订单的平均配送天数是多少？",
         gold="SELECT s.region, avg(date_diff('day', o.purchase_time, o.delivered_time)) FROM orders o "
              "JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state "
              "WHERE o.delivered_time IS NOT NULL GROUP BY s.region"),

    # ---------------- 评价 ----------------
    dict(id="r01", difficulty="easy", topic="评价", question="1 分差评占全部评价的百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE score = 1) / count(*) FROM reviews"),
    dict(id="r02", difficulty="hard", topic="评价", question="差评（1 到 2 分）订单的平均配送天数，比好评（4 到 5 分）订单多几天？",
         gold="SELECT avg(d) FILTER (WHERE score <= 2) - avg(d) FILTER (WHERE score >= 4) FROM "
              "(SELECT r.score, date_diff('day', o.purchase_time, o.delivered_time) AS d FROM reviews r "
              "JOIN orders o USING (order_id) WHERE o.delivered_time IS NOT NULL)"),
    dict(id="r03", difficulty="medium", topic="评价", question="不同评分的订单，平均配送天数分别是多少？",
         gold="SELECT r.score, avg(date_diff('day', o.purchase_time, o.delivered_time)) FROM reviews r "
              "JOIN orders o USING (order_id) WHERE o.delivered_time IS NOT NULL GROUP BY r.score"),
    dict(id="r04", difficulty="medium", topic="评价", question="有多少个订单收到了不止一条评价？",
         gold="SELECT count(*) FROM (SELECT order_id FROM reviews GROUP BY order_id HAVING count(*) > 1)"),
    dict(id="r05", difficulty="medium", topic="评价", question="2018 年 8 月下单的订单，平均评分是多少？",
         gold="SELECT avg(r.score) FROM reviews r JOIN orders o USING (order_id) "
              "WHERE strftime(o.purchase_time, '%Y-%m') = '2018-08'"),
    dict(id="r06", difficulty="medium", topic="评价", question="平均评分最高的大区是哪个？",
         gold="SELECT s.region FROM reviews r JOIN orders o USING (order_id) JOIN customers c USING (customer_id) "
              "JOIN states s ON s.state = c.state GROUP BY s.region ORDER BY avg(r.score) DESC LIMIT 1"),
    dict(id="r07", difficulty="medium", topic="评价", question="被取消的订单，平均评分是多少？",
         gold="SELECT avg(r.score) FROM reviews r JOIN orders o USING (order_id) WHERE o.status = 'canceled'"),
    dict(id="r08", difficulty="hard", topic="评价", question="订单金额（商品价格合计）超过 500 的订单，平均评分是多少？",
         gold="SELECT avg(r.score) FROM reviews r JOIN (SELECT order_id FROM order_items GROUP BY order_id "
              "HAVING sum(price) > 500) t USING (order_id)"),
    dict(id="r09", difficulty="medium", topic="评价", question="评价提交时间平均比评价邀请时间晚几天？",
         gold="SELECT avg(date_diff('day', created_time, answered_time)) FROM reviews",
         alt=["SELECT avg(epoch(answered_time) - epoch(created_time)) / 86400 FROM reviews"]),
    dict(id="r10", difficulty="medium", topic="评价", question="用信用卡支付的订单，平均评分是多少？",
         gold="SELECT avg(r.score) FROM reviews r WHERE r.order_id IN "
              "(SELECT order_id FROM payments WHERE payment_type = 'credit_card')"),

    # ---------------- 支付 ----------------
    dict(id="p01", difficulty="easy", topic="支付", question="分期付款（期数大于 1）的支付记录占百分之多少？",
         gold="SELECT 100.0 * count(*) FILTER (WHERE installments > 1) / count(*) FROM payments"),
    dict(id="p02", difficulty="medium", topic="支付", question="平均每个订单支付了多少钱？",
         gold="SELECT avg(t) FROM (SELECT order_id, sum(payment_value) AS t FROM payments GROUP BY order_id)"),
    dict(id="p03", difficulty="medium", topic="支付", question="各种支付方式的支付金额，各占总支付金额的百分之多少？",
         gold="SELECT payment_type, 100.0 * sum(payment_value) / (SELECT sum(payment_value) FROM payments) "
              "FROM payments GROUP BY payment_type"),
    dict(id="p04", difficulty="easy", topic="支付", question="分 10 期及以上的信用卡支付有多少笔？",
         gold="SELECT count(*) FROM payments WHERE payment_type = 'credit_card' AND installments >= 10"),
    dict(id="p05", difficulty="medium", topic="支付", question="用了不止一种支付方式的订单有多少个？",
         gold="SELECT count(*) FROM (SELECT order_id FROM payments GROUP BY order_id HAVING count(DISTINCT payment_type) > 1)"),

    # ---------------- 综合分析（窗口函数、多步计算）----------------
    dict(id="h01", difficulty="hard", topic="销售", question="每个大区销售额最高的商品类目分别是什么？",
         gold=f"WITH t AS (SELECT s.region, p.category, sum(i.price) AS gmv FROM order_items i "
              f"JOIN orders o USING (order_id) JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state "
              f"JOIN products p USING (product_id) WHERE o.{VALID} AND p.category IS NOT NULL GROUP BY 1, 2) "
              f"SELECT region, category FROM t QUALIFY row_number() OVER (PARTITION BY region ORDER BY gmv DESC) = 1"),
    dict(id="h02", difficulty="hard", topic="销售", question="2018 年 2 到 8 月里，销售额环比增长最多的是哪个月？",
         gold=f"WITH m AS (SELECT strftime(o.purchase_time, '%Y-%m') AS m, sum(i.price) AS gmv FROM order_items i "
              f"JOIN orders o USING (order_id) WHERE o.{VALID} AND o.purchase_time >= '2018-01-01' "
              f"AND o.purchase_time < '2018-09-01' GROUP BY 1) "
              f"SELECT m FROM (SELECT m, gmv / lag(gmv) OVER (ORDER BY m) AS r FROM m) WHERE r IS NOT NULL "
              f"ORDER BY r DESC LIMIT 1"),
    dict(id="h03", difficulty="hard", topic="销售", question="销售额前 5 的类目，各自占总销售额的百分之多少？",
         gold=f"WITH t AS (SELECT p.category, sum(i.price) AS gmv FROM order_items i JOIN orders o USING (order_id) "
              f"JOIN products p USING (product_id) WHERE o.{VALID} GROUP BY 1) "
              f"SELECT category, 100.0 * gmv / (SELECT sum(gmv) FROM t) FROM t WHERE category IS NOT NULL "
              f"ORDER BY gmv DESC LIMIT 5"),
    dict(id="h04", difficulty="hard", topic="销售", question="2017 年每个月的累计销售额是多少（从 1 月开始累加）？",
         gold=f"WITH m AS (SELECT strftime(o.purchase_time, '%Y-%m') AS m, sum(i.price) AS gmv FROM order_items i "
              f"JOIN orders o USING (order_id) WHERE o.{VALID} AND year(o.purchase_time) = 2017 GROUP BY 1) "
              f"SELECT m, sum(gmv) OVER (ORDER BY m) FROM m"),
    dict(id="h05", difficulty="hard", topic="卖家", question="“家具装饰”类目销售额前 3 的卖家是哪几个？给出卖家 ID 和销售额。",
         gold=f"SELECT i.seller_id, sum(i.price) FROM order_items i JOIN orders o USING (order_id) "
              f"JOIN products p USING (product_id) WHERE p.category = '家具装饰' AND o.{VALID} "
              f"GROUP BY 1 ORDER BY 2 DESC LIMIT 3"),
    dict(id="h06", difficulty="hard", topic="趋势", question="2018 年 1 到 8 月里，订单量环比下降最多的是哪个月？",
         gold="WITH m AS (SELECT strftime(purchase_time, '%Y-%m') AS m, count(*) AS n FROM orders "
              "WHERE purchase_time >= '2018-01-01' AND purchase_time < '2018-09-01' GROUP BY 1) "
              "SELECT m FROM (SELECT m, n - lag(n) OVER (ORDER BY m) AS d FROM m) WHERE d IS NOT NULL ORDER BY d ASC LIMIT 1"),
    dict(id="h07", difficulty="hard", topic="卖家", question="销售额排名前 10% 的卖家，贡献了总销售额的百分之多少？",
         gold=f"WITH s AS (SELECT i.seller_id, sum(i.price) AS gmv FROM order_items i JOIN orders o USING (order_id) "
              f"WHERE o.{VALID} GROUP BY 1), r AS (SELECT gmv, ntile(10) OVER (ORDER BY gmv DESC) AS bucket FROM s) "
              f"SELECT 100.0 * sum(gmv) FILTER (WHERE bucket = 1) / sum(gmv) FROM r",
         alt=[f"WITH s AS (SELECT i.seller_id, sum(i.price) AS gmv FROM order_items i JOIN orders o USING (order_id) "
              f"WHERE o.{VALID} GROUP BY 1), r AS (SELECT gmv, row_number() OVER (ORDER BY gmv DESC) AS rk, "
              f"count(*) OVER () AS n FROM s) SELECT 100.0 * sum(gmv) FILTER (WHERE rk <= n * 0.1) / sum(gmv) FROM r"]),
    dict(id="h08", difficulty="hard", topic="销售", question="订单金额（商品价格合计）的中位数是多少？",
         gold="SELECT median(t) FROM (SELECT order_id, sum(price) AS t FROM order_items GROUP BY order_id)"),
    dict(id="h09", difficulty="hard", topic="用户", question="首单之后 90 天内又下了第二单的用户，占全部用户的百分之多少？",
         gold="WITH o AS (SELECT c.customer_unique_id AS u, o.purchase_time AS t, "
              "row_number() OVER (PARTITION BY c.customer_unique_id ORDER BY o.purchase_time) AS k "
              "FROM orders o JOIN customers c USING (customer_id)), f AS (SELECT u, max(t) FILTER (WHERE k = 1) AS t1, "
              "max(t) FILTER (WHERE k = 2) AS t2 FROM o GROUP BY u) "
              "SELECT 100.0 * count(*) FILTER (WHERE t2 <= t1 + INTERVAL 90 DAY) / count(*) FROM f"),
    dict(id="h10", difficulty="hard", topic="商品", question="每个大区里卖出件数最多的商品类目分别是什么？",
         gold="WITH t AS (SELECT s.region, p.category, count(*) AS n FROM order_items i JOIN orders o USING (order_id) "
              "JOIN customers c USING (customer_id) JOIN states s ON s.state = c.state JOIN products p USING (product_id) "
              "WHERE p.category IS NOT NULL GROUP BY 1, 2) "
              "SELECT region, category FROM t QUALIFY row_number() OVER (PARTITION BY region ORDER BY n DESC) = 1"),
    dict(id="h11", difficulty="hard", topic="物流", question="运费占商品价格比例最高的 5 个类目是哪些？比例按运费合计除以价格合计算。",
         gold="SELECT p.category, 100.0 * sum(i.freight_value) / sum(i.price) FROM order_items i "
              "JOIN products p USING (product_id) WHERE p.category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
         alt=["SELECT p.category, sum(i.freight_value) / sum(i.price) FROM order_items i "
              "JOIN products p USING (product_id) WHERE p.category IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 5"]),
    dict(id="h12", difficulty="hard", topic="销售", question="2018 年 1 到 8 月，销售额比 2017 年同期增长最多的 3 个类目是哪些？按增长金额算。",
         gold=f"WITH t AS (SELECT p.category, sum(i.price) FILTER (WHERE year(o.purchase_time) = 2018) AS g18, "
              f"sum(i.price) FILTER (WHERE year(o.purchase_time) = 2017) AS g17 FROM order_items i "
              f"JOIN orders o USING (order_id) JOIN products p USING (product_id) "
              f"WHERE o.{VALID} AND month(o.purchase_time) <= 8 AND p.category IS NOT NULL GROUP BY 1) "
              f"SELECT category FROM t ORDER BY coalesce(g18, 0) - coalesce(g17, 0) DESC LIMIT 3"),

    # ---------------- 数据里没有的信息：应该说明，而不是编造 ----------------
    # 这类题没有标准 SQL，评测时单独统计“是否拒答”。
    dict(id="n01", difficulty="medium", topic="拒答", question="每个用户的年龄分布是怎样的？", gold=None),
    dict(id="n02", difficulty="medium", topic="拒答", question="2019 年的销售额是多少？", gold=None,
         note="数据只到 2018-10，2019 年没有数据；回答 0 或空结果也算正确拒答"),
]
