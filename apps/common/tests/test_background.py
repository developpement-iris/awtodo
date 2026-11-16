import threading
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.common import background


class FakeTask:
    name = "fake"

    def __init__(self, fail=False):
        self.calls = []
        self.thread_names = []
        self.done = threading.Event()
        self.fail = fail
        self.delay = mock.Mock()

    def apply(self, args):
        self.calls.append(args)
        self.thread_names.append(threading.current_thread().name)
        self.done.set()
        if self.fail:
            raise RuntimeError("boom")


class RunInBackgroundTests(SimpleTestCase):
    @override_settings(BACKGROUND_THREAD_TASKS=False)
    def test_defaults_to_celery_delay(self):
        task = FakeTask()
        background.run_in_background(task, "a", "b")
        task.delay.assert_called_once_with("a", "b")
        self.assertEqual(task.calls, [])

    @override_settings(BACKGROUND_THREAD_TASKS=True, CELERY_TASK_ALWAYS_EAGER=True)
    def test_runs_in_a_background_thread(self):
        task = FakeTask()
        with mock.patch.object(background.connections, "close_all") as close_all:
            background.run_in_background(task, "a")
            self.assertTrue(task.done.wait(5))
            background._get_executor().submit(lambda: None).result(5)
        self.assertEqual(task.calls, [("a",)])
        self.assertTrue(task.thread_names[0].startswith("awtodo-bg"))
        task.delay.assert_not_called()
        close_all.assert_called()

    @override_settings(BACKGROUND_THREAD_TASKS=True, CELERY_TASK_ALWAYS_EAGER=True)
    def test_failure_is_contained(self):
        task = FakeTask(fail=True)
        with mock.patch.object(background.connections, "close_all"):
            background.run_in_background(task)
            self.assertTrue(task.done.wait(5))
            background._get_executor().submit(lambda: None).result(5)
        follow_up = FakeTask()
        with mock.patch.object(background.connections, "close_all"):
            background.run_in_background(follow_up)
            self.assertTrue(follow_up.done.wait(5))

    @override_settings(BACKGROUND_THREAD_TASKS=True, CELERY_TASK_ALWAYS_EAGER=False)
    def test_real_broker_keeps_celery(self):
        task = FakeTask()
        background.run_in_background(task, "x")
        task.delay.assert_called_once_with("x")
