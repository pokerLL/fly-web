from fly.middleware.core import MiddlewareManager, BaseMiddleware

""" 
三种Middleware
1. 继承自BaseMiddleware的中间件类
2. yield函数
3. before_request/after_request 等装饰器注册的函数

执行顺序:
1. 装饰器注册的函数
2. yield函数
3. cls中间件

中间价注册:
1. 均需要手动注册, 内置中间价会在初始化时自动注册

何时执行 何时停止:
1. 在请求开始处理前和请求处理后执行
2. before_request 中任一处理器产生返回值则停止执行, 并且不再执行请求处理函数
3. after_request 中任一处理器产生返回值则停止执行

使用建议:
1. 不建议混用, 会导致执行顺序不可控, 尤其是由装饰器注册的中间件
2. 建议统一使用yield函数做自定义中间件
3. 内置中间价统一使用BaseMiddleware子类

"""
