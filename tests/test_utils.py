from fly.utils import run_func


def test_run_func():
    async def coro_func():
        return "coro_func"

    def sync_func():
        return "sync_func"

    async def async_gen_func():
        yield "async_gen_func"

    def sync_gen_func():
        yield "sync_gen_func"

    def run_in_loop(func, *args, **kwagrs):
        import asyncio

        loop = asyncio.new_event_loop()
        return loop.run_until_complete(run_func(func, *args, **kwagrs))

    assert run_in_loop(run_func, coro_func) == "coro_func"
    assert run_in_loop(run_func, sync_func) == "sync_func"
    assert run_in_loop(run_func, async_gen_func) == ["async_gen_func"]
    assert run_in_loop(run_func, sync_gen_func) == ["sync_gen_func"]
