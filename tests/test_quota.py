from datetime import date

from askdata.quota import DailyQuota


def test_quota_runs_out_and_resets_next_day():
    today = [date(2026, 11, 11)]
    quota = DailyQuota(2, today=lambda: today[0])
    assert [quota.take() for _ in range(3)] == [True, True, False]
    assert quota.used == 2
    today[0] = date(2026, 11, 12)
    assert quota.used == 0 and quota.take()


def test_zero_means_unlimited():
    quota = DailyQuota(0)
    assert all(quota.take() for _ in range(100))
