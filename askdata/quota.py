"""公开 Demo 的用量限制：API key 是自己的，不能让路人把额度用光。"""
from __future__ import annotations

import threading
from datetime import date
from typing import Callable


class DailyQuota:
    """全站每天最多回答多少个问题，所有访客共用一个计数，第二天自动清零。

    计数放在进程内存里，服务重启会清零；对一个演示站来说够用了。
    """

    def __init__(self, limit: int, today: Callable[[], date] = date.today):
        self.limit = limit  # 0 或负数表示不限
        self._today = today
        self._day: date | None = None
        self._used = 0
        self._lock = threading.Lock()  # Streamlit 每个访客一个线程，计数要加锁

    def take(self) -> bool:
        """用掉一次额度；今天已经用完时返回 False。"""
        if self.limit <= 0:
            return True
        with self._lock:
            day = self._today()
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    @property
    def used(self) -> int:
        with self._lock:
            return self._used if self._day == self._today() else 0
