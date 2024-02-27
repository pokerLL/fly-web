### Main Features

- All Module interface-oriented - Service Based on Protocol
- Service provider registered to the core container
- get provider instant func from core with provider name - may need different instance with different config
- provider must obey the design（interface）of that module
- Minimize third-party dependency

### Features - V1

- [X] Application

  - [X] Async
  - [X] Sync
  - [X] SSE (Server-Sent Events)
  - [X] WebSocket
  - [X] STATIC
- [X] Routing

  - [X] Normal routing -> `@app.route('/users')`
  - [X] Path param routing -> `@app.route('/users/{int:id}')`
  - [X] Regex routing -> `@app.route('/users/(?P<id>\d+)')`
  - [X] Route Group
    ```python
    from fly import Fly
    from fly.route import Router

    app = Fly(__name__)
    user_router = Router().group("/user")

    @user_router.get("/<int:id>")
    def user(id: int):
        return {"id": id}

    @user_router.post("/<int:id>/info")
    def user_info(id: int):
        return {"id": id, "info": "info"}


    user_operation_router = user_router.group("/operation")

    @user_operation_router.post("/<int:id>")  # /user/operation/1
    def user_operation(id: int, operation):
        return {"id": id, "operation": operation}


    app.register_router(user_route)
    ```
- [X] Middleware

  - [X] Class-based middleware
  - [X] Function middleware -> process_request, process_response
  - [X] Yield function middleware
  - [X] Middleware Order
  - [ ] ~~register~~
    - [ ] to global
    - [ ] to route group
    - [ ] to certain route
  - [X] Offer common middleware
    - [X] CORS
    - [ ] JWT
- [X] Signal

  - [X] built-in signal: before_request, after_request, before_response, after_response
  - [X] exception signal
    ```python
    @app.on_exception(RouterNotFoundError)
    def not_found(exp: Exception):
        return 'not found'
    ```
  - [X] status code signal
    ```python
    @app.on_status(404)
    def not_found(response: Response):
        return 'not found'
    ```
  - [X] custom signal
    ```python
    @app.connect('custom_signal')
    def custom_signal():
        return 'custom signal'

    app.send_signal('custom_signal', arg1, arg2, arg3)
    ```
- [X] Schema

  - [X] Path param (e.g., `/user/{int:id}` or `/users/(?P<id>\d+)`)
  - [X] Query param (e.g., `/users?name=xxx&age=xxx`)
  - [X] Cookie param
  - [ ] ~~Session param~~
  - [X] Header param
  - [X] Body param
  - [X] Input validation
  - [X] Output validation
  - [X] provide a decorator to validate custom function
- [ ] ~~Task~~ Move to V2

  - [ ] task type
    - [ ] background task
    - [ ] delay task
    - [ ] cron task
  - [ ] support callback
  - [ ] Command support
    ```bash
    fly task list
    fly task state
    fly task start/stop/restart [--deamon]
    ```
- [X] Test

  - [X] TestClient
    - [X] HTTP
    - [X] WS
    - [X] SSE
  - [ ] ~~Command support~~ Move to V2
    ```bash
     fly test -d ./tests
    ```
- [X] Config

  - [X] dict input

  - ~~yaml filepath input~~ dont want to import more third modules

  - [ ] ~~support read config from remote real-time~~ Move to V2
- [ ] OpenAPI Support

  - [X] openai.json
  - [X] Auto documentation
    - [X] Swagger UI
  - [ ] ~~Auto SDK - use `<codegen>` to generate client code~~ Move to V2
  - [ ] ~~API Version Management~~ - should be part of route
  - [X] Command support
    ```bash
     fly swagger gen [-o ./swagger.json]
     fly swagger serve [-p 8080] 
         # curl http:127.0.0.1:8080/swagger.json
         # curl http:127.0.0.1:8080/swagger-ui
    ```
  - [X] More sufficient detail support
- [ ] Debug

  - [X] Dev mode - hot reload
  - [X] Debug shell
  - [ ] State Export command support - app & memory & core dump
    ```bash
     fly state export [-o ./state.json]
     fly state dump [-o ./core.dump]
    ```
- [X] Command

  - [X] fly xxx support
    ```bash
    python app.py xxx 
    # should equals to
    fly xxx
    ```
  - [X] more sufficient detail support
    - [X] Description
  - [ ] ~~fly admin~~ Move to V2
    offer default project structure to ensure engineering standardization
    ```bash
    fly admin new <project-name> [-c cookiecutter_dir] [--with-demo]
    fly admin check [-d <project-dir>]
    ```
- [X] View

  - [X] Function-based views (FBV)
  - [X] Class-based views (CBV)
- [X] Context (like Flask)

  - [X] Request context
    - [ ] Stream Body
  - [X] Application context
  - [ ] ~~Gin-like context passthrough~~ Move to V2
- [X] Profiling

  - [X] Request profiling (for debug mode)
  - [X] Request profiling (for 'profile' in query_param) -> /route/xxx&profile&xxx
  - [X] Slow request log
- [ ] HTTP Protocal Feature Support

  - [ ] Keep-Alive
- [ ] Security

  - [X] CORS
  - [ ] XSS
  - [ ] Data Encryption for Transfer
  - [ ] Request process timeout
  - [ ] Others
- [ ] ~~Convenient Protocol Change~~ Move to V2

  - [ ] ASGI App
  - [ ] ~~WSGI App~~
  - [ ] Gin-like App
  - [ ] gRPC App
  - [ ] Message Queue App
  - [ ] Others

  ```python
  from fly import Fly
  from fly.protocal import asgi_app_wrapper, wsgi_app_wrapper, grpc_app_wrapper

  app = Fly(__name__)

  @app.get('/users') # or something else? 
  def users():
      return 'users'

  app = asgi_app_wrapper(app)
  # app = grpc_app_wrapper(app)
  # app = ginlike_app_wrapper(app)

  if __name__ == '__main__':
      app.run()
  ```
- [ ] Util

  - [X] Logger
  - [ ] Code Encryption
- [ ] ~~better idea support~~ Move to V2
- [ ] ~~Metrics(for monitoring)~~

  > Maybe we should monitor nginx or other web server instead of application
  >

### Features - V2

- [ ] Interface-oriented
  - [ ] Base
  - [ ] App
  - [ ] Router
  - [ ] Middleware
  - [ ] Signal
  - [ ] Task
  - [ ] Config
  - [ ] Debug
  - [ ] Command

- Middleware

- [ ] Middleware register
- [ ] to global
- [ ] to route group
- [ ] to certain route
- [ ] Task
  - [ ] task type
    - [ ] background task
    - [ ] delay task
    - [ ] cron task
  - [ ] support callback
  - [ ] Command support
    ```bash
    fly task list
    fly task state
    fly task start/stop/restart [--deamon]
    ```
- [ ] Different Protocol Implement
  - [ ] WSGI App
  - [ ] Gin-like App
  - [ ] gRPC App
  - [ ] Message Queue App
- [ ] better idea support

## BugFix

- [ ] send msg when socket is closed should raise error -> await asgisend('') -> never raise even if socket has closed
  > there should be a function to check whether peer is online - > may be current_request.is_online (property)
  > just something like context.is_active() in grpc-python
  > also should have a function to activly close the socket -> may be current_request.close()
  >
- [ ] support multiple app instance
  > now, there would be something wrong if we run fly command under directory with multiple app instance
  > such like examples/feature_usage
  >
- [ ] graceful shutdown to avoid issues like resource leaks.
